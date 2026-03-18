#!/usr/bin/env python3
"""Seed CWE Top 25 Most Dangerous Software Weaknesses into Nous KG.

Phase 1b of KG Expansion Plan.
Usage: PYTHONPATH=src python3 scripts/seed_cwe_top25.py [--dry-run]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# CWE Top 25 (2024 edition) - curated with ATT&CK mappings
CWE_TOP25 = [
    {"id": "CWE-787", "name": "Out-of-bounds Write", "rank": 1, "tactics": ["TA0002"], "desc": "Writing data past buffer boundaries"},
    {"id": "CWE-79", "name": "Cross-site Scripting (XSS)", "rank": 2, "tactics": ["TA0002"], "desc": "Improper neutralization of input in web pages"},
    {"id": "CWE-89", "name": "SQL Injection", "rank": 3, "tactics": ["TA0001", "TA0009"], "desc": "Improper neutralization of SQL commands"},
    {"id": "CWE-416", "name": "Use After Free", "rank": 4, "tactics": ["TA0002", "TA0004"], "desc": "Referencing memory after it has been freed"},
    {"id": "CWE-78", "name": "OS Command Injection", "rank": 5, "tactics": ["TA0002"], "desc": "Improper neutralization of OS commands"},
    {"id": "CWE-20", "name": "Improper Input Validation", "rank": 6, "tactics": ["TA0001"], "desc": "Not validating or incorrectly validating input"},
    {"id": "CWE-125", "name": "Out-of-bounds Read", "rank": 7, "tactics": ["TA0009"], "desc": "Reading data past buffer boundaries"},
    {"id": "CWE-22", "name": "Path Traversal", "rank": 8, "tactics": ["TA0009"], "desc": "Improper limitation of pathname to restricted directory"},
    {"id": "CWE-352", "name": "Cross-Site Request Forgery", "rank": 9, "tactics": ["TA0002"], "desc": "Not verifying request was intentionally sent"},
    {"id": "CWE-434", "name": "Unrestricted Upload", "rank": 10, "tactics": ["TA0001", "TA0002"], "desc": "Unrestricted upload of file with dangerous type"},
    {"id": "CWE-862", "name": "Missing Authorization", "rank": 11, "tactics": ["TA0004"], "desc": "Not performing authorization check"},
    {"id": "CWE-476", "name": "NULL Pointer Dereference", "rank": 12, "tactics": ["TA0040"], "desc": "Dereferencing a pointer that is NULL"},
    {"id": "CWE-287", "name": "Improper Authentication", "rank": 13, "tactics": ["TA0001", "TA0006"], "desc": "Not properly verifying claimed identity"},
    {"id": "CWE-190", "name": "Integer Overflow", "rank": 14, "tactics": ["TA0002"], "desc": "Integer overflow or wraparound"},
    {"id": "CWE-502", "name": "Deserialization of Untrusted Data", "rank": 15, "tactics": ["TA0002"], "desc": "Deserializing untrusted data without verification"},
    {"id": "CWE-77", "name": "Command Injection", "rank": 16, "tactics": ["TA0002"], "desc": "Improper neutralization of special elements in commands"},
    {"id": "CWE-119", "name": "Buffer Overflow", "rank": 17, "tactics": ["TA0002", "TA0004"], "desc": "Improper restriction of operations within memory buffer"},
    {"id": "CWE-798", "name": "Hard-coded Credentials", "rank": 18, "tactics": ["TA0006"], "desc": "Using hard-coded credentials"},
    {"id": "CWE-918", "name": "Server-Side Request Forgery", "rank": 19, "tactics": ["TA0007", "TA0009"], "desc": "Server makes requests to unintended locations"},
    {"id": "CWE-306", "name": "Missing Critical Authentication", "rank": 20, "tactics": ["TA0001"], "desc": "Not authenticating for critical function"},
    {"id": "CWE-362", "name": "Race Condition", "rank": 21, "tactics": ["TA0004"], "desc": "Concurrent execution using shared resource"},
    {"id": "CWE-269", "name": "Improper Privilege Management", "rank": 22, "tactics": ["TA0004"], "desc": "Not properly managing privileges"},
    {"id": "CWE-94", "name": "Code Injection", "rank": 23, "tactics": ["TA0002"], "desc": "Improper control of code generation"},
    {"id": "CWE-863", "name": "Incorrect Authorization", "rank": 24, "tactics": ["TA0004"], "desc": "Authorization check returns incorrect result"},
    {"id": "CWE-276", "name": "Incorrect Default Permissions", "rank": 25, "tactics": ["TA0003", "TA0004"], "desc": "Setting insecure default permissions"},
]

# Security controls that mitigate CWEs
CONTROLS = [
    {"id": "ctrl:input-validation", "name": "Input Validation", "mitigates": ["CWE-79", "CWE-89", "CWE-78", "CWE-20", "CWE-22", "CWE-77", "CWE-94"]},
    {"id": "ctrl:memory-safety", "name": "Memory Safety", "mitigates": ["CWE-787", "CWE-416", "CWE-125", "CWE-476", "CWE-190", "CWE-119"]},
    {"id": "ctrl:auth-framework", "name": "Authentication Framework", "mitigates": ["CWE-287", "CWE-306", "CWE-798"]},
    {"id": "ctrl:authz-framework", "name": "Authorization Framework", "mitigates": ["CWE-862", "CWE-863", "CWE-269", "CWE-276"]},
    {"id": "ctrl:csrf-protection", "name": "CSRF Protection", "mitigates": ["CWE-352"]},
    {"id": "ctrl:upload-validation", "name": "Upload Validation", "mitigates": ["CWE-434"]},
    {"id": "ctrl:serialization-safety", "name": "Serialization Safety", "mitigates": ["CWE-502"]},
    {"id": "ctrl:ssrf-protection", "name": "SSRF Protection", "mitigates": ["CWE-918"]},
    {"id": "ctrl:concurrency-control", "name": "Concurrency Control", "mitigates": ["CWE-362"]},
]


def main():
    dry_run = "--dry-run" in sys.argv

    from nous.db import NousDB
    from nous.schema import Entity, Relation
    db = NousDB()

    entities = []
    relations = []

    # CWE entities
    for cwe in CWE_TOP25:
        entities.append(Entity(
            id=f"cwe:{cwe['id']}", etype="vulnerability_class",
            labels=["cwe", "top25", "vulnerability"],
            properties={"cwe_id": cwe["id"], "name": cwe["name"],
                       "rank_2024": cwe["rank"], "description": cwe["desc"]},
            source="CWE Top 25 2024", confidence=1.0
        ))
        # CWE → ATT&CK tactic links
        for tactic_id in cwe["tactics"]:
            relations.append(Relation(
                from_id=f"cwe:{cwe['id']}",
                to_id=f"attack:tactic:{tactic_id}",
                rtype="EXPLOITED_BY", confidence=0.85,
                source="CWE-ATT&CK mapping",
                properties={"curated": True}
            ))

    # Control entities
    for ctrl in CONTROLS:
        entities.append(Entity(
            id=ctrl["id"], etype="security_control",
            labels=["control", "mitigation"],
            properties={"name": ctrl["name"]},
            source="OWASP/NIST best practices", confidence=0.9
        ))
        # Control → CWE mitigates links
        for cwe_id in ctrl["mitigates"]:
            relations.append(Relation(
                from_id=ctrl["id"],
                to_id=f"cwe:{cwe_id}",
                rtype="MITIGATES", confidence=0.85,
                source="security_best_practices",
                properties={"curated": True}
            ))

    if dry_run:
        print(f"[DRY RUN] Would add {len(entities)} entities, {len(relations)} relations")
        for e in entities[:5]:
            print(f"  entity: {e.id} ({e.etype})")
        print("  ...")
    else:
        db.upsert_entities(entities)
        db.upsert_relations(relations)
        print(f"Added {len(entities)} entities, {len(relations)} relations")

        ents = db.query('?[count(id)] := *entity{id}')
        rels = db.query('?[count(from_id)] := *relation{from_id}')
        print(f"Total entities: {ents[0].get('count(id)', '?')}")
        print(f"Total relations: {rels[0].get('count(from_id)', '?')}")

        # Type breakdown
        etypes = db.query('?[etype, count(id)] := *entity{id, etype}')
        rtypes = db.query('?[rtype, count(from_id)] := *relation{from_id, rtype}')
        print("\nEntity types:")
        for e in sorted(etypes, key=lambda x: -x.get('count(id)', 0)):
            print(f"  {e['etype']}: {e['count(id)']}")
        print("\nRelation types:")
        for r in sorted(rtypes, key=lambda x: -x.get('count(from_id)', 0)):
            print(f"  {r['rtype']}: {r['count(from_id)']}")


if __name__ == "__main__":
    main()
