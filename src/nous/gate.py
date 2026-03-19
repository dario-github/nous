"""Nous — Gate API (M2.5 + M7.3 Three-Layer Architecture)

三层决策 pipeline：
  Layer 1: Datalog 规则匹配（<5ms）
  Layer 2: Triviality Filter — 安全操作快速放行
  Layer 3: Semantic Gate — LLM 语义判断（200-500ms）

完整流程：
  tool_call → extract_facts → match_constraints → route_verdict
           → [triviality_filter | semantic_gate]
           → proof_trace → log_decision → GateResult

FAIL_CLOSED 原则：Datalog/基础设施异常 → confirm（永不 allow）
FAIL_OPEN 原则：Semantic Gate 异常 → 不改变 Datalog verdict
"""
import json
import logging as _gate_logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from nous.constraint_parser import ConstraintLoadError, load_constraints
from nous.decision_log import CostBreakdown
from nous.fact_extractor import extract_facts
from nous.intent_extractor import extract_intents
from nous.observability import SamplingPolicy, log_decision
from nous.proof_trace import ProofStep, ProofTrace
from nous.resource_budget import load_resource_budget, check_budget
from nous.schema import Constraint
from nous.semantic_gate import SemanticGateConfig, SemanticVerdict, semantic_gate
from nous.triviality_filter import TrivialityConfig, is_trivial
from nous.verdict import (
    MatchResult,
    Verdict,
    match_all_constraints,
    route_verdict,
)


# ── KG Context Builder (P1 from GPT-5.4 critique) ─────────────────────────


def _build_kg_context(facts: dict, db, extra_seeds: Optional[list] = None) -> dict | None:
    """从 facts 提取实体标识，用 Markov Blanket 选择性查 KG 获取上下文。

    E2 改造：用 compute_blanket() 替代简单查找，只注入因果相关实体。
    Loop 49 改造：接受 extra_seeds 参数（如 hypothesized intent 节点），
    避免将 intent 节点写入 facts dict（= 会被 semantic gate 序列化进 LLM prompt）。
    预算：<5ms（24 entities 量级 <1ms）。
    失败时返回 None（不影响 gate pipeline）。
    """
    import logging as _logging
    logger = _logging.getLogger("nous.gate.kg")

    try:
        from nous.markov_blanket import _extract_seed_entities, compute_blanket

        seeds = _extract_seed_entities(facts)

        # Loop 49: 合并 hypothesized intent seeds（单独传入，不经过 facts dict）
        if extra_seeds:
            for s in extra_seeds:
                if s and s not in seeds:
                    seeds.append(s)

        if not seeds:
            return None

        blanket = compute_blanket(db, seeds, max_depth=2, max_entities=15)

        if not blanket or not blanket.get("entities"):
            return None

        # Convert blanket format to legacy kg_context format for compatibility
        # with _format_kg_context_for_prompt and _emit_gate_event
        context: dict = {
            "entities": [],
            "relations": [],
            "policies": [],
            # E2 extension fields
            "blanket": blanket,
        }

        for ent in blanket["entities"]:
            eid = ent.get("id", "")
            # Resolve full entity data from DB for entities with props
            full_ent = db.find_entity(eid)
            if full_ent:
                context["entities"].append(full_ent)
                # Category entities go to policies
                if full_ent.get("etype") == "category":
                    context["policies"].append(full_ent)

        for rel in blanket["relations"]:
            context["relations"].append(rel)

        return context if any(v for k, v in context.items() if k != "blanket") else None

    except Exception as e:
        logger.warning("KG context build failed (non-fatal): %s", e)
        return None


# ── Gate 事件推送 (Loop 42) ────────────────────────────────────────────────

_GATE_EVENTS_FILE: Optional[Path] = None
_gate_event_logger = _gate_logging.getLogger("nous.gate.events")


def _get_gate_events_path() -> Path:
    """返回 gate_events.jsonl 路径，懒初始化。"""
    global _GATE_EVENTS_FILE
    if _GATE_EVENTS_FILE is None:
        logs_dir = Path(__file__).parent.parent.parent / "logs"
        logs_dir.mkdir(exist_ok=True)
        _GATE_EVENTS_FILE = logs_dir / "gate_events.jsonl"
    return _GATE_EVENTS_FILE


def _emit_gate_event(result: "GateResult", tool_call: dict) -> None:
    """将 gate 结果写入 gate_events.jsonl，供 dashboard SSE 消费。

    格式：{ts, tool_call, verdict, proof_trace_summary, kg_entities_involved, layer_path, latency_ms}
    失败不影响 gate pipeline。
    """
    try:
        # proof_trace 摘要：只保留 matched rules
        matched_rules = []
        if result.proof_trace and result.proof_trace.steps:
            matched_rules = [
                s.rule_id for s in result.proof_trace.steps if s.verdict == "match"
            ]

        # KG 涉及的实体 ID
        kg_ids = []
        if result.kg_context:
            for ent_list in (result.kg_context.get("entities", []),
                             result.kg_context.get("policies", [])):
                for e in ent_list:
                    eid = e.get("id") if isinstance(e, dict) else None
                    if eid:
                        kg_ids.append(eid)

        event = {
            "ts": time.time(),
            "tool_call": {
                "tool_name": tool_call.get("tool_name") or tool_call.get("name", "?"),
                "action_type": tool_call.get("action_type", ""),
            },
            "verdict": result.verdict.action,
            "reason": result.verdict.reason[:200] if result.verdict.reason else "",
            "matched_rules": matched_rules,
            "kg_entities_involved": kg_ids,
            "layer_path": result.layer_path,
            "latency_ms": round(result.latency_ms, 2),
        }

        path = _get_gate_events_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    except Exception as exc:
        _gate_event_logger.debug("gate event emit failed (non-fatal): %s", exc)


# ── 默认采样策略 ──────────────────────────────────────────────────────────

_DEFAULT_POLICY = SamplingPolicy(
    block_rate=1.0,
    allow_rate=0.1,
    confirm_rate=1.0,
    warn_rate=0.5,
)


# ── 结果结构 ───────────────────────────────────────────────────────────────


@dataclass
class GateResult:
    """
    gate() 返回值。

    verdict:          最终裁决（Verdict dataclass）
    proof_trace:      推导轨迹（ProofTrace）
    decision_log_id:  写入 decision_log 的 session_key（或 None 如果被采样跳过）
    latency_ms:       完整 pipeline 耗时（毫秒）
    facts:            提取到的事实（供调试）
    cost_breakdown:   各阶段资源消耗明细（M2.P2）
    datalog_verdict:  Datalog 原始裁决（M7.3，三层架构追踪）
    semantic_verdict: Semantic Gate 结果（M7.3，dict 或 None）
    layer_path:       决策路径（M7.3: "datalog_only" | "trivial_allow" | "semantic"）
    """
    verdict: Verdict
    proof_trace: ProofTrace
    decision_log_id: Optional[str]
    latency_ms: float
    facts: dict = field(default_factory=dict)
    cost_breakdown: Optional[CostBreakdown] = None  # M2.P2
    datalog_verdict: Optional[str] = None            # M7.3
    semantic_verdict: Optional[dict] = None          # M7.3
    layer_path: str = "datalog_only"                 # M7.3
    kg_context: Optional[dict] = None                # E2: Markov Blanket selective context (injected into semantic gate)

    def to_dict(self) -> dict:
        d = {
            "verdict": self.verdict.to_dict(),
            "proof_trace": self.proof_trace.to_dict(),
            "decision_log_id": self.decision_log_id,
            "latency_ms": round(self.latency_ms, 3),
            "facts": self.facts,
            "datalog_verdict": self.datalog_verdict,
            "semantic_verdict": self.semantic_verdict,
            "layer_path": self.layer_path,
        }
        if self.cost_breakdown is not None:
            d["cost_breakdown"] = self.cost_breakdown.to_dict()
        return d


# ── 内部：构建 ProofTrace ─────────────────────────────────────────────────


def _build_proof_trace(
    match_results: list[MatchResult],
    final_verdict: str,
    total_ms: float,
) -> ProofTrace:
    """从 MatchResult 列表构建 ProofTrace"""
    steps = []
    for mr in match_results:
        step = ProofStep(
            rule_id=mr.constraint.id,
            fact_bindings=mr.fact_bindings,
            verdict="match" if mr.matched else "no-match",
            timestamp=time.time(),
        )
        steps.append(step)

    return ProofTrace(
        steps=steps,
        final_verdict=final_verdict,
        total_ms=total_ms,
    )


# ── 主 API ─────────────────────────────────────────────────────────────────


def gate(
    tool_call: dict,
    db=None,
    constraints_dir: Optional[Path] = None,
    session_key: Optional[str] = None,
    sampling_policy: Optional[SamplingPolicy] = None,
    triviality_config: Optional[TrivialityConfig] = None,
    semantic_config: Optional[SemanticGateConfig] = None,
    kg_context: Optional[dict] = None,
) -> GateResult:
    """
    三层决策 pipeline 入口。

    Args:
        tool_call:          工具调用 dict（tool_name / action / params 等）
        db:                 NousDB 实例（可选，用于写 decision_log）
        constraints_dir:    约束目录（默认 ontology/constraints/）
        session_key:        日志 session 标识（可选，自动生成）
        sampling_policy:    采样策略（默认 _DEFAULT_POLICY）
        triviality_config:  Layer 2 配置（可选，None → 不启用 triviality filter）
        semantic_config:    Layer 3 配置（可选，None → 不启用 semantic gate）
        kg_context:         KG 上下文（可选，传给 semantic gate）

    Returns:
        GateResult（包含 verdict + proof_trace + datalog_verdict + semantic_verdict + layer_path）

    向后兼容：不传 triviality_config/semantic_config → 行为与 M2.5 完全一致。
    FAIL_CLOSED：Datalog/基础设施异常 → confirm
    FAIL_OPEN：Semantic Gate 异常 → 不改变 Datalog verdict
    """
    t_start = time.perf_counter()

    policy = sampling_policy or _DEFAULT_POLICY
    sk = session_key or f"gate:{t_start:.6f}"

    try:
        # Step 0: 加载资源预算配置（M2.P3）
        budget = load_resource_budget()

        # Step 1: 提取事实（M2.P2: 计时）
        t1_start = time.perf_counter_ns()
        facts = extract_facts(tool_call)
        fact_extraction_us = (time.perf_counter_ns() - t1_start) // 1000

        # Step 1.5: Hypothesized Intent Extraction (Loop 49)
        # 从 prompt + tool_name 推断意图节点，作为 Markov Blanket seed
        # 替代 Loop 48 移除的 category seed（label leakage 修复后的空缺）
        # 注意：intent seeds 单独保存，不写入 facts dict，
        #        避免 semantic gate 将其序列化进 LLM prompt（= 新的 label leakage）
        _intent_prompt = (
            facts.get("full_prompt") or facts.get("content") or
            facts.get("message") or facts.get("query") or ""
        )
        _intent_tool = facts.get("tool_name") or ""
        _intent_seeds = extract_intents(_intent_prompt, _intent_tool)

        # Step 2: 加载约束
        constraints = load_constraints(constraints_dir)

        # Step 3: 约束匹配（M2.P2: 计时）
        t3_start = time.perf_counter_ns()
        match_results = match_all_constraints(constraints, facts)
        constraint_match_us = (time.perf_counter_ns() - t3_start) // 1000

        # Step 4: Verdict 路由
        verdict = route_verdict(match_results)
        datalog_verdict_str = verdict.action

        # Step 4.5: KG Context Lookup — Markov Blanket (E2)
        # E2 改造：用 Markov Blanket 选择性注入替代全量 KG。
        # Loop 43 发现全量注入 FPR 从 5.6% → 11.1%（噪声过多）。
        # Markov Blanket 只注入因果相关实体，预期恢复 FPR 到 5-6%。
        if kg_context is None and db is not None and semantic_config is not None:
            kg_context = _build_kg_context(facts, db, extra_seeds=_intent_seeds)

        # 提取 blanket-formatted context for semantic gate injection
        _blanket_kg_for_semantic = None
        if kg_context is not None and "blanket" in kg_context:
            _blanket_kg_for_semantic = kg_context  # Markov Blanket context (selective)

        # Step 4.6: 三层路由（M7.3）
        layer_path = "datalog_only"
        sem_verdict: Optional[dict] = None

        if verdict.action in ("block", "warn", "rewrite", "require"):
            # 硬裁决 → 直接返回，不需要 LLM
            layer_path = "datalog_only"

        elif verdict.action == "allow":
            # Layer 2: Triviality Filter
            if triviality_config is not None and is_trivial(facts, triviality_config):
                layer_path = "trivial_allow"
            elif semantic_config is not None:
                # Layer 3: Semantic Gate — now with Markov Blanket context (E2)
                layer_path = "semantic"
                sem_verdict = _run_semantic_gate(
                    tool_call, facts, datalog_verdict_str,
                    _blanket_kg_for_semantic, semantic_config,
                    intent_seeds=_intent_seeds,
                )
                verdict = _apply_semantic_verdict(
                    verdict, datalog_verdict_str, sem_verdict, semantic_config,
                )
            # else: no semantic config → pure datalog (backward compatible)

        elif verdict.action in ("confirm", "delegate"):
            # confirm → Semantic Gate 可降级为 allow（降 FPR）
            if semantic_config is not None:
                layer_path = "semantic"
                sem_verdict = _run_semantic_gate(
                    tool_call, facts, datalog_verdict_str,
                    _blanket_kg_for_semantic, semantic_config,
                    intent_seeds=_intent_seeds,
                )
                verdict = _apply_semantic_verdict(
                    verdict, datalog_verdict_str, sem_verdict, semantic_config,
                )

        # Step 5: 构建 ProofTrace
        latency_ms = (time.perf_counter() - t_start) * 1000
        proof_trace = _build_proof_trace(match_results, verdict.action, latency_ms)

        # Step 5.5: 构建 CostBreakdown（M2.P2）
        entities_scanned = len(facts)
        cost_breakdown = CostBreakdown(
            fact_extraction_us=fact_extraction_us,
            constraint_match_us=constraint_match_us,
            entities_scanned=entities_scanned,
            constraints_evaluated=len(constraints),
        )

        # Step 5.6: 资源预算检查（M2.P3：超限 log warning，不 block）
        check_budget(
            budget=budget,
            entities_scanned=entities_scanned,
            constraints_evaluated=len(constraints),
            elapsed_us=int(latency_ms * 1000),
        )

        # Step 6: 写 decision_log
        decision_log_id: Optional[str] = None
        if db is not None:
            logged = log_decision(
                verdict=verdict.action,
                proof_trace=proof_trace,
                sampling_policy=policy,
                db=db,
                session_key=sk,
                tool_name=tool_call.get("tool_name") or tool_call.get("name") or "",
                facts=facts,
                latency_us=int(latency_ms * 1000),
            )
            if logged:
                decision_log_id = sk

        result = GateResult(
            verdict=verdict,
            proof_trace=proof_trace,
            decision_log_id=decision_log_id,
            latency_ms=latency_ms,
            facts=facts,
            cost_breakdown=cost_breakdown,
            datalog_verdict=datalog_verdict_str,
            semantic_verdict=sem_verdict,
            layer_path=layer_path,
            kg_context=kg_context,  # preserved for post-gate enrichment
        )

        # Loop 42: 事件推送到 gate_events.jsonl
        _emit_gate_event(result, tool_call)

        # Loop 42: 边权重贝叶斯更新
        if db is not None and result.kg_context is not None:
            try:
                from nous.edge_weight import update_edge_weights
                update_edge_weights(db, {
                    "verdict": result.verdict.action,
                    "kg_context": result.kg_context,
                    "facts": result.facts,
                })
            except Exception as exc:
                _gate_event_logger.debug("edge weight update failed (non-fatal): %s", exc)

        return result

    except ConstraintLoadError as e:  # FAIL_CLOSED: 约束加载失败 → confirm
        import logging as _logging
        _logging.getLogger("nous.gate").error("FAIL_CLOSED: %s", e)
        latency_ms = (time.perf_counter() - t_start) * 1000

        fail_verdict = Verdict(
            action="confirm",
            rule_id="nous-constraint-load-error",
            reason=f"constraint-load-failed: {e}",
        )
        fail_trace = ProofTrace(
            steps=[],
            final_verdict="confirm",
            total_ms=latency_ms,
        )

        # 尽力写日志（不再抛出）
        try:
            if db is not None:
                log_decision(
                    verdict="confirm",
                    proof_trace=fail_trace,
                    sampling_policy=SamplingPolicy(confirm_rate=1.0),
                    db=db,
                    session_key=sk,
                    tool_name="unknown",
                    facts={"error": str(e)},
                    latency_us=int(latency_ms * 1000),
                )
        except Exception:
            pass

        return GateResult(
            verdict=fail_verdict,
            proof_trace=fail_trace,
            decision_log_id=None,
            latency_ms=latency_ms,
            facts={},
            datalog_verdict=None,
            semantic_verdict=None,
            layer_path="datalog_only",
        )

    except Exception as e:  # 真正的代码 bug — 同样 confirm，但日志更醒目
        import logging as _logging
        _logging.getLogger("nous.gate").critical(
            "UNEXPECTED gate() exception (not ConstraintLoadError): %s: %s",
            type(e).__name__, e, exc_info=True,
        )
        latency_ms = (time.perf_counter() - t_start) * 1000

        fail_verdict = Verdict(
            action="confirm",
            rule_id="nous-engine-error",
            reason=f"nous-engine-unavailable: {type(e).__name__}: {e}",
        )
        fail_trace = ProofTrace(
            steps=[],
            final_verdict="confirm",
            total_ms=latency_ms,
        )

        try:
            if db is not None:
                log_decision(
                    verdict="confirm",
                    proof_trace=fail_trace,
                    sampling_policy=SamplingPolicy(confirm_rate=1.0),
                    db=db,
                    session_key=sk,
                    tool_name="unknown",
                    facts={"error": str(e), "error_type": type(e).__name__},
                    latency_us=int(latency_ms * 1000),
                )
        except Exception:
            pass

        return GateResult(
            verdict=fail_verdict,
            proof_trace=fail_trace,
            decision_log_id=None,
            latency_ms=latency_ms,
            facts={},
            datalog_verdict=None,
            semantic_verdict=None,
            layer_path="datalog_only",
        )


# ── 内部：Semantic Gate 调用 + Verdict 合并 ───────────────────────────────


def _run_semantic_gate(
    tool_call: dict,
    facts: dict,
    datalog_verdict: str,
    kg_context: Optional[dict],
    config: SemanticGateConfig,
    intent_seeds: Optional[list] = None,
) -> Optional[dict]:
    """调用 Semantic Gate，返回 SemanticVerdict dict 或 None。"""
    result = semantic_gate(
        tool_call=tool_call,
        facts=facts,
        datalog_verdict=datalog_verdict,
        kg_context=kg_context,
        config=config,
        intent_seeds=intent_seeds,
    )
    return dict(result) if result is not None else None


def _apply_semantic_verdict(
    current_verdict: Verdict,
    datalog_verdict: str,
    sem_verdict: Optional[dict],
    config: SemanticGateConfig,
) -> Verdict:
    """Confidence-Calibrated Verdict Fusion (Loop 4 + Loop 8).

    设计原则：Datalog 是强先验，LLM 需要提供高置信度证据才能推翻。

    规则：
    - shadow 模式 → 不改变（只记录）
    - active 模式：
      Datalog "allow":
        - semantic block (conf >= block_upgrade_threshold) → 升级为 block
        - semantic block (conf < threshold) → 保持 allow（证据不足）
        - semantic confirm → 保持 allow（LLM 犹豫不推翻规则许可）
        - semantic allow → 保持 allow
      Datalog "confirm"/"delegate":
        - semantic allow (conf >= allow_downgrade_threshold) → 降级为 allow
        - semantic allow (conf < threshold) → 保持 confirm
        - semantic block (conf >= block_upgrade_threshold) → 升级为 block
        - semantic block (conf < block_upgrade_threshold) → 保持 confirm（Loop 8: 低置信度不升级，由人类决定）
        - semantic confirm → 保持 confirm
    """
    if config.mode != "active":
        return current_verdict

    if sem_verdict is None:
        return current_verdict

    sem_action = sem_verdict.get("action", "")
    sem_reason = sem_verdict.get("reason", "")
    sem_confidence = float(sem_verdict.get("confidence", 0.5))

    if datalog_verdict == "allow":
        if sem_action == "block" and sem_confidence >= config.block_upgrade_threshold:
            return Verdict(
                action="block",
                rule_id="semantic-gate",
                reason=f"[semantic block@{sem_confidence:.2f}] {sem_reason}",
                all_matched=current_verdict.all_matched,
            )
        # semantic block below threshold / confirm / allow → keep allow
        # Key insight: LLM "confirm" (hesitation) should NOT override Datalog's allow
        return current_verdict

    elif datalog_verdict in ("confirm", "delegate"):
        if sem_action == "allow" and sem_confidence >= config.allow_downgrade_threshold:
            return Verdict(
                action="allow",
                rule_id=f"{current_verdict.rule_id}+semantic-override",
                reason=f"[semantic allow@{sem_confidence:.2f}] {sem_reason}",
                all_matched=current_verdict.all_matched,
            )
        elif sem_action == "block" and sem_confidence >= config.block_upgrade_threshold:
            return Verdict(
                action="block",
                rule_id=f"{current_verdict.rule_id}+semantic-upgrade",
                reason=f"[semantic block@{sem_confidence:.2f}] {sem_reason}",
                all_matched=current_verdict.all_matched,
            )
        elif sem_action == "block":
            # Low-confidence block → keep confirm (Loop 8: insufficient evidence, let human decide)
            return current_verdict
        # sem confirm or low-confidence allow → keep confirm
        return current_verdict

    return current_verdict
