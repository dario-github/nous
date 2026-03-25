"""Tests for nous.edge_weight — Bayesian edge weight updates."""
import json
import pytest
from nous.db import NousDB
from nous.schema import Entity, Relation
from nous.edge_weight import update_edge_weights, _extract_entity_ids


@pytest.fixture
def db():
    """In-memory NousDB with test entities and relations."""
    d = NousDB(":memory:")
    d.upsert_entities([
        Entity(id="tool:send_email", etype="tool", labels=["tool"]),
        Entity(id="person:alice", etype="person", labels=["person"]),
    ])
    d.upsert_relations([
        Relation(from_id="tool:send_email", to_id="person:alice", rtype="governed_by",
                 properties={"alpha": 1.0, "beta": 1.0}, confidence=0.5),
    ])
    return d


def _read_relation(db: NousDB, fid: str, tid: str, rt: str) -> dict:
    rows = db._query_with_params(
        "?[from_id, to_id, rtype, props, confidence] := "
        "*relation{from_id, to_id, rtype, props, confidence}, "
        "from_id = $fid, to_id = $tid, rtype = $rt",
        {"fid": fid, "tid": tid, "rt": rt},
    )
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
    return rows[0]


class TestExtractEntityIds:
    def test_from_kg_context(self):
        result = _extract_entity_ids({
            "kg_context": {"entities": [{"id": "tool:x"}], "policies": [{"id": "cat:y"}]},
            "facts": {},
        })
        assert result == {"tool:x", "cat:y"}

    def test_from_facts(self):
        result = _extract_entity_ids({
            "kg_context": None,
            "facts": {"tool_name": "send_email", "target": "person:alice"},
        })
        assert "send_email" in result
        assert "tool:send_email" in result
        assert "person:alice" in result

    def test_empty(self):
        assert _extract_entity_ids({"verdict": "block"}) == set()


class TestUpdateEdgeWeights:
    def test_block_increases_alpha(self, db):
        gate_result = {
            "verdict": "block",
            "kg_context": {"entities": [{"id": "tool:send_email"}], "policies": []},
            "facts": {},
        }
        count = update_edge_weights(db, gate_result)
        assert count == 1
        rel = _read_relation(db, "tool:send_email", "person:alice", "governed_by")
        props = rel["props"] if isinstance(rel["props"], dict) else json.loads(rel["props"])
        assert props["alpha"] == pytest.approx(2.0)
        assert props["beta"] == pytest.approx(1.0)
        assert rel["confidence"] == pytest.approx(2.0 / 3.0)

    def test_allow_increases_beta(self, db):
        gate_result = {
            "verdict": "allow",
            "kg_context": None,
            "facts": {"tool_name": "send_email"},
        }
        count = update_edge_weights(db, gate_result)
        assert count >= 1
        rel = _read_relation(db, "tool:send_email", "person:alice", "governed_by")
        props = rel["props"] if isinstance(rel["props"], dict) else json.loads(rel["props"])
        assert props["alpha"] == pytest.approx(1.0)
        assert props["beta"] == pytest.approx(1.5)
        assert rel["confidence"] == pytest.approx(1.0 / 2.5)

    def test_confirm_small_alpha_increase(self, db):
        gate_result = {
            "verdict": "confirm",
            "kg_context": {"entities": [{"id": "tool:send_email"}], "policies": []},
            "facts": {},
        }
        count = update_edge_weights(db, gate_result)
        assert count == 1
        rel = _read_relation(db, "tool:send_email", "person:alice", "governed_by")
        props = rel["props"] if isinstance(rel["props"], dict) else json.loads(rel["props"])
        assert props["alpha"] == pytest.approx(1.3)

    def test_unknown_verdict_noop(self, db):
        assert update_edge_weights(db, {"verdict": "warn", "facts": {}}) == 0

    def test_no_entities_noop(self, db):
        assert update_edge_weights(db, {"verdict": "block", "facts": {}}) == 0

    def test_no_relations_returns_zero(self):
        d = NousDB(":memory:")
        d.upsert_entities([Entity(id="tool:orphan", etype="tool")])
        gate_result = {
            "verdict": "block",
            "kg_context": {"entities": [{"id": "tool:orphan"}], "policies": []},
            "facts": {},
        }
        assert update_edge_weights(d, gate_result) == 0

    def test_deduplication(self, db):
        """Same edge found via both from_id and to_id should only update once."""
        gate_result = {
            "verdict": "block",
            "kg_context": {
                "entities": [{"id": "tool:send_email"}, {"id": "person:alice"}],
                "policies": [],
            },
            "facts": {},
        }
        count = update_edge_weights(db, gate_result)
        assert count == 1  # single edge, not 2
        rel = _read_relation(db, "tool:send_email", "person:alice", "governed_by")
        props = rel["props"] if isinstance(rel["props"], dict) else json.loads(rel["props"])
        assert props["alpha"] == pytest.approx(2.0)  # updated once, not twice

    def test_cumulative_updates(self, db):
        """Two sequential block verdicts should accumulate."""
        gate_result = {
            "verdict": "block",
            "kg_context": {"entities": [{"id": "tool:send_email"}], "policies": []},
            "facts": {},
        }
        update_edge_weights(db, gate_result)
        update_edge_weights(db, gate_result)
        rel = _read_relation(db, "tool:send_email", "person:alice", "governed_by")
        props = rel["props"] if isinstance(rel["props"], dict) else json.loads(rel["props"])
        assert props["alpha"] == pytest.approx(3.0)
        assert rel["confidence"] == pytest.approx(3.0 / 4.0)
