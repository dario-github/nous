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


# ── Loop 37: Harmful Domain Guard（Rule 4b 安全网） ─────────────────────────
# 目的：捕获 benign signal 无法覆盖的有害领域（毒品名+合成、武器+制造等）
# 设计：比 _ESCALATION_PATTERNS 更宽——escalation 检查具体犯罪行为，
#        domain guard 检查领域知识（物质名 + 操作动词的组合）
# 原则：只在 Rule 4b bypass 路径上使用，不影响正常的 trivial 判断

_HARMFUL_SUBSTANCE_NAMES = re.compile(
    r"\b(GHB|gamma.?hydroxybutyr|ketamine|fentanyl|methamphetamine|meth\b|MDMA|"
    r"ecstasy|LSD|lysergic|heroin|cocaine|crack\s+cocaine|psilocybin|DMT|"
    r"amphetamine|oxycodone|oxycontin|morphine\s+(?:synth|produc|extract)|"
    r"PCP|phencyclidine|cathinone|bath\s+salts|carfentanil)\b", re.I
)

_HARMFUL_DOMAIN_PATTERNS = [
    # 毒品合成/制造语境
    re.compile(r"(?:synth\w+|produc\w+|manufactur\w+|cook\w*)\s+.{0,40}(?:compound|substance|batch|purity|yield)", re.I),
    re.compile(r"(?:precursor|reagent|catalyst)\s+.{0,30}(?:method|ratio|protocol|route)", re.I),
    re.compile(r"(?:purity|potency)\s+.{0,10}(?:\d+\s*%|percent)", re.I),
    re.compile(r"(?:dosage|dose)\s+.{0,30}(?:recreational|dissociativ|psychoactiv|threshold|strong|lethal)", re.I),
    re.compile(r"(?:K-hole|k\.hole|trip\s+dose)", re.I),
    # 武器/爆炸物制造
    re.compile(r"(?:assembl\w+|build\w*|construct\w*)\s+.{0,30}(?:detonat|explosive|IED|incendiary)", re.I),
    re.compile(r"(?:3D\s*print|blueprint)\s+.{0,20}(?:gun|firearm|receiver|weapon)", re.I),
    re.compile(r"(?:nerve\s+agent|sarin|VX|ricin|anthrax)\s+.{0,20}(?:synth|produc|extract|cultiv)", re.I),
    # 反模式排除（合法语境）
    # - "purity of water" / "synthesis of research paper" 不应匹配
    # - 上方 patterns 已通过 domain-specific 词锚定，FP 风险低
]


def _has_harmful_domain_signal(content: str) -> bool:
    """检测有害领域信号（物质名 + 合成/操作语境）。

    用于 Rule 4b benign signal bypass 的安全网。
    Loop 37: 修复 ch-h26（GHB 合成伪装成庆祝公告）。
    """
    if not content or len(content) < 15:
        return False
    # 物质名直接匹配
    if _HARMFUL_SUBSTANCE_NAMES.search(content):
        return True
    # 领域模式匹配
    return any(p.search(content) for p in _HARMFUL_DOMAIN_PATTERNS)


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


# ── Loop 12: 结构化安全模式检测 ───────────────────────────────────────────

def _is_safe_encryption_sharing(facts: dict) -> bool:
    """检测良性加密共享模式：加密文件 + 发送解密指令给同组织成员。

    满足条件：
    1. 存在加密相关操作
    2. 所有收件人属于同一组织（same domain）
    3. 无勒索信号（ransom/payment/victim/BTC）

    这修复了 22-3 val FP：内部加密被误判为勒索软件。
    """
    prompt = facts.get("full_prompt", "") or facts.get("content", "")
    if not prompt:
        return False

    # 必须有加密上下文
    import re
    if not re.search(r'encrypt', prompt, re.I):
        return False

    # 必须有同域名收件人（组织内部）
    if not facts.get("recipients_same_domain"):
        return False

    # 必须无勒索信号
    if facts.get("has_ransom_signal", False):
        return False

    return True


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
        # Rule 3a: 已知只读命令
        if cmd:
            if cmd in cfg.allow_readonly_commands:
                return True
            for safe_cmd in cfg.allow_readonly_commands:
                if cmd.startswith(safe_cmd + " "):
                    return True
        # Rule 3b (Loop 12): 良性加密共享模式
        if _is_safe_encryption_sharing(facts):
            return True
        return False

    # Rule 4: send_message 同组织通信（Loop 12）
    if action_type == "send_message":
        if facts.get("recipients_same_domain") and not facts.get("has_ransom_signal", False):
            content = _extract_content_for_escalation(facts)
            if not _has_escalation_signal(content):
                return True
        # Fall through to Rule 4b (benign signal bypass) instead of returning False

    # Rule 4b (Loop 35): 强良性结构信号绕过
    # 当 fact_extractor 检测到明确的良性意图信号（已含反模式排除），
    # 且无内容升级信号 + 无有害领域信号时，视为 trivially benign，跳过 semantic gate。
    # 修复 52-2 FP：celebration_signal 正确触发但 DeepSeek-V3.1 仍 block@≥0.90。
    #
    # Loop 36 安全修复：移除 has_factual_correction_signal
    # Loop 37 安全修复：增加 harmful domain guard（ch-h26 GHB celebration bypass）
    # 原因：benign signal 的 anti-pattern 无法穷举所有有害领域，
    # 需要一个统一的 domain-level 安全网阻止 "毒品合成庆祝"/"武器制造里程碑" 类 bypass。
    _STRONG_BENIGN_SIGNALS = (
        "has_celebration_signal",       # 真实成就/庆祝公告（排除 rumor/lie/fake）
        "has_own_submission_signal",    # 帮人提交自己的作业（排除外部代码获取）
        "has_advocacy_signal",          # 公益/倡导内容
        # has_factual_correction_signal REMOVED (Loop 36): bypass rate 75% on challenge set
    )
    benign_signal_active = any(facts.get(sig, False) for sig in _STRONG_BENIGN_SIGNALS)
    if benign_signal_active:
        content = _extract_content_for_escalation(facts)
        if not _has_escalation_signal(content) and not _has_harmful_domain_signal(content):
            return True  # 良性信号 + 无有害内容 + 无有害领域 → trivially benign

    # Rule 5: 自定义谓词
    for predicate in cfg.extra_predicates:
        try:
            if predicate(facts):
                return True
        except Exception:
            # 谓词异常 → 保守处理，不视为 trivial
            pass

    # Rule 5: 默认不安全
    return False
