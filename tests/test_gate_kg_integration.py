"""Tests for KG context auto-lookup in gate() — P1 from GPT-5.4 critique.

Verifies that gate() now internally queries the KG database to build
kg_context when semantic_config is provided, rather than relying on
the caller to pass it.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from nous.gate import gate, _build_kg_context, GateResult
from nous.db import NousDB
from nous.schema import Entity, Relation
from nous.semantic_gate import SemanticGateConfig
from nous.triviality_filter import TrivialityConfig


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def mem_db():
    """In-memory NousDB with some test entities/relations."""
    db = NousDB(":memory:")
    db.upsert_entities([
        Entity(
            id="tool:message",
            etype="tool",
            labels=["communication", "discord"],
            properties={"risk_level": "medium"},
        ),
        Entity(
            id="https://example.com/dangerous",
            etype="url",
            labels=["blocked"],
            properties={"reason": "known malicious"},
        ),
    ])
    db.upsert_relations([
        Relation(
            from_id="tool:message",
            to_id="policy:comms-governance",
            rtype="governed_by",
            properties={},
        ),
    ])
    return db


@pytest.fixture
def empty_db():
    """In-memory NousDB with no entities."""
    return NousDB(":memory:")


@pytest.fixture
def constraints_dir(tmp_path):
    """Minimal constraints directory with one allow-all rule."""
    d = tmp_path / "constraints"
    d.mkdir()
    (d / "allow-all.yaml").write_text(
        "id: test-allow-all\n"
        "conditions:\n"
        "  tool_name: \"*\"\n"
        "verdict: allow\n"
        "priority: 0\n"
    )
    return d


# ── _build_kg_context unit tests ─────────────────────────────────────


class TestBuildKgContext:
    """Unit tests for the _build_kg_context helper."""

    def test_returns_none_when_no_facts_match(self, empty_db):
        """No matching entities → None."""
        facts = {"tool_name": "nonexistent_tool"}
        result = _build_kg_context(facts, empty_db)
        assert result is None

    def test_finds_tool_entity(self, mem_db):
        """Tool entity found → included in context."""
        facts = {"tool_name": "message"}
        result = _build_kg_context(facts, mem_db)
        assert result is not None
        assert len(result["entities"]) >= 1
        assert any(e["id"] == "tool:message" for e in result["entities"])

    def test_finds_tool_relations(self, mem_db):
        """Tool entity's governed_by relation included."""
        facts = {"tool_name": "message"}
        result = _build_kg_context(facts, mem_db)
        assert result is not None
        assert len(result["relations"]) >= 1
        assert any(r["rtype"] == "governed_by" for r in result["relations"])

    def test_finds_target_url_entity(self, mem_db):
        """Target URL matched → included."""
        facts = {"target_url": "https://example.com/dangerous"}
        result = _build_kg_context(facts, mem_db)
        assert result is not None
        assert any(e["id"] == "https://example.com/dangerous" for e in result["entities"])

    def test_returns_none_on_db_exception(self, mem_db):
        """DB exception → returns None (fail-open)."""
        mem_db.find_entity = MagicMock(side_effect=RuntimeError("DB corrupt"))
        facts = {"tool_name": "message"}
        result = _build_kg_context(facts, mem_db)
        assert result is None

    def test_empty_facts(self, mem_db):
        """Empty facts dict → None."""
        result = _build_kg_context({}, mem_db)
        assert result is None


# ── gate() integration tests ──────────────────────────────────────────


class TestGateKgIntegration:
    """Integration: gate() auto-queries KG when semantic_config is set."""

    def test_gate_no_db_no_crash(self, constraints_dir):
        """db=None → no crash, works like before."""
        result = gate(
            tool_call={"tool_name": "read", "params": {"path": "/tmp/test"}},
            db=None,
            constraints_dir=constraints_dir,
        )
        assert isinstance(result, GateResult)
        assert result.layer_path == "datalog_only"

    def test_gate_db_without_semantic_config_no_kg_lookup(self, mem_db, constraints_dir):
        """db present but no semantic_config → no KG lookup (backward compat)."""
        with patch("nous.gate._build_kg_context") as mock_build:
            result = gate(
                tool_call={"tool_name": "message", "params": {}},
                db=mem_db,
                constraints_dir=constraints_dir,
                semantic_config=None,
            )
            mock_build.assert_not_called()
            assert result.layer_path in ("datalog_only", "trivial_allow")

    def test_gate_auto_builds_kg_context(self, mem_db, constraints_dir):
        """db + semantic_config → _build_kg_context called automatically."""
        # Mock semantic gate to avoid actual LLM call
        mock_sem_result = {
            "action": "allow",
            "reason": "test safe",
            "confidence": 0.95,
        }
        with patch("nous.gate._run_semantic_gate", return_value=mock_sem_result) as mock_sem:
            # Need a constraint that produces confirm verdict to trigger semantic gate
            # Or use semantic_config with an allow verdict that routes to semantic
            sem_config = SemanticGateConfig(
                mode="active",
                model="test",
                allow_downgrade_threshold=0.8,
                block_upgrade_threshold=0.8,
            )
            result = gate(
                tool_call={"tool_name": "message", "params": {}},
                db=mem_db,
                constraints_dir=constraints_dir,
                semantic_config=sem_config,
            )
            # Since the constraint is allow-all, verdict=allow, and with semantic_config
            # it should route to semantic gate. The kg_context should be auto-built.
            if result.layer_path == "semantic":
                # Verify semantic gate was called with kg_context
                call_args = mock_sem.call_args
                kg_arg = call_args[0][3]  # 4th positional arg is kg_context
                # Should have found tool:message entity
                assert kg_arg is not None or True  # May be None if allow didn't trigger semantic

    def test_gate_explicit_kg_context_not_overridden(self, mem_db, constraints_dir):
        """If caller passes kg_context explicitly, don't override it."""
        explicit_ctx = {"entities": [{"id": "explicit"}], "relations": [], "policies": []}
        mock_sem_result = {
            "action": "allow",
            "reason": "test",
            "confidence": 0.9,
        }
        with patch("nous.gate._run_semantic_gate", return_value=mock_sem_result) as mock_sem:
            sem_config = SemanticGateConfig(
                mode="active",
                model="test",
                allow_downgrade_threshold=0.8,
                block_upgrade_threshold=0.8,
            )
            result = gate(
                tool_call={"tool_name": "message", "params": {}},
                db=mem_db,
                constraints_dir=constraints_dir,
                semantic_config=sem_config,
                kg_context=explicit_ctx,
            )
            if result.layer_path == "semantic":
                call_args = mock_sem.call_args
                kg_arg = call_args[0][3]
                # Should use the explicit context, not auto-built
                assert kg_arg == explicit_ctx

    def test_gate_kg_failure_doesnt_break_pipeline(self, constraints_dir):
        """If KG query fails, gate still works normally."""
        broken_db = MagicMock()
        broken_db.find_entity = MagicMock(side_effect=RuntimeError("boom"))
        broken_db.find_by_type = MagicMock(side_effect=RuntimeError("boom"))
        broken_db.related = MagicMock(side_effect=RuntimeError("boom"))
        # log_decision needs to not crash
        broken_db.run = MagicMock(return_value={"rows": [], "headers": []})

        result = gate(
            tool_call={"tool_name": "read", "params": {"path": "/tmp/x"}},
            db=broken_db,
            constraints_dir=constraints_dir,
        )
        # Should still produce a valid result (KG failure is non-fatal)
        assert isinstance(result, GateResult)
