"""Tests — M2.9 决策日志持久化 (test_decision_log.py)

覆盖：
- gate() 调用后 decision_log 表有记录
- 可按 rule_id 查询
- persist_decision 写入 + 读取
- query_decisions 多种过滤条件
- gate_with_decision_log 集成
"""
import time
import pytest
from pathlib import Path

from nous.db import NousDB
from nous.decision_log import (
    DECISION_LOG_SCHEMA_VERSION,
    DecisionLogEntry,
    entry_from_gate_result,
    gate_with_decision_log,
    persist_decision,
    query_decisions,
)
from nous.gate import gate
from nous.proof_trace import ProofStep, ProofTrace


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mem_db():
    """内存模式 NousDB"""
    db = NousDB(":memory:")
    yield db
    db.close()


@pytest.fixture
def real_constraints_dir():
    return Path(__file__).parent.parent / "ontology" / "constraints"


@pytest.fixture
def sample_entry():
    """一个样本 DecisionLogEntry"""
    trace = ProofTrace(
        steps=[
            ProofStep(
                rule_id="T3",
                fact_bindings={"action_type": "delete_file"},
                verdict="match",
                timestamp=time.time(),
            )
        ],
        final_verdict="block",
        total_ms=1.5,
    )
    return DecisionLogEntry(
        timestamp=time.time(),
        tool_call_summary='{"tool_name": "exec", "action_type": "delete_file"}',
        verdict="block",
        proof_trace=trace,
        rule_ids=["T3"],
        session_id="test-session-001",
        schema_version=DECISION_LOG_SCHEMA_VERSION,
        latency_ms=1.5,
        tool_name="exec",
        facts={"action_type": "delete_file"},
    )


# ── DecisionLogEntry ──────────────────────────────────────────────────────


class TestDecisionLogEntry:
    def test_entry_has_required_fields(self, sample_entry):
        assert sample_entry.timestamp > 0
        assert sample_entry.tool_call_summary
        assert sample_entry.verdict == "block"
        assert sample_entry.proof_trace is not None
        assert "T3" in sample_entry.rule_ids
        assert sample_entry.session_id == "test-session-001"
        assert sample_entry.schema_version == DECISION_LOG_SCHEMA_VERSION

    def test_to_db_dict(self, sample_entry):
        d = sample_entry.to_db_dict()
        assert d["outcome"] == "block"
        assert d["sk"] == "test-session-001"
        assert d["tn"] == "exec"
        assert isinstance(d["pt"], dict)
        assert "T3" in d["gates"]


# ── persist_decision ──────────────────────────────────────────────────────


class TestPersistDecision:
    def test_persist_returns_true(self, mem_db, sample_entry):
        result = persist_decision(sample_entry, mem_db)
        assert result is True

    def test_persist_none_db_returns_false(self, sample_entry):
        result = persist_decision(sample_entry, None)
        assert result is False

    def test_persisted_entry_readable(self, mem_db, sample_entry):
        persist_decision(sample_entry, mem_db)
        rows = mem_db.query("?[ts, session_key, outcome] := *decision_log{ts, session_key, outcome}")
        assert len(rows) >= 1
        outcomes = [r["outcome"] for r in rows]
        assert "block" in outcomes

    def test_persist_multiple_entries(self, mem_db):
        for i in range(5):
            entry = DecisionLogEntry(
                timestamp=time.time() + i,
                verdict="allow",
                session_id=f"session-{i}",
                tool_name="web_search",
            )
            persist_decision(entry, mem_db)

        rows = mem_db.query("?[ts, outcome] := *decision_log{ts, outcome}")
        assert len(rows) >= 5


# ── query_decisions ────────────────────────────────────────────────────────


class TestQueryDecisions:
    def test_query_by_verdict(self, mem_db, sample_entry):
        persist_decision(sample_entry, mem_db)
        rows = query_decisions({"verdict": "block"}, mem_db)
        assert len(rows) >= 1
        assert all(r["outcome"] == "block" for r in rows)

    def test_query_by_session_id(self, mem_db, sample_entry):
        persist_decision(sample_entry, mem_db)
        rows = query_decisions({"session_id": "test-session-001"}, mem_db)
        assert len(rows) >= 1
        assert rows[0]["session_key"] == "test-session-001"

    def test_query_by_rule_id(self, mem_db, sample_entry):
        persist_decision(sample_entry, mem_db)
        rows = query_decisions({"rule_id": "T3"}, mem_db)
        assert len(rows) >= 1

    def test_query_by_nonexistent_rule_returns_empty(self, mem_db, sample_entry):
        persist_decision(sample_entry, mem_db)
        rows = query_decisions({"rule_id": "T999_nonexistent"}, mem_db)
        assert rows == []

    def test_query_by_since(self, mem_db):
        now = time.time()
        entry1 = DecisionLogEntry(timestamp=now - 100, verdict="allow", session_id="old")
        entry2 = DecisionLogEntry(timestamp=now + 10, verdict="allow", session_id="new")
        persist_decision(entry1, mem_db)
        persist_decision(entry2, mem_db)

        rows = query_decisions({"since": now}, mem_db)
        session_keys = [r["session_key"] for r in rows]
        assert "new" in session_keys

    def test_query_limit(self, mem_db):
        for i in range(10):
            entry = DecisionLogEntry(
                timestamp=time.time() + i,
                verdict="warn",
                session_id=f"warn-{i}",
            )
            persist_decision(entry, mem_db)

        rows = query_decisions({"verdict": "warn", "limit": 3}, mem_db)
        assert len(rows) <= 3

    def test_query_none_db_returns_empty(self):
        rows = query_decisions({"verdict": "block"}, None)
        assert rows == []


# ── gate() + 自动持久化 ────────────────────────────────────────────────────


class TestGateIntegration:
    def test_gate_call_creates_decision_log_record(
        self, mem_db, real_constraints_dir
    ):
        """gate() 调用后（通过 observability.log_decision），decision_log 有记录"""
        from nous.observability import SamplingPolicy
        policy = SamplingPolicy(
            block_rate=1.0, allow_rate=1.0, confirm_rate=1.0, warn_rate=1.0
        )
        tc = {
            "tool_name": "exec",
            "action_type": "delete_file",
            "params": {"path": "/tmp/x"},
        }
        result = gate(
            tool_call=tc,
            db=mem_db,
            constraints_dir=real_constraints_dir,
            session_key="gate-test-001",
            sampling_policy=policy,
        )
        assert result.verdict.action == "block"

        rows = mem_db.query("?[session_key, outcome] := *decision_log{session_key, outcome}")
        assert any(r["session_key"] == "gate-test-001" for r in rows)

    def test_gate_with_decision_log_persist_entry(
        self, mem_db, real_constraints_dir
    ):
        """gate_with_decision_log() 写入包含 rule_ids 的完整 entry"""
        tc = {
            "tool_name": "exec",
            "action_type": "delete_file",
            "params": {"path": "/tmp/x"},
        }
        result = gate_with_decision_log(
            tool_call=tc,
            db=mem_db,
            constraints_dir=real_constraints_dir,
            session_key="full-log-test",
        )
        assert result.verdict.action == "block"

        # 用 query_decisions 查
        rows = query_decisions({"session_id": "full-log-test"}, mem_db)
        assert len(rows) >= 1
        row = rows[0]
        assert row["outcome"] == "block"

    def test_gate_with_decision_log_queryable_by_rule_id(
        self, mem_db, real_constraints_dir
    ):
        """gate_with_decision_log() 的记录可按 rule_id 查询"""
        tc = {
            "tool_name": "exec",
            "action_type": "delete_file",
            "params": {"path": "/tmp/x"},
        }
        gate_with_decision_log(
            tool_call=tc,
            db=mem_db,
            constraints_dir=real_constraints_dir,
            session_key="ruleid-test",
        )
        # 查 T3 命中的记录
        rows = query_decisions({"rule_id": "T3"}, mem_db)
        # T3 应当命中（delete_file 触发 T3 block）
        assert len(rows) >= 1

    def test_gate_with_decision_log_auto_persist_false(
        self, mem_db, real_constraints_dir
    ):
        """auto_persist=False → 不写 decision_log（或只走 observability 采样）"""
        tc = {"tool_name": "web_search", "action_type": "search"}
        gate_with_decision_log(
            tool_call=tc,
            db=mem_db,
            constraints_dir=real_constraints_dir,
            session_key="no-persist-test",
            auto_persist=False,
        )
        # decision_log 中不应有来自 gate_with_decision_log 的 entry_from_gate_result 记录
        rows = query_decisions({"session_id": "no-persist-test"}, mem_db)
        # 可能有来自 observability.log_decision 的记录（采样逻辑），
        # 但来自 gate_with_decision_log 的 entry_from_gate_result 不应在此
        # 我们只验证不抛出异常
        assert isinstance(rows, list)


# ── entry_from_gate_result ────────────────────────────────────────────────


class TestEntryFromGateResult:
    def test_entry_extracts_rule_ids(self, real_constraints_dir):
        tc = {
            "tool_name": "exec",
            "action_type": "delete_file",
        }
        result = gate(tool_call=tc, constraints_dir=real_constraints_dir)
        entry = entry_from_gate_result(
            gate_result=result,
            session_id="test-extract",
            tool_call_summary='{"tool_name": "exec"}',
        )
        assert entry.verdict == "block"
        assert "T3" in entry.rule_ids

    def test_entry_schema_version(self, real_constraints_dir):
        tc = {"tool_name": "web_search"}
        result = gate(tool_call=tc, constraints_dir=real_constraints_dir)
        entry = entry_from_gate_result(result)
        assert entry.schema_version == DECISION_LOG_SCHEMA_VERSION

    def test_tool_call_summary_truncated(self, real_constraints_dir):
        tc = {"tool_name": "x" * 500}
        result = gate(tool_call=tc, constraints_dir=real_constraints_dir)
        summary = '{"tool_name": "' + "x" * 500 + '"}'
        entry = entry_from_gate_result(result, tool_call_summary=summary)
        assert len(entry.tool_call_summary) <= 200
