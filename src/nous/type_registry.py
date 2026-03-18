"""Nous — Object Type Registry (Palantir-inspired Strong Typing)

从现有数据自动推导的 schema + 智能校验。

设计原则（保持智能）：
- required 缺失 → 拒绝写入 / 自动补全（如 name_zh）
- unknown 属性 → 接受但标记 confidence 降低
- schema 可从数据自动推导 + 支持动态扩展
- 定期审计 schema 覆盖率

灵感来源：Palantir Ontology Object Types + Link Types
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PropertySchema:
    """属性定义"""
    name: str
    type: str = "string"  # string, int, float, list, dict
    required: bool = False
    description: str = ""


@dataclass
class ObjectType:
    """对象类型定义（对标 Palantir Object Type）"""
    etype: str
    display_name: str = ""
    display_name_zh: str = ""
    properties: dict[str, PropertySchema] = field(default_factory=dict)
    description: str = ""
    
    @property
    def required_props(self) -> list[str]:
        return [k for k, v in self.properties.items() if v.required]
    
    @property
    def optional_props(self) -> list[str]:
        return [k for k, v in self.properties.items() if not v.required]


@dataclass
class LinkType:
    """关系类型定义（对标 Palantir Link Type）"""
    rtype: str
    display_name_zh: str = ""
    from_types: list[str] = field(default_factory=list)  # 允许的源类型
    to_types: list[str] = field(default_factory=list)     # 允许的目标类型
    description: str = ""


@dataclass
class ValidationResult:
    """校验结果"""
    valid: bool
    errors: list[str] = field(default_factory=list)      # 必须修复
    warnings: list[str] = field(default_factory=list)     # 建议修复
    confidence_penalty: float = 0.0                        # 建议降低的置信度


# ── Registry ──────────────────────────────────────────────────────────────

# 从现有数据统计推导（≥90% 出现率 = required）
OBJECT_TYPES: dict[str, ObjectType] = {
    "attack_tactic": ObjectType(
        etype="attack_tactic",
        display_name="ATT&CK Tactic",
        display_name_zh="ATT&CK 战术",
        properties={
            "name": PropertySchema("name", required=True),
            "name_zh": PropertySchema("name_zh", required=True),
            "mitre_id": PropertySchema("mitre_id", required=True),
            "description": PropertySchema("description", required=True),
            "valid_from": PropertySchema("valid_from"),
        },
    ),
    "attack_technique": ObjectType(
        etype="attack_technique",
        display_name="ATT&CK Technique",
        display_name_zh="ATT&CK 技术",
        properties={
            "name": PropertySchema("name", required=True),
            "name_zh": PropertySchema("name_zh", required=True),
            "mitre_id": PropertySchema("mitre_id", required=True),
            "description": PropertySchema("description", required=True),
            "tactic_id": PropertySchema("tactic_id", required=True),
            "valid_from": PropertySchema("valid_from"),
        },
    ),
    "vulnerability_class": ObjectType(
        etype="vulnerability_class",
        display_name="CWE Vulnerability",
        display_name_zh="CWE 漏洞类",
        properties={
            "name": PropertySchema("name", required=True),
            "name_zh": PropertySchema("name_zh", required=True),
            "cwe_id": PropertySchema("cwe_id", required=True),
            "description": PropertySchema("description", required=True),
            "rank_2024": PropertySchema("rank_2024", "int", required=True),
            "valid_from": PropertySchema("valid_from"),
            "mitigation_hints": PropertySchema("mitigation_hints", "list"),
        },
    ),
    "security_control": ObjectType(
        etype="security_control",
        display_name="Security Control",
        display_name_zh="安全控制措施",
        properties={
            "name": PropertySchema("name", required=True),
            "name_zh": PropertySchema("name_zh", required=True),
            "description": PropertySchema("description", required=True),
            "framework": PropertySchema("framework", required=True),
            "control_id": PropertySchema("control_id"),
            "function_id": PropertySchema("function_id"),
            "level": PropertySchema("level"),
            "theme": PropertySchema("theme"),
            "category_id": PropertySchema("category_id"),
        },
    ),
    "regulation": ObjectType(
        etype="regulation",
        display_name="Regulation / Framework",
        display_name_zh="法规/框架",
        properties={
            "full_name": PropertySchema("full_name", required=True),
            "name_zh": PropertySchema("name_zh", required=True),
            "publisher": PropertySchema("publisher", required=True),
            "scope": PropertySchema("scope", required=True),
            "year": PropertySchema("year", "int", required=True),
            "version": PropertySchema("version"),
            "url": PropertySchema("url"),
        },
    ),
    "policy": ObjectType(
        etype="policy",
        display_name="Policy Rule",
        display_name_zh="策略规则",
        properties={
            "description": PropertySchema("description", required=True),
            "name_zh": PropertySchema("name_zh", required=True),
            "rule": PropertySchema("rule", required=True),
            "source_rule": PropertySchema("source_rule", required=True),
            "applies_to": PropertySchema("applies_to", required=True),
            "valid_from": PropertySchema("valid_from"),
        },
    ),
    "person": ObjectType(
        etype="person",
        display_name="Person",
        display_name_zh="人物",
        properties={
            "name": PropertySchema("name", required=True),
            "name_zh": PropertySchema("name_zh", required=True),
            "valid_from": PropertySchema("valid_from"),
        },
    ),
    "project": ObjectType(
        etype="project",
        display_name="Project",
        display_name_zh="项目",
        properties={
            "name": PropertySchema("name", required=True),
            "name_zh": PropertySchema("name_zh"),
            "valid_from": PropertySchema("valid_from"),
            "status": PropertySchema("status"),
        },
    ),
    "tool": ObjectType(
        etype="tool",
        display_name="Tool / Capability",
        display_name_zh="工具",
        properties={
            "name": PropertySchema("name", required=True),
            "name_zh": PropertySchema("name_zh", required=True),
            "category": PropertySchema("category", required=True),
            "call_count": PropertySchema("call_count", "int"),
        },
    ),
    "concept": ObjectType(
        etype="concept",
        display_name="Concept",
        display_name_zh="概念",
        properties={
            "name_zh": PropertySchema("name_zh", required=True),
            "count": PropertySchema("count", "int"),
        },
        description="Shadow/temporal patterns, abstract concepts",
    ),
    "category": ObjectType(
        etype="category",
        display_name="Category",
        display_name_zh="分类",
        properties={
            "name_zh": PropertySchema("name_zh", required=True),
            "description": PropertySchema("description"),
            "severity": PropertySchema("severity"),
        },
    ),
    "temporal": ObjectType(
        etype="temporal",
        display_name="Temporal Pattern",
        display_name_zh="时间模式",
        properties={
            "name_zh": PropertySchema("name_zh", required=True),
            "count": PropertySchema("count", "int", required=True),
        },
    ),
    "constraint": ObjectType(
        etype="constraint",
        display_name="Constraint Rule",
        display_name_zh="约束规则",
        properties={
            "name_zh": PropertySchema("name_zh", required=True),
            "rule_id": PropertySchema("rule_id", required=True),
            "trigger_count": PropertySchema("trigger_count", "int"),
        },
    ),
}

# ── Link Type Registry ────────────────────────────────────────────────────

LINK_TYPES: dict[str, LinkType] = {
    "USES_TECHNIQUE": LinkType("USES_TECHNIQUE", "使用技术",
        from_types=["attack_tactic"], to_types=["attack_technique"]),
    "MITIGATED_BY": LinkType("MITIGATED_BY", "被缓解",
        from_types=["vulnerability_class", "attack_technique"],
        to_types=["security_control"]),
    "MAPPED_TO": LinkType("MAPPED_TO", "映射到",
        from_types=["security_control", "regulation"],
        to_types=["security_control", "regulation"]),
    "EXPLOITS": LinkType("EXPLOITS", "利用",
        from_types=["attack_technique"], to_types=["vulnerability_class"]),
    "IMPLEMENTS": LinkType("IMPLEMENTS", "实现",
        from_types=["policy"], to_types=["regulation", "security_control"]),
    "REGULATES": LinkType("REGULATES", "监管",
        from_types=["regulation"], to_types=["security_control", "policy"]),
    "CO_OCCURS": LinkType("CO_OCCURS", "共现",
        from_types=[], to_types=[]),  # 任意类型
    "RELATED_TO": LinkType("RELATED_TO", "相关",
        from_types=[], to_types=[]),
    "WORKS_ON": LinkType("WORKS_ON", "参与",
        from_types=["person"], to_types=["project"]),
}


# ── Validation Engine ─────────────────────────────────────────────────────

def validate_entity(etype: str, properties: dict) -> ValidationResult:
    """校验实体属性是否符合 schema。
    
    智能策略：
    - required 缺失 → error
    - unknown 属性 → warning + confidence penalty
    - 未注册类型 → warning（允许写入，新类型自动发现）
    """
    result = ValidationResult(valid=True)
    
    ot = OBJECT_TYPES.get(etype)
    if not ot:
        result.warnings.append(f"Unknown etype '{etype}' — not in registry. "
                              f"Consider adding it after stabilization.")
        result.confidence_penalty = 0.1
        return result
    
    # Check required
    for key in ot.required_props:
        if key not in properties or properties[key] is None or properties[key] == '':
            result.valid = False
            result.errors.append(f"Missing required property '{key}' for {etype}")
    
    # Check unknown keys
    known_keys = set(ot.properties.keys())
    for key in properties:
        if key not in known_keys:
            result.warnings.append(f"Unknown property '{key}' for {etype}")
            result.confidence_penalty = max(result.confidence_penalty, 0.05)
    
    return result


def validate_relation(rtype: str, from_etype: str, to_etype: str) -> ValidationResult:
    """校验关系类型是否合法。"""
    result = ValidationResult(valid=True)
    
    lt = LINK_TYPES.get(rtype)
    if not lt:
        result.warnings.append(f"Unknown rtype '{rtype}' — not in registry.")
        result.confidence_penalty = 0.05
        return result
    
    if lt.from_types and from_etype not in lt.from_types:
        result.warnings.append(
            f"{rtype}: source type '{from_etype}' not in allowed {lt.from_types}")
        result.confidence_penalty = 0.1
    
    if lt.to_types and to_etype not in lt.to_types:
        result.warnings.append(
            f"{rtype}: target type '{to_etype}' not in allowed {lt.to_types}")
        result.confidence_penalty = 0.1
    
    return result


def audit_coverage(db) -> dict:
    """审计 schema 覆盖率——每种类型有多少实体满足 required 属性。"""
    import json
    rows = db.db.run('?[etype, props] := *entity{etype, props}')
    
    report = {}
    for etype, ot in OBJECT_TYPES.items():
        etype_rows = [(json.loads(r['props']) if isinstance(r['props'], str) 
                       else (r['props'] or {}))
                      for _, r in rows.iterrows() if r['etype'] == etype]
        total = len(etype_rows)
        if total == 0:
            report[etype] = {"total": 0, "valid": 0, "coverage": 0}
            continue
        
        valid = 0
        for props in etype_rows:
            ok = all(props.get(k) for k in ot.required_props)
            if ok:
                valid += 1
        
        report[etype] = {
            "total": total,
            "valid": valid,
            "coverage": round(valid / total * 100, 1),
            "display_name_zh": ot.display_name_zh,
        }
    
    return report
