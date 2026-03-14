"""Nous — Triviality Filter (M7.3 Layer 2, Loop 8: Content Escalation)

快速预筛选：判断操作是否安全无需 LLM 语义审查。
位于 Datalog 规则匹配后、Semantic Gate 前。

设计原则：
- 只做结构匹配 + 轻量内容信号检测，无副作用，<0.5ms
- 宁漏不误：不确定的一律返回 False（进入 Semantic Gate）
- 可配置白名单 + 自定义谓词
- **Loop 8**: 即使 action_type 安全，如果内容包含有害意图信号，也路由到 Semantic Gate
  这修复了 "全部由 trivial 操作组成的有害场景" 的结构性盲点
  (Fraud 58-x: web_search+web_fetch only, Drugs 10-x: web_search only)
"""
from __future__ import annotations

import re
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


# ── 内容升级信号（Loop 8: 路由启发式，非最终判决） ──────────────────────────
# 目的：检测 tool_call 内容中的有害意图信号，阻止 trivial auto-allow
# 原则：高精度（不误伤正常搜索），只影响路由（实际 allow/block 由 semantic gate 决定）
# 路线：Route B 过渡方案，后续替换为 embedding-based intent classifier

_ESCALATION_PATTERNS = [
    # ── 金融犯罪/欺诈 ──
    re.compile(r"stolen\s+(credit\s+card|financial|identit)", re.I),
    re.compile(r"dark\s+web", re.I),
    re.compile(r"phishing\s+kit", re.I),
    re.compile(r"hid(e|ing)\s+income\s+from\s+tax", re.I),
    re.compile(r"offshore\s+accounts?\s+.*shell\s+compan", re.I),
    re.compile(r"money\s+launder", re.I),
    re.compile(r"counterfeit\s+(money|currency|bill)", re.I),
    re.compile(r"tax\s+(evasion|fraud)", re.I),
    re.compile(r"ponzi\s+scheme", re.I),
    re.compile(r"identity\s+theft", re.I),
    # ── 毒品 ──
    re.compile(r"illegal\s+drugs?", re.I),
    re.compile(r"manufactur(e|ing)\s+.*meth", re.I),
    re.compile(r"buy\s+and\s+sell\s+.*drugs?", re.I),
    re.compile(r"drug\s+(supplier|dealer|handoff|traffick)", re.I),
    re.compile(r"(raw\s+materials?|precursor)\s+.*(?:meth|fentanyl|cocaine|heroin)", re.I),
    # ── 网络犯罪 ──
    re.compile(r"(create|build|write|develop)\s+.*malware", re.I),
    re.compile(r"ransomware\s+(attack|deploy|creat)", re.I),
    re.compile(r"exploit\s+vulnerabilit", re.I),
    re.compile(r"(hack|breach)\s+(into|a\s+)", re.I),
    re.compile(r"(ddos|denial.of.service)\s+attack", re.I),
    # ── 武器/暴力 ──
    re.compile(r"(build|make|assembl)\w*\s+.*\b(bomb|explosive|weapon)", re.I),
    re.compile(r"(buy|purchase|obtain)\s+.*\b(firearm|gun)\b.*illegal", re.I),
    # ── 虐待/剥削 ──
    re.compile(r"child\s+(exploit|abuse|porn)", re.I),
    re.compile(r"human\s+trafficking", re.I),
]


def _has_escalation_signal(content: str) -> bool:
    """检查内容是否包含有害意图信号。<0.3ms for typical content."""
    if not content or len(content) < 10:
        return False
    for pattern in _ESCALATION_PATTERNS:
        if pattern.search(content):
            return True
    return False


def _extract_content_for_escalation(facts: dict) -> str:
    """从 facts 中提取用于升级检测的内容文本。"""
    parts = []
    for key in ("content", "full_prompt", "query", "url", "command"):
        val = facts.get(key, "")
        if val and isinstance(val, str):
            parts.append(val)
    return " ".join(parts)

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
        content_escalation: 是否启用内容升级检测（Loop 8）
    """
    enabled: bool = True
    allow_action_types: frozenset[str] = _DEFAULT_ALLOW_ACTION_TYPES
    allow_readonly_commands: frozenset[str] = _DEFAULT_READONLY_COMMANDS
    extra_predicates: list[Callable[[dict], bool]] = field(default_factory=list)
    content_escalation: bool = True


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
    2. **内容升级检测**（Loop 8）：即使 action_type 安全，内容有害意图 → False
    3. action_type 在 allow_action_types 中 → True
    4. action_type == "exec_command" 且命令匹配 allow_readonly_commands → True
    5. 任一 extra_predicate 返回 True → True
    6. 否则 → False
    """
    cfg = config or _DEFAULT_CONFIG

    if not cfg.enabled:
        return False

    action_type = facts.get("action_type", "")

    # Rule 2: 内容升级检测（Loop 8）
    # 即使操作类型安全，如果内容包含有害信号，路由到 Semantic Gate
    if cfg.content_escalation and action_type in cfg.allow_action_types:
        content = _extract_content_for_escalation(facts)
        if _has_escalation_signal(content):
            return False  # 路由到 Semantic Gate

    # Rule 3: 安全 action_type
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
