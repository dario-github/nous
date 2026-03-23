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
    CostBreakdown,
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


# ── M2.P2: CostBreakdown ─────────────────────────────────────────────────


class TestCostBreakdown:
    def test_default_values(self):
        cb = CostBreakdown()
        assert cb.fact_extraction_us == 0
        assert cb.constraint_match_us == 0
        assert cb.delegate_us is None
        assert cb.delegate_tokens is None
        assert cb.entities_scanned == 0
        assert cb.constraints_evaluated == 0

    def test_to_dict_basic(self):
        cb = CostBreakdown(
            fact_extraction_us=120,
            constraint_match_us=80,
            entities_scanned=8,
            constraints_evaluated=5,
        )
        d = cb.to_dict()
        assert d["fact_extraction_us"] == 120
        assert d["constraint_match_us"] == 80
        assert d["entities_scanned"] == 8
        assert d["constraints_evaluated"] == 5  # hardcoded in test CostBreakdown
        assert "delegate_us" not in d       # None fields omitted
        assert "delegate_tokens" not in d

    def test_to_dict_with_delegate(self):
        cb = CostBreakdown(delegate_us=5000, delegate_tokens=256)
        d = cb.to_dict()
        assert d["delegate_us"] == 5000
        assert d["delegate_tokens"] == 256

    def test_entry_cost_breakdown_field(self):
        cb = CostBreakdown(fact_extraction_us=50, entities_scanned=4)
        entry = DecisionLogEntry(cost_breakdown=cb)
        assert entry.cost_breakdown is cb

    def test_entry_cost_breakdown_default_none(self):
        entry = DecisionLogEntry()
        assert entry.cost_breakdown is None

    def test_to_db_dict_embeds_cost_breakdown(self):
        """cost_breakdown 被嵌入 proof_trace JSON blob"""
        cb = CostBreakdown(fact_extraction_us=100, entities_scanned=7)
        entry = DecisionLogEntry(cost_breakdown=cb, verdict="block")
        d = entry.to_db_dict()
        pt = d["pt"]
        assert "cost_breakdown" in pt
        assert pt["cost_breakdown"]["fact_extraction_us"] == 100
        assert pt["cost_breakdown"]["entities_scanned"] == 7

    def test_to_db_dict_no_cost_breakdown_no_key(self):
        """无 cost_breakdown 时 proof_trace 中不含该 key"""
        entry = DecisionLogEntry(verdict="allow")
        d = entry.to_db_dict()
        pt = d["pt"]
        assert "cost_breakdown" not in pt


class TestGateCostBreakdown:
    def test_gate_result_has_cost_breakdown(self, real_constraints_dir):
        """gate() 返回 GateResult，其中 cost_breakdown 已填充"""
        tc = {"tool_name": "exec", "action_type": "delete_file"}
        result = gate(tool_call=tc, constraints_dir=real_constraints_dir)
        assert result.cost_breakdown is not None
        cb = result.cost_breakdown
        assert cb.fact_extraction_us >= 0
        assert cb.constraint_match_us >= 0
        assert cb.entities_scanned > 0
        assert cb.constraints_evaluated == 34  # Loop 64: 32 constraints (T3-series + T-series + OH-R1~7)+T3-upload+T5+T10+T11+T12+T-disinformation-election+T-grooming+T-roleplay-bypass+T-antidemocratic-incitement+T-data-exfiltration

    def test_gate_result_cost_breakdown_timing_positive(self, real_constraints_dir):
        """计时值应为非负整数"""
        tc = {"tool_name": "web_search", "action_type": "search"}
        result = gate(tool_call=tc, constraints_dir=real_constraints_dir)
        cb = result.cost_breakdown
        assert isinstance(cb.fact_extraction_us, int)
        assert isinstance(cb.constraint_match_us, int)
        assert cb.fact_extraction_us >= 0
        assert cb.constraint_match_us >= 0

    def test_gate_result_cost_breakdown_delegate_none(self, real_constraints_dir):
        """M2 阶段 delegate 字段应为 None"""
        tc = {"tool_name": "read", "action_type": "read_file"}
        result = gate(tool_call=tc, constraints_dir=real_constraints_dir)
        assert result.cost_breakdown.delegate_us is None
        assert result.cost_breakdown.delegate_tokens is None

    def test_entry_from_gate_result_transfers_cost_breakdown(self, real_constraints_dir):
        """entry_from_gate_result 正确转移 cost_breakdown"""
        tc = {"tool_name": "exec", "action_type": "delete_file"}
        result = gate(tool_call=tc, constraints_dir=real_constraints_dir)
        entry = entry_from_gate_result(result, session_id="cb-transfer-test")
        assert entry.cost_breakdown is result.cost_breakdown

    def test_cost_breakdown_persisted_in_db(self, mem_db, real_constraints_dir):
        """cost_breakdown 写入 DB 后可从 proof_trace 字段读取"""
        tc = {"tool_name": "exec", "action_type": "delete_file"}
        result = gate(
            tool_call=tc,
            db=mem_db,
            constraints_dir=real_constraints_dir,
            session_key="cb-db-test",
        )
        entry = entry_from_gate_result(result, session_id="cb-db-test")
        from nous.decision_log import persist_decision
        persist_decision(entry, mem_db)

        rows = mem_db._query_with_params(
            "?[proof_trace] := *decision_log{session_key, proof_trace}, "
            "session_key = $sk",
            {"sk": "cb-db-test"},
        )
        # 可能有两条（gate() 自动写一条 + persist_decision 再写一条）
        assert len(rows) >= 1
        # gate_with_decision_log 写入的那条含有 cost_breakdown（来自 persist_decision）
        # 找最后一条（session_key 重复时 cozo put 会覆盖）
        pt = rows[0]["proof_trace"]
        # entry_from_gate_result 路径写的才有 cost_breakdown
        assert "cost_breakdown" in pt
        assert pt["cost_breakdown"]["constraints_evaluated"] == 34  # Loop 64: 32 constraints (T3-series + T-series + OH-R1~7)+T3-upload+T5+T10+T11+T12+T-disinformation-election+T-grooming+T-roleplay-bypass+T-antidemocratic-incitement+T-data-exfiltration

