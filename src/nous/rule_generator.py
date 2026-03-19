"""Nous — LLM → Constraint 自动生成 (E3)

用 LLM 将自然语言安全政策转换为 YAML 约束规则。

核心功能：
  generate_rule()   — 自然语言 → Constraint 对象
  validate_rule()   — 语法+语义+一致性验证
  propose_rules()   — 安全事件日志 → 候选规则列表

安全约束：
  - 自动生成的 verdict 只能是 "confirm"
  - 必须通过 validate_rule() 才能保存
  - 保存到 ontology/constraints/auto/ 目录
  - 所有规则带 source: "auto-generated" 元数据
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import yaml

from nous.constraint_parser import load_constraints, parse_constraint_file
from nous.schema import Constraint

logger = logging.getLogger("nous.rule_generator")

# ── 类型定义 ────────────────────────────────────────────────────────────────

LLMProvider = Callable[[str, int, str], str]
"""LLM 调用协议：(prompt, timeout_ms, model) -> str"""

# ── 默认路径 ────────────────────────────────────────────────────────────────

_CONSTRAINTS_DIR = (
    Path(__file__).parent.parent.parent  # nous/ root
    / "ontology" / "constraints"
)

_AUTO_DIR = _CONSTRAINTS_DIR / "auto"

# ── 验证结果 ────────────────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    """validate_rule() 的返回结果"""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ── Prompt 模板 ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT_TEMPLATE = (
    "You are a constraint rule generator for the Nous safety engine.\n"
    "Your job is to convert natural language security policies into YAML constraint rules.\n\n"
    "## YAML Constraint Format\n\n"
    "Each constraint is a YAML dict with these fields:\n"
    "- id: string (unique identifier, format: AUTO-<CATEGORY>-<slug>)\n"
    "- name: string (human-readable name)\n"
    "- priority: integer (1-100, lower = higher priority; default 75 for auto rules)\n"
    "- enabled: true\n"
    "- trigger: dict describing when to fire (see examples)\n"
    '- verdict: "confirm" (MUST always be "confirm" for auto-generated rules)\n'
    "- reason: string explaining why this rule fires\n"
    "- metadata: dict with extra info\n\n"
    "## Trigger Format\n\n"
    "Triggers match against extracted facts from tool calls. Common patterns:\n"
    "- action_type match: action_type: {{in: [action1, action2]}}\n"
    "- single field match: field_name: value\n"
    "- numeric threshold: field_name: {{gt: number}}\n"
    "- boolean flag: flag_name: true\n"
    "- combined (AND): multiple keys in trigger dict\n\n"
    "## Fact Table Schema\n\n"
    "Facts are key-value pairs extracted from tool calls:\n"
    "- action_type: the type of action (e.g., delete_file, send_message, write_file, upload)\n"
    "- tool_name: name of the tool being called\n"
    "- target: target of the action (file path, channel, URL, etc.)\n"
    "- content: content being sent/written (when applicable)\n"
    "- output_target: where output goes (discord, slack, etc.)\n"
    "- estimated_lines: estimated line count for write operations\n"
    "- url_has_social_pattern: boolean, true if URL matches social media\n"
    "- search_lang: language parameter for search\n"
    "- Additional context-specific facts\n\n"
    "## Output Format\n\n"
    "Return ONLY valid YAML (no markdown fences, no explanation). Example:\n\n"
    "id: AUTO-TIME-no-public-msg-after-hours\n"
    "name: 工作时间外禁止公共频道消息\n"
    "priority: 75\n"
    "enabled: true\n"
    "trigger:\n"
    "  action_type:\n"
    "    in: [send_message]\n"
    "  target_is_public: true\n"
    "  outside_work_hours: true\n"
    "verdict: confirm\n"
    'reason: "禁止在工作时间外发送消息到公共频道"\n'
    "metadata:\n"
    "  source: auto-generated\n"
    '  policy_text: "禁止在工作时间外发送消息到公共频道"\n\n'
    "{examples_section}\n"
)

EXAMPLES_HEADER = """## Existing Rules (for reference)

"""

_GENERATE_USER_TEMPLATE = (
    "Convert the following security policy into a YAML constraint rule.\n\n"
    "Policy: {policy_text}\n\n"
    "Remember:\n"
    '1. verdict MUST be "confirm" (never "allow", "deny", or "block")\n'
    "2. id format: AUTO-<CATEGORY>-<slug>\n"
    '3. metadata must include source: "auto-generated"\n'
    "4. Return ONLY valid YAML, no markdown fences\n"
)

_INCIDENT_SYSTEM_TEMPLATE = (
    "You are a security analyst for the Nous safety engine.\n"
    "Analyze incident logs and propose constraint rules that would have prevented these incidents.\n\n"
    "For each rule, output valid YAML in the same format as above.\n"
    'Separate multiple rules with "---" (YAML document separator).\n\n'
    "Rules:\n"
    '1. verdict MUST always be "confirm"\n'
    "2. id format: AUTO-<CATEGORY>-<slug>\n"
    '3. metadata must include source: "auto-generated"\n'
    "4. Focus on generalizable patterns, not one-off incidents\n"
    '5. Return ONLY valid YAML documents separated by "---"\n\n'
    "{examples_section}\n"
)

_INCIDENT_USER_TEMPLATE = (
    "Analyze these security incidents and propose rules:\n\n"
    "{incidents_text}\n\n"
    "Propose up to {max_rules} generalizable rules that would help catch similar incidents.\n"
)


# ── 辅助函数 ────────────────────────────────────────────────────────────────


def _load_examples(constraints_dir: Optional[Path] = None, max_examples: int = 4) -> str:
    """从现有约束文件中提取 few-shot 示例"""
    cdir = constraints_dir or _CONSTRAINTS_DIR
    if not cdir.exists():
        return ""

    examples = []
    for yaml_file in sorted(cdir.glob("*.yaml"))[:max_examples]:
        try:
            with open(yaml_file, encoding="utf-8") as f:
                content = f.read().strip()
            examples.append(content)
        except Exception:
            continue

    if not examples:
        return ""

    return EXAMPLES_HEADER + "\n---\n".join(examples)


def _parse_yaml_response(raw: str) -> dict:
    """解析 LLM 返回的 YAML，处理常见格式问题"""
    text = raw.strip()

    # 去除 markdown 代码块包裹
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)

    parsed = yaml.safe_load(text)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected YAML dict, got {type(parsed).__name__}")
    return parsed


def _parse_multi_yaml_response(raw: str) -> list[dict]:
    """解析含多个 YAML 文档的 LLM 响应"""
    text = raw.strip()

    # 去除 markdown 代码块
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)

    results = []
    for doc in yaml.safe_load_all(text):
        if isinstance(doc, dict):
            results.append(doc)
    return results


def _enforce_safety(raw_dict: dict, policy_text: str = "") -> dict:
    """强制安全约束：verdict=confirm，source=auto-generated"""
    # 强制 verdict = confirm
    raw_dict["verdict"] = "confirm"

    # 强制 enabled = true
    raw_dict["enabled"] = True

    # 确保 metadata 存在
    if "metadata" not in raw_dict or not isinstance(raw_dict.get("metadata"), dict):
        raw_dict["metadata"] = {}

    raw_dict["metadata"]["source"] = "auto-generated"
    raw_dict["metadata"]["generated_at"] = time.strftime("%Y-%m-%d")

    if policy_text:
        raw_dict["metadata"]["policy_text"] = policy_text

    # 确保 id 以 AUTO- 开头
    rule_id = raw_dict.get("id", "")
    if not rule_id:
        slug = re.sub(r"[^\w]", "-", policy_text[:40]).strip("-").lower()
        raw_dict["id"] = f"AUTO-POLICY-{slug}" if slug else f"AUTO-POLICY-{int(time.time())}"
    elif not rule_id.startswith("AUTO-"):
        raw_dict["id"] = f"AUTO-{rule_id}"

    # 确保必填字段
    if "trigger" not in raw_dict or not isinstance(raw_dict.get("trigger"), dict):
        raw_dict["trigger"] = {}

    if "priority" not in raw_dict:
        raw_dict["priority"] = 75

    if "reason" not in raw_dict:
        raw_dict["reason"] = policy_text or "Auto-generated rule"

    return raw_dict


def _dict_to_constraint(d: dict) -> Constraint:
    """将 dict 转为 Constraint 对象"""
    return Constraint(
        id=d["id"],
        name=d.get("name", ""),
        priority=d.get("priority", 75),
        enabled=d.get("enabled", True),
        trigger=d.get("trigger", {}),
        verdict=d["verdict"],
        reason=d.get("reason", ""),
        rewrite_params=d.get("rewrite_params"),
        metadata=d.get("metadata", {}),
        dialect=d.get("dialect", "cozo"),
        semantics=d.get("semantics"),
    )


# ── 核心 API ───────────────────────────────────────────────────────────────


def generate_rule(
    policy_text: str,
    llm_provider: LLMProvider,
    examples: Optional[list[str]] = None,
    constraints_dir: Optional[Path] = None,
    timeout_ms: int = 30000,
    model: str = "default",
) -> Constraint:
    """从自然语言安全政策生成 Constraint。

    Args:
        policy_text:     自然语言安全政策描述
        llm_provider:    LLM 调用函数 (prompt, timeout_ms, model) -> str
        examples:        额外的 few-shot 示例（YAML 字符串列表）
        constraints_dir: 现有约束目录（用于 few-shot）
        timeout_ms:      LLM 调用超时
        model:           模型名

    Returns:
        Constraint 对象（verdict 强制为 "confirm"）

    Raises:
        ValueError: LLM 返回格式错误或缺少必要字段
    """
    if not policy_text or not policy_text.strip():
        raise ValueError("policy_text cannot be empty")

    # 构建 few-shot 示例
    examples_section = _load_examples(constraints_dir)
    if examples:
        if examples_section:
            examples_section += "\n---\n" + "\n---\n".join(examples)
        else:
            examples_section = EXAMPLES_HEADER + "\n---\n".join(examples)

    system = _SYSTEM_PROMPT_TEMPLATE.format(examples_section=examples_section)
    user = _GENERATE_USER_TEMPLATE.format(policy_text=policy_text)
    prompt = f"{system}\n\n{user}"

    # 调用 LLM
    raw_response = llm_provider(prompt, timeout_ms, model)

    # 解析响应
    try:
        parsed = _parse_yaml_response(raw_response)
    except Exception as e:
        raise ValueError(f"Failed to parse LLM response as YAML: {e}") from e

    # 强制安全约束
    safe_dict = _enforce_safety(parsed, policy_text)

    # 构建 Constraint
    return _dict_to_constraint(safe_dict)


def validate_rule(
    constraint: Constraint,
    existing_constraints: Optional[list[Constraint]] = None,
    constraints_dir: Optional[Path] = None,
) -> ValidationResult:
    """验证自动生成的约束规则。

    三层验证：
    1. 语法验证：字段完整性、类型正确性
    2. 语义验证：trigger 非空、verdict 合法
    3. 一致性检查：与现有规则是否冲突（同 id 不同 verdict）

    Args:
        constraint:            要验证的 Constraint
        existing_constraints:  现有约束列表（可选，用于冲突检测）
        constraints_dir:       现有约束目录（如果 existing_constraints 为空则从这里加载）

    Returns:
        ValidationResult
    """
    errors = []
    warnings = []

    # ── 1. 语法验证 ──
    if not constraint.id:
        errors.append("Missing required field: id")

    if not constraint.id.startswith("AUTO-"):
        warnings.append(f"Auto-generated rule id should start with 'AUTO-': {constraint.id}")

    if not constraint.verdict:
        errors.append("Missing required field: verdict")

    if constraint.verdict != "confirm":
        errors.append(
            f"Auto-generated rules must have verdict='confirm', got '{constraint.verdict}'"
        )

    if not isinstance(constraint.trigger, dict):
        errors.append(f"trigger must be a dict, got {type(constraint.trigger).__name__}")

    if not constraint.trigger:
        errors.append("trigger cannot be empty — rule would never fire")

    if not constraint.reason:
        warnings.append("Rule has no reason — consider adding explanation")

    # ── 2. 语义验证 ──
    meta = constraint.metadata or {}
    if meta.get("source") != "auto-generated":
        warnings.append("metadata.source should be 'auto-generated'")

    # 检查 trigger 值的基本类型合法性
    for key, val in (constraint.trigger or {}).items():
        if val is None:
            errors.append(f"trigger['{key}'] is None — invalid")
        elif isinstance(val, dict):
            # 检查操作符合法性
            valid_ops = {"in", "gt", "lt", "gte", "lte", "eq", "ne", "contains", "not_in"}
            for op in val:
                if op not in valid_ops:
                    warnings.append(
                        f"trigger['{key}'] uses unknown operator '{op}'"
                    )

    # priority 范围检查
    if not (1 <= constraint.priority <= 100):
        warnings.append(f"priority {constraint.priority} outside recommended range [1, 100]")

    # ── 3. 一致性检查 ──
    if existing_constraints is None and constraints_dir:
        try:
            existing_constraints = load_constraints(constraints_dir)
        except Exception:
            existing_constraints = []

    if existing_constraints:
        for existing in existing_constraints:
            if existing.id == constraint.id and existing.verdict != constraint.verdict:
                errors.append(
                    f"Conflict: rule '{constraint.id}' already exists with "
                    f"verdict='{existing.verdict}', new verdict='{constraint.verdict}'"
                )
            elif existing.id == constraint.id:
                warnings.append(
                    f"Rule '{constraint.id}' already exists — will shadow existing"
                )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def propose_rules(
    incident_log: list[dict],
    llm_provider: LLMProvider,
    constraints_dir: Optional[Path] = None,
    max_rules: int = 5,
    timeout_ms: int = 60000,
    model: str = "default",
) -> list[Constraint]:
    """从安全事件日志中提取可泛化的规则。

    Args:
        incident_log:    事件日志列表（每个 dict 含 rule/trigger_type/summary/result 等字段）
        llm_provider:    LLM 调用函数
        constraints_dir: 现有约束目录（用于 few-shot + 冲突检测）
        max_rules:       最多生成的规则数
        timeout_ms:      LLM 调用超时
        model:           模型名

    Returns:
        通过验证的 Constraint 列表（已去除无效规则）
    """
    if not incident_log:
        return []

    # 构建事件摘要
    incidents_text = ""
    for i, inc in enumerate(incident_log[:20], 1):  # 最多送 20 条
        rule = inc.get("rule", "unknown")
        trigger = inc.get("trigger_type", "unknown")
        summary = inc.get("summary", "")
        result = inc.get("result", "unknown")
        incidents_text += (
            f"{i}. [{rule}] trigger={trigger}, result={result}: {summary}\n"
        )

    examples_section = _load_examples(constraints_dir)
    system = _INCIDENT_SYSTEM_TEMPLATE.format(examples_section=examples_section)
    user = _INCIDENT_USER_TEMPLATE.format(
        incidents_text=incidents_text,
        max_rules=max_rules,
    )
    prompt = f"{system}\n\n{user}"

    raw_response = llm_provider(prompt, timeout_ms, model)

    # 解析多个 YAML 文档
    try:
        docs = _parse_multi_yaml_response(raw_response)
    except Exception as e:
        logger.warning("Failed to parse incident response: %s", e)
        return []

    # 加载现有约束用于冲突检测
    existing = None
    if constraints_dir:
        try:
            existing = load_constraints(constraints_dir)
        except Exception:
            existing = []

    results = []
    for doc in docs[:max_rules]:
        try:
            safe = _enforce_safety(doc)
            c = _dict_to_constraint(safe)
            vr = validate_rule(c, existing_constraints=existing)
            if vr.valid:
                results.append(c)
            else:
                logger.info(
                    "Proposed rule %s failed validation: %s", c.id, vr.errors
                )
        except Exception as e:
            logger.warning("Failed to process proposed rule: %s", e)
            continue

    return results


# ── 保存 ───────────────────────────────────────────────────────────────────


def save_rule(
    constraint: Constraint,
    auto_dir: Optional[Path] = None,
) -> Path:
    """将验证通过的规则保存到 auto/ 目录。

    Args:
        constraint: 已通过 validate_rule() 的 Constraint
        auto_dir:   保存目录（默认 ontology/constraints/auto/）

    Returns:
        写入的文件路径

    Raises:
        ValueError: 规则未通过安全检查
    """
    if constraint.verdict != "confirm":
        raise ValueError(
            f"Cannot save rule with verdict='{constraint.verdict}', must be 'confirm'"
        )

    meta = constraint.metadata or {}
    if meta.get("source") != "auto-generated":
        raise ValueError("Cannot save rule without source='auto-generated' metadata")

    target_dir = auto_dir or _AUTO_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_id = re.sub(r"[^\w\-]", "_", constraint.id)[:60]
    filename = f"{safe_id}.yaml"
    filepath = target_dir / filename

    rule_dict = {
        "id": constraint.id,
        "name": constraint.name,
        "priority": constraint.priority,
        "enabled": constraint.enabled,
        "trigger": constraint.trigger,
        "verdict": constraint.verdict,
        "reason": constraint.reason,
        "metadata": constraint.metadata,
    }

    if constraint.rewrite_params:
        rule_dict["rewrite_params"] = constraint.rewrite_params

    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(rule_dict, f, allow_unicode=True, default_flow_style=False)

    logger.info("[rule_generator] Auto rule saved: %s", filepath)
    return filepath
