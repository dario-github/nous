#!/usr/bin/env python3
"""Nous — KG Security Entity Seeding Script

Seeds the knowledge graph with security-domain entities that
_build_kg_context() can find during gate pipeline execution.

Current KG: 24 person/concept/project entities — zero tool/policy/category.
This script adds entities that give the semantic gate real context.

Usage:
    cd .
    PYTHONPATH=src .venv/bin/python scripts/seed_security_entities.py [--db PATH] [--dry-run]
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.db import NousDB
from nous.schema import Entity, Relation

# ── Tool Entities ─────────────────────────────────────────────────────────
# Format: _build_kg_context() looks for f"tool:{tool_name}"
# Properties encode risk level and required safeguards

TOOL_ENTITIES = [
    # High-risk execution tools
    Entity(
        id="tool:exec",
        etype="tool",
        labels=["tool", "execution", "high-risk"],
        properties={
            "risk_level": "critical",
            "description": "Execute arbitrary shell commands",
            "requires_confirmation": True,
            "irreversible": True,
            "attack_surface": ["code_execution", "file_system", "network"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="tool:write",
        etype="tool",
        labels=["tool", "file-system", "medium-risk"],
        properties={
            "risk_level": "high",
            "description": "Write content to file, overwrite if exists",
            "requires_confirmation": False,  # unless protected path
            "irreversible": True,
            "attack_surface": ["file_overwrite", "config_tampering"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="tool:edit",
        etype="tool",
        labels=["tool", "file-system", "medium-risk"],
        properties={
            "risk_level": "medium",
            "description": "Precise surgical file edits",
            "requires_confirmation": False,
            "irreversible": False,  # can be reverted
            "attack_surface": ["config_tampering"],
        },
        source="seed:security-v1",
    ),
    # Communication tools
    Entity(
        id="tool:message",
        etype="tool",
        labels=["tool", "communication", "medium-risk"],
        properties={
            "risk_level": "medium",
            "description": "Send messages via channel plugins (Discord/Slack)",
            "requires_confirmation": False,
            "irreversible": True,  # can't unsend
            "attack_surface": ["social_engineering", "spam", "phishing"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="tool:tts",
        etype="tool",
        labels=["tool", "communication", "low-risk"],
        properties={
            "risk_level": "low",
            "description": "Text to speech conversion",
            "requires_confirmation": False,
            "irreversible": False,
            "attack_surface": [],
        },
        source="seed:security-v1",
    ),
    # Browser / web tools
    Entity(
        id="tool:browser",
        etype="tool",
        labels=["tool", "web", "medium-risk"],
        properties={
            "risk_level": "medium",
            "description": "Control web browser (navigate, click, type)",
            "requires_confirmation": False,
            "irreversible": True,
            "attack_surface": ["credential_exposure", "data_exfil", "web_injection"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="tool:web_search",
        etype="tool",
        labels=["tool", "web", "low-risk"],
        properties={
            "risk_level": "low",
            "description": "Search the web via Brave API",
            "requires_confirmation": False,
            "irreversible": False,
            "attack_surface": [],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="tool:web_fetch",
        etype="tool",
        labels=["tool", "web", "low-risk"],
        properties={
            "risk_level": "low",
            "description": "Fetch and extract content from URL",
            "requires_confirmation": False,
            "irreversible": False,
            "attack_surface": ["ssrf"],
        },
        source="seed:security-v1",
    ),
    # Node control tools
    Entity(
        id="tool:nodes",
        etype="tool",
        labels=["tool", "device-control", "medium-risk"],
        properties={
            "risk_level": "medium",
            "description": "Control paired nodes (camera, screen, location)",
            "requires_confirmation": False,
            "irreversible": False,
            "attack_surface": ["privacy_violation", "surveillance"],
        },
        source="seed:security-v1",
    ),
    # System tools
    Entity(
        id="tool:gateway",
        etype="tool",
        labels=["tool", "system", "critical-risk"],
        properties={
            "risk_level": "critical",
            "description": "Restart, configure, or update the gateway daemon",
            "requires_confirmation": True,
            "irreversible": True,
            "attack_surface": ["service_disruption", "config_tampering"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="tool:cron",
        etype="tool",
        labels=["tool", "scheduling", "medium-risk"],
        properties={
            "risk_level": "medium",
            "description": "Manage scheduled tasks",
            "requires_confirmation": False,
            "irreversible": True,
            "attack_surface": ["persistence", "privilege_escalation"],
        },
        source="seed:security-v1",
    ),
    # Session tools
    Entity(
        id="tool:sessions_spawn",
        etype="tool",
        labels=["tool", "orchestration", "medium-risk"],
        properties={
            "risk_level": "medium",
            "description": "Spawn isolated sub-agent sessions",
            "requires_confirmation": False,
            "irreversible": False,
            "attack_surface": ["resource_exhaustion", "privilege_delegation"],
        },
        source="seed:security-v1",
    ),
    # Read-only tools (low risk)
    Entity(
        id="tool:read",
        etype="tool",
        labels=["tool", "file-system", "low-risk"],
        properties={
            "risk_level": "low",
            "description": "Read file contents",
            "requires_confirmation": False,
            "irreversible": False,
            "attack_surface": ["data_exfil"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="tool:memory_search",
        etype="tool",
        labels=["tool", "memory", "low-risk"],
        properties={
            "risk_level": "low",
            "description": "Semantic search over memory files",
            "requires_confirmation": False,
            "irreversible": False,
            "attack_surface": [],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="tool:image",
        etype="tool",
        labels=["tool", "analysis", "low-risk"],
        properties={
            "risk_level": "low",
            "description": "Analyze images with vision model",
            "requires_confirmation": False,
            "irreversible": False,
            "attack_surface": [],
        },
        source="seed:security-v1",
    ),
]

# ── Policy Entities ───────────────────────────────────────────────────────
# These map harm categories to governance rules

POLICY_ENTITIES = [
    Entity(
        id="policy:destructive-ops",
        etype="policy",
        labels=["policy", "governance"],
        properties={
            "description": "Destructive operations require explicit confirmation",
            "applies_to": ["exec", "write", "gateway"],
            "rule": "Any operation that deletes files, modifies configs, or publishes content requires user confirmation",
            "source_rule": "T3",
        },
        source="seed:security-v1",
    ),
    Entity(
        id="policy:data-integrity",
        etype="policy",
        labels=["policy", "governance"],
        properties={
            "description": "Data outputs must be factually grounded",
            "applies_to": ["message", "write"],
            "rule": "Data analysis, system evaluation, and investment decisions must be backed by real evidence. No guessing or fabrication.",
            "source_rule": "T6",
        },
        source="seed:security-v1",
    ),
    Entity(
        id="policy:content-safety",
        etype="policy",
        labels=["policy", "governance"],
        properties={
            "description": "Harmful content generation is prohibited",
            "applies_to": ["message", "write", "exec", "sessions_spawn"],
            "rule": "Refuse requests involving weapons synthesis, bioweapons, unauthorized system intrusion, or targeted harm plans",
            "source_rule": "T14",
        },
        source="seed:security-v1",
    ),
    Entity(
        id="policy:social-media-links",
        etype="policy",
        labels=["policy", "governance"],
        properties={
            "description": "Social media links must use standard parsing pipeline",
            "applies_to": ["browser", "web_fetch"],
            "rule": "Social media URLs must go through tikhub→summarize→browser pipeline, not direct browser access",
            "source_rule": "T5",
        },
        source="seed:security-v1",
    ),
    Entity(
        id="policy:temporal-verification",
        etype="policy",
        labels=["policy", "governance"],
        properties={
            "description": "Time-sensitive information must be verified with tools",
            "applies_to": ["message", "write"],
            "rule": "Stock prices, model versions, API status, news must be verified with tools, not recalled from memory",
            "source_rule": "T1",
        },
        source="seed:security-v1",
    ),
    Entity(
        id="policy:large-file-safety",
        etype="policy",
        labels=["policy", "governance"],
        properties={
            "description": "Large file writes must be split",
            "applies_to": ["write"],
            "rule": "Single write operations must not exceed 400 lines. Use skeleton-first approach for large files.",
            "source_rule": "T10",
        },
        source="seed:security-v1",
    ),
]

# ── Category Entities ─────────────────────────────────────────────────────
# AgentHarm benchmark categories — _build_kg_context() queries f"category:{category}"

CATEGORY_ENTITIES = [
    Entity(
        id="category:Cybercrime",
        etype="category",
        labels=["category", "harm"],
        properties={
            "description": "Credential harvesting, unauthorized access, malware creation",
            "severity": "critical",
            "evasion_patterns": ["academic_research_framing", "testing_simulation"],
            "signal_keywords": ["credential", "phishing", "exploit", "vulnerability"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="category:Fraud",
        etype="category",
        labels=["category", "harm"],
        properties={
            "description": "Synthetic identities, financial fraud, impersonation",
            "severity": "critical",
            "evasion_patterns": ["academic_alibi", "business_use_case"],
            "signal_keywords": ["synthetic", "identity", "impersonate", "forge"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="category:Weapons",
        etype="category",
        labels=["category", "harm"],
        properties={
            "description": "Weapons creation, modification, or procurement",
            "severity": "critical",
            "evasion_patterns": ["engineering_design", "educational_context"],
            "signal_keywords": ["weapon", "launcher", "explosive", "ammunition"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="category:Physical_harm",
        etype="category",
        labels=["category", "harm"],
        properties={
            "description": "Chemical weapons, crowd control agents, poisons",
            "severity": "critical",
            "evasion_patterns": ["engineering_design", "research_context"],
            "signal_keywords": ["chemical", "toxic", "harm", "crowd control"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="category:Harassment",
        etype="category",
        labels=["category", "harm"],
        properties={
            "description": "Targeted harassment, doxxing, stalking",
            "severity": "high",
            "evasion_patterns": ["academic_study", "journalism"],
            "signal_keywords": ["harass", "stalk", "doxx", "threaten"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="category:Hate",
        etype="category",
        labels=["category", "harm"],
        properties={
            "description": "Hate speech, discrimination, extremism",
            "severity": "high",
            "evasion_patterns": ["historical_analysis", "comparative_study"],
            "signal_keywords": ["hate", "supremacy", "discriminate", "extremist"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="category:Drugs",
        etype="category",
        labels=["category", "harm"],
        properties={
            "description": "Drug synthesis, distribution networks",
            "severity": "high",
            "evasion_patterns": ["chemistry_education", "harm_reduction"],
            "signal_keywords": ["synthesis", "precursor", "distribution", "controlled"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="category:Sexual",
        etype="category",
        labels=["category", "harm"],
        properties={
            "description": "Non-consensual content, exploitation",
            "severity": "critical",
            "evasion_patterns": ["creative_writing", "fictional_context"],
            "signal_keywords": ["exploit", "non-consensual", "minor"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="category:Copyright",
        etype="category",
        labels=["category", "harm"],
        properties={
            "description": "Copyright infringement, IP theft",
            "severity": "medium",
            "evasion_patterns": ["fair_use_claim", "educational_purpose"],
            "signal_keywords": ["copyright", "pirate", "reproduce", "clone"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="category:Disinformation",
        etype="category",
        labels=["category", "harm"],
        properties={
            "description": "Fake news, misleading content, propaganda",
            "severity": "high",
            "evasion_patterns": ["media_literacy", "satire_framing"],
            "signal_keywords": ["disinformation", "fake", "misleading", "propaganda"],
        },
        source="seed:security-v1",
    ),
    Entity(
        id="category:Other",
        etype="category",
        labels=["category", "harm"],
        properties={
            "description": "Miscellaneous harmful: fake compliance, forgery",
            "severity": "medium",
            "evasion_patterns": ["tail_injection", "context_confusion"],
            "signal_keywords": ["compliance", "forge", "counterfeit", "fake"],
        },
        source="seed:security-v1",
    ),
]

# ── Relations ─────────────────────────────────────────────────────────────
# Connect tools to policies via governed_by

RELATIONS = [
    # exec governed by destructive-ops and content-safety
    Relation(from_id="tool:exec", to_id="policy:destructive-ops", rtype="governed_by", source="seed:security-v1"),
    Relation(from_id="tool:exec", to_id="policy:content-safety", rtype="governed_by", source="seed:security-v1"),
    # write governed by destructive-ops and large-file-safety
    Relation(from_id="tool:write", to_id="policy:destructive-ops", rtype="governed_by", source="seed:security-v1"),
    Relation(from_id="tool:write", to_id="policy:large-file-safety", rtype="governed_by", source="seed:security-v1"),
    Relation(from_id="tool:write", to_id="policy:data-integrity", rtype="governed_by", source="seed:security-v1"),
    # message governed by data-integrity and content-safety
    Relation(from_id="tool:message", to_id="policy:data-integrity", rtype="governed_by", source="seed:security-v1"),
    Relation(from_id="tool:message", to_id="policy:content-safety", rtype="governed_by", source="seed:security-v1"),
    Relation(from_id="tool:message", to_id="policy:temporal-verification", rtype="governed_by", source="seed:security-v1"),
    # browser governed by social-media-links
    Relation(from_id="tool:browser", to_id="policy:social-media-links", rtype="governed_by", source="seed:security-v1"),
    # gateway governed by destructive-ops
    Relation(from_id="tool:gateway", to_id="policy:destructive-ops", rtype="governed_by", source="seed:security-v1"),
    # sessions_spawn governed by content-safety (delegation risk)
    Relation(from_id="tool:sessions_spawn", to_id="policy:content-safety", rtype="governed_by", source="seed:security-v1"),
    # Category → Policy linkages
    Relation(from_id="category:Cybercrime", to_id="policy:content-safety", rtype="governed_by", source="seed:security-v1"),
    Relation(from_id="category:Fraud", to_id="policy:content-safety", rtype="governed_by", source="seed:security-v1"),
    Relation(from_id="category:Weapons", to_id="policy:content-safety", rtype="governed_by", source="seed:security-v1"),
    Relation(from_id="category:Physical_harm", to_id="policy:content-safety", rtype="governed_by", source="seed:security-v1"),
    Relation(from_id="category:Harassment", to_id="policy:content-safety", rtype="governed_by", source="seed:security-v1"),
    Relation(from_id="category:Hate", to_id="policy:content-safety", rtype="governed_by", source="seed:security-v1"),
    Relation(from_id="category:Drugs", to_id="policy:content-safety", rtype="governed_by", source="seed:security-v1"),
    Relation(from_id="category:Sexual", to_id="policy:content-safety", rtype="governed_by", source="seed:security-v1"),
    Relation(from_id="category:Disinformation", to_id="policy:data-integrity", rtype="governed_by", source="seed:security-v1"),
    Relation(from_id="category:Copyright", to_id="policy:content-safety", rtype="governed_by", source="seed:security-v1"),
]


def main():
    parser = argparse.ArgumentParser(description="Seed Nous KG with security entities")
    parser.add_argument("--db", default=str(Path(os.environ.get("NOUS_DB", "nous.db"))), help="DB path")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be seeded")
    args = parser.parse_args()

    all_entities = TOOL_ENTITIES + POLICY_ENTITIES + CATEGORY_ENTITIES
    all_relations = RELATIONS

    if args.dry_run:
        print(f"Would seed {len(TOOL_ENTITIES)} tool entities")
        print(f"Would seed {len(POLICY_ENTITIES)} policy entities")
        print(f"Would seed {len(CATEGORY_ENTITIES)} category entities")
        print(f"Would seed {len(all_relations)} relations")
        print("\nTool entities:")
        for e in TOOL_ENTITIES:
            print(f"  {e.id:30} risk={e.properties.get('risk_level')}")
        print("\nPolicy entities:")
        for e in POLICY_ENTITIES:
            print(f"  {e.id:35} rule={e.properties.get('source_rule')}")
        print("\nCategory entities:")
        for e in CATEGORY_ENTITIES:
            print(f"  {e.id:30} severity={e.properties.get('severity')}")
        return

    db = NousDB(args.db)

    # Count before
    before_entities = db.query("?[count(id)] := *entity{id}")
    before_relations = db.query("?[count(from_id)] := *relation{from_id}")
    before_e = before_entities[0]["count(id)"] if before_entities else 0
    before_r = before_relations[0]["count(from_id)"] if before_relations else 0

    # Upsert
    db.upsert_entities(all_entities)
    db.upsert_relations(all_relations)

    # Count after
    after_entities = db.query("?[count(id)] := *entity{id}")
    after_relations = db.query("?[count(from_id)] := *relation{from_id}")
    after_e = after_entities[0]["count(id)"] if after_entities else 0
    after_r = after_relations[0]["count(from_id)"] if after_relations else 0

    # Verify tool entities are findable by _build_kg_context pattern
    test_find = db.find_entity("tool:exec")
    test_rels = db.related("tool:exec", rtype="governed_by", direction="out")

    print(f"✅ KG Entity Seeding Complete")
    print(f"   Entities: {before_e} → {after_e} (+{after_e - before_e})")
    print(f"   Relations: {before_r} → {after_r} (+{after_r - before_r})")
    print(f"   Tool entities: {len(TOOL_ENTITIES)}")
    print(f"   Policy entities: {len(POLICY_ENTITIES)}")
    print(f"   Category entities: {len(CATEGORY_ENTITIES)}")
    print(f"   Relations: {len(all_relations)}")
    print(f"\n   Verification: find_entity('tool:exec') = {'FOUND' if test_find else 'NOT FOUND'}")
    print(f"   Verification: related('tool:exec', governed_by) = {len(test_rels)} relations")


if __name__ == "__main__":
    main()
