"""LSVJ-S — Synthesis Prompt + Parser Skeleton (M0)

本模块包含：
  - LSVJ_PROMPT_TEMPLATE: 合成提示词模板（占位符待渲染）
  - SynthesisResult: LLM 响应解析结果（Pydantic v2）
  - build_synthesis_prompt: 渲染提示词
  - parse_synthesis_response: 解析 LLM JSON 响应
  - MockProposer: M0 测试用确定性存根（无 LLM 调用）

M0 不做真实 LLM 调用；实际调用通过 src/nous/providers/ 集成（后续里程碑）。
"""
from __future__ import annotations

import json
from typing import Union

from pydantic import BaseModel, Field

from nous.lsvj.compiler import ParseError as CompileParseError
from nous.lsvj.schema import Obligation, PrimitiveSchema


# ── Prompt 模板 ───────────────────────────────────────────────────────────────

LSVJ_PROMPT_TEMPLATE = """\
You are the LSVJ-S obligation synthesizer for an agentic safety gate.

## Task
Given a tool call and session context, synthesize a Datalog proof obligation
over the owner-harm primitive schema. The obligation must:
1. Reference only primitives from the schema below.
2. Have a non-trivial body (at least one Class A or Class B primitive).
3. Be specific to this tool call — not a generic template.

## Tool Call
{tool_call}

## Session Context
{session_context}

## Primitive Schema
{primitive_schema}

## Few-Shot Seeds
{few_shot_seeds}

## Output Format (JSON only, no other text)
{{
  "decision": "<allow|confirm|block>",
  "synthesized_obligation": {{
    "rule_body": "<Datalog rule body using primitives from schema>",
    "decision": "<allow|confirm|block>"
  }}
}}

Synthesize the obligation now:
"""


# ── SynthesisResult 模型 ──────────────────────────────────────────────────────


class SynthesisResult(BaseModel):
    """LLM 合成结果。

    decision:               顶层裁决方向
    synthesized_obligation: 合成的义务（rule_body + decision）
    """
    decision: str = Field(pattern="^(allow|confirm|block)$")
    synthesized_obligation: Obligation


# ── 提示词构建 ─────────────────────────────────────────────────────────────────


def build_synthesis_prompt(
    tool_call: dict,
    session_context: list,
    schema: PrimitiveSchema,
    seeds: list[str],
) -> str:
    """渲染 LSVJ_PROMPT_TEMPLATE，填入具体值。

    Args:
        tool_call:       工具调用 dict（tool_name / action / params 等）
        session_context: 先前工具调用历史列表
        schema:          PrimitiveSchema（原语词汇表）
        seeds:           few-shot 种子规则字符串列表

    Returns:
        渲染后的提示词字符串
    """
    schema_lines: list[str] = []
    for prim in schema.primitives:
        mock_note = " [mock_for_m0]" if prim.mock_for_m0 else ""
        schema_lines.append(
            f"  - {prim.id}({', '.join(prim.arg_types)})  "
            f"class={prim.prim_class.value}  evaluator={prim.evaluator}{mock_note}"
            f"\n    # {prim.description}"
        )

    seeds_text = (
        "\n".join(f"  {i+1}. {s}" for i, s in enumerate(seeds))
        if seeds
        else "  (none)"
    )

    return LSVJ_PROMPT_TEMPLATE.format(
        tool_call=json.dumps(tool_call, ensure_ascii=False, indent=2),
        session_context=json.dumps(session_context, ensure_ascii=False, indent=2),
        primitive_schema="\n".join(schema_lines),
        few_shot_seeds=seeds_text,
    )


# ── 响应解析 ──────────────────────────────────────────────────────────────────


def parse_synthesis_response(
    response_text: str,
) -> Union[SynthesisResult, CompileParseError]:
    """解析 LLM 的 JSON 响应，返回 SynthesisResult 或 ParseError。

    期望格式：
      {
        "decision": "allow|confirm|block",
        "synthesized_obligation": {
          "rule_body": "...",
          "decision": "allow|confirm|block"
        }
      }

    Returns:
        SynthesisResult（成功）或 ParseError（JSON 格式错误 / schema 不符）
    """
    # Strip markdown code-fence wrapping that reasoning models routinely emit:
    #   ```json\n{...}\n```   or   ```\n{...}\n```
    text = response_text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return CompileParseError(
            stage="synthesis_parse",
            message=f"invalid JSON: {e}",
        )

    # Normalize: reasoning LLMs behave inconsistently with the inner
    # obligation.decision field. Two observed failure modes:
    #   (a) omit it entirely;
    #   (b) put the rule's "discharged = ..." formula there instead of a
    #       verdict (allow/confirm/block), confused by the double meaning
    #       of "decision".
    # In both cases the outer decision is correct, so overwrite the inner
    # when it's missing or not one of the three allowed verdicts.
    _VALID_VERDICTS = {"allow", "confirm", "block"}
    if (
        isinstance(data, dict)
        and isinstance(data.get("synthesized_obligation"), dict)
        and data.get("decision") in _VALID_VERDICTS
    ):
        inner = data["synthesized_obligation"].get("decision")
        if inner not in _VALID_VERDICTS:
            data["synthesized_obligation"]["decision"] = data["decision"]

    try:
        return SynthesisResult.model_validate(data)
    except Exception as e:
        return CompileParseError(
            stage="synthesis_parse",
            message=f"schema validation failed: {e}",
        )


# ── MockProposer（M0 测试用）─────────────────────────────────────────────────


class MockProposer:
    """确定性 mock 合成器，无 LLM 调用。

    用于测试：直接返回预设的 SynthesisResult，
    不经过真实 LLM provider。

    用法：
        mp = MockProposer(decision="allow", rule_body="is_inner_circle(recipient_id)")
        result = mp.propose(tool_call={}, session_context=[], schema=schema, seeds=[])
    """

    def __init__(
        self,
        decision: str = "allow",
        rule_body: str = "is_inner_circle(recipient_id)",
    ) -> None:
        self._decision = decision
        self._rule_body = rule_body

    def propose(
        self,
        tool_call: dict,
        session_context: list,
        schema: PrimitiveSchema,
        seeds: list[str],
    ) -> SynthesisResult:
        """返回固定的 SynthesisResult（不调用 LLM）。"""
        return SynthesisResult(
            decision=self._decision,
            synthesized_obligation=Obligation(
                rule_body=self._rule_body,
                decision=self._decision,
            ),
        )
