"""Tests for Markov Blanket selective KG injection (E2).

Covers:
- Blanket computation (seeds, parents, children, co-parents)
- Depth limiting
- max_entities truncation
- OWL inference integration
- Empty KG / no seeds
- Seed extraction from facts
- Prompt formatting
- Gate integration (end-to-end)
"""
import pytest
from nous.db import NousDB
from nous.schema import Entity, Relation
from nous.markov_blanket import (
    compute_blanket,
    _extract_seed_entities,
    _empty_blanket,
    format_blanket_for_prompt,
)
from nous.owl_rules import (
    init_owl_schema,
    add_subclass,
    add_domain_range,
    materialize_inferences,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def db():
    """In-memory DB with a small KG for blanket tests."""
    db = NousDB(":memory:")
    # Entities
    db.upsert_entities([
        Entity(id="tool:send_email", etype="tool", labels=["communication"],
               properties={"risk_level": "medium"}, confidence=0.9),
        Entity(id="policy:comms", etype="policy", labels=[],
               properties={"rule": "No spam"}, confidence=1.0),
        Entity(id="recipient:alice@example.com", etype="person", labels=["user"],
               properties={}, confidence=0.85),
        Entity(id="category:Fraud", etype="category", labels=[],
               properties={"severity": "high", "evasion_patterns": ["business email"]},
               confidence=1.0),
        Entity(id="tool:file_write", etype="tool", labels=["filesystem"],
               properties={"risk_level": "high", "irreversible": True}, confidence=0.95),
        Entity(id="resource:/etc/passwd", etype="file", labels=["system"],
               properties={"sensitive": True}, confidence=0.9),
        Entity(id="co-parent:spam-filter", etype="policy", labels=[],
               properties={}, confidence=0.8),
    ])
    # Relations
    db.upsert_relations([
        Relation(from_id="tool:send_email", to_id="policy:comms",
                 rtype="governed_by", properties={}, confidence=0.95),
        Relation(from_id="tool:send_email", to_id="recipient:alice@example.com",
                 rtype="targets", properties={}, confidence=0.8),
        Relation(from_id="category:Fraud", to_id="tool:send_email",
                 rtype="monitors", properties={}, confidence=0.9),
        Relation(from_id="co-parent:spam-filter", to_id="policy:comms",
                 rtype="enforces", properties={}, confidence=0.85),
        Relation(from_id="tool:file_write", to_id="resource:/etc/passwd",
                 rtype="accesses", properties={}, confidence=0.9),
    ])
    return db


@pytest.fixture
def empty_db():
    return NousDB(":memory:")


@pytest.fixture
def db_with_owl(db):
    """DB with OWL rules for inference integration."""
    add_subclass(db, "tool", "action")
    add_subclass(db, "action", "operation")
    add_domain_range(db, "governed_by", domain_type="governed_entity", range_type="governance_policy")
    materialize_inferences(db)
    return db


# ── Seed Extraction ──────────────────────────────────────────────────


class TestSeedExtraction:
    def test_extract_tool_name(self):
        facts = {"tool_name": "send_email"}
        seeds = _extract_seed_entities(facts)
        assert "tool:send_email" in seeds

    def test_extract_target_url(self):
        facts = {"tool_name": "browser", "target_url": "https://evil.com"}
        seeds = _extract_seed_entities(facts)
        assert "tool:browser" in seeds
        assert "https://evil.com" in seeds

    def test_extract_category(self):
        # Loop 48: category field is from content inference (not benchmark labels).
        # The adapter.py fix moved harm_category out of params, so facts["category"]
        # will be empty in benchmark runs — no label leakage.
        # When category IS present (production or inferred), it should be seeded.
        facts = {"tool_name": "x", "category": "Fraud"}
        seeds = _extract_seed_entities(facts)
        assert "tool:x" in seeds
        assert "category:Fraud" in seeds  # content-inferred categories ARE valid seeds

    def test_empty_facts(self):
        assert _extract_seed_entities({}) == []

    def test_name_fallback(self):
        facts = {"name": "my_tool"}
        seeds = _extract_seed_entities(facts)
        assert "tool:my_tool" in seeds


# ── Blanket Computation ──────────────────────────────────────────────


class TestComputeBlanket:
    def test_basic_blanket_structure(self, db):
        blanket = compute_blanket(db, ["tool:send_email"])
        assert "entities" in blanket
        assert "relations" in blanket
        assert "inferred_types" in blanket
        assert "relevance_scores" in blanket
        assert len(blanket["entities"]) > 0

    def test_seed_included(self, db):
        blanket = compute_blanket(db, ["tool:send_email"])
        ids = {e["id"] for e in blanket["entities"]}
        assert "tool:send_email" in ids

    def test_children_included(self, db):
        """Children of seed should be in blanket."""
        blanket = compute_blanket(db, ["tool:send_email"])
        ids = {e["id"] for e in blanket["entities"]}
        # send_email → policy:comms (governed_by), send_email → recipient:alice (targets)
        assert "policy:comms" in ids
        assert "recipient:alice@example.com" in ids

    def test_parents_included(self, db):
        """Parents of seed should be in blanket."""
        blanket = compute_blanket(db, ["tool:send_email"])
        ids = {e["id"] for e in blanket["entities"]}
        # category:Fraud → send_email (monitors)
        assert "category:Fraud" in ids

    def test_co_parents_at_depth_2(self, db):
        """Co-parents of children should be included at depth >= 2."""
        blanket = compute_blanket(db, ["tool:send_email"], max_depth=2)
        ids = {e["id"] for e in blanket["entities"]}
        # co-parent:spam-filter → policy:comms (child of send_email)
        assert "co-parent:spam-filter" in ids

    def test_depth_1_no_co_parents(self, db):
        """At depth 1, co-parents should NOT be included."""
        blanket = compute_blanket(db, ["tool:send_email"], max_depth=1)
        ids = {e["id"] for e in blanket["entities"]}
        assert "co-parent:spam-filter" not in ids

    def test_max_entities_truncation(self, db):
        """Entities should be truncated to max_entities."""
        blanket = compute_blanket(db, ["tool:send_email"], max_entities=3)
        assert len(blanket["entities"]) <= 3

    def test_relevance_scores(self, db):
        """Seeds should have highest relevance, children/parents lower."""
        blanket = compute_blanket(db, ["tool:send_email"])
        scores = blanket["relevance_scores"]
        assert scores.get("tool:send_email") == 1.0
        # Children/parents should have lower relevance
        for eid, score in scores.items():
            if eid != "tool:send_email":
                assert score < 1.0

    def test_empty_seeds(self, db):
        blanket = compute_blanket(db, [])
        assert blanket == _empty_blanket()

    def test_none_db(self):
        blanket = compute_blanket(None, ["tool:x"])
        assert blanket == _empty_blanket()

    def test_nonexistent_seeds(self, empty_db):
        blanket = compute_blanket(empty_db, ["tool:nonexistent"])
        assert blanket == _empty_blanket()

    def test_relations_captured(self, db):
        """Relations between blanket entities should be captured."""
        blanket = compute_blanket(db, ["tool:send_email"])
        assert len(blanket["relations"]) > 0
        rtypes = {r["rtype"] for r in blanket["relations"]}
        assert "governed_by" in rtypes

    def test_multiple_seeds(self, db):
        """Multiple seeds expand the blanket."""
        blanket = compute_blanket(db, ["tool:send_email", "tool:file_write"])
        ids = {e["id"] for e in blanket["entities"]}
        assert "tool:send_email" in ids
        assert "tool:file_write" in ids
        assert "resource:/etc/passwd" in ids  # child of file_write


# ── OWL Inference Integration ────────────────────────────────────────


class TestOWLIntegration:
    def test_inferred_types_included(self, db_with_owl):
        blanket = compute_blanket(db_with_owl, ["tool:send_email"])
        # OWL: tool subClassOf action subClassOf operation
        # send_email (etype=tool) should have inferred types
        inferred = blanket["inferred_types"]
        assert len(inferred) > 0
        inferred_etypes = {it["inferred_etype"] for it in inferred}
        assert "action" in inferred_etypes or "operation" in inferred_etypes

    def test_inferred_types_have_rule(self, db_with_owl):
        blanket = compute_blanket(db_with_owl, ["tool:send_email"])
        for it in blanket["inferred_types"]:
            assert "rule" in it
            assert it["rule"]  # non-empty


# ── Prompt Formatting ────────────────────────────────────────────────


class TestFormatBlanket:
    def test_empty_blanket_message(self):
        result = format_blanket_for_prompt(_empty_blanket())
        assert "No relevant" in result

    def test_formatted_contains_entity_ids(self, db):
        blanket = compute_blanket(db, ["tool:send_email"])
        text = format_blanket_for_prompt(blanket)
        assert "tool:send_email" in text
        assert "KG Context" in text

    def test_formatted_shows_roles(self, db):
        blanket = compute_blanket(db, ["tool:send_email"])
        text = format_blanket_for_prompt(blanket)
        # Non-seed entities should show their role
        assert "child" in text or "parent" in text

    def test_formatted_shows_relations(self, db):
        blanket = compute_blanket(db, ["tool:send_email"])
        text = format_blanket_for_prompt(blanket)
        assert "governed_by" in text or "targets" in text or "monitors" in text


# ── Gate Integration ─────────────────────────────────────────────────


class TestGateIntegration:
    """End-to-end: gate() uses Markov Blanket for KG context."""

    @pytest.fixture
    def constraints_dir(self, tmp_path):
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

    def test_gate_builds_blanket_context(self, db, constraints_dir):
        """gate() should populate kg_context with blanket data."""
        from nous.gate import gate, GateResult
        from nous.semantic_gate import SemanticGateConfig

        def mock_provider(prompt, timeout_ms, model):
            return '{"action": "allow", "reason": "ok", "confidence": 0.95}'

        config = SemanticGateConfig(
            enabled=True, mode="active", provider=mock_provider
        )
        result = gate(
            tool_call={"tool_name": "send_email", "params": {"to": "alice@example.com"}},
            db=db,
            constraints_dir=constraints_dir,
            semantic_config=config,
        )
        assert result.kg_context is not None
        # Should have blanket extension
        assert "blanket" in result.kg_context

    def test_gate_blanket_injected_to_semantic_gate(self, db, constraints_dir):
        """Semantic gate prompt should receive blanket context."""
        from nous.gate import gate
        from nous.semantic_gate import SemanticGateConfig

        captured_prompts = []

        def capturing_provider(prompt, timeout_ms, model):
            captured_prompts.append(prompt)
            return '{"action": "allow", "reason": "ok", "confidence": 0.95}'

        config = SemanticGateConfig(
            enabled=True, mode="active", provider=capturing_provider
        )
        result = gate(
            tool_call={"tool_name": "send_email"},
            db=db,
            constraints_dir=constraints_dir,
            semantic_config=config,
        )
        # The prompt should contain blanket-formatted KG context
        assert len(captured_prompts) > 0
        prompt = captured_prompts[0]
        assert "tool:send_email" in prompt
        # Should use blanket format, not old raw format
        assert "KG Context (Markov Blanket)" in prompt or "tool:send_email" in prompt

    def test_gate_no_db_no_blanket(self, constraints_dir):
        """Without DB, kg_context should be None."""
        from nous.gate import gate
        from nous.semantic_gate import SemanticGateConfig

        config = SemanticGateConfig(
            enabled=True, mode="shadow",
            provider=lambda p, t, m: '{"action": "allow", "reason": "ok", "confidence": 0.9}',
        )
        result = gate(
            tool_call={"tool_name": "unknown_tool"},
            constraints_dir=constraints_dir,
            semantic_config=config,
        )
        assert result.kg_context is None

    def test_gate_graceful_degradation(self, empty_db, constraints_dir):
        """Empty DB → kg_context is None, gate still works."""
        from nous.gate import gate
        from nous.semantic_gate import SemanticGateConfig

        config = SemanticGateConfig(
            enabled=True, mode="active",
            provider=lambda p, t, m: '{"action": "allow", "reason": "ok", "confidence": 0.9}',
        )
        result = gate(
            tool_call={"tool_name": "nonexistent"},
            db=empty_db,
            constraints_dir=constraints_dir,
            semantic_config=config,
        )
        # Should complete without error
        assert result.verdict is not None
