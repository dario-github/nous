"""Nous — Intent Extractor (Phase 4: Intent Decomposition)

从请求 prompt + tool_calls 中提取结构化意图事实。

核心思想：不让 LLM 判断 "是否有害"（难，准确率 ~70-90%），
而让 LLM 做 "意图分类"（易，准确率 ~95%+）。

分类比判断容易，因为：
- 判断需要应用安全策略（LLM 的安全策略和我们的不一定一致）
- 分类只需要理解语义（LLM 的核心能力）

输出 IntentFact，供 Datalog 推理。
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Optional, Protocol


# ── 数据结构 ──────────────────────────────────────────────────────────────


@dataclass
class IntentFact:
    """从请求中提取的结构化意图。

    goal:           行为目标的语义标签
    target_scope:   "self" | "known_contacts" | "public" | "specific_person" | "system"
    content_nature: "creative" | "factual" | "promotional" | "supportive" |
                    "harmful" | "deceptive" | "neutral"
    beneficiary:    "self" | "others" | "community" | "attacker" | "unknown"
    """
    goal: str
    target_scope: str = "unknown"
    content_nature: str = "neutral"
    beneficiary: str = "unknown"
    latency_ms: float = 0.0
    raw_response: str = ""
    error: Optional[str] = None


# ── Goal Taxonomy ────────────────────────────────────────────────────────

BENIGN_GOALS = frozenset({
    # Creative / Artistic
    "create_art", "sell_art", "share_creative_work",
    # Social / Supportive
    "share_achievement", "celebrate_success", "fan_appreciation",
    "support_cause", "advocacy", "encourage_volunteering",
    # Professional / Academic
    "submit_own_work", "share_research", "professional_communication",
    "backup_data", "system_administration",
    # Personal
    "personal_communication", "share_experience", "seek_help",
    "organize_event", "plan_travel",
    # Commercial
    "sell_product", "advertise_service", "customer_support",
    # Informational
    "share_news", "factual_correction", "educational_content",
})

HARMFUL_GOALS = frozenset({
    # Violence / Harm
    "create_weapon", "cause_physical_harm", "threaten_person",
    "plan_attack", "enable_terrorism",
    # Cyber
    "create_malware", "hack_system", "steal_data",
    "deploy_ransomware", "bypass_security",
    # Deception / Manipulation
    "spread_disinformation", "create_propaganda", "impersonate_person",
    "academic_fraud", "financial_fraud", "phishing",
    # Exploitation
    "harass_person", "stalk_person", "blackmail",
    "distribute_csam", "exploit_minor",
    # Hate
    "spread_hate", "incite_violence", "discriminate_group",
    # Drugs
    "manufacture_drugs", "sell_drugs", "distribute_drugs",
})

# Goals that need context to determine safety
AMBIGUOUS_GOALS = frozenset({
    "send_mass_message", "post_on_social_media", "share_content",
    "automate_process", "collect_data", "access_system",
})


# ── Prompt Template ──────────────────────────────────────────────────────

_EXTRACTION_PROMPT = """You are an intent classifier. Given a user request and the tools it would use, extract the PRIMARY GOAL as a structured fact.

DO NOT judge whether the request is harmful or safe. Only classify the intent.

## Request
{prompt}

## Tools Used
{tools}

## Instructions
Respond with EXACTLY this JSON format:
```json
{{
  "goal": "<one of the known goals, or a new descriptive_snake_case label>",
  "target_scope": "<self|known_contacts|public|specific_person|system>",
  "content_nature": "<creative|factual|promotional|supportive|harmful|deceptive|neutral>",
  "beneficiary": "<self|others|community|attacker|unknown>"
}}
```

Known benign goals: create_art, sell_art, share_creative_work, share_achievement, celebrate_success, fan_appreciation, support_cause, advocacy, encourage_volunteering, submit_own_work, share_research, professional_communication, backup_data, system_administration, personal_communication, share_experience, seek_help, sell_product, advertise_service, share_news, factual_correction, educational_content

Known harmful goals: create_malware, hack_system, steal_data, deploy_ransomware, bypass_security, spread_disinformation, create_propaganda, impersonate_person, academic_fraud, financial_fraud, phishing, harass_person, stalk_person, blackmail, distribute_csam, spread_hate, incite_violence, discriminate_group, manufacture_drugs, sell_drugs

If the goal doesn't fit any known label, create a descriptive one like "organize_event" or "generate_fake_review".

Respond with ONLY the JSON, no explanation."""


# ── LLM Provider Protocol ────────────────────────────────────────────────


class LLMProvider(Protocol):
    def __call__(self, prompt: str, timeout_ms: int, model: str) -> str: ...


# ── Intent Extraction ────────────────────────────────────────────────────


def _parse_response(raw: str) -> dict:
    """从 LLM 响应中提取 JSON。"""
    # Try to find JSON in code block
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # Try bare JSON
    m = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    raise ValueError(f"No JSON found in response: {raw[:200]}")


def extract_intent(
    prompt: str,
    tool_names: list[str],
    provider: LLMProvider,
    model: str = "default",
    timeout_ms: int = 5000,
) -> IntentFact:
    """提取请求的结构化意图。

    Args:
        prompt: 用户的完整请求文本
        tool_names: 请求中使用的工具名列表
        provider: LLM 调用接口
        model: 模型标识符
        timeout_ms: 超时（毫秒）

    Returns:
        IntentFact，包含结构化意图字段。
        提取失败时返回 error 字段非空的 IntentFact。
    """
    filled_prompt = _EXTRACTION_PROMPT.format(
        prompt=prompt[:2000],  # 截断过长的 prompt
        tools=", ".join(tool_names),
    )

    t0 = time.monotonic()
    try:
        raw = provider(filled_prompt, timeout_ms, model)
        latency = (time.monotonic() - t0) * 1000

        parsed = _parse_response(raw)
        return IntentFact(
            goal=parsed.get("goal", "unknown"),
            target_scope=parsed.get("target_scope", "unknown"),
            content_nature=parsed.get("content_nature", "neutral"),
            beneficiary=parsed.get("beneficiary", "unknown"),
            latency_ms=latency,
            raw_response=raw[:500],
        )
    except Exception as e:
        latency = (time.monotonic() - t0) * 1000
        return IntentFact(
            goal="unknown",
            error=str(e)[:200],
            latency_ms=latency,
        )


# ── Verdict from Intent ──────────────────────────────────────────────────


def intent_verdict(intent: IntentFact) -> tuple[str, str]:
    """基于 intent fact 推断 verdict。

    Returns:
        (verdict, reason) 其中 verdict 是 "allow" | "block" | "confirm" | "unknown"
    """
    if intent.error:
        return ("unknown", f"Intent extraction failed: {intent.error}")

    goal = intent.goal.lower().strip()

    # 1. 明确的 benign goal
    if goal in BENIGN_GOALS:
        return ("allow", f"Benign goal: {goal}")

    # 2. 明确的 harmful goal
    if goal in HARMFUL_GOALS:
        return ("block", f"Harmful goal: {goal}")

    # 3. Ambiguous goal — 用 content_nature 辅助判断
    if intent.content_nature in ("harmful", "deceptive"):
        return ("block", f"Ambiguous goal '{goal}' with harmful content nature")

    if intent.content_nature in ("creative", "factual", "supportive", "promotional"):
        if intent.beneficiary in ("self", "others", "community"):
            return ("allow", f"Ambiguous goal '{goal}' with benign content ({intent.content_nature}) and benign beneficiary ({intent.beneficiary})")

    # 4. 真的无法判断
    return ("confirm", f"Uncertain intent: goal={goal}, content={intent.content_nature}, beneficiary={intent.beneficiary}")
