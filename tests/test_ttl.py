"""Nous — TTL 衰减测试 (M3.5)"""
import tempfile
import time
from pathlib import Path

import yaml

from nous.db import NousDB
from nous.decision_log import DecisionLogEntry, persist_decision
from nous.proof_trace import ProofTrace
from nous.ttl import check_rule_ttl


pytestmark = pytest.mark.skipif(
    not KG_AVAILABLE,
    reason="KG entities dir not present (skipped on bare CI / sanitised public clones)",
)


def _write_rule(path: Path, rule_id: str, enabled: bool = True, created_at: float | None = None):
    data = {
        "id": rule_id,
        "enabled": enabled,
        "priority": 10,
        "trigger": {"action_type": rule_id.lower()},
        "verdict": "block",
        "metadata": {},
    }
    if created_at is not None:
        data["metadata"]["created_at"] = created_at
    with open(path / f"{rule_id}.yaml", "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def _log_trigger(db: NousDB, session_id: str, rule_id: str, ts: float):
    entry = DecisionLogEntry(
        timestamp=ts,
        tool_call_summary="ttl",
        verdict="block",
        proof_trace=ProofTrace(steps=[], final_verdict="block", total_ms=1.0),
        rule_ids=[rule_id],
        session_id=session_id,
        tool_name="test_tool",
        facts={"action_type": "ttl_test"},
        latency_ms=1.0,
    )
    persist_decision(entry, db)


def test_ttl_warning_and_disable_logic():
    db = NousDB(":memory:")
    now = time.time()

    with tempfile.TemporaryDirectory() as tmpdir:
        constraints_dir = Path(tmpdir)

        # 35 天未触发 => warning
        _write_rule(constraints_dir, "RULE-WARN")
        _log_trigger(db, "warn-session", "RULE-WARN", now - 35 * 86400)

        # 61 天未触发 => disable
        _write_rule(constraints_dir, "RULE-DISABLE")
        _log_trigger(db, "disable-session", "RULE-DISABLE", now - 61 * 86400)

        alerts = check_rule_ttl(constraints_dir, db)

        assert len(alerts) == 2
        actions = {a.rule_id: a.action for a in alerts}
        assert actions["RULE-WARN"] == "warning"
        assert actions["RULE-DISABLE"] == "disable"

        # verify YAML updated to enabled:false
        with open(constraints_dir / "RULE-DISABLE.yaml", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["enabled"] is False
        assert data["metadata"]["disabled_by_ttl"] is True
