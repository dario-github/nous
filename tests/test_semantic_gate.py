"""Tests for Nous — Semantic Gate (M7.3 Layer 3)"""
import json
import pytest
from nous.semantic_gate import (
    SemanticGateConfig,
    SemanticVerdict,
    build_prompt,
    parse_llm_response,
    semantic_gate,
)


# ── Mock LLM Provider ────────────────────────────────────────────────────


def make_mock_provider(response: str, delay_ms: float = 0):
    """创建 mock LLM provider。"""
    import time

    def provider(prompt: str, timeout_ms: int, model: str) -> str:
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)
        return response

    return provider


def make_failing_provider(error_cls=RuntimeError, msg="LLM error"):
    """创建会抛异常的 mock provider。"""
    def provider(prompt: str, timeout_ms: int, model: str) -> str:
        raise error_cls(msg)
    return provider


# ── build_prompt tests ────────────────────────────────────────────────────


class TestBuildPrompt:
    """Prompt 构建测试。"""

    def test_includes_all_sections(self):
        prompt = build_prompt(
            tool_call={"tool_name": "publish_post", "params": {"content": "hello"}},
            facts={"action_type": "publish_post"},
            datalog_verdict="confirm",
            kg_context={"entity": "test"},
            policy_text="No harm policy.",
            max_content_chars=8000,
        )
        assert "Role" in prompt
        assert "Safety Policy" in prompt
        assert "No harm policy." in prompt
        assert "confirm" in prompt
        assert "publish_post" in prompt
        assert '"entity": "test"' in prompt

    def test_no_kg_context(self):
        prompt = build_prompt(
            tool_call={"tool_name": "test"},
            facts={"action_type": "test"},
            datalog_verdict="allow",
            kg_context=None,
            policy_text=None,
            max_content_chars=8000,
        )
        assert "No additional context" in prompt

    def test_truncates_long_content(self):
        long_content = "x" * 10000
        prompt = build_prompt(
            tool_call={"tool_name": "test", "params": {"content": long_content}},
            facts={"action_type": "test"},
            datalog_verdict="allow",
            kg_context=None,
            policy_text=None,
            max_content_chars=500,
        )
        assert "truncated at 500 chars" in prompt

    def test_default_policy_when_none(self):
        prompt = build_prompt(
            tool_call={"tool_name": "test"},
            facts={},
            datalog_verdict="allow",
            kg_context=None,
            policy_text=None,
            max_content_chars=8000,
        )
        assert "Block requests that facilitate violence" in prompt

    def test_custom_policy_text(self):
        prompt = build_prompt(
            tool_call={"tool_name": "test"},
            facts={},
            datalog_verdict="allow",
            kg_context=None,
            policy_text="Custom policy: be nice.",
            max_content_chars=8000,
        )
        assert "Custom policy: be nice." in prompt
        assert "Block requests that facilitate violence" not in prompt


# ── parse_llm_response tests ──────────────────────────────────────────────


class TestParseLlmResponse:
    """LLM 响应解析测试。"""

    def test_valid_json(self):
        raw = '{"action": "block", "reason": "harmful", "confidence": 0.9}'
        result = parse_llm_response(raw)
        assert result is not None
        assert result["action"] == "block"
        assert result["reason"] == "harmful"
        assert result["confidence"] == 0.9

    def test_json_in_markdown_codeblock(self):
        raw = '```json\n{"action": "allow", "reason": "safe", "confidence": 0.8}\n```'
        result = parse_llm_response(raw)
        assert result is not None
        assert result["action"] == "allow"

    def test_json_in_plain_codeblock(self):
        raw = '```\n{"action": "confirm", "reason": "unclear", "confidence": 0.5}\n```'
        result = parse_llm_response(raw)
        assert result is not None
        assert result["action"] == "confirm"

    def test_json_with_surrounding_text(self):
        raw = 'Here is my analysis:\n{"action": "block", "reason": "malware", "confidence": 0.95}\nEnd.'
        result = parse_llm_response(raw)
        assert result is not None
        assert result["action"] == "block"

    def test_invalid_action_returns_none(self):
        """Unknown action → returns None (strict validation)."""
        raw = '{"action": "invalid_action", "reason": "test", "confidence": 0.5}'
        result = parse_llm_response(raw)
        assert result is None

    def test_missing_confidence_defaults_to_0_5(self):
        raw = '{"action": "allow", "reason": "safe"}'
        result = parse_llm_response(raw)
        assert result is not None
        assert result["confidence"] == 0.5

    def test_confidence_clamp(self):
        raw = '{"action": "allow", "reason": "safe", "confidence": 1.5}'
        result = parse_llm_response(raw)
        assert result["confidence"] == 1.0

        raw = '{"action": "allow", "reason": "safe", "confidence": -0.5}'
        result = parse_llm_response(raw)
        assert result["confidence"] == 0.0

    def test_empty_string_returns_none(self):
        assert parse_llm_response("") is None

    def test_garbage_returns_none(self):
        assert parse_llm_response("I don't understand the question.") is None

    def test_no_action_field_returns_none(self):
        raw = '{"verdict": "block", "reason": "test"}'
        assert parse_llm_response(raw) is None


# ── semantic_gate integration tests ───────────────────────────────────────


class TestSemanticGate:
    """Semantic gate 主函数测试。"""

    def test_disabled_returns_none(self):
        config = SemanticGateConfig(enabled=False)
        result = semantic_gate(
            tool_call={"tool_name": "test"},
            facts={"action_type": "test"},
            datalog_verdict="allow",
            config=config,
        )
        assert result is None

    def test_off_mode_returns_none(self):
        config = SemanticGateConfig(mode="off")
        result = semantic_gate(
            tool_call={"tool_name": "test"},
            facts={"action_type": "test"},
            datalog_verdict="allow",
            config=config,
        )
        assert result is None

    def test_no_provider_returns_none(self):
        config = SemanticGateConfig(provider=None)
        result = semantic_gate(
            tool_call={"tool_name": "test"},
            facts={"action_type": "test"},
            datalog_verdict="allow",
            config=config,
        )
        assert result is None

    def test_success_with_mock_provider(self):
        response = '{"action": "block", "reason": "harmful content", "confidence": 0.92}'
        config = SemanticGateConfig(
            mode="active",
            provider=make_mock_provider(response),
        )
        result = semantic_gate(
            tool_call={"tool_name": "publish_post", "params": {"content": "bad stuff"}},
            facts={"action_type": "publish_post"},
            datalog_verdict="confirm",
            config=config,
        )
        assert result is not None
        assert result["action"] == "block"
        assert result["reason"] == "harmful content"
        assert result["confidence"] == 0.92
        assert result["latency_ms"] >= 0

    def test_shadow_mode_still_returns_verdict(self):
        """Shadow mode 仍然返回 verdict（但 gate 不 enforce）。"""
        response = '{"action": "allow", "reason": "safe", "confidence": 0.8}'
        config = SemanticGateConfig(
            mode="shadow",
            provider=make_mock_provider(response),
        )
        result = semantic_gate(
            tool_call={"tool_name": "test"},
            facts={"action_type": "test"},
            datalog_verdict="confirm",
            config=config,
        )
        assert result is not None
        assert result["action"] == "allow"

    def test_provider_exception_returns_none(self):
        config = SemanticGateConfig(
            mode="active",
            provider=make_failing_provider(),
        )
        result = semantic_gate(
            tool_call={"tool_name": "test"},
            facts={"action_type": "test"},
            datalog_verdict="allow",
            config=config,
        )
        assert result is None

    def test_provider_bad_response_returns_none(self):
        config = SemanticGateConfig(
            mode="active",
            provider=make_mock_provider("I don't know."),
        )
        result = semantic_gate(
            tool_call={"tool_name": "test"},
            facts={"action_type": "test"},
            datalog_verdict="allow",
            config=config,
        )
        assert result is None

    def test_with_kg_context(self):
        response = '{"action": "block", "reason": "known bad entity", "confidence": 0.95}'
        config = SemanticGateConfig(
            mode="active",
            provider=make_mock_provider(response),
        )
        result = semantic_gate(
            tool_call={"tool_name": "send_email"},
            facts={"action_type": "send_message"},
            datalog_verdict="allow",
            kg_context={"entity_reputation": "spam_associated"},
            config=config,
        )
        assert result is not None
        assert result["action"] == "block"
