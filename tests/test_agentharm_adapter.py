"""Tests for AgentHarm adapter."""
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"
sys.path.insert(0, str(SRC_DIR))


class TestAdapter:
    def test_dangerous_func_to_exec_destructive(self):
        from nous.benchmarks.agentharm.adapter import get_action_type
        assert get_action_type("create_ransomware") == "exec_destructive"

    def test_delete_func_to_delete_file(self):
        from nous.benchmarks.agentharm.adapter import get_action_type
        assert get_action_type("delete_access_logs") == "delete_file"

    def test_social_post_to_publish_post(self):
        from nous.benchmarks.agentharm.adapter import get_action_type
        assert get_action_type("post_on_x") == "publish_post"

    def test_search_to_web_search(self):
        from nous.benchmarks.agentharm.adapter import get_action_type
        assert get_action_type("query_google_search") == "web_search"

    def test_financial_to_financial_transfer(self):
        from nous.benchmarks.agentharm.adapter import get_action_type
        assert get_action_type("paypal_transfer") == "financial_transfer"

    def test_unknown_func_returns_unknown(self):
        from nous.benchmarks.agentharm.adapter import get_action_type
        assert get_action_type("totally_made_up_xyz") == "unknown"

    def test_scenario_to_tool_calls_count(self):
        from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
        scenario = {"id": "h1", "prompt": "test",
                    "target_functions": ["create_ransomware", "send_email"],
                    "category": "X", "name": "T"}
        calls = scenario_to_tool_calls(scenario)
        assert len(calls) == 2

    def test_tool_call_has_action_type_field(self):
        from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
        scenario = {"id": "h1", "prompt": "bad",
                    "target_functions": ["create_ransomware"],
                    "category": "X", "name": "T"}
        tc = scenario_to_tool_calls(scenario)[0]
        assert tc["action_type"] == "exec_destructive"

    def test_tool_call_preserves_func_name(self):
        from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
        scenario = {"id": "h1", "prompt": "test",
                    "target_functions": ["post_on_x"],
                    "category": "D", "name": "T"}
        tc = scenario_to_tool_calls(scenario)[0]
        assert tc["tool_name"] == "post_on_x"

    def test_tool_call_truncates_prompt(self):
        from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
        scenario = {"id": "h1", "prompt": "A" * 500,
                    "target_functions": ["create_ransomware"],
                    "category": "X", "name": "T"}
        tc = scenario_to_tool_calls(scenario)[0]
        assert len(tc["params"]["source_prompt"]) == 200

    def test_empty_target_functions(self):
        from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
        scenario = {"id": "h0", "prompt": "nothing",
                    "target_functions": [], "category": "X", "name": "T"}
        assert scenario_to_tool_calls(scenario) == []

    def test_is_t3_trigger_dangerous(self):
        from nous.benchmarks.agentharm.adapter import is_t3_trigger
        assert is_t3_trigger("create_ransomware") is True
        assert is_t3_trigger("delete_access_logs") is True
        assert is_t3_trigger("post_on_x") is True

    def test_is_t3_trigger_safe(self):
        from nous.benchmarks.agentharm.adapter import is_t3_trigger
        assert is_t3_trigger("query_google_search") is False
        assert is_t3_trigger("paypal_transfer") is False
        assert is_t3_trigger("send_email") is False


class TestCompatibility:
    def _scenario(self, func_name, category="X"):
        return {"id": "test", "prompt": "test prompt",
                "target_functions": [func_name], "category": category, "name": "T"}

    def test_ransomware_extracts_exec_destructive(self):
        from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
        from nous.fact_extractor import extract_facts
        facts = extract_facts(scenario_to_tool_calls(self._scenario("create_ransomware"))[0])
        assert facts["action_type"] == "exec_destructive"

    def test_post_on_x_extracts_publish_post(self):
        from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
        from nous.fact_extractor import extract_facts
        facts = extract_facts(scenario_to_tool_calls(self._scenario("post_on_x"))[0])
        assert facts["action_type"] == "publish_post"

    def test_search_extracts_web_search(self):
        from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
        from nous.fact_extractor import extract_facts
        facts = extract_facts(scenario_to_tool_calls(self._scenario("query_google_search"))[0])
        assert facts["action_type"] == "web_search"

    def test_gate_blocks_ransomware(self):
        from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
        from nous.gate import gate
        result = gate(scenario_to_tool_calls(self._scenario("create_ransomware"))[0],
                      db=None, constraints_dir=CONSTRAINTS_DIR)
        assert result.verdict.action == "block"
        assert result.verdict.rule_id == "T3"

    def test_gate_allows_financial_transfer(self):
        from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
        from nous.gate import gate
        result = gate(scenario_to_tool_calls(self._scenario("paypal_transfer"))[0],
                      db=None, constraints_dir=CONSTRAINTS_DIR)
        assert result.verdict.action == "allow"
