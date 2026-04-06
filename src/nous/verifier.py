"""Nous — Post-Gate Verifier (Layer 4)

独立于保安（gate）的审计员。不依赖 gate 自报盲区，
用确定性规则独立推导 gate 不可能看到什么，然后和 gate 的判断对账。

设计原则：
- 纯确定性规则，不调 LLM
- FAIL_OPEN: 任何异常 → 不改变 verdict
- 每条规则独立、可审计、可单独开关
- 红色 flag → 强制升级为 confirm（除非已经是 block）
- 黄色 flag → 累积超过阈值时升级

五条审计规则（v1，2026-04-06 Dario 确认）：
  V1: 命令要运行文件，但保安没看过文件内容 → 🔴
  V2: 用户说的是"按照某处的指示做" → 🔴
  V3: 先读了文件，然后紧接着运行命令 → 🟡
  V4: 命令的行为模式（下载后运行 / 往外发数据）→ 🟡
  V5: 命令本身就是高危操作 → 🟢（已有，保留）
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("nous.verifier")


# ── 数据结构 ──────────────────────────────────────────────────────────────


@dataclass
class VerifierFlag:
    """审计员发现的一个问题。"""
    rule_id: str           # V1, V2, V3, V4, V5
    severity: str          # "red" | "yellow" | "green"
    reason: str            # 人类可读的原因
    evidence: str          # 触发的具体证据


@dataclass
class VerifierResult:
    """审计结果。"""
    flags: list[VerifierFlag] = field(default_factory=list)
    recommendation: str = "pass"   # "pass" | "upgrade_to_confirm" | "upgrade_to_block"
    original_verdict: str = ""

    @property
    def red_count(self) -> int:
        return sum(1 for f in self.flags if f.severity == "red")

    @property
    def yellow_count(self) -> int:
        return sum(1 for f in self.flags if f.severity == "yellow")

    def to_dict(self) -> dict:
        return {
            "flags": [
                {"rule_id": f.rule_id, "severity": f.severity,
                 "reason": f.reason, "evidence": f.evidence}
                for f in self.flags
            ],
            "recommendation": self.recommendation,
            "red_count": self.red_count,
            "yellow_count": self.yellow_count,
        }


@dataclass
class VerifierConfig:
    """审计员配置。"""
    enabled: bool = True
    yellow_threshold: int = 2       # 黄色累计达到此数 → 升级
    v1_enabled: bool = True         # 运行文件但没看内容
    v2_enabled: bool = True         # "按照某处的指示做"
    v3_enabled: bool = True         # 读文件后执行命令
    v4_enabled: bool = True         # 行为模式（下载后运行/往外发数据）
    v5_enabled: bool = True         # 高危操作（已有逻辑，补充检查）


# ── 规则实现 ──────────────────────────────────────────────────────────────

# 文件执行模式：bash/sh/python/node/ruby/perl + 文件路径
_FILE_EXEC_PATTERN = re.compile(
    r'\b(?:bash|sh|zsh|python3?|node|ruby|perl)\s+'
    r'[~./][\w/\-.]+'
)

# 从外部下载后执行的模式
_DOWNLOAD_EXEC_PATTERNS = [
    re.compile(r'curl\s+\S+\s*\|\s*(?:bash|sh|python)', re.IGNORECASE),
    re.compile(r'wget\s+\S+\s*&&\s*(?:bash|sh|python|chmod)', re.IGNORECASE),
    re.compile(r'curl\s+.*-o\s+\S+.*&&\s*(?:bash|sh|python|chmod|\./)', re.IGNORECASE),
]

# 往外发数据的模式
_DATA_EXFIL_PATTERNS = [
    re.compile(r'curl\s+.*-X\s*POST\s+https?://', re.IGNORECASE),
    re.compile(r'curl\s+.*-d\s+.*https?://', re.IGNORECASE),
    re.compile(r'curl\s+.*--data\s+.*https?://', re.IGNORECASE),
    re.compile(r'wget\s+.*--post-data', re.IGNORECASE),
    re.compile(r'nc\s+\S+\s+\d+\s*<', re.IGNORECASE),  # netcat exfil
]

# "按照某处指示做"的语义模式
_DELEGATED_INSTRUCTION_PATTERNS = [
    re.compile(r'follow\s+(?:the\s+)?instructions?\s+(?:in|from)', re.IGNORECASE),
    re.compile(r'execute\s+(?:the\s+)?(?:steps?|commands?|instructions?)\s+(?:in|from)', re.IGNORECASE),
    re.compile(r'run\s+(?:the\s+)?(?:steps?|commands?|script)\s+(?:in|from|described)', re.IGNORECASE),
    re.compile(r'按照.*(?:邮件|文档|工单|说明|指示|步骤).*(?:操作|执行|做)', re.IGNORECASE),
    re.compile(r'根据.*(?:邮件|文档|工单).*(?:操作|执行)', re.IGNORECASE),
]

# 高危操作模式
_HIGH_RISK_PATTERNS = [
    re.compile(r'rm\s+-rf?\s+/', re.IGNORECASE),
    re.compile(r'chmod\s+777', re.IGNORECASE),
    re.compile(r'>>?\s*~/\.ssh/authorized_keys', re.IGNORECASE),
    re.compile(r'passwd\b', re.IGNORECASE),
    re.compile(r'DROP\s+(?:TABLE|DATABASE)', re.IGNORECASE),
    re.compile(r'TRUNCATE\s+TABLE', re.IGNORECASE),
]


def _check_v1_file_exec_blind(tool_call: dict, facts: dict) -> Optional[VerifierFlag]:
    """V1: 命令要运行文件，但 gate 没看过文件内容。

    触发条件：bash/python/etc + 文件路径
    gate 能看到命令字符串，但看不到文件内容。
    """
    # 检查 tool_call 参数中的 bash 命令
    bash_cmd = _extract_bash_command(tool_call)
    if not bash_cmd:
        return None

    match = _FILE_EXEC_PATTERN.search(bash_cmd)
    if match:
        return VerifierFlag(
            rule_id="V1",
            severity="red",
            reason="命令要运行一个文件，但保安没看过文件内容",
            evidence=match.group(),
        )
    return None


def _check_v2_delegated_instructions(tool_call: dict, facts: dict) -> Optional[VerifierFlag]:
    """V2: 用户说的是"按照某处的指示做"。

    触发条件：prompt 中出现 "follow instructions in/from [file/email/ticket]"
    真正的指令不是用户给的，是文件给的 — gate 不知道文件里写了什么。
    """
    prompt = facts.get("full_prompt") or facts.get("content") or facts.get("message") or ""
    if not prompt:
        return None

    for pattern in _DELEGATED_INSTRUCTION_PATTERNS:
        match = pattern.search(prompt)
        if match:
            return VerifierFlag(
                rule_id="V2",
                severity="red",
                reason="用户说的是按照某处的指示做，真正的指令不是用户给的",
                evidence=match.group(),
            )
    return None


def _check_v3_read_then_exec(tool_call: dict, facts: dict) -> Optional[VerifierFlag]:
    """V3: 先读了文件，然后紧接着运行命令。

    触发条件：tool_calls 链中，前面是 read_file，后面是 bash，
    且 bash 参数引用了读取的路径。
    """
    # 这需要 session_context（先前工具调用历史）
    # 当前在 tool_call 本身检查：如果单个 tool_call 包含多步操作
    tool_calls = tool_call.get("tool_calls") or []
    if not tool_calls:
        # 检查单个 tool_call 是否是 bash，且 facts 中有 read_file 记录
        return None

    read_paths: set[str] = set()
    for tc in tool_calls:
        action = tc.get("action", "")
        params = tc.get("params", {})

        if action in ("read_file", "read"):
            path = params.get("path", "")
            if path:
                read_paths.add(path)

        if action in ("bash", "exec", "shell"):
            cmd = params.get("command", "") or params.get("cmd", "")
            # 检查 bash 命令是否引用了之前读取的文件路径
            for rp in read_paths:
                # 路径或文件名出现在命令中
                if rp in cmd or rp.split("/")[-1] in cmd:
                    return VerifierFlag(
                        rule_id="V3",
                        severity="yellow",
                        reason="先读了文件，然后紧接着用那个文件运行命令",
                        evidence=f"read: {rp} → exec: {cmd[:100]}",
                    )

    return None


def _check_v4_behavior_pattern(tool_call: dict, facts: dict) -> Optional[VerifierFlag]:
    """V4: 命令的行为模式 — 下载后运行 / 往外发数据。

    不看网址是什么（白名单不靠谱），看行为本身。
    """
    bash_cmd = _extract_bash_command(tool_call)
    if not bash_cmd:
        return None

    # 下载后运行
    for pattern in _DOWNLOAD_EXEC_PATTERNS:
        match = pattern.search(bash_cmd)
        if match:
            return VerifierFlag(
                rule_id="V4",
                severity="yellow",
                reason="从网上下载东西然后直接运行",
                evidence=match.group(),
            )

    # 往外发数据
    for pattern in _DATA_EXFIL_PATTERNS:
        match = pattern.search(bash_cmd)
        if match:
            return VerifierFlag(
                rule_id="V4",
                severity="yellow",
                reason="把数据往外发",
                evidence=match.group(),
            )

    return None


def _check_v5_high_risk_ops(tool_call: dict, facts: dict) -> Optional[VerifierFlag]:
    """V5: 命令本身就是高危操作。

    这条和现有逻辑有重叠，作为兜底补充。
    """
    bash_cmd = _extract_bash_command(tool_call)
    if not bash_cmd:
        return None

    for pattern in _HIGH_RISK_PATTERNS:
        match = pattern.search(bash_cmd)
        if match:
            return VerifierFlag(
                rule_id="V5",
                severity="green",
                reason="命令本身就是高危操作",
                evidence=match.group(),
            )

    return None


# ── 辅助函数 ──────────────────────────────────────────────────────────────


def _extract_bash_command(tool_call: dict) -> str:
    """从 tool_call 中提取 bash 命令字符串。

    支持多种格式：
    - {"params": {"command": "..."}}
    - {"tool_calls": [{"action": "bash", "params": {"command": "..."}}]}
    - {"arguments": {"command": "..."}}
    """
    # 直接参数
    params = tool_call.get("params") or tool_call.get("arguments") or {}
    cmd = params.get("command") or params.get("cmd") or ""
    if cmd:
        return cmd

    # 嵌套 tool_calls
    tool_calls = tool_call.get("tool_calls") or []
    commands = []
    for tc in tool_calls:
        action = tc.get("action", "")
        if action in ("bash", "exec", "shell"):
            p = tc.get("params", {})
            c = p.get("command", "") or p.get("cmd", "")
            if c:
                commands.append(c)

    return " && ".join(commands)


# ── 主 API ────────────────────────────────────────────────────────────────


def verify(
    tool_call: dict,
    facts: dict,
    gate_verdict: str,
    config: Optional[VerifierConfig] = None,
) -> VerifierResult:
    """运行审计员检查。

    Args:
        tool_call:     工具调用 dict
        facts:         提取的事实
        gate_verdict:  保安的裁决（"allow" | "block" | "confirm"）
        config:        审计员配置（可选）

    Returns:
        VerifierResult，包含 flags 列表和建议。

    FAIL_OPEN: 任何异常 → 返回空 VerifierResult（不影响 verdict）。
    """
    cfg = config or VerifierConfig()

    if not cfg.enabled:
        return VerifierResult(original_verdict=gate_verdict)

    result = VerifierResult(original_verdict=gate_verdict)

    try:
        # 只有 gate 说 allow 时才需要审计
        # block 的不需要审计（已经拦了）
        # confirm 的也不需要（已经要确认了）
        if gate_verdict != "allow":
            return result

        # 逐条运行审计规则
        checks = []
        if cfg.v1_enabled:
            checks.append(_check_v1_file_exec_blind)
        if cfg.v2_enabled:
            checks.append(_check_v2_delegated_instructions)
        if cfg.v3_enabled:
            checks.append(_check_v3_read_then_exec)
        if cfg.v4_enabled:
            checks.append(_check_v4_behavior_pattern)
        if cfg.v5_enabled:
            checks.append(_check_v5_high_risk_ops)

        for check_fn in checks:
            try:
                flag = check_fn(tool_call, facts)
                if flag is not None:
                    result.flags.append(flag)
            except Exception as e:
                logger.debug("Verifier check %s failed (non-fatal): %s",
                             check_fn.__name__, e)

        # 决定建议
        if result.red_count > 0:
            result.recommendation = "upgrade_to_confirm"
        elif result.yellow_count >= cfg.yellow_threshold:
            result.recommendation = "upgrade_to_confirm"
        else:
            result.recommendation = "pass"

        return result

    except Exception as e:
        logger.warning("Verifier failed (FAIL_OPEN): %s", e)
        return VerifierResult(original_verdict=gate_verdict)


def apply_verifier_result(
    current_verdict: "Verdict",
    verifier_result: VerifierResult,
) -> "Verdict":
    """根据审计结果修改 verdict。

    规则：
    - recommendation == "pass" → 不改变
    - recommendation == "upgrade_to_confirm" + 当前 allow → 升级为 confirm
    - recommendation == "upgrade_to_block" + 当前 allow/confirm → 升级为 block
    - 当前已经是 block → 不降级
    """
    from nous.verdict import Verdict

    if verifier_result.recommendation == "pass":
        return current_verdict

    if current_verdict.action == "block":
        return current_verdict  # 不降级

    if verifier_result.recommendation == "upgrade_to_confirm":
        if current_verdict.action == "allow":
            flags_summary = "; ".join(
                f"[{f.rule_id}/{f.severity}] {f.reason}"
                for f in verifier_result.flags
            )
            return Verdict(
                action="confirm",
                rule_id=f"{current_verdict.rule_id}+verifier",
                reason=f"[verifier override] {flags_summary}",
                all_matched=current_verdict.all_matched,
            )
        return current_verdict

    if verifier_result.recommendation == "upgrade_to_block":
        flags_summary = "; ".join(
            f"[{f.rule_id}/{f.severity}] {f.reason}"
            for f in verifier_result.flags
        )
        return Verdict(
            action="block",
            rule_id=f"{current_verdict.rule_id}+verifier",
            reason=f"[verifier block] {flags_summary}",
            all_matched=current_verdict.all_matched,
        )

    return current_verdict
