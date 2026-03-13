"""Nous — Gate API (M2.5)

完整决策 pipeline：
  tool_call → extract_facts → load_constraints → match → route_verdict
           → proof_trace → log_decision → GateResult

FAIL_CLOSED 原则：任何异常 → confirm（永不 allow）
"""
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from nous.constraint_parser import load_constraints
from nous.decision_log import CostBreakdown
from nous.fact_extractor import extract_facts
from nous.observability import SamplingPolicy, log_decision
from nous.proof_trace import ProofStep, ProofTrace
from nous.resource_budget import load_resource_budget, check_budget
from nous.schema import Constraint
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
    """
    verdict: Verdict
    proof_trace: ProofTrace
    decision_log_id: Optional[str]
    latency_ms: float
    facts: dict = field(default_factory=dict)
    cost_breakdown: Optional[CostBreakdown] = None  # M2.P2

    def to_dict(self) -> dict:
        d = {
            "verdict": self.verdict.to_dict(),
            "proof_trace": self.proof_trace.to_dict(),
            "decision_log_id": self.decision_log_id,
            "latency_ms": round(self.latency_ms, 3),
            "facts": self.facts,
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
) -> GateResult:
    """
    决策 pipeline 入口。

    Args:
        tool_call:        工具调用 dict（tool_name / action / params 等）
        db:               NousDB 实例（可选，用于写 decision_log）
        constraints_dir:  约束目录（默认 ontology/constraints/）
        session_key:      日志 session 标识（可选，自动生成）
        sampling_policy:  采样策略（默认 _DEFAULT_POLICY）

    Returns:
        GateResult（包含 verdict + proof_trace + decision_log_id）

    FAIL_CLOSED：任何异常 → confirm + reason="nous-engine-unavailable"
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
        )

    except Exception as e:  # FAIL_CLOSED
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
        )
