"""tests/lsvj/test_gate.py — admit_rule 4-stage gate 测试"""
from __future__ import annotations

import pytest

from nous.lsvj.gate import AdmissionResult, GateVerdict, MockEvaluator, admit_rule
from nous.lsvj.schema import PrimitiveSchema


# ── (a) 有效规则，扰动敏感，已准入 ──────────────────────────────────────────


def test_admit_valid_perturbation_sensitive_rule(schema_fixture: PrimitiveSchema) -> None:
    """is_inner_circle=True, owner_has_directed=True → discharged=True.
    翻转任一原语 → discharged=False → 扰动敏感 + 有决定性原语 → admitted=True。
    """
    bindings = {
        "is_inner_circle": True,
        "owner_has_directed": True,
    }
    result = admit_rule(
        rule_text="is_inner_circle(recipient_id), owner_has_directed(action_id)",
        schema=schema_fixture,
        bindings=bindings,
    )
    assert result.admitted is True
    assert result.discharged is True
    assert len(result.decisive_primitives) > 0
    assert result.reasons == []


def test_admit_single_prim_true_is_admitted(schema_fixture: PrimitiveSchema) -> None:
    """单原语 True → discharged=True; 翻转 → False → 敏感且 decisive → admitted。"""
    bindings = {"is_inner_circle": True}
    result = admit_rule(
        rule_text="is_inner_circle(recipient_id)",
        schema=schema_fixture,
        bindings=bindings,
    )
    assert result.admitted is True
    assert "is_inner_circle" in result.decisive_primitives


def test_admit_single_prim_false_is_admitted(schema_fixture: PrimitiveSchema) -> None:
    """单原语 False → discharged=False; 翻转 → True → 扰动敏感 + decisive → admitted。"""
    bindings = {"is_inner_circle": False}
    result = admit_rule(
        rule_text="is_inner_circle(recipient_id)",
        schema=schema_fixture,
        bindings=bindings,
    )
    assert result.admitted is True
    assert "is_inner_circle" in result.decisive_primitives


def test_admit_result_compile_result_attached(schema_fixture: PrimitiveSchema) -> None:
    bindings = {"is_inner_circle": True}
    result = admit_rule(
        rule_text="is_inner_circle(recipient_id)",
        schema=schema_fixture,
        bindings=bindings,
    )
    assert result.compile_result is not None
    assert result.compile_result.passed is True


# ── (b) 空洞/無效規則，在編譯期階段被拒絕 ───────────────────────────────────


def test_admit_rejects_empty_rule(schema_fixture: PrimitiveSchema) -> None:
    """空规则体 → b.1 parse 失败 → admitted=False。"""
    result = admit_rule(
        rule_text="",
        schema=schema_fixture,
        bindings={},
    )
    assert result.admitted is False
    assert any("parse" in r.lower() for r in result.reasons)


def test_admit_rejects_vacuous_true_body(schema_fixture: PrimitiveSchema) -> None:
    """discharged = true 字面量 → b.3 syntactic 失败 → admitted=False。
    规则体包含 is_inner_circle(x) 但 raw 中有 discharged = true → 平凡。
    """
    from nous.lsvj.compiler import ParsedRule, PrimitiveCall
    from nous.lsvj.gate import _execute_rule, MockEvaluator
    # 直接测试 compile_check 对含 'discharged = true' 字面的规则拒绝
    from nous.lsvj.compiler import compile_check
    cc = compile_check("is_inner_circle(x), discharged = true", schema_fixture)
    assert cc.passed is False
    assert cc.syntactic_ok is False


def test_admit_rejects_undefined_primitive(schema_fixture: PrimitiveSchema) -> None:
    """未声明原语 → b.2 type_check 失败 → admitted=False。"""
    result = admit_rule(
        rule_text="ghost_prim(x)",
        schema=schema_fixture,
        bindings={"ghost_prim": True},
    )
    assert result.admitted is False
    assert any("type_check" in r for r in result.reasons)


def test_admit_rejects_only_class_c_rule(schema_fixture: PrimitiveSchema) -> None:
    """仅含 Class C 原语 → b.3 syntactic 失败（无 A/B 原语）→ admitted=False。"""
    result = admit_rule(
        rule_text="body_reveals_inner_relation(text, entity_id, result)",
        schema=schema_fixture,
        bindings={"body_reveals_inner_relation": True},
    )
    assert result.admitted is False
    assert any("syntactic" in r for r in result.reasons)


# ── (c) 扰动不敏感/无决定性原语，在 b.4 阶段被拒绝 ──────────────────────────


def test_admit_rejects_when_both_primitives_false(schema_fixture: PrimitiveSchema) -> None:
    """两个原语均 False → AND 语义 discharged=False。
    扰动：翻转一个 → 另一个仍 False → AND 仍 False → 扰动不敏感 → b.4-A 失败。
    """
    bindings = {
        "is_inner_circle": False,
        "owner_has_directed": False,
    }
    result = admit_rule(
        rule_text="is_inner_circle(recipient_id), owner_has_directed(action_id)",
        schema=schema_fixture,
        bindings=bindings,
        N=10,
        seed=42,
    )
    assert result.admitted is False
    assert any("b.4-A" in r or "perturbation" in r.lower() for r in result.reasons)


def test_admit_rejects_perturbation_invariant_rule(schema_fixture: PrimitiveSchema) -> None:
    """构造一个扰动不敏感场景：使用 MockEvaluator 忽略 bindings，始终返回固定值。
    evaluator 始终返回 True → 翻转 bindings 无效 → discharged 恒 True → 不敏感。
    """
    # evaluator 的 truth_table 覆盖 bindings，始终返回 True
    always_true_ev = MockEvaluator({
        "is_inner_circle": True,
        "owner_has_directed": True,
    })
    # bindings 中翻转不影响 evaluator（evaluator 从 truth_table 读，不从 bindings 读
    # 当 prim_id 不在 bindings 时）
    # 为了让 evaluator 忽略 bindings 翻转，我们用空 bindings 并让 truth_table 固定
    result = admit_rule(
        rule_text="is_inner_circle(recipient_id), owner_has_directed(action_id)",
        schema=schema_fixture,
        bindings={},  # 空 bindings → evaluator 从 truth_table 读 → 恒 True
        evaluator=always_true_ev,
        N=5,
        seed=0,
    )
    # discharged 恒 True，翻转 bindings 对 evaluator 无影响（truth_table 优先）
    # → 扰动不敏感 → b.4-A 失败
    assert result.admitted is False
    assert any("b.4-A" in r or "perturbation" in r.lower() for r in result.reasons)


# ── MockEvaluator 直接测试 ────────────────────────────────────────────────────


def test_mock_evaluator_reads_bindings() -> None:
    ev = MockEvaluator()
    assert ev.evaluate("some_prim", [], {"some_prim": True}) is True
    assert ev.evaluate("some_prim", [], {"some_prim": False}) is False


def test_mock_evaluator_reads_truth_table() -> None:
    ev = MockEvaluator({"my_prim": True})
    assert ev.evaluate("my_prim", [], {}) is True
    assert ev.evaluate("missing", [], {}) is False


def test_mock_evaluator_bindings_override_truth_table() -> None:
    ev = MockEvaluator({"my_prim": True})
    assert ev.evaluate("my_prim", [], {"my_prim": False}) is False


# ── GateVerdict 结构 ──────────────────────────────────────────────────────────


def test_gate_verdict_instantiation() -> None:
    v = GateVerdict(discharged=True, primitive_values={"is_inner_circle": True})
    assert v.discharged is True
    assert v.primitive_values["is_inner_circle"] is True
