"""tests/lsvj/test_compiler.py — parse_rule / type_check / syntactic_non_triviality / compile_check"""
from __future__ import annotations

import pytest

from nous.lsvj.compiler import (
    CompileCheckResult,
    ParseError,
    ParsedRule,
    PrimitiveCall,
    TypeCheckResult,
    compile_check,
    parse_rule,
    syntactic_non_triviality,
    type_check,
)
from nous.lsvj.schema import PrimitiveSchema


# ── parse_rule — valid ────────────────────────────────────────────────────────


def test_parse_single_call() -> None:
    result = parse_rule("is_inner_circle(recipient_id)")
    assert isinstance(result, ParsedRule)
    assert len(result.calls) == 1
    assert result.calls[0].prim_id == "is_inner_circle"
    assert result.calls[0].args == ["recipient_id"]


def test_parse_two_calls() -> None:
    result = parse_rule(
        "is_inner_circle(recipient_id), owner_has_directed(action_id)"
    )
    assert isinstance(result, ParsedRule)
    assert len(result.calls) == 2
    ids = [c.prim_id for c in result.calls]
    assert "is_inner_circle" in ids
    assert "owner_has_directed" in ids


def test_parse_two_arg_call() -> None:
    result = parse_rule("payload_contains_regex(body_text, secret_pattern)")
    assert isinstance(result, ParsedRule)
    assert result.calls[0].prim_id == "payload_contains_regex"
    assert len(result.calls[0].args) == 2


def test_parse_skips_not_keyword() -> None:
    # discharged 赋值表达式中的 not 不应产生原语调用
    result = parse_rule(
        "is_inner_circle(recipient_id), "
        "discharged = not is_inner_circle(recipient_id)"
    )
    assert isinstance(result, ParsedRule)
    prim_ids = [c.prim_id for c in result.calls]
    assert "is_inner_circle" in prim_ids
    assert "not" not in prim_ids


# ── parse_rule — malformed ────────────────────────────────────────────────────


def test_parse_empty_string_returns_error() -> None:
    result = parse_rule("")
    assert isinstance(result, ParseError)
    assert result.stage == "parse"


def test_parse_whitespace_only_returns_error() -> None:
    result = parse_rule("   ")
    assert isinstance(result, ParseError)


def test_parse_no_calls_returns_error() -> None:
    # 无函数调用语法的规则体
    result = parse_rule("discharged = true")
    assert isinstance(result, ParseError)


# ── type_check ────────────────────────────────────────────────────────────────


def test_type_check_valid(schema_fixture: PrimitiveSchema) -> None:
    parsed = parse_rule("is_inner_circle(recipient_id)")
    assert isinstance(parsed, ParsedRule)
    tc = type_check(parsed, schema_fixture)
    assert tc.ok is True
    assert tc.errors == []


def test_type_check_undefined_primitive(schema_fixture: PrimitiveSchema) -> None:
    parsed = parse_rule("undefined_prim(x)")
    assert isinstance(parsed, ParsedRule)
    tc = type_check(parsed, schema_fixture)
    assert tc.ok is False
    assert any("undefined primitive" in e for e in tc.errors)


def test_type_check_wrong_arity(schema_fixture: PrimitiveSchema) -> None:
    # is_inner_circle arity=1; pass 2 args
    parsed = parse_rule("is_inner_circle(arg1, arg2)")
    assert isinstance(parsed, ParsedRule)
    tc = type_check(parsed, schema_fixture)
    assert tc.ok is False
    assert any("arity mismatch" in e for e in tc.errors)


def test_type_check_multiple_errors(schema_fixture: PrimitiveSchema) -> None:
    parsed = parse_rule("bad_prim(x), is_inner_circle(a, b)")
    assert isinstance(parsed, ParsedRule)
    tc = type_check(parsed, schema_fixture)
    assert tc.ok is False
    assert len(tc.errors) == 2


# ── syntactic_non_triviality ──────────────────────────────────────────────────


def test_syntactic_non_triviality_valid_rule() -> None:
    parsed = parse_rule("is_inner_circle(recipient_id)")
    assert isinstance(parsed, ParsedRule)
    assert syntactic_non_triviality(parsed) is True


def test_syntactic_literal_discharged_true_rejected() -> None:
    # construct a ParsedRule with literal true in raw text manually
    from nous.lsvj.compiler import PrimitiveCall, ParsedRule
    parsed = ParsedRule(
        calls=[PrimitiveCall(prim_id="is_inner_circle", args=["x"])],
        raw="is_inner_circle(x), discharged = true",
    )
    assert syntactic_non_triviality(parsed) is False


def test_syntactic_true_for_x_pattern_rejected() -> None:
    from nous.lsvj.compiler import PrimitiveCall, ParsedRule
    parsed = ParsedRule(
        calls=[PrimitiveCall(prim_id="is_inner_circle", args=["x"])],
        raw="true_for_x := true",
    )
    assert syntactic_non_triviality(parsed) is False


# ── compile_check — integration ───────────────────────────────────────────────


def test_compile_check_passes_valid_rule(schema_fixture: PrimitiveSchema) -> None:
    result = compile_check(
        "is_inner_circle(recipient_id), owner_has_directed(action_id)",
        schema_fixture,
    )
    assert result.passed is True
    assert result.parse_ok is True
    assert result.type_ok is True
    assert result.syntactic_ok is True
    assert result.parsed_rule is not None


def test_compile_check_fails_empty(schema_fixture: PrimitiveSchema) -> None:
    result = compile_check("", schema_fixture)
    assert result.passed is False
    assert result.parse_ok is False


def test_compile_check_fails_undefined_primitive(schema_fixture: PrimitiveSchema) -> None:
    result = compile_check("nonexistent_prim(x)", schema_fixture)
    assert result.passed is False
    assert result.parse_ok is True
    assert result.type_ok is False


def test_compile_check_fails_wrong_arity(schema_fixture: PrimitiveSchema) -> None:
    result = compile_check("is_inner_circle(a, b, c)", schema_fixture)
    assert result.passed is False
    assert result.type_ok is False


def test_compile_check_fails_only_class_c(schema_fixture: PrimitiveSchema) -> None:
    # body_reveals_inner_relation is Class C arity=3 — no A/B → syntactic failure
    result = compile_check(
        "body_reveals_inner_relation(text, entity_id, result)",
        schema_fixture,
    )
    assert result.passed is False
    assert result.parse_ok is True
    assert result.type_ok is True
    assert result.syntactic_ok is False


def test_compile_check_errors_list_nonempty_on_failure(
    schema_fixture: PrimitiveSchema,
) -> None:
    result = compile_check("bad_prim(x)", schema_fixture)
    assert result.passed is False
    assert len(result.errors) > 0
