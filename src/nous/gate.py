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
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from nous.constraint_parser import ConstraintLoadError, load_constraints
from nous.decision_log import CostBreakdown
from nous.fact_extractor import extract_facts
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

        # Step 2: 加载约束
        constraints = load_constraints(constraints_dir)

        # Step 3: 约束匹配（M2.P2: 计时）
        t3_start = time.perf_counter_ns()
        match_results = match_all_constraints(constraints, facts)
        constraint_match_us = (time.perf_counter_ns() - t3_start) // 1000

        # Step 4: Verdict 路由
        verdict = route_verdict(match_results)
        datalog_verdict_str = verdict.action

        # Step 4.5: 三层路由（M7.3）
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
                # Layer 3: Semantic Gate
                layer_path = "semantic"
                sem_verdict = _run_semantic_gate(
                    tool_call, facts, datalog_verdict_str,
                    kg_context, semantic_config,
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
                    kg_context, semantic_config,
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

        return GateResult(
            verdict=verdict,
            proof_trace=proof_trace,
            decision_log_id=decision_log_id,
            latency_ms=latency_ms,
            facts=facts,
            cost_breakdown=cost_breakdown,
            datalog_verdict=datalog_verdict_str,
            semantic_verdict=sem_verdict,
            layer_path=layer_path,
        )

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
) -> Optional[dict]:
    """调用 Semantic Gate，返回 SemanticVerdict dict 或 None。"""
    result = semantic_gate(
        tool_call=tool_call,
        facts=facts,
        datalog_verdict=datalog_verdict,
        kg_context=kg_context,
        config=config,
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
