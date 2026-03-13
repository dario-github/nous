import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.benchmarks.agentharm.metrics import compute_metrics, format_report
from nous.benchmarks.agentharm.runner import BenchmarkResult, ToolCallResult

class TestMetrics:
    def _r(self, sid, cat, is_harmful, blocked, rules=None):
        tr = ToolCallResult(
            func_name="f", action_type="exec_destructive",
            verdict_action="block" if blocked else "allow",
            verdict_rule_id=(rules[0] if rules else "T3") if blocked else None,
            verdict_reason=None, latency_ms=1.0,
        )
        return BenchmarkResult(sid, sid, cat, is_harmful, blocked, [tr])

    def test_tpr(self):
        results = [
            self._r("h1", "A", True, True), self._r("h2", "A", True, True),
            self._r("h3", "B", True, False), self._r("h4", "B", True, False),
        ]
        m = compute_metrics(results)
        assert m["total_harmful"] == 4
        assert m["harmful_blocked"] == 2
        assert m["harmful_block_rate"] == 0.5

    def test_fpr(self):
        results = [
            self._r("b1", "S", False, False), self._r("b2", "S", False, True),
            self._r("b3", "S", False, False),
        ]
        m = compute_metrics(results)
        assert m["total_benign"] == 3
        assert m["benign_false_positive"] == 1
        assert abs(m["benign_fp_rate"] - 1/3) < 0.001

    def test_coverage_gap_detected(self):
        results = [
            self._r("h1", "Cyberattack", True, True),
            self._r("h2", "Fraud", True, False),
            self._r("h3", "Fraud", True, False),
        ]
        m = compute_metrics(results)
        assert "Fraud" in m["coverage_gaps"]
        assert "Cyberattack" not in m["coverage_gaps"]

    def test_no_gap_when_all_blocked(self):
        results = [self._r("h1", "A", True, True), self._r("h2", "B", True, True)]
        m = compute_metrics(results)
        assert m["coverage_gaps"] == []

    def test_rule_trigger_counts(self):
        def mktc(rule, blocked=True):
            return ToolCallResult(func_name="f", action_type="exec_destructive",
                verdict_action="block" if blocked else "allow",
                verdict_rule_id=rule if blocked else None,
                verdict_reason=None, latency_ms=1.0)

        r1 = BenchmarkResult("h1", "h1", "A", True, True, [mktc("T3")])
        r2 = BenchmarkResult("h2", "h2", "A", True, True, [mktc("T3"), mktc("T5")])
        r3 = BenchmarkResult("h3", "h3", "A", True, False, [mktc("T3", False)])
        m = compute_metrics([r1, r2, r3])
        assert m["rule_trigger_counts"]["T3"] == 2
        assert m["rule_trigger_counts"]["T5"] == 1

    def test_by_category(self):
        results = [
            self._r("h1", "Cyberattack", True, True),
            self._r("h2", "Cyberattack", True, False),
            self._r("h3", "Fraud", True, False),
            self._r("b1", "Cyberattack", False, False),
        ]
        m = compute_metrics(results)
        cat = m["by_category"]["Cyberattack"]
        assert cat["harmful_total"] == 2
        assert cat["harmful_blocked"] == 1
        assert cat["harmful_block_rate"] == 0.5

    def test_empty_results(self):
        m = compute_metrics([])
        assert m["total_harmful"] == 0
        assert m["harmful_block_rate"] == 0.0
        assert m["coverage_gaps"] == []

    def test_tool_level_metrics(self):
        def mktc(v):
            return ToolCallResult(func_name="f", action_type="exec_destructive",
                verdict_action=v, verdict_rule_id="T3" if v == "block" else None,
                verdict_reason=None, latency_ms=1.0)

        r = BenchmarkResult("h1", "h1", "X", True, True,
                            [mktc("block"), mktc("allow"), mktc("block")])
        m = compute_metrics([r])
        assert m["harmful_tool_calls_total"] == 3
        assert m["harmful_tool_calls_blocked"] == 2
        assert abs(m["harmful_tool_block_rate"] - 2/3) < 0.001

    def test_format_report_sections(self):
        results = [self._r("h1", "Cyberattack", True, True),
                   self._r("b1", "Safe", False, False)]
        m = compute_metrics(results)
        report = format_report(m)
        assert "核心指标" in report
        assert "覆盖缺口分析" in report
        assert "分类级明细" in report
