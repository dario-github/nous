"""tests/lsvj/test_synthesis.py — synthesis prompt + parser + MockProposer 测试"""
from __future__ import annotations

import json

import pytest

from nous.lsvj.compiler import ParseError
from nous.lsvj.schema import PrimitiveSchema
from nous.lsvj.synthesis import (
    LSVJ_PROMPT_TEMPLATE,
    MockProposer,
    SynthesisResult,
    build_synthesis_prompt,
    parse_synthesis_response,
)


# ── LSVJ_PROMPT_TEMPLATE ──────────────────────────────────────────────────────


def test_prompt_template_is_string() -> None:
    assert isinstance(LSVJ_PROMPT_TEMPLATE, str)
    assert len(LSVJ_PROMPT_TEMPLATE) > 100


def test_prompt_template_has_required_placeholders() -> None:
    assert "{tool_call}" in LSVJ_PROMPT_TEMPLATE
    assert "{session_context}" in LSVJ_PROMPT_TEMPLATE
    assert "{primitive_schema}" in LSVJ_PROMPT_TEMPLATE
    assert "{few_shot_seeds}" in LSVJ_PROMPT_TEMPLATE


def test_prompt_template_mentions_output_format() -> None:
    assert "decision" in LSVJ_PROMPT_TEMPLATE
    assert "synthesized_obligation" in LSVJ_PROMPT_TEMPLATE


# ── build_synthesis_prompt ────────────────────────────────────────────────────


def test_build_prompt_returns_string(schema_fixture: PrimitiveSchema) -> None:
    prompt = build_synthesis_prompt(
        tool_call={"tool_name": "send_email", "params": {"to": "alice@example.com"}},
        session_context=[],
        schema=schema_fixture,
        seeds=[],
    )
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_build_prompt_contains_tool_call(schema_fixture: PrimitiveSchema) -> None:
    prompt = build_synthesis_prompt(
        tool_call={"tool_name": "send_email"},
        session_context=[],
        schema=schema_fixture,
        seeds=[],
    )
    assert "send_email" in prompt


def test_build_prompt_contains_primitive_ids(schema_fixture: PrimitiveSchema) -> None:
    prompt = build_synthesis_prompt(
        tool_call={"tool_name": "test_action"},
        session_context=[],
        schema=schema_fixture,
        seeds=[],
    )
    assert "is_inner_circle" in prompt
    assert "owner_has_directed" in prompt
    assert "payload_contains_regex" in prompt


def test_build_prompt_contains_seeds(schema_fixture: PrimitiveSchema) -> None:
    seeds = ["is_inner_circle(recipient_id)", "external_url(target_url)"]
    prompt = build_synthesis_prompt(
        tool_call={"tool_name": "test"},
        session_context=[],
        schema=schema_fixture,
        seeds=seeds,
    )
    assert "is_inner_circle(recipient_id)" in prompt
    assert "external_url(target_url)" in prompt


def test_build_prompt_no_seeds_shows_none(schema_fixture: PrimitiveSchema) -> None:
    prompt = build_synthesis_prompt(
        tool_call={"tool_name": "test"},
        session_context=[],
        schema=schema_fixture,
        seeds=[],
    )
    assert "(none)" in prompt


def test_build_prompt_contains_session_context(schema_fixture: PrimitiveSchema) -> None:
    ctx = [{"tool_name": "read_file", "result": "ok"}]
    prompt = build_synthesis_prompt(
        tool_call={"tool_name": "send_email"},
        session_context=ctx,
        schema=schema_fixture,
        seeds=[],
    )
    assert "read_file" in prompt


def test_build_prompt_marks_class_c_mock(schema_fixture: PrimitiveSchema) -> None:
    prompt = build_synthesis_prompt(
        tool_call={"tool_name": "test"},
        session_context=[],
        schema=schema_fixture,
        seeds=[],
    )
    assert "mock_for_m0" in prompt


# ── parse_synthesis_response ──────────────────────────────────────────────────


def test_parse_valid_response() -> None:
    response = json.dumps({
        "decision": "allow",
        "synthesized_obligation": {
            "rule_body": "is_inner_circle(recipient_id)",
            "decision": "allow",
        },
    })
    result = parse_synthesis_response(response)
    assert isinstance(result, SynthesisResult)
    assert result.decision == "allow"
    assert result.synthesized_obligation.rule_body == "is_inner_circle(recipient_id)"


def test_parse_block_decision() -> None:
    response = json.dumps({
        "decision": "block",
        "synthesized_obligation": {
            "rule_body": "external_url(target)",
            "decision": "block",
        },
    })
    result = parse_synthesis_response(response)
    assert isinstance(result, SynthesisResult)
    assert result.decision == "block"


def test_parse_malformed_json_returns_parse_error() -> None:
    result = parse_synthesis_response("not valid json {{{")
    assert isinstance(result, ParseError)
    assert result.stage == "synthesis_parse"
    assert "invalid JSON" in result.message


def test_parse_missing_decision_field_returns_parse_error() -> None:
    response = json.dumps({
        "synthesized_obligation": {
            "rule_body": "is_inner_circle(x)",
            "decision": "allow",
        }
    })
    result = parse_synthesis_response(response)
    assert isinstance(result, ParseError)
    assert result.stage == "synthesis_parse"


def test_parse_invalid_decision_value_returns_parse_error() -> None:
    response = json.dumps({
        "decision": "maybe",
        "synthesized_obligation": {
            "rule_body": "is_inner_circle(x)",
            "decision": "allow",
        },
    })
    result = parse_synthesis_response(response)
    assert isinstance(result, ParseError)


def test_parse_empty_string_returns_parse_error() -> None:
    result = parse_synthesis_response("")
    assert isinstance(result, ParseError)


# ── MockProposer ──────────────────────────────────────────────────────────────


def test_mock_proposer_returns_synthesis_result(schema_fixture: PrimitiveSchema) -> None:
    mp = MockProposer(decision="allow", rule_body="is_inner_circle(recipient_id)")
    result = mp.propose(
        tool_call={"tool_name": "send_email"},
        session_context=[],
        schema=schema_fixture,
        seeds=[],
    )
    assert isinstance(result, SynthesisResult)
    assert result.decision == "allow"
    assert result.synthesized_obligation.rule_body == "is_inner_circle(recipient_id)"


def test_mock_proposer_default_values(schema_fixture: PrimitiveSchema) -> None:
    mp = MockProposer()
    result = mp.propose(
        tool_call={},
        session_context=[],
        schema=schema_fixture,
        seeds=[],
    )
    assert isinstance(result, SynthesisResult)
    assert result.decision == "allow"


def test_mock_proposer_block_decision(schema_fixture: PrimitiveSchema) -> None:
    mp = MockProposer(decision="block", rule_body="external_url(target)")
    result = mp.propose(
        tool_call={},
        session_context=[],
        schema=schema_fixture,
        seeds=[],
    )
    assert result.decision == "block"
    assert result.synthesized_obligation.decision == "block"


def test_mock_proposer_is_deterministic(schema_fixture: PrimitiveSchema) -> None:
    mp = MockProposer(decision="confirm", rule_body="owner_has_directed(action_id)")
    r1 = mp.propose({}, [], schema_fixture, [])
    r2 = mp.propose({"tool_name": "different"}, ["ctx"], schema_fixture, ["seed"])
    assert r1.decision == r2.decision
    assert r1.synthesized_obligation.rule_body == r2.synthesized_obligation.rule_body
