"""LSVJ-S — Compile-Time Gate Stages b.1–b.3 (M0)

三个编译期检查：
  b.1 parse_rule      — 正则解析 Datalog 规则体，提取原语调用 token 列表
  b.2 type_check      — 验证每个原语调用引用已声明原语且 arity 匹配
  b.3 syntactic_non_triviality — 规则体必须包含 ≥1 个 A/B 类原语，且头部不是字面 true

这三个阶段合并为 compile_check()，任一失败即 fail-closed → confirm。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Union

from nous.lsvj.schema import PrimitiveClass, PrimitiveSchema


# ── 数据结构 ─────────────────────────────────────────────────────────────────


@dataclass
class PrimitiveCall:
    """解析出的单条原语调用 token。"""
    prim_id: str
    args: list[str]


@dataclass
class ParsedRule:
    """parse_rule 成功结果：原语调用列表 + 原始规则文本。"""
    calls: list[PrimitiveCall]
    raw: str


@dataclass
class ParseError:
    """parse_rule / compile_check 失败原因。"""
    stage: str          # "parse" | "type_check" | "syntactic"
    message: str


@dataclass
class TypeCheckResult:
    """type_check 结果。"""
    ok: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class CompileCheckResult:
    """compile_check 综合结果。"""
    passed: bool
    parse_ok: bool = False
    type_ok: bool = False
    syntactic_ok: bool = False
    errors: list[str] = field(default_factory=list)
    parsed_rule: Union[ParsedRule, None] = None


# ── b.1 parse_rule ────────────────────────────────────────────────────────────

# 单条原语调用模式：identifier(arg1, arg2, ...)
_CALL_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)"   # primitive id
    r"\s*\("
    r"([^)]*)"                      # args (anything except closing paren)
    r"\)"
)

# 检测字面 true 规则头（e.g. "discharged = true" 或 "true_for_x := true"）
_LITERAL_TRUE_RE = re.compile(
    r"(?:discharged\s*=\s*true|true_for_\w+\s*:=\s*true)",
    re.IGNORECASE,
)

# 跳过非原语关键字（出现在 discharged 表达式右侧）
_SKIP_IDS = frozenset({"not", "true", "false", "and", "or"})


def parse_rule(rule_text: str) -> Union[ParsedRule, ParseError]:
    """b.1: 从规则体文本提取原语调用 token 列表。

    格式：primitive_id(arg1, arg2, ...), primitive_id2(arg), ...
    忽略 discharged = ... 赋值部分中的 not/true/false 等关键字。

    返回 ParsedRule（成功）或 ParseError（失败）。
    """
    if not rule_text or not rule_text.strip():
        return ParseError(stage="parse", message="empty rule text")

    calls: list[PrimitiveCall] = []
    for m in _CALL_RE.finditer(rule_text):
        prim_id = m.group(1)
        if prim_id in _SKIP_IDS:
            continue
        raw_args = m.group(2).strip()
        args = [a.strip() for a in raw_args.split(",") if a.strip()] if raw_args else []
        calls.append(PrimitiveCall(prim_id=prim_id, args=args))

    if not calls:
        return ParseError(
            stage="parse",
            message=f"no primitive calls found in rule: {rule_text!r}",
        )

    return ParsedRule(calls=calls, raw=rule_text)


# ── b.2 type_check ────────────────────────────────────────────────────────────


def type_check(
    parsed_rule: ParsedRule,
    schema: PrimitiveSchema,
) -> TypeCheckResult:
    """b.2: 验证每个原语调用引用已声明原语且 arity 匹配。

    M0 仅做 arity count-check，不做完整类型推断。
    """
    errors: list[str] = []

    for call in parsed_rule.calls:
        prim = schema.by_id(call.prim_id)
        if prim is None:
            errors.append(f"undefined primitive: {call.prim_id!r}")
            continue
        if len(call.args) != prim.arity:
            errors.append(
                f"arity mismatch for {call.prim_id!r}: "
                f"expected {prim.arity}, got {len(call.args)}"
            )

    return TypeCheckResult(ok=len(errors) == 0, errors=errors)


# ── b.3 syntactic_non_triviality ──────────────────────────────────────────────


def syntactic_non_triviality(parsed_rule: ParsedRule) -> bool:
    """b.3 (schema-free variant): 规则体在句法上非平凡。

    返回 False（拒绝）的条件：
      - 规则体包含字面 `discharged = true` 或 `true_for_x := true`
      - 解析出零条原语调用

    此变体不检查 A/B 类原语（无 schema）。
    在 compile_check 内部使用带 schema 的完整版本。
    """
    if _LITERAL_TRUE_RE.search(parsed_rule.raw):
        return False
    if not parsed_rule.calls:
        return False
    return True


def _syntactic_non_triviality_with_schema(
    parsed_rule: ParsedRule,
    schema: PrimitiveSchema,
) -> bool:
    """带 schema 的句法非平凡检查：要求 ≥1 个 A/B 类原语。

    仅在 compile_check 内部（type_check 通过后）调用。
    """
    if _LITERAL_TRUE_RE.search(parsed_rule.raw):
        return False

    for call in parsed_rule.calls:
        prim = schema.by_id(call.prim_id)
        if prim is not None and prim.prim_class in (PrimitiveClass.A, PrimitiveClass.B):
            return True

    # 零个 A/B 原语 → 句法平凡
    return False


# ── compile_check ─────────────────────────────────────────────────────────────


def compile_check(rule_text: str, schema: PrimitiveSchema) -> CompileCheckResult:
    """综合 b.1–b.3 三阶段检查。

    任一阶段失败 → passed=False，errors 列表说明原因。
    全部通过 → passed=True，parsed_rule 携带解析结果。
    """
    # b.1 parse
    parse_result = parse_rule(rule_text)
    if isinstance(parse_result, ParseError):
        return CompileCheckResult(
            passed=False,
            parse_ok=False,
            errors=[f"[parse] {parse_result.message}"],
        )

    # b.2 type_check
    tc = type_check(parse_result, schema)
    if not tc.ok:
        return CompileCheckResult(
            passed=False,
            parse_ok=True,
            type_ok=False,
            errors=[f"[type_check] {e}" for e in tc.errors],
            parsed_rule=parse_result,
        )

    # b.3 syntactic non-triviality（带 schema）
    if not _syntactic_non_triviality_with_schema(parse_result, schema):
        return CompileCheckResult(
            passed=False,
            parse_ok=True,
            type_ok=True,
            syntactic_ok=False,
            errors=["[syntactic] rule body is trivially true or contains no Class A/B primitives"],
            parsed_rule=parse_result,
        )

    return CompileCheckResult(
        passed=True,
        parse_ok=True,
        type_ok=True,
        syntactic_ok=True,
        parsed_rule=parse_result,
    )
