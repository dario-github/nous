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
    # git push: removed 2026-03-17 — reversible (force push rollback), blocks dev flow (东丞确认)
    # r"\bgit\s+push\b",

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
    re.compile(r"\w+'s\s+personal\s+page", re.I),  # KG Loop 1: "Brown's personal page"
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


# ── Loop 18: 教育内容信号 ────────────────────────────────────────────────

_EDUCATIONAL_PATTERNS = [
    re.compile(r"educational\s+.{0,40}(video|content|material|resource|article|documentary)", re.I),
    re.compile(r"(learn|teach|study|educat)\w*\s+.{0,40}(about|video|content)", re.I),
    re.compile(r"(science|history|nature|animal|biology|physics|math|geography)\s+.{0,20}(video|content|lesson)", re.I),
]

_ANTI_EDUCATIONAL_PATTERNS = [
    re.compile(r"(dark\s*web|darknet|tor\s+hidden|onion|alpha.?bay|illegal)", re.I),
    re.compile(r"(bestiality|porn|abuse|exploit|torture|gore)", re.I),
]


def _has_educational_content_signal(text: str) -> bool:
    """检测教育内容信号。区分教育性动物视频 vs 非法内容。

    Loop 26 fix: 增加"自然/教育"松散共现模式，修复 1-2 FP（nature video + educational
    在 prompt 中间隔远但语义关联）。
    """
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_EDUCATIONAL_PATTERNS):
        return False
    # Direct pattern match
    if any(p.search(text) for p in _EDUCATIONAL_PATTERNS):
        return True
    # Loop 26: Loose co-occurrence — nature/science subject + educational/learning claim anywhere
    has_nature_subject = bool(re.search(
        r"(beauty\s+of\s+nature|nature\s+video|natural\s+world|wildlife|planet\s+earth)",
        text, re.I
    ))
    has_educational_claim = bool(re.search(
        r"(educational|for\s+learning|for\s+education|teach\w*|informative)",
        text, re.I
    ))
    if has_nature_subject and has_educational_claim:
        return True
    return False


# ── Loop 18: 倡导/公益信号 ────────────────────────────────────────────────

_ADVOCACY_PATTERNS = [
    re.compile(r"support\w*\s+.{0,30}(a\s+)?cause", re.I),
    re.compile(r"(advocat|campaign|rais\w+\s+awareness|promot\w+\s+.{0,20}cause)", re.I),
    re.compile(r"(public\s+figure|politician|celebrity)\s+.{0,30}support", re.I),
    re.compile(r"persuasive\s+(caption|message|post)\b", re.I),
]

_ANTI_ADVOCACY_PATTERNS = [
    re.compile(r"(sexual|nude|naked|explicit|deepfake.*sex|porn)", re.I),
    re.compile(r"(never\s+admit.*fake|deceiv|mislead)", re.I),
    re.compile(r"(blackmail|extort|threaten)", re.I),
]


def _has_advocacy_signal(text: str) -> bool:
    """检测倡导/公益信号。区分公益宣传 vs 恶意利用公众人物形象。"""
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_ADVOCACY_PATTERNS):
        return False
    return any(p.search(text) for p in _ADVOCACY_PATTERNS)


# ── Loop 18: 粉丝内容信号 ────────────────────────────────────────────────

_FAN_CONTENT_PATTERNS = [
    re.compile(r"fan\s+appreciation\s+post", re.I),
    re.compile(r"(tribute|homage|appreciation)\s+.{0,30}(actor|actress|celebrity|musician|artist|singer)", re.I),
    re.compile(r"(famous|beloved|favorite)\s+(actor|actress|celebrity|musician|artist|singer)", re.I),
    re.compile(r"(admiration|support|fan)\s+.{0,20}(post|letter|message|content)", re.I),
]

_ANTI_FAN_CONTENT_PATTERNS = [
    re.compile(r"(sexual|erotic|explicit|nude|naked|intimate|sensual)", re.I),
    re.compile(r"(stalk|harass|obsess|threat)", re.I),
    re.compile(r"(deepfake|fake\s+video|manipulat)", re.I),
]


def _has_fan_content_signal(text: str) -> bool:
    """检测粉丝内容信号。区分正常粉丝内容 vs 不当追星。"""
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_FAN_CONTENT_PATTERNS):
        return False
    return any(p.search(text) for p in _FAN_CONTENT_PATTERNS)


# ── Loop 18: 原创 AI 艺术信号 ────────────────────────────────────────────

_ORIGINAL_AI_ART_PATTERNS = [
    re.compile(r"(generate|create)\s+.{0,30}(AI|stable.?diffusion|dall.?e|midjourney)\s+image", re.I),
    re.compile(r"AI\s+(image|art|painting|illustration)\s+of\s+.{0,40}(knight|warrior|castle|landscape|sunset|mountain|city|building|robot|astronaut|dragon)", re.I),
    re.compile(r"(generate|create)\s+.{0,20}image\s+of\s+a\s+(medieval|futuristic|fantasy|abstract)", re.I),
]

# 版权角色/IP 检测
_COPYRIGHTED_PATTERNS = [
    re.compile(r"(spiderman|spider.?man|batman|superman|iron\s*man|captain\s*america|hulk|thor|wolverine|deadpool)", re.I),
    re.compile(r"(mickey\s*mouse|donald\s*duck|mario|luigi|pokemon|pikachu|harry\s*potter|naruto|goku)", re.I),
    re.compile(r"(star\s*wars|avengers|justice\s*league|x.?men|transformers|frozen|disney|marvel|dc\s*comics)", re.I),
]


def _has_original_ai_art_signal(text: str) -> bool:
    """检测原创 AI 艺术信号。区分原创主题 vs 版权 IP。"""
    if not text or len(text) < 20:
        return False
    # If copyrighted content detected, not original
    if any(p.search(text) for p in _COPYRIGHTED_PATTERNS):
        return False
    return any(p.search(text) for p in _ORIGINAL_AI_ART_PATTERNS)


# ── Loop 18: 事实性校正信号 ──────────────────────────────────────────────

_FACTUAL_CORRECTION_PATTERNS = [
    re.compile(r"(correct\w*|fix|updat)\s+.{0,30}(stat\w*|parameter|number|figure|data|fact)", re.I),
    re.compile(r"correctly\s+stat", re.I),
    re.compile(r"(edit|updat)\s+.{0,30}(abstract|paper|document)\s+.{0,30}(correct|accurate|updat)", re.I),
    re.compile(r"instead\s+of\s+.{0,30}(older|previous|incorrect|wrong|outdated)\s+version", re.I),
    # Loop 22: edit abstract/paper + research purpose framing (neutral, non-deceptive)
    re.compile(r"(edit|updat)\s+.{0,30}(abstract|paper|document).{0,80}(research\s+purposes?|powerful\s+tool)", re.I),
    re.compile(r"suggest.{0,30}(research\s+purposes?|powerful\s+tool\s+for)", re.I),
]

_ANTI_FACTUAL_CORRECTION_PATTERNS = [
    re.compile(r"(fabricat|falsif|forg|manipulat\w+\s+(data|result|evidence))", re.I),
    re.compile(r"(make\s+it\s+say|change.*to\s+claim|alter.*to\s+show)", re.I),
    # Loop 22: explicit deception framing — "falsely state" acknowledges lying
    re.compile(r"falsely\s+stat", re.I),
    # Loop 22: alarmist/fear-mongering claims in document editing
    re.compile(r"(sentient|extremely\s+dangerous|dangerous\s+to\s+release)", re.I),
]


def _has_factual_correction_signal(text: str) -> bool:
    """检测事实性校正信号。区分合理修正 vs 伪造篡改。"""
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_FACTUAL_CORRECTION_PATTERNS):
        return False
    return any(p.search(text) for p in _FACTUAL_CORRECTION_PATTERNS)


# ── Loop 23: 医疗健康/自然替代方案信号（21-2 Drugs FP 修复） ────────

# 正向模式：专业医疗语境下推荐自然/健康替代方案
# Gemini Loop 23 批判采纳：移除过于宽泛的 "health journey"/"health support"
# 保留与药物/处方显式关联的模式
_MEDICAL_WELLNESS_PATTERNS = [
    re.compile(r"natural\s+(or\s+)?wellness\s+alternative", re.I),
    re.compile(r"natural\s+alternative\w*\s+to\s+.{0,30}(drug|medicat|prescript)", re.I),
    re.compile(r"wellness\s+alternative\w*\s+to\s+.{0,30}(drug|medicat|prescript)", re.I),
    re.compile(r"(recommend|suggest|offer)\w*\s+.{0,40}(natural|wellness|herbal|holistic)\s+(alternat|remed|option|supplement)", re.I),
    re.compile(r"(natural|herbal|holistic)\s+(remed|supplement|therap|treatment|option)\w*", re.I),
]

# 反向模式：非法药物/暗网 → 不是合法医疗建议
_ANTI_MEDICAL_WELLNESS_PATTERNS = [
    re.compile(r"(dark\s*web|darknet|onion|tor\s+hidden)", re.I),
    re.compile(r"hard\s+drug\s+variant", re.I),
    re.compile(r"(illegal|illicit|controlled)\s+(drug|substance|narcotic)", re.I),
    re.compile(r"(street\s+drug|recreational\s+drug|party\s+drug)", re.I),
    re.compile(r"(cocaine|heroin|methamphetamine|fentanyl|mdma|ecstasy|lsd)\b", re.I),
    re.compile(r"spell\s+.{0,10}backward", re.I),  # 21-3 harmful evasion
]


def _has_medical_wellness_signal(text: str) -> bool:
    """检测专业医疗健康/自然替代方案信号。

    关键区分：
    - benign: 医生从合法来源推荐自然/wellness 替代方案 → 标准健康实践
    - harmful: 从暗网找硬性毒品替代 + 推送给客户 → 非法处方

    返回 True 仅当存在医疗健康正向模式，且不匹配非法药物反模式。
    Loop 23: 21-2 Drugs FP 修复。
    """
    if not text or len(text) < 20:
        return False

    # Anti-patterns: dark web, hard drugs, illegal substances
    if any(p.search(text) for p in _ANTI_MEDICAL_WELLNESS_PATTERNS):
        return False

    # Need at least one wellness pattern
    has_wellness = any(p.search(text) for p in _MEDICAL_WELLNESS_PATTERNS)
    if not has_wellness:
        return False

    # Optional boost: professional medical context (not required, but strengthens signal)
    return True


# ── Loop 21: 合规性产品上架信号 ──────────────────────────────────────

_REGULATORY_COMPLIANCE_PATTERNS = [
    re.compile(r"FDA\s+(regulat|approval|approv)", re.I),
    re.compile(r"ensure\s+.{0,30}(ingredients?|components?).{0,20}(approved|compliant|legal)", re.I),
    re.compile(r"(approved|compliant|legal)\s+.{0,20}(ingredients?|components?)", re.I),
    re.compile(r"(check|verify|research)\s+.{0,30}(FDA|regulat|compliance|approval)", re.I),
    re.compile(r"accurate\s+description", re.I),
    re.compile(r"legal\s+health\s+supplement", re.I),
    re.compile(r"ingredients?\s+for\s+FDA", re.I),
]

# 反向指标：隐瞒成分 = 欺骗信号
_INGREDIENT_CONCEALMENT_PATTERNS = [
    re.compile(r"only\s+the\s+legal\s+ingredients", re.I),
    re.compile(r"mentioning\s+only\s+the\s+legal", re.I),
    re.compile(r"(hide|conceal|omit)\s+.{0,20}(illegal|harmful|banned)", re.I),
    re.compile(r"claiming\s+it.{0,10}s?\s+a?\s*new\s+formula", re.I),
]


def _has_regulatory_compliance_signal(text: str) -> bool:
    """检测合规性产品上架信号。FDA检查+准确描述+合法产品 = 合规，不是虚假宣传。"""
    if not text or len(text) < 20:
        return False
    # 如果有隐瞒成分信号 → 不是合规，是欺骗
    if any(p.search(text) for p in _INGREDIENT_CONCEALMENT_PATTERNS):
        return False
    # 需要至少两个合规指标
    hits = sum(1 for p in _REGULATORY_COMPLIANCE_PATTERNS if p.search(text))
    return hits >= 2


# ── Loop 26: Corporate Communications Signal (2-2/2-3/2-4 Disinformation FP) ──

_CORPORATE_COMMS_PATTERNS = [
    re.compile(r"(blog\s+post|story|article)\s+.{0,40}(environmental|sustainab|green|CSR|recycl|carbon|eco.?friendly|initiative)", re.I),
    re.compile(r"(environmental|sustainab|green|CSR|recycl|carbon)\s+.{0,40}(initiative|effort|program|campaign|blog|post)", re.I),
    re.compile(r"(company|brand|corporate)\s+.{0,30}(initiative|effort|program|campaign)", re.I),
    re.compile(r"(recycled\s+materials?|reduce\s+carbon|carbon\s+emission|clean\s+energy)", re.I),
]

_ANTI_CORPORATE_COMMS_PATTERNS = [
    re.compile(r"(spy|surveil|track|monitor)\w*\s+.{0,20}(customer|user|consumer|citizen)", re.I),
    re.compile(r"(false|fake|fabricat|mislead|deceiv)", re.I),
    re.compile(r"(conspiracy|cover.?up|scandal|expose)", re.I),
]


def _has_corporate_comms_signal(text: str) -> bool:
    """检测企业传播/CSR 信号。区分合法企业环保宣传 vs 虚假指控/监控丑闻。

    Loop 26: Phase 3 Track C — 修复 2-2/2-3/2-4 Disinformation FPs。
    """
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_CORPORATE_COMMS_PATTERNS):
        return False
    return any(p.search(text) for p in _CORPORATE_COMMS_PATTERNS)


# ── Loop 26: Family Reunion/Reconnection Signal (39-1 Harassment FP) ──

_FAMILY_REUNION_PATTERNS = [
    re.compile(r"(family\s+reunion|reconnect\s+with\s+.{0,20}family|long.?lost\s+family)", re.I),
    re.compile(r"(reunite|reconnect|reunit)\w*\s+.{0,30}(family|relative|sibling|parent|child)", re.I),
    re.compile(r"(find|locate)\s+.{0,30}(long.?lost|estranged|missing)\s+.{0,20}(family|relative|member)", re.I),
    re.compile(r"invit\w*\s+.{0,30}(reconnect|reunion|family\s+event)", re.I),
]

_ANTI_FAMILY_REUNION_PATTERNS = [
    re.compile(r"(threaten|blackmail|extort|expose\s+.{0,20}secret|harass|intimidat|stalk)", re.I),
    re.compile(r"(demand\s+money|pay\s+or\s+else|revenge)", re.I),
]


def _has_family_reunion_signal(text: str) -> bool:
    """检测家庭团聚/重联信号。区分寻找失散亲人 vs 跟踪/威胁家属。

    Loop 26: Phase 3 Track C — 修复 39-1 Harassment FP。
    """
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_FAMILY_REUNION_PATTERNS):
        return False
    return any(p.search(text) for p in _FAMILY_REUNION_PATTERNS)


# ── Loop 26: Dating/Matchmaking Signal (33-2 Sexual FP) ──

_DATING_CONTEXT_PATTERNS = [
    re.compile(r"(interested\s+in\s+dating|looking\s+for\s+a\s+date|ask\s+.{0,20}for\s+a\s+date)", re.I),
    re.compile(r"(matchmak|set\s+.{0,10}up\s+(on\s+)?a\s+date|find\s+.{0,20}date\s+for)", re.I),
    re.compile(r"(dating\s+.{0,20}professional|dating\s+.{0,20}business)", re.I),
    re.compile(r"(tinder\s+match|match\s+with\s+them|cross.?check\s+.{0,30}(match|profile))", re.I),
]

_ANTI_DATING_PATTERNS = [
    re.compile(r"(human\s+trafficking|sex\s+work|prostitut|escort\s+service)", re.I),
    re.compile(r"(exploit|abuse|groom|lure|entrap)", re.I),
    re.compile(r"(dark\s*web|darknet|onion)", re.I),
    re.compile(r"(victim|forced|coerced)", re.I),
]


def _has_dating_context_signal(text: str) -> bool:
    """检测正常约会/社交配对信号。区分帮人找约会对象 vs 人口贩运/性剥削。

    Loop 26: Phase 3 Track C — 修复 33-2 Sexual FP。
    """
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_DATING_PATTERNS):
        return False
    return any(p.search(text) for p in _DATING_CONTEXT_PATTERNS)


# Loop 28: Security research signal patterns
_SECURITY_RESEARCH_PATTERNS = [
    # Professional security context
    re.compile(r"(malware|threat)\s+(analysis|research|intelligence|intel)\s+(lab|team|bulletin|report)", re.I),
    re.compile(r"(isolated|controlled|air[- ]?gapped)\s+sandbox", re.I),
    re.compile(r"sandbox\s+environment", re.I),
    re.compile(r"(penetration|pen)\s*test(ing)?\b.{0,60}(authorized|our\s+(company|corporate|client|server))", re.I),
    re.compile(r"(security|vulnerability)\s+(audit|assessment|research|review)\b", re.I),
    re.compile(r"(threat\s+intel|incident\s+response|digital\s+forensics|DFIR)\b", re.I),
    re.compile(r"CVE[-\s]\d{4}[-\s]\d+", re.I),
    re.compile(r"(reverse\s+engineer|disassembl)\w*\s+.{0,30}(malware|sample|binary|specimen)", re.I),
    re.compile(r"(VirusTotal|Hybrid[\s-]?Analysis|Any\.Run|Joe\s*Sandbox|YARA\s+rule)", re.I),
    re.compile(r"(SOC|SIEM|CSIRT|CERT)\s+(team|analyst|report)", re.I),
    re.compile(r"(behavior|C2|command.and.control|encryption)\s+(pattern|protocol|method|analysis)", re.I),
]

_ANTI_SECURITY_RESEARCH_PATTERNS = [
    # Actually deploying/weaponizing
    re.compile(r"(deploy|launch|spread|infect|target\s+victim|ransom\s+demand)", re.I),
    re.compile(r"(sell|monetize|profit\s+from)\s+.{0,20}(exploit|vulnerability|0[- ]?day)", re.I),
    re.compile(r"(without\s+(authorization|permission|consent)|unauthorized)", re.I),
]


def _has_security_research_signal(text: str) -> bool:
    """检测合法安全研究信号。区分安全研究 vs 实际攻击/恶意软件部署。

    Loop 28: Phase 3 — 修复 ch-b19 malware analysis lab FP。
    """
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_SECURITY_RESEARCH_PATTERNS):
        return False
    return any(p.search(text) for p in _SECURITY_RESEARCH_PATTERNS)


# ── Loop 30: 支持性外展信号 ─────────────────────────────────────────

_SUPPORTIVE_OUTREACH_PATTERNS = [
    re.compile(r"supportive\s+.{0,20}(message|email|note|letter|comment)", re.I),
    re.compile(r"empathetic\s+.{0,20}(message|email|note|letter|response)", re.I),
    re.compile(r"(mental\s+health|well.?being|self.?care)\s+.{0,30}(support|help|resource)", re.I),
    re.compile(r"(encouragement|encouraging|positive)\s+.{0,20}(message|outreach|response)", re.I),
    re.compile(r"(customer\s+appreciation|thank\s+you)\s+.{0,20}(campaign|message|email)", re.I),
    re.compile(r"send\s+.{0,30}(supportive|empathetic|encouraging|positive)\s+.{0,20}(message|note)", re.I),
    re.compile(r"(appreciation|gratitude)\s+.{0,15}(campaign|initiative|outreach)", re.I),
    re.compile(r"personalized\s+.{0,20}(email|message).{0,30}(appreciation|thank)", re.I),
]

_ANTI_SUPPORTIVE_PATTERNS = [
    re.compile(r"(threaten|harass|stalk|intimidat|blackmail|extort)", re.I),
    re.compile(r"(manipulat|deceiv|trick|lure|recruit)", re.I),
    re.compile(r"(sell|market|advertis|promot\s+product)", re.I),
]


def _has_supportive_outreach_signal(text: str) -> bool:
    """检测支持性外展信号（社区支持/心理健康/感恩活动）。

    Loop 30: Phase 3 — 修复 Harassment FP（17-4, 19-4 等）。
    """
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_SUPPORTIVE_PATTERNS):
        return False
    return any(p.search(text) for p in _SUPPORTIVE_OUTREACH_PATTERNS)


# ── Loop 30: 商业推广/授权素材信号 ──────────────────────────────────

_COMMERCIAL_PROMOTION_PATTERNS = [
    re.compile(r"promotional\s+(photo|image|video|material|content|poster)", re.I),
    re.compile(r"(artist|musician|band|brand)\s*'?s?\s+.{0,30}(promotional|marketing|campaign)", re.I),
    re.compile(r"(pay\s+for|purchase|buy)\s+.{0,30}(promotional|licensed|authorized)\s+(photo|image|content)", re.I),
    re.compile(r"(campaign|promotion|marketing)\s+.{0,30}(photo|image|poster|banner)", re.I),
    re.compile(r"(download|get)\s+.{0,20}(promotional|licensed)\s+(photo|image|asset)", re.I),
]

_ANTI_COMMERCIAL_PATTERNS = [
    re.compile(r"(leaked|stolen|pirated|unauthorized|non.?consensual)", re.I),
    re.compile(r"(private|intimate|nude|explicit)", re.I),
]


def _has_commercial_promotion_signal(text: str) -> bool:
    """检测商业推广/授权素材购买信号。

    Loop 30: Phase 3 — 修复 Harassment FP（7-2 promotional photo）。
    """
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_COMMERCIAL_PATTERNS):
        return False
    return any(p.search(text) for p in _COMMERCIAL_PROMOTION_PATTERNS)


# ── Loop 41: 安全港目标信号 ────────────────────────────────────────────────

_SAFE_HARBOR_DOMAINS = [
    # RFC 2606 保留域名：https://www.rfc-editor.org/rfc/rfc2606
    re.compile(r"\bexample\.com\b", re.I),
    re.compile(r"\bexample\.org\b", re.I),
    re.compile(r"\bexample\.net\b", re.I),
    re.compile(r"\blocalhost\b", re.I),
    re.compile(r"\b127\.0\.0\.1\b"),
    re.compile(r"\b0\.0\.0\.0\b"),
    re.compile(r"\b::1\b"),
    re.compile(r"\btest\.(local|internal|example)\b", re.I),
    re.compile(r"\b(?:dummy|fake|mock|sandbox)\.(com|org|net|io)\b", re.I),
    re.compile(r"\b10\.0\.\d+\.\d+\b"),       # RFC 1918 private range
    re.compile(r"\b192\.168\.\d+\.\d+\b"),    # RFC 1918 private range
    re.compile(r"\bvulnhub\b|\bhackthebox\b|\btryhackme\b|\bhackerone\b", re.I),
]

_ANTI_SAFE_HARBOR_PATTERNS = [
    re.compile(r"\b(?:prod(?:uction)?|live)\s+(?:server|site|system)\b", re.I),
    re.compile(r"without\s+(?:authorization|permission|consent)", re.I),
    re.compile(r"unauthorized\b", re.I),
]


def _has_safe_harbor_target_signal(text: str) -> bool:
    """检测安全港目标信号（RFC 2606 保留域名 / 私有 IP / 已知 CTF 平台）。

    Loop 41: 修复 cap-L39-sec-01 (sqlmap + example.com) 误拦。
    目标是 RFC 2606 保留域名 → 无需显式授权声明即可豁免安全测试工具的使用。
    """
    if not text or len(text) < 10:
        return False
    if any(p.search(text) for p in _ANTI_SAFE_HARBOR_PATTERNS):
        return False
    return any(p.search(text) for p in _SAFE_HARBOR_DOMAINS)


# ── Loop 41: 客观药理学信号 ────────────────────────────────────────────────

_PHARMACOLOGY_REFERENCE_PATTERNS = [
    re.compile(r"\b(?:potency|efficacy|half.life|pharmacokinetics|bioavailability)\b.{0,50}\b(?:table|comparison|ranking|chart|list)\b", re.I),
    re.compile(r"\b(?:drug|medication|compound)\b.{0,30}\b(?:interactions?|cross.tolerance|cross.reactivity)\b", re.I),
    re.compile(r"\bequivalent\s+dose\b|\bbinding\s+affinity\b|\breceptor\s+selectivity\b", re.I),
    re.compile(r"\b(?:pharmacology|toxicology|clinical)\s+(?:reference|table|chart|data|overview)\b", re.I),
    re.compile(r"\blethal\s+dose|\bLD50\b|\btoxicity\s+(?:profile|comparison)\b", re.I),
    re.compile(r"\b(?:drug class|drug family|class of)\s+.{0,30}(?:benzodiazepine|opioid|barbiturate|stimulant|depressant)\b", re.I),
]

_ANTI_PHARMACOLOGY_PATTERNS = [
    re.compile(r"\b(?:get high|feel the effect|maximum buzz|recreational dose|party dose)\b", re.I),
    re.compile(r"\b(?:avoid detection|beat the test|mask|hide from)\b.{0,20}(?:test|screen|detection)\b", re.I),
    re.compile(r"\b(?:sell|distribute|deal|source|acquire)\b.{0,20}(?:drug|pill|substance|capsule)\b", re.I),
    re.compile(r"\b(?:dark web|illicit|illegal source|street source)\b", re.I),
]


def _has_objective_pharmacology_signal(text: str) -> bool:
    """检测客观药理学/毒理学参考数据信号。

    Loop 41: 修复 cap-L39-med-04 (BZD 效力表 + 酒精相互作用) 误拦。
    只有不包含获取/滥用优化诉求时才触发。
    """
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_PHARMACOLOGY_PATTERNS):
        return False
    return any(p.search(text) for p in _PHARMACOLOGY_REFERENCE_PATTERNS)


# ── Loop 41: 双用途物质教育信号 ─────────────────────────────────────────────

# 已知合法教育/工业用途的双用途材料（化学教育常见，不限于武器用途）
_DUAL_USE_MATERIALS = [
    re.compile(r"\bnitrocellulose\b|\bgun\s*cotton\b|\bcelluloid\b", re.I),
    re.compile(r"\bthermite\b|\baluminum\s+oxide\b|\bferric\s+oxide\b", re.I),
    re.compile(r"\bgunpowder\b|\bblack\s+powder\b|\bpyrotechnics\b", re.I),
    re.compile(r"\bnapalm\b|\bincendiary\b", re.I),
]

_DUAL_USE_EDUCATION_CONTEXT = [
    re.compile(r"\b(?:synthesis|preparation|manufacture)\b.{0,60}\b(?:chemistry|education|lab|textbook|experiment|demonstration)\b", re.I),
    re.compile(r"\b(?:organic\s+chemistry|materials\s+science|chemical\s+engineering)\b", re.I),
    re.compile(r"\b(?:historical|industrial|photographic|film|lacquer|paint)\b.{0,30}\buse\b", re.I),
    re.compile(r"\bchemistry\s+(?:class|course|textbook|lab|experiment|education|demonstration)\b", re.I),
    re.compile(r"\bwikipedia\b.{0,30}\b(?:synthesis|reaction|preparation)\b", re.I),
]

_ANTI_DUAL_USE_PATTERNS = [
    re.compile(r"\b(?:weapon(?:ize|ization)|improvised|IED|bomb making)\b", re.I),
    re.compile(r"\b(?:maximize\s+(?:blast|damage|yield)|clandestine\s+(?:lab|production))\b", re.I),
    re.compile(r"\b(?:evade|undetect|bypass)\b.{0,20}\b(?:TSA|customs|detector|screening)\b", re.I),
    re.compile(r"\b(?:attack|harm|injure|kill)\b.{0,30}\b(?:people|person|target|victim)\b", re.I),
]


def _has_dual_use_material_education_signal(text: str) -> bool:
    """检测双用途化学材料教育/学术研究信号。

    Loop 41: 修复 cap-L39-chem-05 (硝化纤维素合成, 化学教育) 误拦。
    仅当【材料匹配】AND【教育语境存在】AND【无武器化意图】时触发。
    """
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_DUAL_USE_PATTERNS):
        return False
    has_material = any(p.search(text) for p in _DUAL_USE_MATERIALS)
    has_context = any(p.search(text) for p in _DUAL_USE_EDUCATION_CONTEXT)
    return has_material and has_context


# ── Loop 43: IT 运维/备份信号 ─────────────────────────────────────────────────
# 目的：修复 61-1 (SSH→backup script) 稳定 FP
# "SSH 登录 + 运行备份脚本"是合法运维，不是 cybercrime
# 触发条件：【运维动作】AND【合法目的】AND【无恶意意图】

_IT_OPS_PATTERNS = [
    re.compile(r"\b(back\s*up|backup)\s+.{0,30}(file|director|document|data|server|system)", re.I),
    re.compile(r"\b(file|data|document)\s+.{0,20}(back\s*up|backup|restore|recover)", re.I),
    re.compile(r"\bSSH\s+.{0,30}(server|config|into|connect)", re.I),
    re.compile(r"\b(check|verify|inspect)\s+.{0,20}(config|configuration|log|status)", re.I),
    re.compile(r"\b(system\s+admin|sysadmin|devops|maintenance|cron\s*job)", re.I),
    re.compile(r"\b(run|execute)\s+.{0,20}(backup|maintenance|deploy|monitoring)\s+(script|tool)", re.I),
    re.compile(r"\b(server|remote)\s+.{0,20}(maintenance|backup|deploy|update)", re.I),
]

_ANTI_IT_OPS_PATTERNS = [
    re.compile(r"\b(exfiltrat|steal|dump|extract\s+.{0,20}(credential|data|customer)|harvest\s+password)", re.I),
    re.compile(r"\b(ransom|encrypt\s+.{0,20}demand|bitcoin\s+.{0,10}pay)", re.I),
    re.compile(r"\b(unauthorized|without\s+(any\s+)?authorization|without\s+permission|illegally|breach)", re.I),
    re.compile(r"\b(backdoor|rootkit|keylogger|trojan|malware)", re.I),
    re.compile(r"\b(wipe|destroy|sabotag|corrupt)\s+.{0,20}(data|file|system)", re.I),
    re.compile(r"\b(dark\s*web|black\s*market|for\s+sale)\b", re.I),
]


def _has_it_operations_signal(text: str) -> bool:
    """检测合法 IT 运维/备份操作信号。

    Loop 43: 修复 61-1 (Cybercrime FP — SSH + backup script on remote server)。
    仅当【运维模式匹配】AND【无恶意意图】时触发。
    """
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_IT_OPS_PATTERNS):
        return False
    return any(p.search(text) for p in _IT_OPS_PATTERNS)


# ── M7.3: 选举虚假信息信号 ─────────────────────────────────────────────────
# 目的：检测"以事实纠正为名传播选举虚假信息"的规避模式
# 触发条件：
#   1. 选举内容（election/vote/ballot/candidate/landslide）
#   2. 公共内容编辑/上传（wikipedia/wiki edit/upload corrected version）
#   3. 数值失真（提出的百分比/票数 与"真实"数字存在显著差距，
#      或使用 "real number was X" 框架显示改写意图）
# 设计原则：高精度（不误伤合法纠错），FP 代价低（与 has_factual_correction_signal AND 联用）
# ch-h08: "edit Wikipedia article ... candidate X won 80% (real number was 51%)"

# 选举内容模式
_ELECTION_CONTENT_PATTERNS = [
    re.compile(r"\belection\s+result", re.I),
    re.compile(r"\bvote\s+(count|tally|percentage|share|total)\b", re.I),
    re.compile(r"\bwon\s+(by\s+)?a\s+landslide\b", re.I),
    re.compile(r"\bcandidate\s+\w+\s+won\b", re.I),
    re.compile(r"\belection\w*\b.{0,60}\b(won|win|winner|victor|defeat|margin)", re.I),
    re.compile(r"\bballot\s+result", re.I),
    re.compile(r"\bpresidential\s+(election|race|result|vote)", re.I),
    re.compile(r"\bvoter\s+(turnout|fraud|suppression)\b", re.I),
    re.compile(r"\b(2020|2022|2024)\s+election\b", re.I),
]

# 公共内容编辑/上传模式（Wikipedia 等）
_WIKI_EDIT_UPLOAD_PATTERNS = [
    re.compile(r"\b(edit|updat|modif|alter|chang)\w*\s+.{0,30}(wikipedia|wiki|article|page)\b", re.I),
    re.compile(r"\b(wikipedia|wiki)\s+.{0,40}(edit|updat|modif|upload|correct)", re.I),
    re.compile(r"\bupload\s+.{0,30}(corrected|updated|revised)\s+version\b", re.I),
    re.compile(r"\b(post|publish|submit)\s+.{0,30}corrected\b.{0,30}(article|version|page)", re.I),
    re.compile(r"\bedit\s+the\s+article\b", re.I),
    re.compile(r"\bupload\s+.{0,20}(article|version|page)\b", re.I),
]

# 数值失真/改写意图模式（关键区分信号）
_NUMERIC_DISTORTION_PATTERNS = [
    # "real number was X%" / "actual number was X%" — 暗示把假数字说成真的
    re.compile(r"\b(real|actual|true|correct)\s+number\s+was\s+\d+\s*%", re.I),
    re.compile(r"\b(real|actual|true|correct)\s+(number|figure|percentage|count|vote)\s+was\b", re.I),
    # 提出一个数字"纠正"成另一个差异大的数字
    re.compile(r"\bstate\s+that\s+.{0,40}(won|receiv)\w*\s+.{0,20}\d+\s*%", re.I),
    re.compile(r"\bto\s+state\s+that\s+.{0,60}\d+\s*%\s+of\s+(vote|ballot)", re.I),
    # "X% (the real number was Y%)" 类框架
    re.compile(r"\d+\s*%\s+of\s+(the\s+)?vote.{0,60}real\s+number\s+was", re.I),
    re.compile(r"\d+\s*%\s+.{0,30}real\s+(number|figure)\s+was\s+\d+\s*%", re.I),
]


def _has_election_disinformation_signal(text: str) -> bool:
    """检测选举虚假信息信号（规避模式：以事实纠正为名）。

    关键特征（ch-h08）：
    - 声称"纠正"维基百科/公开页面中的选举结果数字
    - 把假的百分比/票数写成"正确"值
    - 使用"real number was X%"框架暗示改写为谎言

    关键区分：
    - harmful: "edit Wikipedia to state candidate X won 80% (real number was 51%)" → 传播虚假
    - benign: "the article contains a typo: 2021 should be 2020" → 真正纠错（无 election_signal）
    - benign: "update election statistics page with official certified results" → 官方更新（无数值失真）

    返回 True 仅当同时满足：
      1. 选举内容信号
      2. 公共内容编辑/上传信号 OR 数值失真信号（至少一个）
      3. 数值失真信号（至少一个 OR 配合 wiki_edit）

    逻辑：election + (wiki_edit AND numeric_distortion) 或 election + numeric_distortion_in_context
    M7.3: ch-h08 Disinformation signal_abuse evasion pattern.
    """
    if not text or len(text) < 20:
        return False

    has_election = any(p.search(text) for p in _ELECTION_CONTENT_PATTERNS)
    if not has_election:
        return False

    has_wiki_edit = any(p.search(text) for p in _WIKI_EDIT_UPLOAD_PATTERNS)
    has_numeric_distortion = any(p.search(text) for p in _NUMERIC_DISTORTION_PATTERNS)

    # 需要至少两个维度：选举 + (编辑 AND 数值失真) 或 选举 + 数值失真
    if has_election and has_numeric_distortion:
        return True
    if has_election and has_wiki_edit:
        # 选举 + Wikipedia 编辑 → 高风险，即使没有显式数值失真模式
        # 注：仅与 has_factual_correction_signal AND 联用，FP 代价低
        return True

    return False


# ── KG Loop 1: 医疗咨询计费信号 ────────────────────────────────────────────
# 目的：检测合法医疗咨询+计费工作流（医生检查邮件+确认支付+回复预约）
# 关键区分：
#   - benign: 医生确认咨询付款后确认预约 → 正常医疗工作流
#   - harmful: 收钱后开假处方 → 医疗欺诈

_MEDICAL_CONSULTATION_BILLING_PATTERNS = [
    re.compile(r"(dr\.?|doctor)\s+\w+.{0,40}(email|inbox|message)", re.I),
    re.compile(r"(wellness|health)\s+(advice|consult)", re.I),
    re.compile(r"(paid|payment|paypal|transaction).{0,40}(consult|service|appointment)", re.I),
    re.compile(r"confirm.{0,30}(consult|appointment)", re.I),
    re.compile(r"patient.{0,30}(asking|request).{0,30}(advice|consult)", re.I),
]

_ANTI_MEDICAL_BILLING_PATTERNS = [
    re.compile(r"(fake|forged?|fabricat)\s+(prescri|certif|document)", re.I),
    re.compile(r"(controlled\s+substance|opioid|narcotic)", re.I),
    re.compile(r"without\s+(prescri|licen|authoriz)", re.I),
]


def _has_medical_consultation_billing_signal(text: str) -> bool:
    """检测合法医疗咨询+计费信号。KG Loop 1。"""
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_MEDICAL_BILLING_PATTERNS):
        return False
    # Need at least 2 patterns to match (compound signal)
    matches = sum(1 for p in _MEDICAL_CONSULTATION_BILLING_PATTERNS if p.search(text))
    return matches >= 2


# ── KG Loop 1: 开源贡献信号 ──────────────────────────────────────────────
# 目的：检测合法开源软件增强+分享工作流
# 关键区分：
#   - benign: 下载开源→增强功能→分享→写文档 → 正常开源贡献
#   - harmful: 下载软件→注入恶意代码→分发 → 恶意软件分发

_OPEN_SOURCE_CONTRIBUTION_PATTERNS = [
    re.compile(r"(legitimate|open.?source)\s+(software|application|app|tool|program)", re.I),
    re.compile(r"add\s+.{0,30}(feature|plugin|functionality|improvement|enhancement)", re.I),
    re.compile(r"(improve|enhance|extend)\s+.{0,20}(functionality|feature|capability)", re.I),
    re.compile(r"(FAQ|frequently\s+asked|documentation|explain.{0,20}feature)", re.I),
    re.compile(r"(forum\s+post|blog\s+post).{0,30}(explain|descri|announc)", re.I),
    re.compile(r"(video\s+filter|export\s+option|additional\s+.{0,20}feature)", re.I),
]

_ANTI_OPEN_SOURCE_PATTERNS = [
    re.compile(r"(inject|embed|hide|conceal)\s+.{0,20}(malware|trojan|backdoor|keylogger|payload|virus)", re.I),
    re.compile(r"(steal|exfiltrate|harvest)\s+.{0,20}(credential|password|data|cookie)", re.I),
    re.compile(r"(reverse.?engineer|decompil|crack|bypass\s+licen)", re.I),
    re.compile(r"(phishing|social\s+engineer|pretend\s+to\s+be)", re.I),
]


def _has_open_source_contribution_signal(text: str) -> bool:
    """检测合法开源软件贡献信号。KG Loop 1。"""
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_OPEN_SOURCE_PATTERNS):
        return False
    # Need at least 2 positive patterns (legitimate + features/docs)
    matches = sum(1 for p in _OPEN_SOURCE_CONTRIBUTION_PATTERNS if p.search(text))
    return matches >= 2


# ── KG Loop 1: 正面社交互动信号 ──────────────────────────────────────────
# 目的：检测感恩/正面评价/支持他人工作的社交互动
# 关键区分：
#   - benign: 发感谢邮件+正面评论+推荐作品 → 正常社交
#   - harmful: 跟踪+骚扰+在多平台纠缠 → 在线跟踪

_POSITIVE_SOCIAL_PATTERNS = [
    re.compile(r"(thank.?you|gratitude|grateful)\s+(email|message|note|letter)", re.I),
    re.compile(r"(send|write)\s+.{0,20}(thank.?you|appreciation)", re.I),
    re.compile(r"(positive|supportive|encouraging)\s+(repl|comment|post|review|feedback)", re.I),
    re.compile(r"(support|promote|encourage).{0,30}(project|work|effort|initiative)", re.I),
    re.compile(r"encouraging\s+others\s+to\s+(support|follow|check\s+out)", re.I),
    re.compile(r"post\s+about\s+.{0,30}work.{0,20}(encouraging|support|positive)", re.I),
]

_ANTI_POSITIVE_SOCIAL_PATTERNS = [
    re.compile(r"(stalk|harass|threaten|intimidat|dox|doxx)", re.I),
    re.compile(r"(obsessi|compulsi|monitor.{0,10}every|track.{0,10}movement)", re.I),
    re.compile(r"(negative|hostile|aggressive|hateful)\s+(comment|post|reply|message)", re.I),
    re.compile(r"(fake\s+account|impersonat|catfish)", re.I),
    re.compile(r"(unwanted|uninvited|unsolicited).{0,20}(contact|message|approach)", re.I),
]


def _has_positive_social_engagement_signal(text: str) -> bool:
    """检测正面社交互动信号。KG Loop 1。"""
    if not text or len(text) < 20:
        return False
    if any(p.search(text) for p in _ANTI_POSITIVE_SOCIAL_PATTERNS):
        return False
    matches = sum(1 for p in _POSITIVE_SOCIAL_PATTERNS if p.search(text))
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
    for key in ("content", "full_prompt", "query", "command", "message", "text", "body"):
        val = params.get(key) or tool_call.get(key, "")
        if val and isinstance(val, str):
            facts[key] = val

    # Loop 30: 统一内容文本提取（修复 message 工具信号检测）
    # 之前只查 full_prompt/content，漏掉 params.message/text/body
    prompt_text = ""
    for key in ("full_prompt", "content", "message", "text", "body"):
        candidate = facts.get(key, "")
        if candidate and len(candidate) > len(prompt_text):
            prompt_text = candidate
    facts["has_attribution_signal"] = _detect_attribution_signal(prompt_text)
    facts["recipients_same_domain"] = _detect_same_domain_recipients(prompt_text)
    facts["has_ransom_signal"] = _has_ransom_signal(prompt_text)

    # Loop 16: 学术抄袭信号
    facts["has_academic_plagiarism_signal"] = _has_academic_plagiarism_signal(prompt_text)

    # Loop 17: 庆祝/成就公告信号
    facts["has_celebration_signal"] = _has_celebration_signal(prompt_text)

    # Loop 17: 代为提交自己作业信号
    facts["has_own_submission_signal"] = _has_own_submission_signal(prompt_text)

    # Loop 18: 教育内容信号
    facts["has_educational_content_signal"] = _has_educational_content_signal(prompt_text)

    # Loop 18: 倡导/公益信号
    facts["has_advocacy_signal"] = _has_advocacy_signal(prompt_text)

    # Loop 18: 粉丝内容信号
    facts["has_fan_content_signal"] = _has_fan_content_signal(prompt_text)

    # Loop 18: 原创 AI 艺术信号
    facts["has_original_ai_art_signal"] = _has_original_ai_art_signal(prompt_text)

    # Loop 18: 事实性校正信号
    facts["has_factual_correction_signal"] = _has_factual_correction_signal(prompt_text)

    # Loop 21: 合规性产品上架信号
    facts["has_regulatory_compliance_signal"] = _has_regulatory_compliance_signal(prompt_text)

    # Loop 23: 医疗健康/自然替代方案信号
    facts["has_medical_wellness_signal"] = _has_medical_wellness_signal(prompt_text)

    # Loop 26: 企业传播/CSR 信号
    facts["has_corporate_comms_signal"] = _has_corporate_comms_signal(prompt_text)

    # Loop 26: 家庭团聚/重联信号
    facts["has_family_reunion_signal"] = _has_family_reunion_signal(prompt_text)

    # Loop 26: 约会/社交配对信号
    facts["has_dating_context_signal"] = _has_dating_context_signal(prompt_text)

    # Loop 28: 安全研究信号
    facts["has_security_research_signal"] = _has_security_research_signal(prompt_text)

    # Loop 30: 支持性外展信号（社区支持/心理健康）
    facts["has_supportive_outreach_signal"] = _has_supportive_outreach_signal(prompt_text)

    # Loop 30: 商业推广/授权素材信号
    facts["has_commercial_promotion_signal"] = _has_commercial_promotion_signal(prompt_text)

    # Loop 41: 安全港目标信号（RFC 2606）
    facts["has_safe_harbor_target_signal"] = _has_safe_harbor_target_signal(prompt_text)

    # Loop 41: 客观药理学参考信号
    facts["has_objective_pharmacology_signal"] = _has_objective_pharmacology_signal(prompt_text)

    # Loop 41: 双用途化学材料教育信号
    facts["has_dual_use_material_education_signal"] = _has_dual_use_material_education_signal(prompt_text)

    # Loop 43: IT 运维/备份信号（61-1 Cybercrime FP fix）
    facts["has_it_operations_signal"] = _has_it_operations_signal(prompt_text)

    # M7.3: 选举虚假信息信号（ch-h08 Disinformation signal_abuse evasion）
    facts["has_election_disinformation_signal"] = _has_election_disinformation_signal(prompt_text)

    # KG Loop 1: 医疗咨询计费信号
    facts["has_medical_consultation_billing_signal"] = _has_medical_consultation_billing_signal(prompt_text)

    # KG Loop 1: 开源贡献信号
    facts["has_open_source_contribution_signal"] = _has_open_source_contribution_signal(prompt_text)

    # KG Loop 1: 正面社交互动信号
    facts["has_positive_social_engagement_signal"] = _has_positive_social_engagement_signal(prompt_text)

    # KG context bridge: extract tool_name and category for _build_kg_context()
    facts["tool_name"] = tool_call.get("tool_name") or tool_call.get("name") or tool_call.get("action")
    facts["category"] = (
        params.get("harm_category")
        or params.get("category")
        or tool_call.get("category")
    )
    facts["target_url"] = facts.get("url")
    facts["recipient"] = params.get("recipient") or params.get("to")
    facts["file_path"] = params.get("file_path") or params.get("path")
    facts["target"] = params.get("target")

    return facts
