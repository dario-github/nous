"""Nous — Outcome 回填测试 (M3.1)"""
import time

from nous.db import NousDB
from nous.decision_log import entry_from_gate_result, persist_decision
from nous.gate import GateResult
from nous.outcome import OutcomeType, backfill_outcome, get_pending_outcomes
from nous.proof_trace import ProofTrace
from nous.verdict import Verdict


pytestmark = pytest.mark.skipif(
    not KG_AVAILABLE,
    reason="KG entities dir not present (skipped on bare CI / sanitised public clones)",
)


def test_outcome_backfill():
    db = NousDB(":memory:")

    # 构造假 GateResult
    v = Verdict(action="block", rule_id="T3", reason="test")
    pt = ProofTrace(steps=[], final_verdict="block", total_ms=1.0)
    gr = GateResult(verdict=v, proof_trace=pt, decision_log_id="test-session-1", latency_ms=1.0)

    # 1. 持久化一条初始记录
    entry = entry_from_gate_result(gr, session_id="test-session-1")
    persist_decision(entry, db)

    # 2. 查询待回填
    pending = get_pending_outcomes(db)
    assert len(pending) == 1
    assert pending[0]["session_key"] == "test-session-1"
    assert pending[0]["outcome"] == "block"  # 初始值为 gate verdict

    # 3. 执行回填 (FP)
    success = backfill_outcome("test-session-1", OutcomeType.fp, db)
    assert success

    # 4. 再次查询待回填 (应为空)
    pending_after = get_pending_outcomes(db)
    assert len(pending_after) == 0

    # 5. 验证数据库中 outcome 已更新
    rows = db._query_with_params("?[outcome] := *decision_log{session_key, outcome}, session_key = 'test-session-1'", {})
    assert rows[0]["outcome"] == "fp"
