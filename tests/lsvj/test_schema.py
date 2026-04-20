"""tests/lsvj/test_schema.py — PrimitiveSchema YAML 加载 + 查找辅助方法测试"""
from __future__ import annotations

import pytest

from nous.lsvj.schema import (
    Obligation,
    Primitive,
    PrimitiveClass,
    PrimitiveSchema,
    load_schema_from_yaml,
)


# ── YAML 加载 ─────────────────────────────────────────────────────────────────


def test_load_schema_returns_primitive_schema(schema_fixture: PrimitiveSchema) -> None:
    assert isinstance(schema_fixture, PrimitiveSchema)


def test_load_schema_has_six_primitives(schema_fixture: PrimitiveSchema) -> None:
    assert len(schema_fixture.primitives) == 6


def test_load_schema_all_are_primitive_instances(schema_fixture: PrimitiveSchema) -> None:
    for p in schema_fixture.primitives:
        assert isinstance(p, Primitive)


def test_load_schema_file_not_found_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_schema_from_yaml("/nonexistent/path/schema.yaml")


# ── 类别分区 ──────────────────────────────────────────────────────────────────


def test_schema_has_two_class_a(schema_fixture: PrimitiveSchema) -> None:
    class_a = schema_fixture.by_class(PrimitiveClass.A)
    assert len(class_a) == 2


def test_schema_has_two_class_b(schema_fixture: PrimitiveSchema) -> None:
    class_b = schema_fixture.by_class(PrimitiveClass.B)
    assert len(class_b) == 2


def test_schema_has_two_class_c(schema_fixture: PrimitiveSchema) -> None:
    class_c = schema_fixture.by_class(PrimitiveClass.C)
    assert len(class_c) == 2


def test_class_a_ids(schema_fixture: PrimitiveSchema) -> None:
    ids = {p.id for p in schema_fixture.by_class(PrimitiveClass.A)}
    assert ids == {"is_inner_circle", "owner_has_directed"}


def test_class_b_ids(schema_fixture: PrimitiveSchema) -> None:
    ids = {p.id for p in schema_fixture.by_class(PrimitiveClass.B)}
    assert ids == {"payload_contains_regex", "external_url"}


def test_class_c_ids(schema_fixture: PrimitiveSchema) -> None:
    ids = {p.id for p in schema_fixture.by_class(PrimitiveClass.C)}
    assert ids == {"body_reveals_inner_relation", "authority_coercion_present"}


# ── lookup helpers ────────────────────────────────────────────────────────────


def test_by_id_found(schema_fixture: PrimitiveSchema) -> None:
    p = schema_fixture.by_id("is_inner_circle")
    assert p is not None
    assert p.id == "is_inner_circle"
    assert p.prim_class == PrimitiveClass.A
    assert p.arity == 1


def test_by_id_not_found_returns_none(schema_fixture: PrimitiveSchema) -> None:
    assert schema_fixture.by_id("nonexistent_primitive") is None


def test_ids_returns_all_six(schema_fixture: PrimitiveSchema) -> None:
    ids = schema_fixture.ids()
    assert len(ids) == 6
    assert "is_inner_circle" in ids
    assert "payload_contains_regex" in ids
    assert "body_reveals_inner_relation" in ids


# ── Primitive フィールド ──────────────────────────────────────────────────────


def test_class_c_mock_for_m0_true(schema_fixture: PrimitiveSchema) -> None:
    for p in schema_fixture.by_class(PrimitiveClass.C):
        assert p.mock_for_m0 is True


def test_class_a_mock_for_m0_false(schema_fixture: PrimitiveSchema) -> None:
    for p in schema_fixture.by_class(PrimitiveClass.A):
        assert p.mock_for_m0 is False


def test_payload_contains_regex_arity_2(schema_fixture: PrimitiveSchema) -> None:
    p = schema_fixture.by_id("payload_contains_regex")
    assert p is not None
    assert p.arity == 2
    assert p.arg_types == ["text", "pattern"]


# ── Obligation モデル ─────────────────────────────────────────────────────────


def test_obligation_valid() -> None:
    ob = Obligation(rule_body="is_inner_circle(recipient_id)", decision="allow")
    assert ob.decision == "allow"


def test_obligation_invalid_decision_raises() -> None:
    with pytest.raises(Exception):
        Obligation(rule_body="is_inner_circle(x)", decision="unknown_verdict")
