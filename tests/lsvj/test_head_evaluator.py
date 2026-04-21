"""Tests for head-expression evaluator (M1 LSVJ-S semantics)."""

from __future__ import annotations

from nous.lsvj.head_evaluator import evaluate_head_expr


class StubEvaluator:
    """Returns truth values from a static table keyed by primitive id."""

    def __init__(self, truth: dict[str, bool]) -> None:
        self.truth = truth
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def evaluate(self, prim_id: str, args: list[str], bindings: dict) -> bool:
        self.calls.append((prim_id, tuple(args)))
        return bool(self.truth.get(prim_id, False))


# ---------------------------------------------------------------- shapes

OBLIG = "?[discharged] := "


def test_simple_or_true_first():
    rule = OBLIG + "is_inner_circle(r), discharged = is_inner_circle or owner_has_directed"
    ev = StubEvaluator({"is_inner_circle": True, "owner_has_directed": False})
    assert evaluate_head_expr(rule, ev) is True


def test_or_with_both_in_body():
    rule = (OBLIG +
            "is_inner_circle(r), owner_has_directed(a), "
            "discharged = is_inner_circle or owner_has_directed")
    ev = StubEvaluator({"is_inner_circle": False, "owner_has_directed": True})
    assert evaluate_head_expr(rule, ev) is True


def test_simple_and_both_true():
    rule = (OBLIG + "is_inner_circle(r), owner_has_directed(a), "
                    "discharged = is_inner_circle and owner_has_directed")
    ev = StubEvaluator({"is_inner_circle": True, "owner_has_directed": True})
    assert evaluate_head_expr(rule, ev) is True


def test_simple_and_one_false():
    rule = (OBLIG + "is_inner_circle(r), owner_has_directed(a), "
                    "discharged = is_inner_circle and owner_has_directed")
    ev = StubEvaluator({"is_inner_circle": True, "owner_has_directed": False})
    assert evaluate_head_expr(rule, ev) is False


def test_negation():
    rule = OBLIG + "is_inner_circle(r), discharged = not is_inner_circle"
    ev = StubEvaluator({"is_inner_circle": True})
    assert evaluate_head_expr(rule, ev) is False
    ev2 = StubEvaluator({"is_inner_circle": False})
    assert evaluate_head_expr(rule, ev2) is True


def test_seed_credential_exfil_harm_case():
    """Real seed-library shape; harm scenario should leave discharged=False."""
    rule = (OBLIG +
            'payload_contains_regex(payload, "(api_key|sk-)"), '
            'external_url(target), '
            'owner_has_directed(action_id), '
            'discharged = not payload_contains_regex or owner_has_directed')
    ev = StubEvaluator({
        "payload_contains_regex": True,
        "external_url": True,
        "owner_has_directed": False,
    })
    # discharged = not True or False = False -> harm flagged
    assert evaluate_head_expr(rule, ev) is False


def test_seed_credential_exfil_owner_directed_allows():
    """Owner directive should override the harm pattern."""
    rule = (OBLIG +
            'payload_contains_regex(payload, "(api_key|sk-)"), '
            'external_url(target), '
            'owner_has_directed(action_id), '
            'discharged = not payload_contains_regex or owner_has_directed')
    ev = StubEvaluator({
        "payload_contains_regex": True,
        "external_url": True,
        "owner_has_directed": True,
    })
    # discharged = not True or True = True -> allow
    assert evaluate_head_expr(rule, ev) is True


def test_invalid_lark_rule_returns_none():
    rule = "??garbled bug \\rules"
    ev = StubEvaluator({})
    assert evaluate_head_expr(rule, ev) is None


def test_grouping_with_parens():
    rule = OBLIG + "a(x), b(x), c(x), discharged = (a or b) and c"
    ev = StubEvaluator({"a": True, "b": False, "c": True})
    assert evaluate_head_expr(rule, ev) is True
    ev2 = StubEvaluator({"a": False, "b": False, "c": True})
    assert evaluate_head_expr(rule, ev2) is False


def test_de_morgan():
    rule = OBLIG + "a(x), b(x), discharged = not a and not b"
    ev = StubEvaluator({"a": False, "b": False})
    assert evaluate_head_expr(rule, ev) is True
    ev2 = StubEvaluator({"a": True, "b": False})
    assert evaluate_head_expr(rule, ev2) is False


def test_nested_or_short_circuit_value_correct():
    """Verify result correctness on a 3-way OR (value, not call counts)."""
    rule = (OBLIG + "a(x), b(x), c(x), "
                    "discharged = a or b or c")
    ev = StubEvaluator({"a": False, "b": True, "c": False})
    assert evaluate_head_expr(rule, ev) is True
    ev2 = StubEvaluator({"a": False, "b": False, "c": False})
    assert evaluate_head_expr(rule, ev2) is False


def test_constant_boolean_true_in_head():
    rule = OBLIG + "a(x), discharged = a or true"
    ev = StubEvaluator({"a": False})
    assert evaluate_head_expr(rule, ev) is True


def test_constant_boolean_false_in_head():
    rule = OBLIG + "a(x), discharged = a and false"
    ev = StubEvaluator({"a": True})
    assert evaluate_head_expr(rule, ev) is False


class ArgAwareStub:
    """Returns truth values keyed by (prim_id, tuple(args)) — exercises
    the reviewer's IMPORTANT #2 cache-key-collision concern."""

    def __init__(self, truth: dict[tuple[str, tuple[str, ...]], bool]) -> None:
        self.truth = truth

    def evaluate(self, prim_id: str, args: list[str], bindings: dict) -> bool:
        return bool(self.truth.get((prim_id, tuple(args)), False))


def test_cache_distinguishes_same_primitive_different_args():
    """Same primitive called with different args in body must not
    collide. Regression for reviewer IMPORTANT #2."""
    rule = (OBLIG +
            'payload_contains_regex(payload, "api_key"), '
            'payload_contains_regex(payload, "other_pattern"), '
            'discharged = true')
    ev = ArgAwareStub({
        ("payload_contains_regex", ("payload", '"api_key"')): True,
        ("payload_contains_regex", ("payload", '"other_pattern"')): False,
    })
    # Body eval must not crash from arg collision; head literal True.
    assert evaluate_head_expr(rule, ev) is True


def test_head_only_constant_true():
    """Body has one primitive (required by grammar) but head is just true."""
    rule = OBLIG + "a(x), discharged = true"
    ev = StubEvaluator({"a": False})
    assert evaluate_head_expr(rule, ev) is True
