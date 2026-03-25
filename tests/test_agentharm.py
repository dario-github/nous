"""AgentHarm Benchmark — Tests

覆盖：loader (mock), adapter (mapping + tool_call 构造), runner (gate 集成), metrics (计算)
"""
import pytest
from unittest.mock import patch, MagicMock

from nous.benchmarks.agentharm.adapter import (
    FUNCTION_ACTION_MAP,
    get_action_type,
    is_t3_trigger,
    scenario_to_tool_calls,
)
from nous.benchmarks.agentharm.runner import (
    BenchmarkResult,
    ToolCallResult,
    run_benchmark,
)
from nous.benchmarks.agentharm.metrics import compute_metrics, format_report, _safe_rate


# ── Adapter Tests ─────────────────────────────────────────────────────────


class TestAdapter:
    """适配器：函数名→action_type 映射 + tool_call 构造"""

    def test_known_function_maps_correctly(self):
        assert get_action_type("create_ransomware") == "exec_destructive"
        assert get_action_type("delete_access_logs") == "delete_file"
        assert get_action_type("post_on_x") == "publish_post"
        assert get_action_type("send_email") == "send_message"
        assert get_action_type("query_google_search") == "web_search"

    def test_unknown_function_returns_unknown(self):
        assert get_action_type("completely_made_up") == "unknown"
        assert get_action_type("") == "unknown"

    def test_t3_trigger_detection(self):
        assert is_t3_trigger("create_ransomware") is True  # exec_destructive
        assert is_t3_trigger("delete_access_logs") is True  # delete_file
        assert is_t3_trigger("post_on_x") is True          # publish_post
        assert is_t3_trigger("send_email") is False         # send_message
        assert is_t3_trigger("unknown_func") is False       # unknown

    def test_scenario_to_tool_calls_basic(self):
        scenario = {
            "id": "test-1",
            "prompt": "Do something harmful",
            "target_functions": ["create_ransomware", "send_email"],
            "category": "Cybercrime",
            "name": "Test Scenario",
        }
        calls = scenario_to_tool_calls(scenario)
        assert len(calls) == 2

        # First call
        assert calls[0]["tool_name"] == "create_ransomware"
        assert calls[0]["action_type"] == "exec_destructive"
        assert calls[0].get("_harm_category") == "Cybercrime"  # Loop 48: moved out of params to prevent label leakage

        # Second call
        assert calls[1]["tool_name"] == "send_email"
        assert calls[1]["action_type"] == "send_message"

    def test_scenario_to_tool_calls_prompt_truncation(self):
        long_prompt = "x" * 500
        scenario = {
            "id": "trunc-1",
            "prompt": long_prompt,
            "target_functions": ["send_email"],
            "category": "Fraud",
        }
        calls = scenario_to_tool_calls(scenario)
        # Loop 18: full_prompt 不再截断，传完整 prompt 给 fact_extractor
        assert calls[0]["params"]["full_prompt"] == long_prompt

    def test_scenario_to_tool_calls_empty_functions(self):
        scenario = {"id": "empty", "prompt": "no tools", "target_functions": []}
        calls = scenario_to_tool_calls(scenario)
        assert calls == []

    def test_action_type_injected_into_tool_call(self):
        """确认 action_type 字段被直接设置（fact_extractor 最高优先级路径）"""
        scenario = {
            "id": "inject-1",
            "prompt": "test",
            "target_functions": ["add_hidden_malware"],
            "category": "Cybercrime",
        }
        calls = scenario_to_tool_calls(scenario)
        # fact_extractor._extract_action_type 会首先检查显式 action_type
        assert calls[0]["action_type"] == "exec_destructive"


# ── Runner Tests (with real gate) ─────────────────────────────────────────


class TestRunner:
    """Runner：gate 集成测试"""

    def _make_scenario(self, func_name: str, category: str = "Test") -> dict:
        return {
            "id": f"test-{func_name}",
            "prompt": f"test prompt for {func_name}",
            "target_functions": [func_name],
            "category": category,
            "name": f"Test {func_name}",
        }

    def test_harmful_ransomware_blocked(self):
        """create_ransomware → exec_destructive → T3 block"""
        results = run_benchmark(
            [self._make_scenario("create_ransomware", "Cybercrime")],
            is_harmful=True,
        )
        assert len(results) == 1
        assert results[0].any_blocked is True
        assert "T3" in results[0].block_rule_ids

    def test_harmful_post_on_x_blocked(self):
        """post_on_x → publish_post → T3 block"""
        results = run_benchmark(
            [self._make_scenario("post_on_x", "Disinformation")],
            is_harmful=True,
        )
        assert len(results) == 1
        assert results[0].any_blocked is True

    def test_benign_search_allowed(self):
        """query_google_search → web_search → allow"""
        results = run_benchmark(
            [self._make_scenario("query_google_search")],
            is_harmful=False,
        )
        assert len(results) == 1
        assert results[0].any_blocked is False

    def test_benign_send_email_allowed(self):
        """send_email → send_message → allow"""
        results = run_benchmark(
            [self._make_scenario("send_email")],
            is_harmful=False,
        )
        assert len(results) == 1
        assert results[0].any_blocked is False

    def test_unknown_function_allowed(self):
        """unknown → unknown → allow"""
        results = run_benchmark(
            [self._make_scenario("completely_unknown_func")],
            is_harmful=True,
        )
        assert len(results) == 1
        assert results[0].any_blocked is False

    def test_multi_tool_scenario_partial_block(self):
        """场景有多个 tool call，只要一个被 block 就算拦截"""
        scenario = {
            "id": "multi-1",
            "prompt": "multi tool test",
            "target_functions": ["send_email", "create_ransomware"],  # 1 allow + 1 block
            "category": "Cybercrime",
            "name": "Multi Tool",
        }
        results = run_benchmark([scenario], is_harmful=True)
        assert results[0].any_blocked is True
        # send_email 应该 allow
        assert results[0].tool_results[0].is_blocked is False
        # create_ransomware 应该 block
        assert results[0].tool_results[1].is_blocked is True


# ── Metrics Tests ─────────────────────────────────────────────────────────


class TestMetrics:
    """指标计算"""

    def _make_result(
        self,
        is_harmful: bool,
        any_blocked: bool,
        category: str = "Test",
        tool_results: list[ToolCallResult] | None = None,
    ) -> BenchmarkResult:
        if tool_results is None:
            tool_results = [
                ToolCallResult(
                    func_name="test_func",
                    action_type="test",
                    verdict_action="block" if any_blocked else "allow",
                    verdict_rule_id="T3" if any_blocked else None,
                    verdict_reason="test" if any_blocked else None,
                    latency_ms=0.1,
                )
            ]
        return BenchmarkResult(
            scenario_id="test",
            scenario_name="Test",
            category=category,
            is_harmful=is_harmful,
            any_blocked=any_blocked,
            tool_results=tool_results,
        )

    def test_safe_rate_basic(self):
        assert _safe_rate(3, 10) == 0.3
        assert _safe_rate(0, 10) == 0.0
        assert _safe_rate(0, 0) == 0.0

    def test_all_harmful_blocked(self):
        results = [self._make_result(True, True, "Cat1") for _ in range(5)]
        m = compute_metrics(results)
        assert m["harmful_block_rate"] == 1.0
        assert m["harmful_blocked"] == 5

    def test_no_harmful_blocked(self):
        results = [self._make_result(True, False, "Cat1") for _ in range(5)]
        m = compute_metrics(results)
        assert m["harmful_block_rate"] == 0.0
        assert m["coverage_gaps"] == ["Cat1"]

    def test_benign_fp(self):
        results = [
            self._make_result(False, True, "Cat1"),
            self._make_result(False, False, "Cat1"),
        ]
        m = compute_metrics(results)
        assert m["benign_fp_rate"] == 0.5

    def test_mixed_results(self):
        results = [
            self._make_result(True, True, "Cybercrime"),
            self._make_result(True, False, "Cybercrime"),
            self._make_result(True, False, "Fraud"),
            self._make_result(False, False, "Cybercrime"),
            self._make_result(False, True, "Fraud"),
        ]
        m = compute_metrics(results)
        assert m["total_harmful"] == 3
        assert m["total_benign"] == 2
        assert m["harmful_blocked"] == 1
        assert m["benign_false_positive"] == 1
        assert "Fraud" in m["coverage_gaps"]
        assert "Cybercrime" not in m["coverage_gaps"]

    def test_by_category(self):
        results = [
            self._make_result(True, True, "A"),
            self._make_result(True, False, "B"),
        ]
        m = compute_metrics(results)
        assert m["by_category"]["A"]["harmful_block_rate"] == 1.0
        assert m["by_category"]["B"]["harmful_block_rate"] == 0.0

    def test_format_report_produces_markdown(self):
        results = [
            self._make_result(True, True, "Cybercrime"),
            self._make_result(False, False, "Cybercrime"),
        ]
        m = compute_metrics(results)
        report = format_report(m)
        assert "# AgentHarm Baseline Report" in report
        assert "Cybercrime" in report
        assert "TPR" in report

    def test_rule_trigger_counts(self):
        results = [
            self._make_result(True, True, "A"),
            self._make_result(True, True, "B"),
        ]
        m = compute_metrics(results)
        assert m["rule_trigger_counts"].get("T3", 0) == 2
