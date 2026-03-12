"""Nous — Session 隔离守卫 (M2.8)

检测 eval/test session，阻止其写入 memory/ 目录。

API：
    is_eval_session(context: dict) -> bool
        检测 context 的 session tag，若为 eval/test 返回 True。

    guard_memory_write(tool_call: dict, context: dict) -> Verdict
        eval session 尝试写 memory/ → 返回 block Verdict
        normal session → 返回 allow Verdict

集成方式：
    在 gateway_hook.before_tool_call() 中作为额外约束调用，
    或直接在 gate() pipeline 中注入（见 gate_with_session_guard）。
"""
import logging
import re
from typing import Optional

from nous.verdict import Verdict

logger = logging.getLogger("nous.session_guard")

# eval/test session 标识（忽略大小写）
_EVAL_SESSION_TAGS = frozenset({"eval", "test", "evaluation", "testing", "sandbox"})

# memory/ 写入操作的路径模式
_MEMORY_WRITE_PATTERN = re.compile(r"memory[/\\]", re.IGNORECASE)

# 会触发写入的工具/操作名称
_WRITE_TOOL_NAMES = frozenset({
    "write", "write_file", "create_file", "edit", "edit_file",
    "append", "append_file", "save", "save_file", "update", "update_file",
})


# ── 核心函数 ──────────────────────────────────────────────────────────────


def is_eval_session(context: dict) -> bool:
    """
    检测 context dict 是否为 eval/test session。

    检查路径（优先级从高到低）：
    1. context["session_tag"]
    2. context["tags"]（list）
    3. context["session_id"]（包含 eval/test 子串）
    4. context["session_type"]
    5. context["mode"]

    返回 True 表示是 eval/test session。
    """
    if not isinstance(context, dict):
        return False

    # 1. session_tag（字符串）
    session_tag = context.get("session_tag")
    if isinstance(session_tag, str) and session_tag.lower() in _EVAL_SESSION_TAGS:
        return True

    # 2. tags（列表）
    tags = context.get("tags")
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and tag.lower() in _EVAL_SESSION_TAGS:
                return True

    # 3. session_id（包含关键字）
    session_id = context.get("session_id")
    if isinstance(session_id, str):
        sid_lower = session_id.lower()
        if any(ev in sid_lower for ev in ("eval", "test", "sandbox")):
            return True

    # 4. session_type
    session_type = context.get("session_type")
    if isinstance(session_type, str) and session_type.lower() in _EVAL_SESSION_TAGS:
        return True

    # 5. mode
    mode = context.get("mode")
    if isinstance(mode, str) and mode.lower() in _EVAL_SESSION_TAGS:
        return True

    return False


def _is_memory_write(tool_call: dict) -> bool:
    """
    判断 tool_call 是否为写入 memory/ 目录的操作。

    检查：
    1. tool_name/action 是否为写操作
    2. 写入路径是否包含 memory/
    """
    tool_name = (
        tool_call.get("tool_name")
        or tool_call.get("name")
        or tool_call.get("action")
        or ""
    ).lower()

    # 非写操作 → 不触发
    if tool_name not in _WRITE_TOOL_NAMES and not any(
        w in tool_name for w in ("write", "edit", "save", "create", "update", "append")
    ):
        return False

    # 检查路径参数
    params = tool_call.get("params") or tool_call.get("parameters") or {}
    if not isinstance(params, dict):
        params = {}

    # 直接路径字段
    for key in ("path", "file_path", "filepath", "dest", "destination", "target"):
        val = tool_call.get(key) or params.get(key)
        if isinstance(val, str) and _MEMORY_WRITE_PATTERN.search(val):
            return True

    return False


def guard_memory_write(tool_call: dict, context: dict) -> Verdict:
    """
    eval session 写 memory/ → block Verdict
    normal session 或非写操作 → allow Verdict

    Args:
        tool_call: 工具调用 dict
        context:   会话上下文 dict（含 session_tag 等）

    Returns:
        Verdict（block 或 allow）
    """
    if is_eval_session(context) and _is_memory_write(tool_call):
        logger.warning(
            "[session_guard] BLOCK: eval session 试图写入 memory/: tool=%s",
            tool_call.get("tool_name") or tool_call.get("name", "?"),
        )
        return Verdict(
            action="block",
            rule_id="session-guard:eval-memory-write",
            reason="eval/test session 禁止写入 memory/ 目录",
        )

    return Verdict(
        action="allow",
        rule_id="",
        reason="",
    )


# ── 集成：带 session guard 的 gate ────────────────────────────────────────


def gate_with_session_guard(
    tool_call: dict,
    context: Optional[dict] = None,
    **gate_kwargs,
):
    """
    在 gate() 之前先运行 session_guard。

    session guard 触发 block → 直接返回（不运行 gate pipeline）
    否则 → 交给 gate() 处理

    Args:
        tool_call:    工具调用 dict
        context:      会话上下文（含 session_tag 等）
        **gate_kwargs: 透传给 gate() 的参数（db/constraints_dir/session_key 等）

    Returns:
        GateResult（verdict 可能来自 session_guard 或 gate pipeline）
    """
    from nous.gate import gate, GateResult
    from nous.proof_trace import ProofTrace, ProofStep
    import time

    ctx = context or {}
    guard_verdict = guard_memory_write(tool_call, ctx)

    if guard_verdict.action == "block":
        # 构建简单的 GateResult 表示 session guard 触发
        step = ProofStep(
            rule_id=guard_verdict.rule_id,
            fact_bindings={
                "session_tag": ctx.get("session_tag", ""),
                "is_eval": True,
            },
            verdict="match",
            timestamp=time.time(),
        )
        trace = ProofTrace(
            steps=[step],
            final_verdict="block",
            total_ms=0.0,
        )
        return GateResult(
            verdict=guard_verdict,
            proof_trace=trace,
            decision_log_id=None,
            latency_ms=0.0,
            facts={"session_guard": "triggered"},
        )

    # 正常走 gate pipeline
    return gate(tool_call=tool_call, **gate_kwargs)
