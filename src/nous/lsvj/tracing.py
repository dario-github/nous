"""LSVJ-S — Decisive-Primitive Tracing (M0)

诊断工具：对于一个 discharged=True 的规则，识别哪些原语的单次反事实翻转
会使 discharged 变为 False。用于 Claim 2.3 paired-McNemar 因果分析。

注意：这是诊断工具，不是 gate 组件。
"""
from __future__ import annotations

from typing import Union

from nous.lsvj.compiler import ParsedRule, ParseError, parse_rule
from nous.lsvj.gate import Evaluator, MockEvaluator, _execute_rule, _flip_primitive
from nous.lsvj.schema import PrimitiveSchema

# 全局空洞哨兵值：无任何原语驱动 discharged，规则空洞成立
GLOBAL_VACUOUS = "GLOBAL_VACUOUS"


def decisive_primitives(
    rule_body: str,
    schema: PrimitiveSchema,
    bindings: dict,
    evaluator: Union[Evaluator, None] = None,
) -> Union[list[str], str]:
    """识别驱动 discharged=True 的决定性原语。

    对于 discharged=True 的规则，逐一翻转每个原语的返回值，
    检查哪些翻转会使 discharged 变为 False。

    Args:
        rule_body:  Datalog 规则体字符串
        schema:     PrimitiveSchema（当前仅用于接口一致性，M0 解析不依赖 schema）
        bindings:   运行时绑定 dict
        evaluator:  可插拔评估器（None → MockEvaluator 读取 bindings）

    Returns:
        list[str]:       决定性原语 id 列表（≥1 个原语驱动 discharged=True）
        "GLOBAL_VACUOUS": 无任何单原语翻转改变 discharged（空洞成立）
        [] (空列表):      规则 discharged=False，或 parse 失败

    设计选择：discharged=False 时返回空列表而非 GLOBAL_VACUOUS，
    因为空洞性只在"允许"路径上有研究意义。
    """
    if evaluator is None:
        evaluator = MockEvaluator()

    # 解析规则体
    parse_result = parse_rule(rule_body)
    if isinstance(parse_result, ParseError):
        return []

    parsed: ParsedRule = parse_result

    # 基准求值
    discharged_real = _execute_rule(parsed, bindings, evaluator)

    if not discharged_real:
        # 规则未成立，无决定性原语可言
        return []

    # 对每个原语做单次反事实翻转
    decisive: list[str] = []
    for call in parsed.calls:
        flipped = _flip_primitive(bindings, call.prim_id)
        if _execute_rule(parsed, flipped, evaluator) != discharged_real:
            decisive.append(call.prim_id)

    if not decisive:
        # 无任何单原语翻转改变结果 → 空洞成立
        return GLOBAL_VACUOUS

    return decisive
