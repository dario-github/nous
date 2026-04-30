"""
Nous gate 防御适配层 for AgentDojo

NousFilteredRuntime: 继承 FunctionsRuntime，在每次工具调用前调用 Nous gate。
如果 gate 判定 block，或在无人工确认的 batch eval 中判定 confirm → 返回拒绝信息，不执行工具。
如果 gate 判定 allow/warn → 透传执行。

设计决策：
- 继承而非组合：run_task_with_pipeline 期望 runtime_class(tools)，必须是 FunctionsRuntime 子类
- FAIL_OPEN：gate 异常时透传执行，不影响 utility 评估
- 全局决策日志：通过类变量收集跨任务的决策，供评估脚本读取
- 多层配置：通过 configure() 控制启用哪几层
"""

import logging
from collections.abc import Mapping, Sequence
from typing import Any, Optional

from agentdojo.functions_runtime import Function, FunctionReturnType, FunctionsRuntime, TaskEnvironment

logger = logging.getLogger(__name__)

BLOCKED_RESULT = "[NOUS_BLOCKED] 此工具调用已被 Nous 安全门控拦截。"


def _to_nous_format(function: str, kwargs: Mapping[str, Any]) -> dict:
    """把 AgentDojo 工具调用格式转换为 Nous gate 格式。

    Nous gate 期望: {"tool_name": str, "action": str, "params": dict}
    """
    return {
        "tool_name": function,
        "action": function,
        "params": dict(kwargs),
    }


class NousFilteredRuntime(FunctionsRuntime):
    """FunctionsRuntime 子类，在 run_function 前插入 Nous gate 检查。

    使用方式：
        # 配置层（在 main 中调用一次）
        NousFilteredRuntime.configure(
            verifier_config=VerifierConfig(),       # Layer 4（零成本）
            semantic_config=SemanticGateConfig(...), # Layer 3（需 LLM）
        )

        # 运行评估
        results = suite.run_task_with_pipeline(
            agent_pipeline=pipeline,
            user_task=task,
            injection_task=inj_task,
            injections=injections,
            runtime_class=NousFilteredRuntime,  # ← 替换默认 runtime
        )

    决策日志通过 NousFilteredRuntime.get_log() 读取（类级别，跨实例共享）。
    """

    # 类级别决策日志，跨实例累积
    _log: list[dict] = []

    # 类级别层配置
    _verifier_config: Optional[Any] = None   # VerifierConfig | None
    _semantic_config: Optional[Any] = None   # SemanticGateConfig | None

    # P1 实验：当前任务的用户原始目标（每个任务开始前调用 set_user_goal 设置）
    _user_goal: str = ""

    def __init__(self, functions: Sequence[Function] = []) -> None:
        super().__init__(functions)

    @classmethod
    def set_user_goal(cls, goal: str) -> None:
        """设置当前任务的用户目标（P1 实验用，注入到 gate 的 tool_call 元数据）。"""
        cls._user_goal = goal or ""

    @classmethod
    def configure(
        cls,
        verifier_config: Optional[Any] = None,
        semantic_config: Optional[Any] = None,
    ) -> None:
        """配置启用哪几层防御。

        Args:
            verifier_config: Layer 4 审计员配置（None → 禁用）
            semantic_config: Layer 3 语义门控配置（None → 禁用）
        """
        cls._verifier_config = verifier_config
        cls._semantic_config = semantic_config

    @classmethod
    def get_log(cls) -> list[dict]:
        return list(cls._log)

    @classmethod
    def clear_log(cls) -> None:
        cls._log.clear()

    def run_function(
        self,
        env: TaskEnvironment | None,
        function: str,
        kwargs: Mapping[str, Any],
        raise_on_error: bool = False,
    ) -> tuple[FunctionReturnType, str | None]:
        """在执行工具前调用 Nous gate。block → 拒绝；否则透传。"""
        from nous.gate import gate

        tool_call = _to_nous_format(function, kwargs)
        # P1 实验：注入用户原始任务目标（_user_goal 前缀 _ 表示元数据，不是工具参数）
        if self.__class__._user_goal:
            tool_call["_user_goal"] = self.__class__._user_goal
        gate_verdict = "allow"
        effective_verdict = "allow"
        latency_ms = 0.0
        layer_path = "datalog_only"
        semantic_verdict: Optional[dict] = None
        verifier_result: Optional[dict] = None
        verifier_flags: list[dict] = []

        try:
            result = gate(
                tool_call=tool_call,
                verifier_config=self.__class__._verifier_config,
                semantic_config=self.__class__._semantic_config,
            )
            gate_verdict = result.verdict.action if hasattr(result.verdict, "action") else str(result.verdict)
            # In batch eval there is no human-in-loop, so "confirm" must escalate
            # to actual block (otherwise verifier engages but never defends).
            effective_verdict = "block" if gate_verdict in ("block", "confirm") else gate_verdict
            latency_ms = result.latency_ms
            layer_path = getattr(result, "layer_path", "datalog_only")
            semantic_verdict = getattr(result, "semantic_verdict", None)

            # 收集 verifier flags（供分析用）
            if result.verifier_result:
                verifier_result = result.verifier_result
                verifier_flags = verifier_result.get("flags", [])

        except Exception as exc:
            # FAIL_OPEN：gate 异常不影响评估
            logger.warning("Nous gate exception (fail-open): %s", exc)
            gate_verdict = "allow"
            effective_verdict = "allow"

        block_source = None
        if effective_verdict == "block":
            block_source = "confirm_to_block" if gate_verdict == "confirm" else "gate_block"

        NousFilteredRuntime._log.append(
            {
                "function": function,
                "kwargs": dict(kwargs),
                "verdict": effective_verdict,           # backward-compat field
                "gate_verdict": gate_verdict,
                "effective_verdict": effective_verdict,
                "execution_blocked": effective_verdict == "block",
                "block_source": block_source,
                "latency_ms": latency_ms,
                "layer_path": layer_path,
                "semantic_verdict": semantic_verdict,
                "verifier_recommendation": (verifier_result or {}).get("recommendation"),
                "verifier_flags": verifier_flags,
            }
        )

        if effective_verdict == "block":
            logger.info("Nous BLOCKED (%s): %s(%s)", gate_verdict, function, dict(kwargs))
            return BLOCKED_RESULT, None

        logger.debug("Nous %s: %s", gate_verdict, function)
        return super().run_function(env, function, kwargs, raise_on_error=raise_on_error)
