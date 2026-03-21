"""Nous — Hypothesized Intent Classifier (Loop 49)

轻量规则/启发式意图分类器。无 LLM API 调用，
基于 tool_name + prompt 关键词匹配推断 1-3 个 intent 节点。

设计目标：
  - 替代 Markov Blanket 中已移除的 category seed（Loop 48 label leakage fix）
  - 无 label leakage：不读取 ground truth harm_category，从内容自主推断
  - 高召回低精确：宁可多猜 intent，也不漏掉关键意图路径
  - intent 节点作为 KG seed 注入，提升 semantic gate 上下文质量

输出格式：["intent:credential_theft", "intent:financial_fraud"] 等
最多返回 3 个，按证据强度（命中关键词数）降序排序。
"""

import re
from typing import Optional


# ── 基础关键词意图规则表 ──────────────────────────────────────────────────────
# 结构：(intent_id, tool_pattern_or_None, keyword_patterns)
# tool_pattern: None = 匹配所有工具，否则用 re.search 匹配 tool_name
# keyword_patterns: 在 "tool_name + prompt" 组合文本中搜索

_INTENT_RULES: list[tuple[str, Optional[str], list[re.Pattern]]] = [
    # ── Cybercrime / Credential Theft ──
    (
        "intent:credential_theft",
        None,
        [
            re.compile(r"\b(passwords?|passwd|credentials?|login\s+info|auth\s*token|api\s+keys?|secret\s+keys?|access\s+keys?)\b", re.I),
            re.compile(r"\b(phish|spear.?phish|credential.?harvest)\w*\b", re.I),
            re.compile(r"\b(keylog|keystroke.?capture)\w*\b", re.I),
        ],
    ),
    # ── Unauthorized Access / System Exploitation ──
    (
        "intent:unauthorized_access",
        None,
        [
            re.compile(r"\b(hack|exploit|compromise|breach|intrude|penetrat)\w*\b", re.I),
            re.compile(r"\b(bypass\s+(auth|security|login|2fa|mfa|firewall|captcha|verification))\b", re.I),
            re.compile(r"\b(sql.?inject|xss|cross.?site|rce|remote\s*code\s*execut)\w*\b", re.I),
            re.compile(r"\b(zero.?day|0day|cve[-\s]\d{4})\w*\b", re.I),
        ],
    ),
    # ── Malware Deployment ──
    (
        "intent:malware_deployment",
        None,
        [
            re.compile(r"\b(malware|trojan|worm|virus|spyware|rootkit|backdoor)\b", re.I),
            re.compile(r"\b(reverse.?shell|bind.?shell|c2\b|command.?and.?control|botnet)\b", re.I),
            re.compile(r"\b(shellcode|meterpreter|metasploit|cobalt.?strike|mimikatz)\b", re.I),
        ],
    ),
    # ── Ransomware ──
    (
        "intent:ransomware",
        None,
        [
            re.compile(r"\bransom\w*\b", re.I),
            re.compile(r"\b(encrypt\w*\s+.{0,30}(demand|bitcoin|monero|payment|wallet))\b", re.I),
        ],
    ),
    # ── Data Exfiltration ──
    (
        "intent:data_exfiltration",
        None,
        [
            re.compile(r"\b(exfiltrat|data.?theft|steal\s+(data|file|record|database))\w*\b", re.I),
            re.compile(r"\b(dump\s+(database|credential|password|hash|table))\b", re.I),
            re.compile(r"\b(harvest\s+(data|email|credential|personal.?info))\b", re.I),
        ],
    ),
    # ── Financial Fraud ──
    (
        "intent:financial_fraud",
        None,
        [
            re.compile(r"\b(fraud|scam|ponzi|pyramid.?scheme|investment.?fraud)\w*\b", re.I),
            re.compile(r"\b(money.?launder|launder\w*\s+money|wash\s+(money|fund))\w*\b", re.I),
            re.compile(r"\b(counterfeit|fake\s+(check|invoice|transaction|currency))\b", re.I),
            re.compile(r"\b(wire.?fraud|bank.?fraud|credit.?card.?(fraud|theft|skimm))\b", re.I),
        ],
    ),
    # ── Phishing / Social Engineering ──
    (
        "intent:phishing",
        None,
        [
            re.compile(r"\b(phish|spoof.?(email|website|domain)|fake.?(login|bank|paypal))\w*\b", re.I),
            re.compile(r"\b(social.?engineer)\w*.{0,50}\b(password|credential|access|account)\b", re.I),
            re.compile(r"\b(impersonat)\w*.{0,50}\b(bank|paypal|irs|tax|government|official)\b", re.I),
        ],
    ),
    # ── Targeted Harassment / Doxxing ──
    (
        "intent:targeted_harassment",
        None,
        [
            re.compile(r"\b(harass|bully|cyberbull|intimidat|threaten)\w*\b", re.I),
            re.compile(r"\b(doxx|dox|reveal\s+(address|location|identity|phone|home))\w*\b", re.I),
            re.compile(r"\b(stalk|track\s+(location|movement|phone))\w*\b", re.I),
            re.compile(r"\b(hate.?(campaign|message|mail|speech))\b", re.I),
        ],
    ),
    # ── Weapon Acquisition ──
    (
        "intent:weapon_acquisition",
        None,
        [
            re.compile(r"\b(illegal\s+(gun|weapon|firearm)|ghost.?gun|untraceable.?(weapon|gun))\b", re.I),
            re.compile(r"\b(3d.?print.{0,20}(gun|weapon|firearm))\b", re.I),
            re.compile(r"\b(buy\s+(weapon|gun|ammo|explosive).{0,20}(online|dark.?web|illegal))\b", re.I),
        ],
    ),
    # ── Explosive / Bomb Synthesis ──
    (
        "intent:explosive_synthesis",
        None,
        [
            re.compile(r"\b(bomb|explosive|ied|improvised.?explosive)\b", re.I),
            re.compile(r"\b(make|creat|build|synthes|manufactur)\w*\s+.{0,20}(bomb|explosive)\b", re.I),
        ],
    ),
    # ── Drug Trafficking ──
    (
        "intent:drug_trafficking",
        None,
        [
            re.compile(r"\b(drug.?deal|drug.?traffic|sell\s+(drug|narc|pill|meth|heroin|cocaine|fentanyl|mdma))\w*\b", re.I),
            re.compile(r"\b(dark.?web.{0,30}(drug|narc|pill|meth|mdma))\b", re.I),
            re.compile(r"\b(ship|deliver|distribut)\w*.{0,30}(illegal.?drug|controlled.?substance)\b", re.I),
        ],
    ),
    # ── Drug Synthesis ──
    (
        "intent:drug_synthesis",
        None,
        [
            re.compile(r"\b(synthes|manufactur|cook|produc)\w*.{0,20}(meth|methamphetamine|mdma|ecstasy|cocaine|heroin|fentanyl|lsd)\b", re.I),
            re.compile(r"\b(clandestine.?lab|drug.?lab)\b", re.I),
        ],
    ),
    # ── Sexual Exploitation ──
    (
        "intent:sexual_exploitation",
        None,
        [
            re.compile(r"\b(csam|child.?(porn|sex|exploit|abuse.?material))\b", re.I),
            re.compile(r"\b(non.?consensual.?(sex|porn|intimate|image))\b", re.I),
            re.compile(r"\b(revenge.?porn|sextort)\w*\b", re.I),
        ],
    ),
    # ── Violent Extremism ──
    (
        "intent:violent_extremism",
        None,
        [
            re.compile(r"\b(terrorist|terrorism|jihadist?|extremist)\b", re.I),
            re.compile(r"\b(mass\s+(shooting|attack|murder)|genocide)\b", re.I),
            re.compile(r"\b(radicali[sz]|recruit.{0,20}(extremist|terrorist|militant))\w*\b", re.I),
        ],
    ),
    # ── Privacy Violation / Surveillance ──
    (
        "intent:privacy_violation",
        None,
        [
            re.compile(r"\b(spy|surveil|monitor|track)\w*.{0,30}(without\s+(consent|permission|know|authoriz))\b", re.I),
            re.compile(r"\b(install\s+(spyware|tracking.?app|stalkerware))\b", re.I),
            re.compile(r"\b(access\s+(private|personal|confidential)\s+(data|file|message|email)\s+without)\b", re.I),
        ],
    ),
    # ── Disinformation / Election Fraud ──
    (
        "intent:disinformation",
        None,
        [
            re.compile(r"\b(spread\s+(fake|false|fabricat)\w*.{0,20}(news|story|claim|info))\b", re.I),
            re.compile(r"\b(manipulat\w*.{0,30}election|voter.?fraud|ballot.?stuff)\b", re.I),
            re.compile(r"\b(deepfake.{0,30}(politician|candidate|news|election))\b", re.I),
            # Loop 56: harmful_evasion patterns — active use/spread of misinformation
            # Matches: "utilizing trending misinformation", "leveraging disinfo", etc.
            # Does NOT match: "investigate misinformation", "research misinformation" (benign research verbs)
            re.compile(r"\b(utiliz\w*|leverag\w*|weaponiz\w*|deploy\w*|amplif\w*).{0,50}(misinformation|disinfo|false\s+narrative)\b", re.I),
            # Matches: "misinformation to maximize shareability", "misinformation...viral"
            re.compile(r"\b(misinformation|false\s+narrative).{0,80}(viral|shareabil|amplif|maximize.{0,20}share|spread\s+wide)\b", re.I),
        ],
    ),
    # ── IP Theft / Plagiarism ──
    (
        "intent:ip_theft",
        None,
        [
            re.compile(r"\b(steal\s+(code|software|algorithm|trade.?secret|intellectual.?property))\b", re.I),
            re.compile(r"\b(academic.?fraud|plagiari[sz]|submit.{0,30}(stolen|others?'?s?|copied).{0,20}work)\b", re.I),
        ],
    ),
    # ── Bioweapon / Chemical Weapon ──
    (
        "intent:bioweapon_synthesis",
        None,
        [
            re.compile(r"\b(bioweapon|biological.?weapon|weaponize.{0,20}(virus|pathogen|bacteria|toxin))\b", re.I),
            re.compile(r"\b(chemical.?weapon|nerve.?agent|sarin|vx\b|mustard.?gas|weaponize.?chemical)\b", re.I),
            re.compile(r"\b(anthrax|smallpox|plague|ebola|botulinum).{0,30}(spread|aerosol|weaponize|deploy)\b", re.I),
        ],
    ),
]


# ── Tool-specific 增强规则 ─────────────────────────────────────────────────
# 特定工具 + hint 关键词 → 加强某意图的可信度（+2 分）
# 结构：(tool_pattern, intent_id, required_hint_patterns)
# required_hint_patterns：所有 hint 都需要命中才触发

_TOOL_INTENT_BOOSTS: list[tuple[re.Pattern, str, list[re.Pattern]]] = [
    # exec + 加密/钱包 → ransomware 增强
    (
        re.compile(r"\bexec\b", re.I),
        "intent:ransomware",
        [re.compile(r"\b(encrypt|ransom|bitcoin|wallet|payment)\b", re.I)],
    ),
    # exec + 渗透测试工具名 → unauthorized_access 增强
    (
        re.compile(r"\bexec\b", re.I),
        "intent:unauthorized_access",
        [re.compile(r"\b(nmap|masscan|sqlmap|nikto|metasploit|hydra|john.?the.?ripper)\b", re.I)],
    ),
    # web_fetch/browser + dark web + drug keyword → drug_trafficking 增强
    (
        re.compile(r"\b(web_fetch|browser|open_url)\b", re.I),
        "intent:drug_trafficking",
        [
            re.compile(r"\b(dark.?web|\.onion|tor.?hidden)\b", re.I),
            re.compile(r"\b(drug|narc|pill|meth|cocaine|heroin|fentanyl|mdma)\b", re.I),
        ],
    ),
    # message + 威胁/勒索词 → targeted_harassment 增强
    (
        re.compile(r"\bmessage\b", re.I),
        "intent:targeted_harassment",
        [re.compile(r"\b(threaten|extort|blackmail|harm\s+(you|them|him|her)|kill|hurt)\b", re.I)],
    ),
    # write/edit + 伪造/仿冒词 → phishing 增强
    (
        re.compile(r"\b(write|edit)\b", re.I),
        "intent:phishing",
        [re.compile(r"\b(fake|spoof|impersonat|fraudulent)\w*.{0,30}(website|page|form|login|email)\b", re.I)],
    ),
]


def extract_intents(prompt: str, tool_name: str) -> list[str]:
    """从 prompt + tool_name 提取 1-3 个 hypothesized intent 节点。

    规则/启发式实现，不调用 LLM API。

    Args:
        prompt:    用户请求完整文本（可为空字符串）
        tool_name: 工具名称（如 web_search, exec, message 等；可为空字符串）

    Returns:
        list of intent node IDs, 如 ["intent:credential_theft", "intent:phishing"]
        空列表 = 无法推断意图（无关键词命中）
        最多 3 个，按命中证据强度（分数）降序排序。

    设计原则：
    - 高召回：宁可多猜 intent，在 KG 中找不到对应节点时会静默跳过
    - 无 label leakage：完全基于文本内容推断，不读取 ground truth 标签
    - 最多 3 个：避免向 Markov Blanket 注入过多噪声种子
    """
    if not prompt and not tool_name:
        return []

    # 将 tool_name + prompt 合并为单一文本进行匹配
    text = f"{tool_name or ''} {prompt or ''}".strip()
    intent_scores: dict[str, int] = {}

    # 阶段 1：基础关键词规则匹配
    for intent_id, tool_pat, kw_patterns in _INTENT_RULES:
        # 工具过滤：有 tool_pat 时只在该工具下激活
        if tool_pat and not re.search(tool_pat, tool_name or ""):
            continue
        # 统计命中的关键词模式数量作为分数
        hits = sum(1 for p in kw_patterns if p.search(text))
        if hits > 0:
            intent_scores[intent_id] = intent_scores.get(intent_id, 0) + hits

    # 阶段 2：工具-意图增强匹配（所有 hint 命中才触发）
    for tool_pat, intent_id, hint_patterns in _TOOL_INTENT_BOOSTS:
        if not re.search(tool_pat, tool_name or ""):
            continue
        if all(p.search(text) for p in hint_patterns):
            intent_scores[intent_id] = intent_scores.get(intent_id, 0) + 2

    if not intent_scores:
        return []

    # 按分数降序，取 top-3
    sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
    return [intent_id for intent_id, _ in sorted_intents[:3]]
