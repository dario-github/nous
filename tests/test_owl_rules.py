"""Tests for OWL 2 RL reasoning rules (E1).

Covers:
- SubClassOf transitive closure
- Property chain inference
- Domain/Range type inference
- Integration with NousDB convenience methods
- MITRE ATT&CK data scenarios
"""
import pytest
import sys
sys.path.insert(0, 'tests')
from _paths import KG_AVAILABLE
import time

from nous.db import NousDB
from nous.schema import Entity, Relation
from nous.owl_rules import (
    add_subclass,
    add_property_chain,
    add_domain_range,
    materialize_inferences,
    inferred_types,
    inferred_relations,
    subclass_closure,
    subclass_descendants,
    init_owl_schema,
)


pytestmark = pytest.mark.skipif(
    not KG_AVAILABLE,
    reason="KG entities dir not present (skipped on bare CI / sanitised public clones)",
)


@pytest.fixture
def db():
    """In-memory NousDB with OWL tables."""
    d = NousDB(":memory:")
    yield d
    d.close()


@pytest.fixture
def mitre_db(db):
    """NousDB seeded with a subset of MITRE ATT&CK data + OWL axioms."""
    # Entities: 2 tactics, 3 techniques
    entities = [
        Entity(id="attack:tactic:TA0001", etype="attack_tactic",
               labels=["mitre"], properties={"name": "Initial Access"}),
        Entity(id="attack:tactic:TA0002", etype="attack_tactic",
               labels=["mitre"], properties={"name": "Execution"}),
        Entity(id="attack:technique:T1566", etype="attack_technique",
               labels=["mitre"], properties={"name": "Phishing", "tactic_id": "TA0001"}),
        Entity(id="attack:technique:T1059", etype="attack_technique",
               labels=["mitre"], properties={"name": "Command Interpreter", "tactic_id": "TA0002"}),
        Entity(id="attack:technique:T1203", etype="attack_technique",
               labels=["mitre"], properties={"name": "Client Execution", "tactic_id": "TA0002"}),
        # A category entity
        Entity(id="category:Cybercrime", etype="harm_category",
               labels=["agentharm"], properties={"name": "Cybercrime"}),
        # A target entity
        Entity(id="target:acme_corp", etype="organization",
               labels=[], properties={"name": "Acme Corp"}),
        # A location entity
        Entity(id="location:us_east", etype="region",
               labels=[], properties={"name": "US East"}),
    ]
    db.upsert_entities(entities)

    # Relations
    relations = [
        Relation(from_id="attack:tactic:TA0001",
                 to_id="attack:technique:T1566", rtype="CONTAINS"),
        Relation(from_id="attack:tactic:TA0002",
                 to_id="attack:technique:T1059", rtype="CONTAINS"),
        Relation(from_id="attack:tactic:TA0002",
                 to_id="attack:technique:T1203", rtype="CONTAINS"),
        Relation(from_id="category:Cybercrime",
                 to_id="attack:tactic:TA0001", rtype="EXPLOITED_BY"),
        # For property chain test: target -> located_in -> region
        Relation(from_id="attack:technique:T1566",
                 to_id="target:acme_corp", rtype="TARGETS"),
        Relation(from_id="target:acme_corp",
                 to_id="location:us_east", rtype="LOCATED_IN"),
    ]
    db.upsert_relations(relations)

    # OWL axioms: type hierarchy
    # attack_technique subClassOf cyber_action
    add_subclass(db, "attack_technique", "cyber_action")
    # cyber_action subClassOf harmful_action
    add_subclass(db, "cyber_action", "harmful_action")
    # harmful_action subClassOf action (3-level chain)
    add_subclass(db, "harmful_action", "action")
    # attack_tactic subClassOf attack_strategy
    add_subclass(db, "attack_tactic", "attack_strategy")

    # Property chain: TARGETS ∘ LOCATED_IN → OPERATES_IN
    add_property_chain(db, "chain:targets_located",
                       "TARGETS", "LOCATED_IN", "OPERATES_IN")

    # Domain/Range
    add_domain_range(db, "CONTAINS",
                     domain_type="attack_tactic", range_type="attack_technique")
    add_domain_range(db, "TARGETS",
                     domain_type="threat_actor", range_type="organization")

    return db


# ── Test 1: SubClassOf transitive closure ────────────────────────────

class TestSubClassTransitive:
    def test_direct_subclass(self, mitre_db):
        """Direct subclass: attack_technique → cyber_action."""
        supers = subclass_closure(mitre_db, "attack_technique")
        assert "cyber_action" in supers

    def test_transitive_2hop(self, mitre_db):
        """2-hop: attack_technique → cyber_action → harmful_action."""
        supers = subclass_closure(mitre_db, "attack_technique")
        assert "harmful_action" in supers

    def test_transitive_3hop(self, mitre_db):
        """3-hop: attack_technique → ... → action."""
        supers = subclass_closure(mitre_db, "attack_technique")
        assert "action" in supers
        # Should have all 3 superclasses
        assert set(supers) == {"cyber_action", "harmful_action", "action"}

    def test_descendants(self, mitre_db):
        """Descendants of harmful_action includes attack_technique + cyber_action."""
        descs = subclass_descendants(mitre_db, "harmful_action")
        assert "cyber_action" in descs
        assert "attack_technique" in descs

    def test_materialize_subclass_types(self, mitre_db):
        """After materialize, technique entities get inferred types."""
        stats = materialize_inferences(mitre_db)
        assert stats["subclass_count"] > 0

        # T1566 is attack_technique → should be inferred as cyber_action, harmful_action, action
        types = inferred_types(mitre_db, "attack:technique:T1566")
        type_names = [t["inferred_etype"] for t in types]
        assert "cyber_action" in type_names
        assert "harmful_action" in type_names
        assert "action" in type_names

    def test_tactic_inferred_type(self, mitre_db):
        """Tactic entities get attack_strategy via subclass."""
        materialize_inferences(mitre_db)
        types = inferred_types(mitre_db, "attack:tactic:TA0001")
        type_names = [t["inferred_etype"] for t in types]
        assert "attack_strategy" in type_names


# ── Test 2: Property chain ───────────────────────────────────────────

class TestPropertyChain:
    def test_chain_inference(self, mitre_db):
        """TARGETS ∘ LOCATED_IN → OPERATES_IN."""
        stats = materialize_inferences(mitre_db)
        assert stats["chain_count"] >= 1

        # T1566 targets acme_corp, acme_corp located_in us_east
        # → T1566 OPERATES_IN us_east
        rels = inferred_relations(mitre_db, "attack:technique:T1566", "out")
        rtypes = [(r["to_id"], r["rtype"]) for r in rels]
        assert ("location:us_east", "OPERATES_IN") in rtypes

    def test_chain_confidence(self, mitre_db):
        """Inferred chain relations have reduced confidence (0.9)."""
        materialize_inferences(mitre_db)
        rels = inferred_relations(mitre_db, "attack:technique:T1566", "out")
        operates_in = [r for r in rels if r["rtype"] == "OPERATES_IN"]
        assert len(operates_in) == 1
        assert operates_in[0]["confidence"] == pytest.approx(0.9)

    def test_chain_no_false_positive(self, mitre_db):
        """No chain fires when intermediate node is missing."""
        # T1059 has no TARGETS relation → no OPERATES_IN
        materialize_inferences(mitre_db)
        rels = inferred_relations(mitre_db, "attack:technique:T1059", "out")
        assert all(r["rtype"] != "OPERATES_IN" for r in rels)


# ── Test 3: Domain/Range ─────────────────────────────────────────────

class TestDomainRange:
    def test_domain_inference(self, mitre_db):
        """CONTAINS domain=attack_tactic → tactic gets inferred type."""
        materialize_inferences(mitre_db)
        # TA0001 is from_id of CONTAINS → domain type = attack_tactic
        types = inferred_types(mitre_db, "attack:tactic:TA0001")
        type_names = [t["inferred_etype"] for t in types]
        assert "attack_tactic" in type_names

    def test_range_inference(self, mitre_db):
        """CONTAINS range=attack_technique → technique gets inferred type."""
        materialize_inferences(mitre_db)
        types = inferred_types(mitre_db, "attack:technique:T1566")
        type_names = [t["inferred_etype"] for t in types]
        assert "attack_technique" in type_names

    def test_targets_domain_inference(self, mitre_db):
        """TARGETS domain=threat_actor → T1566 gets threat_actor type."""
        materialize_inferences(mitre_db)
        types = inferred_types(mitre_db, "attack:technique:T1566")
        type_names = [t["inferred_etype"] for t in types]
        # T1566 is from_id of TARGETS → domain = threat_actor
        assert "threat_actor" in type_names

    def test_targets_range_inference(self, mitre_db):
        """TARGETS range=organization → acme_corp gets organization type."""
        materialize_inferences(mitre_db)
        types = inferred_types(mitre_db, "target:acme_corp")
        type_names = [t["inferred_etype"] for t in types]
        assert "organization" in type_names


# ── Test 4: NousDB integration ───────────────────────────────────────

class TestNousDBIntegration:
    def test_run_owl_reasoning(self, mitre_db):
        """NousDB.run_owl_reasoning() works."""
        stats = mitre_db.run_owl_reasoning()
        assert stats["total"] > 0
        assert "subclass_count" in stats
        assert "chain_count" in stats
        assert "domain_range_count" in stats

    def test_inferred_type_method(self, mitre_db):
        """NousDB.inferred_type() convenience method."""
        mitre_db.run_owl_reasoning()
        types = mitre_db.inferred_type("attack:technique:T1566")
        assert len(types) > 0

    def test_inferred_relations_method(self, mitre_db):
        """NousDB.inferred_relations() convenience method."""
        mitre_db.run_owl_reasoning()
        rels = mitre_db.inferred_relations("attack:technique:T1566")
        assert any(r["rtype"] == "OPERATES_IN" for r in rels)

    def test_idempotent_reasoning(self, mitre_db):
        """Running reasoning twice produces same results (clear + rematerialize)."""
        stats1 = mitre_db.run_owl_reasoning()
        stats2 = mitre_db.run_owl_reasoning()
        assert stats1["total"] == stats2["total"]


# ── Test 5: Edge cases ───────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_db_reasoning(self, db):
        """Reasoning on empty DB produces zero results."""
        stats = materialize_inferences(db)
        assert stats["total"] == 0

    def test_no_subclass_no_inference(self, db):
        """Entities without subclass axioms get no inferred types from subclass."""
        db.upsert_entities([
            Entity(id="e1", etype="foo", labels=[], properties={}),
        ])
        stats = materialize_inferences(db)
        assert stats["subclass_count"] == 0

    def test_cycle_safe(self, db):
        """Subclass cycle (A subClassOf B, B subClassOf A) doesn't infinite loop."""
        add_subclass(db, "typeA", "typeB")
        add_subclass(db, "typeB", "typeA")
        db.upsert_entities([
            Entity(id="e1", etype="typeA", labels=[], properties={}),
        ])
        # Should not hang — Cozo handles recursive cycles via fixpoint
        stats = materialize_inferences(db)
        types = inferred_types(db, "e1")
        type_names = [t["inferred_etype"] for t in types]
        assert "typeB" in type_names
        assert "typeA" in type_names  # cycle: typeA → typeB → typeA

    def test_inferred_relations_direction_in(self, mitre_db):
        """inferred_relations with direction='in'."""
        mitre_db.run_owl_reasoning()
        rels = mitre_db.inferred_relations("location:us_east", "in")
        assert any(r["rtype"] == "OPERATES_IN" for r in rels)

    def test_subclass_closure_nonexistent(self, db):
        """subclass_closure on non-existent type returns empty."""
        assert subclass_closure(db, "nonexistent_type") == []

    def test_multiple_property_chains(self, db):
        """Multiple chain rules can fire independently."""
        db.upsert_entities([
            Entity(id="a", etype="t1", labels=[], properties={}),
            Entity(id="b", etype="t2", labels=[], properties={}),
            Entity(id="c", etype="t3", labels=[], properties={}),
        ])
        db.upsert_relations([
            Relation(from_id="a", to_id="b", rtype="R1"),
            Relation(from_id="b", to_id="c", rtype="R2"),
            Relation(from_id="a", to_id="b", rtype="S1"),
            Relation(from_id="b", to_id="c", rtype="S2"),
        ])
        add_property_chain(db, "chain1", "R1", "R2", "R3")
        add_property_chain(db, "chain2", "S1", "S2", "S3")

        stats = materialize_inferences(db)
        assert stats["chain_count"] == 2

        rels = inferred_relations(db, "a", "out")
        rtypes = {r["rtype"] for r in rels}
        assert "R3" in rtypes
        assert "S3" in rtypes
