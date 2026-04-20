"""LSVJ-S — 4-Stage Admission Gate (M0)

b.1–b.3 通过 compile_check 处理；本模块实现 b.4 compound 阶段：
  - perturbation-sensitive: N 次随机扰动中 ≥1 次让 discharged 翻转
  - has-decisive-primitive: ∃ 原语，单次翻转其返回值导致 discharged 翻转

评估器接口可插拔（MockEvaluator 用于测试，Cozo evaluator 是后续里程碑）。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Protocol, Union

from nous.lsvj.compiler import CompileCheckResult, ParsedRule, compile_check
from nous.lsvj.schema import PrimitiveSchema


# ── 评估器协议 ────────────────────────────────────────────────────────────────


class Evaluator(Protocol):
    """可插拔原语评估器接口。

    evaluate(prim_id, args, bindings) → 返回布尔值（原语是否成立）。
    bindings 可包含任意 key-value（来自 tool_call 上下文）。
    """

    def evaluate(
        self,
        prim_id: str,
        args: list[str],
        bindings: dict,
    ) -> bool: ...


# ── MockEvaluator（M0 测试用）────────────────────────────────────────────────


class MockEvaluator:
    """确定性 mock 评估器。

    优先读取 bindings["<prim_id>"]，其次读取初始化时的 truth_table，
    找不到时默认返回 False。

    用法：
        ev = MockEvaluator({"is_inner_circle": True, "owner_has_directed": False})
        result = ev.evaluate("is_inner_circle", ["alice"], {})
    """

    def __init__(self, truth_table: dict[str, bool] | None = None) -> None:
        self._table: dict[str, bool] = truth_table or {}

    def evaluate(
        self,
        prim_id: str,
        args: list[str],
        bindings: dict,
    ) -> bool:
        if prim_id in bindings:
            val = bindings[prim_id]
            if isinstance(val, bool):
                return val
        return bool(self._table.get(prim_id, False))


# ── 规则执行器 ────────────────────────────────────────────────────────────────


def _execute_rule(
    parsed_rule: ParsedRule,
    bindings: dict,
    evaluator: Evaluator,
) -> bool:
    """对 parsed_rule 中所有原语调用求值，返回 discharged。

    M0 语义：discharged = AND(evaluate(prim) for prim in calls)
    更复杂的析取/否定表达式在 M1+ 通过 Cozo 执行。
    """
    for call in parsed_rule.calls:
        if not evaluator.evaluate(call.prim_id, call.args, bindings):
            return False
    return True


def _perturb_bindings(
    bindings: dict,
    parsed_rule: ParsedRule,
    rng: random.Random,
) -> dict:
    """生成扰动后的 bindings：随机选择一个原语，翻转其布尔返回值。"""
    if not parsed_rule.calls:
        return dict(bindings)

    call = rng.choice(parsed_rule.calls)
    perturbed = dict(bindings)
    current = bool(perturbed.get(call.prim_id, False))
    perturbed[call.prim_id] = not current
    return perturbed


def _flip_primitive(bindings: dict, prim_id: str) -> dict:
    """翻转单个原语的绑定值（用于 has-decisive-primitive 检查）。"""
    flipped = dict(bindings)
    current = bool(flipped.get(prim_id, False))
    flipped[prim_id] = not current
    return flipped


# ── 结果结构 ──────────────────────────────────────────────────────────────────


@dataclass
class GateVerdict:
    """单次原语评估结果快照（供外部调用方使用）。"""
    discharged: bool
    primitive_values: dict[str, bool] = field(default_factory=dict)


@dataclass
class AdmissionResult:
    """admit_rule 返回值。

    admitted:            全部四阶段通过
    reasons:             失败原因列表（admitted=True 时为空）
    decisive_primitives: 决定性原语 id 列表（admitted=True 时填充）
    discharged:          规则对原始 bindings 的求值结果
    compile_result:      compile_check 详细结果
    """
    admitted: bool
    reasons: list[str] = field(default_factory=list)
    decisive_primitives: list[str] = field(default_factory=list)
    discharged: bool = False
    compile_result: Union[CompileCheckResult, None] = None


# ── 主 API ────────────────────────────────────────────────────────────────────


def admit_rule(
    rule_text: str,
    schema: PrimitiveSchema,
    bindings: dict,
    evaluator: Union[Evaluator, None] = None,
    N: int = 5,
    seed: int = 0,
) -> AdmissionResult:
    """LSVJ-S 4 阶段准入检查。

    Args:
        rule_text:  Datalog 规则体字符串
        schema:     PrimitiveSchema（原语词汇表）
        bindings:   运行时绑定 dict，key 为 primitive_id，value 为布尔值
        evaluator:  可插拔评估器（None → 使用空 MockEvaluator 读取 bindings）
        N:          扰动敏感性检查次数（默认 5）
        seed:       随机种子（保证可重现）

    Returns:
        AdmissionResult

    Gate 逻辑：
      1. compile_check (b.1–b.3)
      2. 执行规则得到 discharged_real
      3. b.4-A: perturbation-sensitive — N 次随机扰动 ≥1 次翻转 discharged
      4. b.4-B: has-decisive-primitive — ∃ 原语单次翻转导致 discharged 翻转
      全部通过 → admitted=True
    """
    if evaluator is None:
        evaluator = MockEvaluator()

    # Step 1: compile_check (b.1–b.3)
    cc = compile_check(rule_text, schema)
    if not cc.passed:
        return AdmissionResult(
            admitted=False,
            reasons=cc.errors,
            compile_result=cc,
        )

    parsed = cc.parsed_rule
    assert parsed is not None  # compile_check passed → parsed is always set

    # Step 2: 执行规则，得到基准 discharged
    discharged_real = _execute_rule(parsed, bindings, evaluator)

    # Step 3: b.4-A — perturbation-sensitive
    rng = random.Random(seed)
    perturbation_sensitive = False
    for _ in range(N):
        perturbed = _perturb_bindings(bindings, parsed, rng)
        if _execute_rule(parsed, perturbed, evaluator) != discharged_real:
            perturbation_sensitive = True
            break

    if not perturbation_sensitive:
        return AdmissionResult(
            admitted=False,
            reasons=["[b.4-A] rule is perturbation-invariant across N perturbations"],
            discharged=discharged_real,
            compile_result=cc,
        )

    # Step 4: b.4-B — has-decisive-primitive
    decisive: list[str] = []
    for call in parsed.calls:
        flipped = _flip_primitive(bindings, call.prim_id)
        if _execute_rule(parsed, flipped, evaluator) != discharged_real:
            decisive.append(call.prim_id)

    if not decisive:
        return AdmissionResult(
            admitted=False,
            reasons=["[b.4-B] no single primitive flip changes discharged (no decisive primitive)"],
            discharged=discharged_real,
            compile_result=cc,
        )

    return AdmissionResult(
        admitted=True,
        decisive_primitives=decisive,
        discharged=discharged_real,
        compile_result=cc,
    )
