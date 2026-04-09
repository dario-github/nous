"""
Nous gate 防御适配层 for AgentDojo

NousFilteredRuntime: 继承 FunctionsRuntime，在每次工具调用前调用 Nous gate。
如果 gate 判定 block → 返回拒绝信息，不执行工具。
如果 gate 判定 allow/warn → 透传执行。

设计决策：
- 继承而非组合：run_task_with_pipeline 期望 runtime_class(tools)，必须是 FunctionsRuntime 子类
- FAIL_OPEN：gate 异常时透传执行，不影响 utility 评估
- 全局决策日志：通过类变量收集跨任务的决策，供评估脚本读取
"""

import logging
from collections.abc import Mapping, Sequence
from typing import Any

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

    def __init__(self, functions: Sequence[Function] = []) -> None:
        super().__init__(functions)

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
        verdict = "allow"
        latency_ms = 0.0

        try:
            result = gate(tool_call=tool_call)
            verdict = result.verdict.action if hasattr(result.verdict, "action") else str(result.verdict)
            latency_ms = result.latency_ms
        except Exception as exc:
            # FAIL_OPEN：gate 异常不影响评估
            logger.warning("Nous gate exception (fail-open): %s", exc)
            verdict = "allow"

        NousFilteredRuntime._log.append(
            {
                "function": function,
                "kwargs": dict(kwargs),
                "verdict": verdict,
                "latency_ms": latency_ms,
            }
        )

        if verdict == "block":
            logger.info("Nous BLOCKED: %s(%s)", function, dict(kwargs))
            return BLOCKED_RESULT, None

        logger.debug("Nous %s: %s", verdict, function)
        return super().run_function(env, function, kwargs, raise_on_error=raise_on_error)
