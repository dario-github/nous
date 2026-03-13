"""AgentHarm — Benchmark Runner

对每个 AgentHarm scenario 执行 Nous gate()，收集结果。

判定逻辑
--------
场景级：任一 tool_call 的 gate() 返回 block 或 confirm → 场景被拦截
工具级：每个 tool_call 独立记录 gate 结果
"""
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from nous.gate import gate, GateResult

logger = logging.getLogger(__name__)

# 默认约束目录（从 nous 项目根推导）
# runner.py @ src/nous/benchmarks/agentharm/runner.py → 5 级 parent = nous/ project root
_DEFAULT_CONSTRAINTS_DIR = (
    Path(__file__).parent.parent.parent.parent.parent / "ontology" / "constraints"
)

# 触发"拦截"的 verdict action 集合
_BLOCKING_VERDICTS = frozenset({"block", "confirm"})


@dataclass
class ToolCallResult:
    """单个 tool_call 的 gate 结果。"""

    func_name: str
    action_type: str
    verdict_action: str
    verdict_rule_id: Optional[str]
    verdict_reason: Optional[str]
    latency_ms: float
    facts: dict = field(default_factory=dict)

    @property
    def is_blocked(self) -> bool:
        return self.verdict_action in _BLOCKING_VERDICTS

    def to_dict(self) -> dict:
        return {
            "func_name": self.func_name,
            "action_type": self.action_type,
            "verdict_action": self.verdict_action,
            "verdict_rule_id": self.verdict_rule_id,
            "verdict_reason": self.verdict_reason,
            "latency_ms": round(self.latency_ms, 3),
            "is_blocked": self.is_blocked,
        }


@dataclass
class BenchmarkResult:
    """单个 AgentHarm scenario 的完整评测结果。"""

    scenario_id: str
    scenario_name: str
    category: str
    is_harmful: bool
    any_blocked: bool
    tool_results: list[ToolCallResult] = field(default_factory=list)

    @property
    def block_rule_ids(self) -> list[str]:
        """返回所有触发拦截的规则 ID 列表。"""
        return [
            r.verdict_rule_id
            for r in self.tool_results
            if r.is_blocked and r.verdict_rule_id
        ]

    @property
    def blocked_funcs(self) -> list[str]:
        """返回被拦截的函数名列表。"""
        return [r.func_name for r in self.tool_results if r.is_blocked]

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "category": self.category,
            "is_harmful": self.is_harmful,
            "any_blocked": self.any_blocked,
            "block_rule_ids": self.block_rule_ids,
            "blocked_funcs": self.blocked_funcs,
            "tool_results": [r.to_dict() for r in self.tool_results],
        }


def _run_single_tool_call(
    tool_call: dict,
    constraints_dir: Path,
) -> ToolCallResult:
    """对单个 tool_call 执行 gate()，返回 ToolCallResult。"""
    func_name = tool_call.get("tool_name", "unknown")
    action_type = tool_call.get("action_type", "unknown")

    gr: GateResult = gate(
        tool_call,
        db=None,  # 纯内存评估，不写 decision_log
        constraints_dir=constraints_dir,
    )

    return ToolCallResult(
        func_name=func_name,
        action_type=action_type,
        verdict_action=gr.verdict.action,
        verdict_rule_id=gr.verdict.rule_id,
        verdict_reason=gr.verdict.reason,
        latency_ms=gr.latency_ms,
        facts=gr.facts,
    )


def run_benchmark(
    scenarios: list[dict],
    is_harmful: bool,
    constraints_dir: Optional[Path] = None,
    verbose: bool = False,
) -> list[BenchmarkResult]:
    """对 scenarios 批量执行 gate()，收集 BenchmarkResult 列表。

    Args:
        scenarios:       AgentHarm scenario dict 列表（来自 loader）
        is_harmful:      True = harmful test cases，False = benign
        constraints_dir: 约束 YAML 目录（默认 ontology/constraints/）
        verbose:         是否打印进度日志

    Returns:
        list[BenchmarkResult]
    """
    from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls

    cdir = constraints_dir or _DEFAULT_CONSTRAINTS_DIR
    results: list[BenchmarkResult] = []

    label = "harmful" if is_harmful else "benign"
    logger.info("Running benchmark on %d %s scenarios...", len(scenarios), label)
    t0 = time.perf_counter()

    for i, scenario in enumerate(scenarios):
        tool_calls = scenario_to_tool_calls(scenario)

        tool_results: list[ToolCallResult] = []
        for tc in tool_calls:
            tr = _run_single_tool_call(tc, cdir)
            tool_results.append(tr)

        any_blocked = any(tr.is_blocked for tr in tool_results)

        result = BenchmarkResult(
            scenario_id=scenario.get("id", f"unknown_{i}"),
            scenario_name=scenario.get("name", ""),
            category=scenario.get("category", "unknown"),
            is_harmful=is_harmful,
            any_blocked=any_blocked,
            tool_results=tool_results,
        )
        results.append(result)

        if verbose and (i + 1) % 20 == 0:
            elapsed = time.perf_counter() - t0
            logger.info(
                "  Progress: %d/%d (%.1fs elapsed)", i + 1, len(scenarios), elapsed
            )

    elapsed_total = time.perf_counter() - t0
    blocked_count = sum(1 for r in results if r.any_blocked)
    logger.info(
        "Finished %d %s scenarios in %.2fs — blocked: %d/%d (%.1f%%)",
        len(scenarios),
        label,
        elapsed_total,
        blocked_count,
        len(results),
        100.0 * blocked_count / len(results) if results else 0.0,
    )

    return results
