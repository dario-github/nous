"""tests/lsvj/test_compiler_lark.py — Lark 主解析器 + 正则降级覆盖测试

按规范验证：
  - parse_with_lark 接受 4 条合法 obligation 规则
  - parse_with_lark 正确拒绝格式错误的规则
  - parse_rule(prefer_lark=True) 设置 parsed_by="lark"
  - parse_rule(prefer_lark=False) 使用正则，parsed_by="regex"
  - Lark 不支持的 Cozo 语法（仅规则体，无 obligation 头）→ 降级到正则，parsed_by="regex"
  - _LARK_AVAILABLE=False 时 parse_with_lark 抛出 RuntimeError
"""
from __future__ import annotations

import pytest

import nous.lsvj.compiler as compiler_module
from nous.lsvj.compiler import (
    ParseError,
    ParsedRule,
    parse_rule,
    parse_with_lark,
)


# ── 4 条合法 obligation 规则（与 cozo-lark-fork-decision.md 烟雾测试一致）────────


# 规则 1：单条 Class A 原语（arity=1），头表达式为绑定变量
_RULE_SINGLE_PRIM = (
    "?[discharged] := is_inner_circle(recipient_id), discharged = r1"
)

# 规则 2：两条 Class A 原语，头表达式为 OR
_RULE_TWO_PRIMS_OR = (
    "?[discharged] := is_inner_circle(recipient_id), "
    "owner_has_directed(action_id), discharged = r1 or r2"
)

# 规则 3：Class B 原语（arity=2），头表达式为单绑定变量
_RULE_TWO_ARG_PRIM = (
    "?[discharged] := payload_contains_regex(body_text, secret_pattern), "
    "discharged = r1"
)

# 规则 4：两条原语，头表达式为 AND + NOT
_RULE_AND_NOT = (
    "?[discharged] := is_inner_circle(recipient_id), "
    "owner_has_directed(action_id), discharged = r1 and not r2"
)


# ── parse_with_lark：4 条合法规则 ───────────────────────────────────────────────


def test_lark_parses_single_prim() -> None:
    result = parse_with_lark(_RULE_SINGLE_PRIM)
    assert isinstance(result, ParsedRule)
    assert result.parsed_by == "lark"
    assert len(result.calls) == 1
    assert result.calls[0].prim_id == "is_inner_circle"
    assert result.calls[0].args == ["recipient_id"]


def test_lark_parses_two_prims_or() -> None:
    result = parse_with_lark(_RULE_TWO_PRIMS_OR)
    assert isinstance(result, ParsedRule)
    assert result.parsed_by == "lark"
    assert len(result.calls) == 2
    ids = [c.prim_id for c in result.calls]
    assert "is_inner_circle" in ids
    assert "owner_has_directed" in ids


def test_lark_parses_two_arg_prim() -> None:
    result = parse_with_lark(_RULE_TWO_ARG_PRIM)
    assert isinstance(result, ParsedRule)
    assert result.parsed_by == "lark"
    assert len(result.calls) == 1
    assert result.calls[0].prim_id == "payload_contains_regex"
    assert result.calls[0].args == ["body_text", "secret_pattern"]


def test_lark_parses_and_not_head() -> None:
    result = parse_with_lark(_RULE_AND_NOT)
    assert isinstance(result, ParsedRule)
    assert result.parsed_by == "lark"
    assert len(result.calls) == 2


# ── parse_with_lark：格式错误的规则被拒绝 ───────────────────────────────────────


def test_lark_rejects_missing_parens() -> None:
    """foo_without_paren 不是合法原语调用（缺少括号）→ ParseError。"""
    malformed = "?[discharged] := foo_without_paren, discharged = true"
    result = parse_with_lark(malformed)
    assert isinstance(result, ParseError)
    assert result.stage == "parse"
    assert "lark parse error" in result.message


def test_lark_rejects_empty() -> None:
    result = parse_with_lark("")
    assert isinstance(result, ParseError)
    assert result.stage == "parse"


# ── parse_rule(prefer_lark=True) 设置 parsed_by="lark" ──────────────────────────


def test_parse_rule_prefer_lark_sets_parsed_by_lark() -> None:
    """完整 obligation 形式 → Lark 成功 → parsed_by="lark"。"""
    result = parse_rule(_RULE_SINGLE_PRIM, prefer_lark=True)
    assert isinstance(result, ParsedRule)
    assert result.parsed_by == "lark"


# ── parse_rule(prefer_lark=False) 使用正则，parsed_by="regex" ────────────────────


def test_parse_rule_prefer_regex_sets_parsed_by_regex() -> None:
    """prefer_lark=False → 正则路径 → parsed_by="regex"。"""
    rule_body = "is_inner_circle(recipient_id), owner_has_directed(action_id)"
    result = parse_rule(rule_body, prefer_lark=False)
    assert isinstance(result, ParsedRule)
    assert result.parsed_by == "regex"
    assert len(result.calls) == 2


# ── 降级：Cozo 规则体语法（无 obligation 头）→ 正则，parsed_by="regex" ─────────────


def test_parse_rule_falls_back_to_regex_for_body_only_syntax() -> None:
    """仅规则体（无 ?[discharged] := 头）→ Lark 拒绝 → 降级到正则 → parsed_by="regex"。"""
    body_only = "is_inner_circle(recipient_id), owner_has_directed(action_id)"
    result = parse_rule(body_only, prefer_lark=True)
    assert isinstance(result, ParsedRule)
    assert result.parsed_by == "regex"
    assert len(result.calls) == 2


# ── _LARK_AVAILABLE=False 时 parse_with_lark 抛出 RuntimeError ──────────────────


def test_parse_with_lark_raises_if_lark_not_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """模拟 lark 未安装：_LARK_AVAILABLE=False → RuntimeError。"""
    monkeypatch.setattr(compiler_module, "_LARK_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="lark not installed"):
        parse_with_lark(_RULE_SINGLE_PRIM)
