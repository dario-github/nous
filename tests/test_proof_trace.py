"""测试 M1.9 + M1.10 — Proof Trace + 可观测性 (proof_trace.py + observability.py)

验证 trace 记录完整性 + 采样率。
"""
import sys
import time
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from nous.db import NousDB
from nous.proof_trace import ProofStep, ProofTrace, trace_gate, _match_constraint
from nous.observability import SamplingPolicy, log_decision, get_decision_stats, SCHEMA_VERSION


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def db():
    _db = NousDB(":memory:")
    yield _db
    _db.close()


CONSTRAINTS_T3 = [
    {
        "id": "T3-delete-file",
        "verdict": "block",
        "enabled": True,
        "match_patterns": {"action_type": "delete_file"},
    },
    {
        "id": "T3-modify-config",
        "verdict": "confirm",
        "enabled": True,
        "match_patterns": {"action_type": "modify_config"},
    },
    {
        "id": "T5-social-url",
        "verdict": "warn",
        "enabled": True,
        "match_patterns": {"tool_name": "browser", "action_type": "open_social"},
    },
]

CONSTRAINTS_EMPTY = []

DISABLED_CONSTRAINT = [
    {
        "id": "T99-disabled",
        "verdict": "block",
        "enabled": False,
        "match_patterns": {"action_type": "delete_file"},
    }
]


# ── 测试 ProofStep ────────────────────────────────────────────────────────


class TestProofStep:
    def test_to_dict(self):
        step = ProofStep(
            rule_id="T3-delete-file",
            fact_bindings={"action_type": "delete_file"},
            verdict="match",
            timestamp=1234567890.0,
        )
        d = step.to_dict()
        assert d["rule_id"] == "T3-delete-file"
        assert d["fact_bindings"] == {"action_type": "delete_file"}
        assert d["verdict"] == "match"
        assert d["timestamp"] == 1234567890.0

    def test_default_timestamp(self):
        t_before = time.time()
        step = ProofStep(rule_id="r1", fact_bindings={}, verdict="no-match")
        t_after = time.time()
        assert t_before <= step.timestamp <= t_after


# ── 测试 ProofTrace ──────────────────────────────────────────────────────


class TestProofTrace:
    def test_to_dict(self):
        trace = ProofTrace(
            steps=[ProofStep("r1", {"k": "v"}, "match", 1.0)],
            final_verdict="block",
            total_ms=1.23,
        )
        d = trace.to_dict()
        assert d["final_verdict"] == "block"
        assert d["total_ms"] == 1.23
        assert len(d["steps"]) == 1
        assert d["steps"][0]["verdict"] == "match"

    def test_from_dict_roundtrip(self):
        original = ProofTrace(
            steps=[
                ProofStep("r1", {"a": 1}, "match", 1.0),
                ProofStep("r2", {}, "no-match", 2.0),
            ],
            final_verdict="block",
            total_ms=0.5,
        )
        reconstructed = ProofTrace.from_dict(original.to_dict())
        assert reconstructed.final_verdict == "block"
        assert len(reconstructed.steps) == 2
        assert reconstructed.steps[0].rule_id == "r1"
        assert reconstructed.steps[1].verdict == "no-match"

    def test_empty_trace(self):
        trace = ProofTrace()
        assert trace.steps == []
        assert trace.final_verdict == "allow"
        d = trace.to_dict()
        assert d["steps"] == []


# ── 测试 _match_constraint ────────────────────────────────────────────────


class TestMatchConstraint:
    def test_exact_match(self):
        constraint = {"match_patterns": {"action_type": "delete_file"}}
        tool_call = {"action_type": "delete_file", "params": {"path": "/tmp/x"}}
        matched, bindings = _match_constraint(tool_call, constraint)
        assert matched is True
        assert bindings == {"action_type": "delete_file"}

    def test_no_match(self):
        constraint = {"match_patterns": {"action_type": "delete_file"}}
        tool_call = {"action_type": "read_file"}
        matched, bindings = _match_constraint(tool_call, constraint)
        assert matched is False
        assert bindings == {}

    def test_multi_field_match(self):
        constraint = {
            "match_patterns": {
                "tool_name": "browser",
                "action_type": "open_social",
            }
        }
        tool_call = {"tool_name": "browser", "action_type": "open_social"}
        matched, bindings = _match_constraint(tool_call, constraint)
        assert matched is True
        assert bindings == {"tool_name": "browser", "action_type": "open_social"}

    def test_multi_field_partial_miss(self):
        constraint = {
            "match_patterns": {
                "tool_name": "browser",
                "action_type": "open_social",
            }
        }
        tool_call = {"tool_name": "browser", "action_type": "navigate"}
        matched, _ = _match_constraint(tool_call, constraint)
        assert matched is False

    def test_list_value_match(self):
        constraint = {
            "match_patterns": {
                "action_type": ["delete_file", "modify_config"]
            }
        }
        tool_call = {"action_type": "modify_config"}
        matched, bindings = _match_constraint(tool_call, constraint)
        assert matched is True

    def test_empty_patterns_no_match(self):
        constraint = {"match_patterns": {}}
        tool_call = {"action_type": "anything"}
        matched, _ = _match_constraint(tool_call, constraint)
        assert matched is False

    def test_no_patterns_field(self):
        constraint = {"rule_body": "", "verdict": "block"}
        tool_call = {"action_type": "anything"}
        matched, _ = _match_constraint(tool_call, constraint)
        assert matched is False


# ── 测试 trace_gate ───────────────────────────────────────────────────────


class TestTraceGate:
    def test_block_verdict(self):
        tool_call = {"action_type": "delete_file", "params": {}}
        trace = trace_gate(tool_call, CONSTRAINTS_T3)
        assert trace.final_verdict == "block"
        # 第一条规则应该匹配
        match_steps = [s for s in trace.steps if s.verdict == "match"]
        assert len(match_steps) >= 1
        assert match_steps[0].rule_id == "T3-delete-file"
        assert match_steps[0].fact_bindings == {"action_type": "delete_file"}

    def test_allow_verdict_no_match(self):
        tool_call = {"action_type": "read_file"}
        trace = trace_gate(tool_call, CONSTRAINTS_T3)
        assert trace.final_verdict == "allow"

    def test_all_steps_recorded(self):
        tool_call = {"action_type": "read_file"}
        trace = trace_gate(tool_call, CONSTRAINTS_T3)
        # 有 3 条约束，全部不匹配，应有 3 个 no-match steps
        assert len(trace.steps) == 3
        assert all(s.verdict == "no-match" for s in trace.steps)

    def test_disabled_constraint_skipped(self):
        tool_call = {"action_type": "delete_file"}
        trace = trace_gate(tool_call, DISABLED_CONSTRAINT)
        # disabled 的约束应被跳过
        assert trace.final_verdict == "allow"
        assert len(trace.steps) == 0

    def test_empty_constraints(self):
        tool_call = {"action_type": "anything"}
        trace = trace_gate(tool_call, CONSTRAINTS_EMPTY)
        assert trace.final_verdict == "allow"
        assert trace.steps == []

    def test_verdict_priority_block_over_warn(self):
        constraints = [
            {"id": "warn-rule", "verdict": "warn", "enabled": True,
             "match_patterns": {"tool_name": "browser"}},
            {"id": "block-rule", "verdict": "block", "enabled": True,
             "match_patterns": {"action_type": "delete_file"}},
        ]
        tool_call = {"tool_name": "browser", "action_type": "delete_file"}
        trace = trace_gate(tool_call, constraints)
        assert trace.final_verdict == "block"

    def test_total_ms_recorded(self):
        tool_call = {"action_type": "read_file"}
        trace = trace_gate(tool_call, CONSTRAINTS_T3)
        assert trace.total_ms >= 0.0
        assert trace.total_ms < 100.0  # 应该很快

    def test_no_match_steps_have_empty_bindings(self):
        tool_call = {"action_type": "read_file"}
        trace = trace_gate(tool_call, CONSTRAINTS_T3)
        for step in trace.steps:
            assert step.fact_bindings == {}

    def test_confirm_verdict(self):
        tool_call = {"action_type": "modify_config"}
        trace = trace_gate(tool_call, CONSTRAINTS_T3)
        assert trace.final_verdict == "confirm"


# ── 测试 SamplingPolicy ───────────────────────────────────────────────────


class TestSamplingPolicy:
    def test_block_always_logged(self):
        policy = SamplingPolicy(block_rate=1.0)
        # 100 次 block 全部应该 should_log = True
        results = [policy.should_log("block") for _ in range(100)]
        assert all(results)

    def test_allow_rate_zero(self):
        policy = SamplingPolicy(allow_rate=0.0)
        results = [policy.should_log("allow") for _ in range(100)]
        assert not any(results)

    def test_allow_rate_one(self):
        policy = SamplingPolicy(allow_rate=1.0)
        results = [policy.should_log("allow") for _ in range(100)]
        assert all(results)

    def test_allow_rate_approx_10_percent(self):
        """统计采样率，应在 [0%, 35%] 范围内（10% ± 统计波动）"""
        policy = SamplingPolicy(allow_rate=0.1)
        # 跑 1000 次，期望约 100 次 True
        results = [policy.should_log("allow") for _ in range(1000)]
        count = sum(results)
        # 极宽容区间：3sigma ~ [4%, 17%]
        assert 20 <= count <= 200, f"采样率偏差过大: {count}/1000"

    def test_unknown_verdict_uses_allow_rate(self):
        policy = SamplingPolicy(allow_rate=0.0)
        assert policy.should_log("unknown") is False

    def test_default_rates(self):
        policy = SamplingPolicy()
        assert policy.block_rate == 1.0
        assert policy.allow_rate == 0.1
        assert policy.confirm_rate == 1.0
        assert policy.warn_rate == 0.5


# ── 测试 log_decision ────────────────────────────────────────────────────


class TestLogDecision:
    def test_block_always_logged_to_db(self, db):
        policy = SamplingPolicy(block_rate=1.0)
        trace = ProofTrace(
            steps=[ProofStep("T3", {"action_type": "delete_file"}, "match")],
            final_verdict="block",
            total_ms=0.5,
        )
        logged = log_decision(
            verdict="block",
            proof_trace=trace,
            sampling_policy=policy,
            db=db,
            session_key="test:session:001",
            tool_name="exec",
            facts={"cmd": "rm -rf /"},
        )
        assert logged is True

    def test_allow_not_logged_when_rate_zero(self, db):
        policy = SamplingPolicy(allow_rate=0.0)
        logged = log_decision(
            verdict="allow",
            proof_trace=None,
            sampling_policy=policy,
            db=db,
        )
        assert logged is False

    def test_no_db_returns_true_when_sampled(self):
        policy = SamplingPolicy(block_rate=1.0)
        logged = log_decision(
            verdict="block",
            proof_trace=None,
            sampling_policy=policy,
            db=None,
        )
        assert logged is True

    def test_schema_version_constant(self):
        assert SCHEMA_VERSION == "1.0"

    def test_proof_trace_in_log(self, db):
        """验证 proof_trace 被正确写入 DB"""
        policy = SamplingPolicy(block_rate=1.0)
        trace = ProofTrace(
            steps=[ProofStep("T3-delete-file", {"action_type": "delete_file"}, "match")],
            final_verdict="block",
            total_ms=1.2,
        )
        log_decision(
            verdict="block",
            proof_trace=trace,
            sampling_policy=policy,
            db=db,
            session_key="test:session:pt-test",
            tool_name="exec",
        )
        # 查询 decision_log
        rows = db._query_with_params(
            "?[session_key, outcome, proof_trace, schema_version] := "
            "*decision_log{session_key, outcome, proof_trace, schema_version}, "
            "session_key = $sk",
            {"sk": "test:session:pt-test"},
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["outcome"] == "block"
        assert row["schema_version"] == "1.0"
        pt = row["proof_trace"]
        assert pt["final_verdict"] == "block"
        assert len(pt["steps"]) == 1


# ── 测试 get_decision_stats ───────────────────────────────────────────────


class TestGetDecisionStats:
    def test_empty_db(self, db):
        stats = get_decision_stats(db)
        # 空表返回空 dict 或 total=0
        assert isinstance(stats, dict)

    def test_stats_after_logging(self, db):
        policy_all = SamplingPolicy(block_rate=1.0, allow_rate=1.0)
        for _ in range(3):
            log_decision("block", None, policy_all, db,
                         session_key=f"s:block:{time.time()}")
        for _ in range(2):
            log_decision("allow", None, policy_all, db,
                         session_key=f"s:allow:{time.time()}")
        stats = get_decision_stats(db)
        assert stats.get("block", 0) == 3
        assert stats.get("allow", 0) == 2
        assert stats.get("total", 0) == 5
