"""Nous — Triviality Filter (M7.3 Layer 2)

快速预筛选：判断操作是否安全无需 LLM 语义审查。
位于 Datalog 规则匹配后、Semantic Gate 前。

设计原则：
- 只做结构匹配，无副作用，<0.1ms
- 宁漏不误：不确定的一律返回 False（进入 Semantic Gate）
- 可配置白名单 + 自定义谓词
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


# ── 默认安全 action_type 集合 ──────────────────────────────────────────────

_DEFAULT_ALLOW_ACTION_TYPES = frozenset({
    "read_file",       # 只读文件
    "web_search",      # 搜索（无写操作）
    "web_fetch",       # 网页抓取
    "read_data",       # 数据读取
    "list",            # 列表操作
    "download",        # 下载（不含执行）
    "transform",       # 格式转换
})

_DEFAULT_READONLY_COMMANDS = frozenset({
    "ls", "pwd", "whoami", "cat", "head", "tail", "wc", "grep", "find",
    "git status", "git log", "git diff", "git branch", "git show",
    "echo", "date", "uname", "df", "du", "file", "which", "env",
    "python3 --version", "node --version", "cargo --version",
})


# ── 配置 ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TrivialityConfig:
    """Triviality filter 配置。

    Attributes:
        enabled: 是否启用。False → is_trivial 始终返回 False
        allow_action_types: 视为安全的 action_type 集合
        allow_readonly_commands: 视为安全的只读命令（精确匹配或前缀匹配）
        extra_predicates: 额外自定义谓词，任一返回 True → 视为 trivial
    """
    enabled: bool = True
    allow_action_types: frozenset[str] = _DEFAULT_ALLOW_ACTION_TYPES
    allow_readonly_commands: frozenset[str] = _DEFAULT_READONLY_COMMANDS
    extra_predicates: list[Callable[[dict], bool]] = field(default_factory=list)


_DEFAULT_CONFIG = TrivialityConfig()


# ── 主函数 ────────────────────────────────────────────────────────────────


def is_trivial(facts: dict, config: TrivialityConfig | None = None) -> bool:
    """判断操作是否安全无需 LLM 审查。

    Args:
        facts: gate pipeline 提取的事实（action_type, url 等）
        config: 可选配置，None 使用默认值

    Returns:
        True → 安全操作，可直接 allow
        False → 需要进入 Semantic Gate

    规则（按顺序）：
    1. config.enabled == False → False（强制禁用）
    2. action_type 在 allow_action_types 中 → True
    3. action_type == "exec_command" 且命令匹配 allow_readonly_commands → True
    4. 任一 extra_predicate 返回 True → True
    5. 否则 → False
    """
    cfg = config or _DEFAULT_CONFIG

    if not cfg.enabled:
        return False

    action_type = facts.get("action_type", "")

    # Rule 2: 安全 action_type
    if action_type in cfg.allow_action_types:
        return True

    # Rule 3: 只读命令匹配
    if action_type == "exec_command":
        cmd = str(facts.get("command", "")).strip()
        if not cmd:
            return False
        # 精确匹配
        if cmd in cfg.allow_readonly_commands:
            return True
        # 前缀匹配（命令 + 空格 + 参数）
        for safe_cmd in cfg.allow_readonly_commands:
            if cmd.startswith(safe_cmd + " "):
                return True
            # 也匹配命令本身（无参数的情况已由精确匹配覆盖）
        return False

    # Rule 4: 自定义谓词
    for predicate in cfg.extra_predicates:
        try:
            if predicate(facts):
                return True
        except Exception:
            # 谓词异常 → 保守处理，不视为 trivial
            pass

    # Rule 5: 默认不安全
    return False
