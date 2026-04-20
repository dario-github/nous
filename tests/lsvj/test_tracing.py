"""tests/lsvj/test_tracing.py — decisive_primitives 反事实追踪测试"""
from __future__ import annotations

import pytest

from nous.lsvj.gate import MockEvaluator
from nous.lsvj.schema import PrimitiveSchema
from nous.lsvj.tracing import GLOBAL_VACUOUS, decisive_primitives


# ── 决定性原语正确识别 ────────────────────────────────────────────────────────


def test_single_prim_true_is_decisive(schema_fixture: PrimitiveSchema) -> None:
    """单原语 True → discharged=True; 翻转 → False → 该原语是决定性原语。"""
    bindings = {"is_inner_circle": True}
    result = decisive_primitives(
        rule_body="is_inner_circle(recipient_id)",
        schema=schema_fixture,
        bindings=bindings,
    )
    assert isinstance(result, list)
    assert "is_inner_circle" in result


def test_two_prims_both_true_both_decisive(schema_fixture: PrimitiveSchema) -> None:
    """两个原语均 True → AND 语义 discharged=True。
    翻转任一 → AND 变 False → 两者均决定性。
    """
    bindings = {
        "is_inner_circle": True,
        "owner_has_directed": True,
    }
    result = decisive_primitives(
        rule_body="is_inner_circle(recipient_id), owner_has_directed(action_id)",
        schema=schema_fixture,
        bindings=bindings,
    )
    assert isinstance(result, list)
    assert "is_inner_circle" in result
    assert "owner_has_directed" in result


def test_discharged_false_returns_empty_list(schema_fixture: PrimitiveSchema) -> None:
    """is_inner_circle=True, owner_has_directed=False → discharged=False → []。
    discharged=False 时无决定性原语可言。
    """
    bindings = {
        "is_inner_circle": True,
        "owner_has_directed": False,
    }
    result = decisive_primitives(
        rule_body="is_inner_circle(recipient_id), owner_has_directed(action_id)",
        schema=schema_fixture,
        bindings=bindings,
    )
    assert result == []


# ── GLOBAL_VACUOUS 路径 ───────────────────────────────────────────────────────


def test_global_vacuous_when_no_primitive_drives_result(
    schema_fixture: PrimitiveSchema,
) -> None:
    """evaluator truth_table 固定返回 True，翻转 bindings 对 evaluator 无影响。
    discharged 恒 True，翻转任一原语后结果不变 → GLOBAL_VACUOUS。
    """
    always_true_ev = MockEvaluator({
        "is_inner_circle": True,
        "owner_has_directed": True,
    })
    # 空 bindings → evaluator 从 truth_table 读，不受 _flip_primitive 影响
    result = decisive_primitives(
        rule_body="is_inner_circle(recipient_id), owner_has_directed(action_id)",
        schema=schema_fixture,
        bindings={},
        evaluator=always_true_ev,
    )
    assert result == GLOBAL_VACUOUS


def test_global_vacuous_constant_is_string() -> None:
    assert isinstance(GLOBAL_VACUOUS, str)
    assert GLOBAL_VACUOUS == "GLOBAL_VACUOUS"


# ── discharged=False 路径 ─────────────────────────────────────────────────────


def test_single_prim_false_returns_empty_list(schema_fixture: PrimitiveSchema) -> None:
    """单原语 False → discharged=False → 返回空列表（不是 GLOBAL_VACUOUS）。"""
    bindings = {"is_inner_circle": False}
    result = decisive_primitives(
        rule_body="is_inner_circle(recipient_id)",
        schema=schema_fixture,
        bindings=bindings,
    )
    assert result == []


# ── 解析失败路径 ───────────────────────────────────────────────────────────────


def test_returns_empty_list_on_parse_error(schema_fixture: PrimitiveSchema) -> None:
    """空规则体 → parse 失败 → 返回空列表。"""
    result = decisive_primitives(
        rule_body="",
        schema=schema_fixture,
        bindings={"is_inner_circle": True},
    )
    assert result == []


# ── 自定义 evaluator 接口 ─────────────────────────────────────────────────────


def test_custom_evaluator_bindings_priority(schema_fixture: PrimitiveSchema) -> None:
    """bindings 优先于 truth_table：翻转 bindings 后 evaluator 读到翻转值。"""
    ev = MockEvaluator({"is_inner_circle": True})
    # bindings 中有 is_inner_circle=True → evaluator 读 bindings → True → discharged=True
    # _flip_primitive → bindings["is_inner_circle"]=False → evaluator 读 False → discharged=False
    result = decisive_primitives(
        rule_body="is_inner_circle(recipient_id)",
        schema=schema_fixture,
        bindings={"is_inner_circle": True},
        evaluator=ev,
    )
    assert isinstance(result, list)
    assert "is_inner_circle" in result
