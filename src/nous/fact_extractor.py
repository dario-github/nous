"""Nous — Fact Extractor (M2.3)

从 tool_call JSON 提取结构化事实，供约束匹配使用。

支持提取的事实维度：
  - action_type: 操作类型（delete_file / write_file / web_search / open_url 等）
  - url: URL 字符串（若有）
  - url_has_social_pattern: 是否匹配社媒域名
  - estimated_lines: 写入内容的估算行数
  - search_lang: 搜索语言参数
  - output_target: 输出目标（discord / slack / telegram 等）
  - content_is_structured: 输出内容是否为结构化（表格/列表/多字段）
  - content_type: 内容类型（text / table / list / rich）

参考：ontology-gate-extension/src/fact-extractor.ts 逻辑迁移。
"""
import re
from typing import Optional

# 社媒域名模式（与 T5.yaml metadata.social_patterns 保持一致）
_SOCIAL_PATTERNS = [
    "twitter.com",
    "x.com",
    "instagram.com",
    "douyin.com",
    "xhslink.com",
    "xiaohongshu.com",
    "weibo.com",
    "tiktok.com",
    "facebook.com",
    "youtube.com",   # 视频平台按 T5 逻辑也算
]


def _is_social_url(url: str) -> bool:
    """检查 URL 是否包含社媒域名"""
    if not url:
        return False
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in _SOCIAL_PATTERNS)


# 破坏性命令模式（对齐 TS engine 的 DESTRUCTIVE_CMDS + 零 FP 代价 FN 修复）
# 对齐原则：只加 FP_risk=0 的模式（即 trigger_log 中 TS 从未 allow 过的命令前缀）
# 分析依据：对 trigger_log 全量数据统计每个新增模式的 FN_fix 和 FP_risk
_DESTRUCTIVE_CMD_PATTERNS = [
    # ── 文件删除 ──
    r"\brm\s+-rf\b",            # rm -rf（递归强制删除）
    r"\brm\s+--no-preserve\b",  # rm --no-preserve-root
    r"\brmdir\b",               # rmdir
    r"\bunlink\b",              # unlink

    # ── Git 远程推送 ──
    r"\bgit\s+push\b",          # git push（推送远程）— git commit 不拦截

    # ── 包/DB 发布 ──
    r"\bnpm\s+publish\b",
    r"\bDROP\s+TABLE\b",
    r"\bDELETE\s+FROM\b",

    # ── 系统破坏 ──
    r"\bformat\b",
    r"\bdd\s+if=",
    r"\btruncate\b",

    # （ssh 不拦截——nodes.run 常规使用）

    # （cat >> 不拦截——日常 memory 写入用）

    # ── Git 远程鉴权环境变量 ──
    r"\bGIT_SSH_",              # GIT_SSH_COMMAND=...

    # ── 绕过门控的尝试模式 ──
    r"\bPRE_AUTHORIZED\b",      # PRE_AUTHORIZED=true
    r"\bEXPECT_IRREVER",        # EXPECT_IRREVERSIBLE=true
]


def _is_destructive_command(cmd: str) -> bool:
    """检查命令是否匹配破坏性模式"""
    if not cmd:
        return False
    return any(re.search(p, cmd, re.IGNORECASE) for p in _DESTRUCTIVE_CMD_PATTERNS)


# ── 结构化良性信号提取（Loop 12: Phase 1 FPR 修复） ──────────────────

# 归属/引用短语：表示内容分享带有来源标注
_ATTRIBUTION_PATTERNS = [
    re.compile(r"with\s+(the\s+)?link\s+(in|to)", re.I),
    re.compile(r"with\s+(proper\s+)?credit", re.I),
    re.compile(r"with\s+(the\s+)?attribution", re.I),
    re.compile(r"(in|add)\s+(the\s+)?description[/,]?\s*(title)?", re.I),
    re.compile(r"give\s+credit", re.I),
    re.compile(r"cite\s+(the\s+)?source", re.I),
    re.compile(r"link\s+(back\s+)?to\s+(the\s+)?original", re.I),
    re.compile(r"include\s+(a\s+)?link", re.I),
    re.compile(r"reference\s+(the\s+)?original", re.I),
]

# 勒索信号：加密 + 这些 = ransomware
_RANSOM_SIGNALS = [
    re.compile(r"\bransom\b", re.I),
    re.compile(r"\bdemand\s+(a\s+)?payment\b", re.I),
    re.compile(r"\bpay\s+\S+\s+\$", re.I),
    re.compile(r"\bbitcoin\s+wallet\b", re.I),
    re.compile(r"\bbtc\b", re.I),
    re.compile(r"\bvictim\b", re.I),
    re.compile(r"\bdecrypt\b.*\bfor\s+(a\s+)?ransom\b", re.I),
]


def _detect_attribution_signal(text: str) -> bool:
    """检测文本中是否包含归属/引用信号（link to original, give credit 等）。

    用于区分 "盗用发布"（无归属→harmful）和 "带来源分享"（有归属→benign）。
    """
    if not text or len(text) < 10:
        return False
    return any(p.search(text) for p in _ATTRIBUTION_PATTERNS)


def _detect_same_domain_recipients(text: str) -> Optional[str]:
    """检测文本中所有 email 地址是否属于同一域名。

    多个 email 同一域名 → 组织内部通信（同事/团队），非攻击目标。
    返回共同域名字符串或 None。
    """
    if not text:
        return None
    emails = re.findall(r'[\w.+-]+@([\w.-]+\.[\w]+)', text)
    if len(emails) < 2:
        return None
    domains = set(d.lower() for d in emails)
    if len(domains) == 1:
        return domains.pop()
    return None


def _has_ransom_signal(text: str) -> bool:
    """检测文本中是否包含勒索信号（ransom, demand payment, Bitcoin wallet 等）。"""
    if not text or len(text) < 10:
        return False
    return any(p.search(text) for p in _RANSOM_SIGNALS)


# ── Loop 16: 学术抄袭/外部提交信号 ───────────────────────────────────────

# 外部来源获取模式
_EXTERNAL_SOURCE_PATTERNS = [
    re.compile(r"find\s+.{0,40}(on\s+the\s+web|online|from\s+the\s+(web|internet))", re.I),
    re.compile(r"(search|look)\s+(for|up)\s+.{0,40}(implementation|code|solution|answer)", re.I),
    re.compile(r"download\s+.{0,30}(code|implementation|solution|script)", re.I),
    re.compile(r"find\s+a\s+(reliable|good|working)\s+.{0,20}implementation", re.I),
    re.compile(r"get\s+.{0,20}(code|implementation)\s+.{0,20}(from|on)\s+(the\s+)?(web|internet|online)", re.I),
]

# 作业提交模式
_ASSIGNMENT_SUBMIT_PATTERNS = [
    re.compile(r"submit\s+.{0,30}(assignment|homework|coursework|project)", re.I),
    re.compile(r"submit\s+(it|this|the\s+code)\s+(to|for|as)", re.I),
    re.compile(r"(assignment|homework|coursework)\s+.{0,20}submit", re.I),
    re.compile(r"turn\s+in\s+.{0,20}(assignment|homework)", re.I),
    re.compile(r"submit_assignment", re.I),
]

# 排除模式：找某人自己的作业（benign）
_OWN_WORK_PATTERNS = [
    re.compile(r"find\s+.{0,20}(personal\s+page|own\s+(page|work|assignment))", re.I),
    re.compile(r"(his|her|their)\s+own\s+(assignment|work|homework)", re.I),
    re.compile(r"find\s+.{0,20}page\s+.{0,30}assignment\s+link", re.I),
    re.compile(r"on\s+behalf\s+of", re.I),
]


def _has_academic_plagiarism_signal(text: str) -> bool:
    """检测学术抄袭信号：从外部来源获取内容 + 提交为作业/homework。

    关键区分：
    - harmful: "find BST code on the web" + "submit as homework" → 外部代码冒充自己作业
    - benign: "find Russel Brown's page" + "submit his assignment" → 帮人提交自己的作业

    返回 True 仅当同时存在外部来源获取 + 作业提交模式，且不匹配"自己作业"排除模式。
    Loop 16: Phase 2 Fraud FN 修复。
    """
    if not text or len(text) < 20:
        return False

    # Check exclusion first: if it's about finding someone's OWN work, not plagiarism
    if any(p.search(text) for p in _OWN_WORK_PATTERNS):
        return False

    has_external = any(p.search(text) for p in _EXTERNAL_SOURCE_PATTERNS)
    has_submit = any(p.search(text) for p in _ASSIGNMENT_SUBMIT_PATTERNS)

    return has_external and has_submit


# ── Loop 17: 庆祝/成就公告信号（Phase 2 Disinformation FP 修复） ────────

_CELEBRATION_PATTERNS = [
    re.compile(r"announce\s+.{0,60}(achiev|grade|award|milestone|promoti|won|receiv|succeed|accomplish)", re.I),
    re.compile(r"celebrat\w*\s+.{0,40}(achiev|grade|award|success|promoti|accomplish)", re.I),
    re.compile(r"(highest|top|best)\s+grade", re.I),
    re.compile(r"highlight\w*\s+.{0,20}(achiev|accomplish|success)", re.I),
    re.compile(r"congrat\w*\s+.{0,40}(on|for)\s+.{0,40}(achiev|grade|award|promoti)", re.I),
]

# 排除模式：虚假声称/恶意散布
_ANTI_CELEBRATION_PATTERNS = [
    re.compile(r"(rumor|lie|fake|fabricat|false|slept|affair|cheat|scandal|defam)", re.I),
    re.compile(r"spread\s+(rumor|lie|false)", re.I),
    re.compile(r"(make\s+up|invent)\s+.{0,20}(stor|claim|accusat)", re.I),
]


def _has_celebration_signal(text: str) -> bool:
    """检测庆祝/成就公告信号。

    关键区分：
    - benign: "Announce that Anna received the highest grade" → 真实成就的公告
    - harmful: "Spread rumors about Anna sleeping with..." → 虚假信息散布

    返回 True 仅当存在庆祝模式且不包含反模式。
    Loop 17: Phase 2 Disinformation FP 修复。
    """
    if not text or len(text) < 20:
        return False

    # Anti-patterns override: if rumor/lie/fabrication detected, not a celebration
    if any(p.search(text) for p in _ANTI_CELEBRATION_PATTERNS):
        return False

    return any(p.search(text) for p in _CELEBRATION_PATTERNS)


# ── Loop 17: 代为提交自己作业信号（Phase 2 Fraud FP 修复） ────────

_OWN_SUBMISSION_PATTERNS = [
    # "find [person]'s personal page" + "submit ... using [person]'s name"
    re.compile(r"(personal\s+page|own\s+page)\s+of\s+\w+", re.I),
    re.compile(r"find\s+.{0,30}page\s+.{0,30}(assignment|homework)\s+link", re.I),
    re.compile(r"submit\s+.{0,20}(assignment|homework)\s+using\s+\w+", re.I),
    re.compile(r"on\s+behalf\s+of\s+\w+", re.I),
    re.compile(r"submit\s+.{0,10}(his|her|their)\s+(assignment|homework|work)", re.I),
]

# 反模式：从网上找代码（这不是帮人提交自己的作业）
_ANTI_OWN_SUBMISSION_PATTERNS = [
    re.compile(r"find\s+.{0,30}(implementation|code|solution)\s+.{0,20}(on|from)\s+(the\s+)?(web|internet|online)", re.I),
    re.compile(r"(don't|do\s+not)\s+hallucinate", re.I),
    re.compile(r"I\s+need\s+.{0,20}(code|implementation|solution)", re.I),
]


def _has_own_submission_signal(text: str) -> bool:
    """检测代为提交自己作业信号。

    关键区分：
    - benign: "Find Russel Brown's personal page + submit using his name" → 帮人提交自己的作业
    - harmful: "Find code on the web + submit as homework" → 学术抄袭

    返回 True 仅当存在代提交模式且不包含反模式（外部代码获取）。
    Loop 17: Phase 2 Fraud FP 修复。
    """
    if not text or len(text) < 20:
        return False

    # Anti-patterns: if looking for code online, not own submission
    if any(p.search(text) for p in _ANTI_OWN_SUBMISSION_PATTERNS):
        return False

    # Need at least 2 own-submission patterns to fire
    matches = sum(1 for p in _OWN_SUBMISSION_PATTERNS if p.search(text))
    return matches >= 2


def _extract_url(tool_call: dict) -> Optional[str]:
    """从 tool_call 提取 URL（多层查找）"""
    # 直接字段
    for key in ("url", "link", "href"):
        val = tool_call.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val

    # params 子字典
    params = tool_call.get("params", {})
    if isinstance(params, dict):
        for key in ("url", "link", "href"):
            val = params.get(key)
            if isinstance(val, str) and val.startswith("http"):
                return val

    return None


def _estimate_lines(tool_call: dict) -> int:
    """
    估算写入内容行数。
    - 优先使用显式 estimated_lines 字段
    - 其次从 content/text 字段计数换行符
    - 默认 0
    """
    # 显式字段
    explicit = tool_call.get("estimated_lines")
    if isinstance(explicit, (int, float)):
        return int(explicit)

    params = tool_call.get("params", {})
    if isinstance(params, dict):
        explicit = params.get("estimated_lines")
        if isinstance(explicit, (int, float)):
            return int(explicit)

    # 从内容计算
    for key in ("content", "text", "body", "data"):
        content = tool_call.get(key) or (
            params.get(key) if isinstance(params, dict) else None
        )
        if isinstance(content, str) and content:
            return content.count("\n") + 1

    return 0


def _extract_action_type(tool_call: dict) -> str:
    """
    推断 action_type：
    1. 显式 action_type 字段
    2. 根据 tool_name 推断
    3. 根据 action 字段
    """
    # 显式字段
    at = tool_call.get("action_type")
    if isinstance(at, str) and at:
        return at

    tool_name = (tool_call.get("tool_name") or tool_call.get("name") or "").lower()
    action = (tool_call.get("action") or "").lower()

    # write / edit → write_file
    if tool_name in ("write", "edit") or action in ("write", "edit"):
        return "write_file"

    # read → read_file
    if tool_name == "read" or action == "read":
        return "read_file"

    # exec → 检查命令内容分级（对齐 TS engine 的 DESTRUCTIVE_CMDS）
    if tool_name == "exec" or action == "exec":
        cmd = str(tool_call.get("command") or tool_call.get("params", {}).get("command", ""))
        if _is_destructive_command(cmd):
            return "exec_destructive"
        return "exec_command"  # 普通 exec，不触发 T3

    # web_fetch → open_url
    if tool_name == "web_fetch" or action in ("fetch", "open"):
        return "open_url"

    # web_search → web_search
    if tool_name == "web_search" or action == "search":
        return "web_search"

    # message → 按 action 分级
    if tool_name == "message":
        msg_action = str(tool_call.get("params", {}).get("action", action)).lower()
        if msg_action == "delete":
            return "delete_message"
        if msg_action == "send":
            return "send_message"  # send_message 不在 T3 列表里
        return f"message_{msg_action}" if msg_action else "send_message"

    # browser delete / rm → delete_file
    cmd = str(tool_call.get("command") or tool_call.get("params", {}).get("command", ""))
    if any(kw in cmd for kw in ("rm ", "rmdir", "unlink", "delete")):
        return "delete_file"

    return action or tool_name or "unknown"


def _extract_search_lang(tool_call: dict) -> Optional[str]:
    """提取 search_lang 参数"""
    # 直接字段
    sl = tool_call.get("search_lang")
    if isinstance(sl, str):
        return sl

    params = tool_call.get("params", {})
    if isinstance(params, dict):
        sl = params.get("search_lang")
        if isinstance(sl, str):
            return sl

    return None


def _extract_output_target(tool_call: dict) -> Optional[str]:
    """
    提取输出目标（discord / slack / telegram 等）。
    查找 channel / target / output_target 字段。
    """
    for key in ("output_target", "target", "channel"):
        val = tool_call.get(key)
        if isinstance(val, str) and val:
            return val.lower()

    params = tool_call.get("params", {})
    if isinstance(params, dict):
        for key in ("output_target", "target", "channel"):
            val = params.get(key)
            if isinstance(val, str) and val:
                return val.lower()

    return None


def _detect_structured_content(tool_call: dict) -> bool:
    """
    判断内容是否为结构化输出（表格 / 多字段卡片 / 列表组合）。
    简单启发式：
    - 包含 Markdown 表格（| col |）
    - 内容有 components / blocks 字段
    - 显式 content_is_structured=true
    - 内容行数 >5 且包含多个 ** 加粗标题
    """
    # 显式标记
    if tool_call.get("content_is_structured") is True:
        return True

    params = tool_call.get("params", {})
    if isinstance(params, dict):
        if params.get("content_is_structured") is True:
            return True
        # Discord Components v2 字段
        if "components" in params or "blocks" in params:
            return True

    if "components" in tool_call or "blocks" in tool_call:
        return True

    # 检查文本内容
    for key in ("message", "content", "text", "body"):
        text = tool_call.get(key) or (
            params.get(key) if isinstance(params, dict) else None
        )
        if isinstance(text, str):
            # Markdown 表格特征
            if re.search(r"\|.+\|.+\|", text):
                return True
            # 多个加粗标题（结构化报告）
            bold_count = len(re.findall(r"\*\*.+?\*\*", text))
            lines = text.split("\n")
            if bold_count >= 3 and len(lines) >= 5:
                return True

    return False


def _detect_content_type(tool_call: dict) -> str:
    """
    检测内容类型：table / list / rich / text
    """
    if tool_call.get("content_is_structured"):
        return "rich"

    params = tool_call.get("params", {})
    if isinstance(params, dict) and ("components" in params or "blocks" in params):
        return "rich"

    for key in ("message", "content", "text", "body"):
        text = tool_call.get(key) or (
            params.get(key) if isinstance(params, dict) else None
        )
        if isinstance(text, str):
            if re.search(r"\|.+\|.+\|", text):
                return "table"
            if re.search(r"^[\s]*[-*•]\s", text, re.MULTILINE):
                return "list"
            lines = text.split("\n")
            if len(lines) == 1:
                return "text"
            return "rich" if len(lines) > 5 else "text"

    return "text"


# ── 主函数 ────────────────────────────────────────────────────────────────


def extract_facts(tool_call: dict) -> dict:
    """
    从 tool_call JSON 提取结构化事实。

    输入：tool_call dict，包含 tool_name/action/params 等
    输出：facts dict，包含所有约束匹配所需的维度

    约束匹配维度：
      action_type:            操作类型
      url:                    URL（若有）
      url_has_social_pattern: 是否社媒 URL (bool)
      estimated_lines:        写入行数估算
      search_lang:            搜索语言（若有）
      output_target:          输出目标（discord 等）
      content_is_structured:  内容是否结构化 (bool)
      content_type:           内容类型
      content:                原始内容文本（用于 semantic gate + 内容升级检测）
      full_prompt:            完整 prompt（用于 semantic gate + 内容升级检测）
      query:                  搜索查询（用于内容升级检测）
      command:                命令文本（用于 triviality filter 命令匹配）
    """
    url = _extract_url(tool_call)
    params = tool_call.get("params") or {}

    facts: dict = {
        "action_type": _extract_action_type(tool_call),
        "url": url,
        "url_has_social_pattern": _is_social_url(url or ""),
        "estimated_lines": _estimate_lines(tool_call),
        "search_lang": _extract_search_lang(tool_call),
        "output_target": _extract_output_target(tool_call),
        "content_is_structured": _detect_structured_content(tool_call),
        "content_type": _detect_content_type(tool_call),
    }

    # Loop 8: 提取内容字段用于内容升级检测和 semantic gate
    for key in ("content", "full_prompt", "query", "command"):
        val = params.get(key) or tool_call.get(key, "")
        if val and isinstance(val, str):
            facts[key] = val

    # Loop 12: 结构化良性信号（Phase 1 FPR 修复）
    # 从 full_prompt/content 提取，用于 Datalog 路由 + triviality filter
    prompt_text = facts.get("full_prompt", "") or facts.get("content", "")
    facts["has_attribution_signal"] = _detect_attribution_signal(prompt_text)
    facts["recipients_same_domain"] = _detect_same_domain_recipients(prompt_text)
    facts["has_ransom_signal"] = _has_ransom_signal(prompt_text)

    # Loop 16: 学术抄袭信号
    facts["has_academic_plagiarism_signal"] = _has_academic_plagiarism_signal(prompt_text)

    # Loop 17: 庆祝/成就公告信号
    facts["has_celebration_signal"] = _has_celebration_signal(prompt_text)

    # Loop 17: 代为提交自己作业信号
    facts["has_own_submission_signal"] = _has_own_submission_signal(prompt_text)

    return facts
