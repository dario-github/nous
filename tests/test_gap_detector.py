"""Nous — 规则缺口检测测试 (M3.2)"""
from nous.db import NousDB
from nous.decision_log import DecisionLogEntry, persist_decision
from nous.gap_detector import detect_gaps
from nous.outcome import OutcomeType, backfill_outcome
from nous.proof_trace import ProofTrace


def _make_entry(session_id: str, action_type: str, rule_ids: list[str], verdict: str = "block"):
    return DecisionLogEntry(
        tool_call_summary="test",
        verdict=verdict,
        proof_trace=ProofTrace(steps=[], final_verdict=verdict, total_ms=1.0),
        rule_ids=rule_ids,
        session_id=session_id,
        tool_name="test_tool",
        facts={"action_type": action_type},
        latency_ms=1.0,
    )


def test_detect_gaps_fp_and_fn_patterns():
    db = NousDB(":memory:")

    # same action_type + same rule => too_strict (fp >= 2)
    for i in range(2):
        sk = f"fp-{i}"
        persist_decision(_make_entry(sk, "safe_op", ["T-STRICT"]), db)
        backfill_outcome(sk, OutcomeType.fp, db)

    # fn >= 1 => too_loose
    persist_decision(_make_entry("fn-1", "dangerous_op", [], verdict="allow"), db)
    backfill_outcome("fn-1", OutcomeType.fn, db)

    gaps = detect_gaps(db, days=7)

    assert len(gaps) == 2

    too_strict = [g for g in gaps if g.pattern_type == "too_strict"][0]
    assert too_strict.action_type == "safe_op"
    assert too_strict.rule_id == "T-STRICT"
    assert too_strict.count == 2
    assert "false positive" in too_strict.suggested_fix

    too_loose = [g for g in gaps if g.pattern_type == "too_loose"][0]
    assert too_loose.action_type == "dangerous_op"
    assert too_loose.count == 1
    assert "false negative" in too_loose.suggested_fix
