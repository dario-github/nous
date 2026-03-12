"""Nous — Verdict 路由器 (M2.4)

将约束匹配结果路由到最终 Verdict。

优先级（数字越大越高）：
  block(5) > confirm(4) > require(3) > warn(2) > rewrite(1) > delegate(0)

多规则命中时取最高优先级的 Verdict。
"""
from dataclasses import dataclass, field
from typing import Optional

from nous.schema import Constraint


# ── 优先级映射 ─────────────────────────────────────────────────────────────

_VERDICT_PRIORITY: dict[str, int] = {
    "block": 5,
    "confirm": 4,
    "require": 3,
    "warn": 2,
    "rewrite": 1,
    "transform": 1,   # transform 与 rewrite 同级
    "delegate": 0,
    "allow": -1,      # allow 最低，兜底
}


# ── 数据结构 ───────────────────────────────────────────────────────────────


@dataclass
class MatchResult:
    """单条约束的匹配结果"""
    constraint: Constraint
    matched: bool
    fact_bindings: dict = field(default_factory=dict)


@dataclass
class Verdict:
    """
    最终裁决。

    action:         block / confirm / require / warn / rewrite / delegate / allow
    rule_id:        触发裁决的规则 ID（多规则命中时为最高优先级规则）
    reason:         裁决原因（来自 Constraint.reason）
    rewrite_params: 重写参数（仅 rewrite/transform 时有值）
    all_matched:    所有命中的规则 ID 列表（用于 proof_trace）
    """
    action: str
    rule_id: str
    reason: str
    rewrite_params: Optional[dict] = None
    all_matched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "rule_id": self.rule_id,
            "reason": self.reason,
            "rewrite_params": self.rewrite_params,
            "all_matched": self.all_matched,
        }


# ── 核心路由函数 ───────────────────────────────────────────────────────────


def route_verdict(matched_constraints: list[MatchResult]) -> Verdict:
    """
    从命中的约束列表中选出最终 Verdict。

    优先级：block > confirm > require > warn > rewrite > delegate
    未命中任何约束 → allow
    """
    # 筛选实际命中的约束
    hits = [m for m in matched_constraints if m.matched]

    if not hits:
        return Verdict(
            action="allow",
            rule_id="",
            reason="无约束命中，放行",
            all_matched=[],
        )

    # 按优先级排序（高 → 低）
    hits.sort(
        key=lambda m: _VERDICT_PRIORITY.get(m.constraint.verdict, 0),
        reverse=True,
    )

    top = hits[0]
    verdict_action = top.constraint.verdict

    # transform → 统一为 rewrite
    if verdict_action == "transform":
        verdict_action = "rewrite"

    return Verdict(
        action=verdict_action,
        rule_id=top.constraint.id,
        reason=top.constraint.reason,
        rewrite_params=top.constraint.rewrite_params,
        all_matched=[m.constraint.id for m in hits],
    )


# ── 约束匹配器 ─────────────────────────────────────────────────────────────


def match_constraint(constraint: Constraint, facts: dict) -> MatchResult:
    """
    检查 facts 是否触发 constraint。

    trigger 支持格式：
      action_type: write_file                  → 精确匹配
      action_type:
        in: [delete_file, modify_config]       → 列表包含匹配
      estimated_lines:
        gt: 400                                → 大于比较
      url_has_social_pattern: true             → 布尔字段匹配
      search_lang: zh                          → 精确匹配
      output_target: discord                   → 精确匹配（同时满足所有 trigger 字段）
    """
    if not constraint.enabled:
        return MatchResult(constraint=constraint, matched=False)

    trigger = constraint.trigger
    if not trigger:
        return MatchResult(constraint=constraint, matched=False)

    bindings: dict = {}

    for key, condition in trigger.items():
        fact_val = facts.get(key)

        # 处理复合条件（dict 格式）
        if isinstance(condition, dict):
            # in: [...]
            if "in" in condition:
                allowed = condition["in"]
                if fact_val not in allowed:
                    return MatchResult(constraint=constraint, matched=False)
                bindings[key] = fact_val

            # gt: N
            elif "gt" in condition:
                threshold = condition["gt"]
                if not (isinstance(fact_val, (int, float)) and fact_val > threshold):
                    return MatchResult(constraint=constraint, matched=False)
                bindings[key] = fact_val

            # lt: N
            elif "lt" in condition:
                threshold = condition["lt"]
                if not (isinstance(fact_val, (int, float)) and fact_val < threshold):
                    return MatchResult(constraint=constraint, matched=False)
                bindings[key] = fact_val

            # contains: "str"
            elif "contains" in condition:
                substr = condition["contains"]
                if not (isinstance(fact_val, str) and substr in fact_val):
                    return MatchResult(constraint=constraint, matched=False)
                bindings[key] = fact_val

            else:
                # 未知 condition 格式，跳过
                pass

        # 简单值匹配
        else:
            # 布尔值
            if isinstance(condition, bool):
                if bool(fact_val) != condition:
                    return MatchResult(constraint=constraint, matched=False)
            else:
                if fact_val != condition:
                    return MatchResult(constraint=constraint, matched=False)
            bindings[key] = fact_val

    return MatchResult(
        constraint=constraint,
        matched=True,
        fact_bindings=bindings,
    )


def match_all_constraints(
    constraints: list[Constraint],
    facts: dict,
) -> list[MatchResult]:
    """对所有约束执行匹配，返回完整结果列表（包含未命中的）"""
    return [match_constraint(c, facts) for c in constraints]
