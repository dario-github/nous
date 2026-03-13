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


# 破坏性命令模式（对齐 TS engine 的 DESTRUCTIVE_CMDS）
_DESTRUCTIVE_CMD_PATTERNS = [
    r"\brm\s+-rf?\b",
    r"\brmdir\b",
    r"\bgit\s+push\b",
    r"\bnpm\s+publish\b",
    r"\bDROP\s+TABLE\b",
    r"\bDELETE\s+FROM\b",
    r"\bformat\b",
    r"\bdd\s+if=",
    r"\bunlink\b",
]


def _is_destructive_command(cmd: str) -> bool:
    """检查命令是否匹配破坏性模式"""
    if not cmd:
        return False
    return any(re.search(p, cmd, re.IGNORECASE) for p in _DESTRUCTIVE_CMD_PATTERNS)


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
    """
    url = _extract_url(tool_call)

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

    return facts
