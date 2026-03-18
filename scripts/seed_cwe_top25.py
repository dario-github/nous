#!/usr/bin/env python3
"""Seed CWE Top 25 Most Dangerous Software Weaknesses into Nous KG.

Phase 1b of KG Expansion Plan.
Usage: PYTHONPATH=src python3 scripts/seed_cwe_top25.py [--dry-run]

Source: https://cwe.mitre.org/top25/archive/2024/2024_cwe_top25.html
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.db import NousDB
from nous.schema import Entity, Relation

# CWE Top 25 (2024 edition) + key supplementary CWEs
CWES = [
    {"id": "CWE-79",  "name": "Cross-site Scripting (XSS)", "rank": 1,
     "desc": "Improper neutralization of input during web page generation",
     "techniques": ["T1059"]},  # Command & Scripting Interpreter
    {"id": "CWE-787", "name": "Out-of-bounds Write", "rank": 2,
     "desc": "Writing data past the end or before the beginning of the intended buffer",
     "techniques": ["T1203"]},  # Exploitation for Client Execution
    {"id": "CWE-89",  "name": "SQL Injection", "rank": 3,
     "desc": "Improper neutralization of special elements used in an SQL command",
     "techniques": ["T1190"]},  # Exploit Public-Facing App
    {"id": "CWE-352", "name": "Cross-Site Request Forgery (CSRF)", "rank": 4,
     "desc": "Web app does not verify that a well-formed request was intentionally provided by the user",
     "techniques": ["T1190"]},
    {"id": "CWE-22",  "name": "Path Traversal", "rank": 5,
     "desc": "Improper limitation of a pathname to a restricted directory",
     "techniques": ["T1005", "T1190"]},  # Data from Local System + Exploit
    {"id": "CWE-125", "name": "Out-of-bounds Read", "rank": 6,
     "desc": "Reading data past the end or before the beginning of the intended buffer",
     "techniques": ["T1005"]},
    {"id": "CWE-78",  "name": "OS Command Injection", "rank": 7,
     "desc": "Improper neutralization of special elements used in an OS command",
     "techniques": ["T1059"]},
    {"id": "CWE-416", "name": "Use After Free", "rank": 8,
     "desc": "Referencing memory after it has been freed",
     "techniques": ["T1203", "T1068"]},  # Client Exec + Priv Esc
    {"id": "CWE-862", "name": "Missing Authorization", "rank": 9,
     "desc": "Software does not perform an authorization check when an actor accesses a resource",
     "techniques": ["T1078"]},  # Valid Accounts
    {"id": "CWE-434", "name": "Unrestricted Upload of Dangerous File", "rank": 10,
     "desc": "Allowing upload of files with dangerous types that can be auto-processed",
     "techniques": ["T1190", "T1105"]},  # Exploit + Ingress Tool Transfer
    {"id": "CWE-94",  "name": "Code Injection", "rank": 11,
     "desc": "Improper control of generation of code (eval injection, template injection)",
     "techniques": ["T1059"]},
    {"id": "CWE-20",  "name": "Improper Input Validation", "rank": 12,
     "desc": "Not validating or incorrectly validating input that can affect control/data flow",
     "techniques": ["T1190"]},
    {"id": "CWE-77",  "name": "Command Injection", "rank": 13,
     "desc": "Improper neutralization of special elements used in a command",
     "techniques": ["T1059"]},
    {"id": "CWE-287", "name": "Improper Authentication", "rank": 14,
     "desc": "Not properly proving that an actor is who they claim to be",
     "techniques": ["T1078", "T1110"]},  # Valid Accounts + Brute Force
    {"id": "CWE-269", "name": "Improper Privilege Management", "rank": 15,
     "desc": "Not properly managing privileges, allowing escalation",
     "techniques": ["T1068", "T1548"]},  # Priv Esc + Abuse Elevation
    {"id": "CWE-502", "name": "Deserialization of Untrusted Data", "rank": 16,
     "desc": "Deserializing untrusted data without sufficient verification",
     "techniques": ["T1059", "T1203"]},
    {"id": "CWE-200", "name": "Exposure of Sensitive Information", "rank": 17,
     "desc": "Exposing sensitive info to an actor not explicitly authorized to access it",
     "techniques": ["T1005", "T1114"]},  # Data collection
    {"id": "CWE-863", "name": "Incorrect Authorization", "rank": 18,
     "desc": "Performing authorization check but incorrectly",
     "techniques": ["T1078"]},
    {"id": "CWE-918", "name": "Server-Side Request Forgery (SSRF)", "rank": 19,
     "desc": "Web server receives URL from upstream and retrieves contents without sufficient validation",
     "techniques": ["T1190"]},
    {"id": "CWE-119", "name": "Improper Restriction of Operations within Memory Buffer", "rank": 20,
     "desc": "Performing operations on a memory buffer without restricting to intended boundaries",
     "techniques": ["T1203"]},
    {"id": "CWE-476", "name": "NULL Pointer Dereference", "rank": 21,
     "desc": "Dereferencing a pointer that is expected to be valid but is NULL",
     "techniques": []},  # DoS primarily
    {"id": "CWE-190", "name": "Integer Overflow or Wraparound", "rank": 22,
     "desc": "Not handling integer overflow or wraparound that leads to unexpected behavior",
     "techniques": ["T1203"]},
    {"id": "CWE-400", "name": "Uncontrolled Resource Consumption", "rank": 23,
     "desc": "Not properly controlling allocation/maintenance of a limited resource (DoS)",
     "techniques": ["T1489"]},  # Service Stop
    {"id": "CWE-306", "name": "Missing Authentication for Critical Function", "rank": 24,
     "desc": "Not requiring authentication for functionality that requires actor identity",
     "techniques": ["T1078"]},
    {"id": "CWE-798", "name": "Use of Hard-coded Credentials", "rank": 25,
     "desc": "Using hard-coded credentials for authentication",
     "techniques": ["T1078", "T1003"]},  # Valid Accounts + Credential Dumping
]

# CWE → NIST CSF control mapping (which controls mitigate which weaknesses)
# Will be used when Phase 1c adds control entities; for now, just store in properties
CWE_CONTROL_HINTS = {
    "CWE-79":  ["input_validation", "output_encoding", "CSP"],
    "CWE-89":  ["parameterized_queries", "input_validation", "least_privilege"],
    "CWE-787": ["memory_safe_language", "bounds_checking", "ASLR"],
    "CWE-78":  ["input_validation", "allowlist", "least_privilege"],
    "CWE-287": ["MFA", "strong_auth", "session_management"],
    "CWE-269": ["least_privilege", "RBAC", "privilege_separation"],
    "CWE-798": ["secrets_management", "credential_rotation", "vault"],
    "CWE-918": ["allowlist", "network_segmentation", "egress_filtering"],
}

# AgentHarm category → relevant CWE mappings
CATEGORY_CWE_MAP = {
    "Cybercrime": ["CWE-89", "CWE-78", "CWE-94", "CWE-787", "CWE-416"],
    "Fraud": ["CWE-287", "CWE-862", "CWE-863", "CWE-306"],
    "Hacking": ["CWE-89", "CWE-78", "CWE-79", "CWE-918", "CWE-22", "CWE-434"],
    "Malware": ["CWE-94", "CWE-502", "CWE-787", "CWE-416"],
}


def main():
    dry_run = "--dry-run" in sys.argv
    db = NousDB("nous.db")

    entities_to_add = []
    relations_to_add = []

    # Add CWE entities
    for cwe in CWES:
        eid = f"cwe:{cwe['id'].lower()}"
        props = {
            "cwe_id": cwe["id"],
            "name": cwe["name"],
            "description": cwe["desc"],
            "rank_2024": cwe["rank"],
            "valid_from": "1999-01-01",  # CWE project started ~1999
        }
        if cwe["id"] in CWE_CONTROL_HINTS:
            props["mitigation_hints"] = CWE_CONTROL_HINTS[cwe["id"]]

        entities_to_add.append(Entity(
            id=eid, etype="vulnerability_class",
            labels=["cwe", "vulnerability", "top25"],
            properties=props,
            source="CWE Top 25 2024", confidence=1.0
        ))

    # CWE → ATT&CK technique relations (EXPLOITED_BY)
    for cwe in CWES:
        cwe_eid = f"cwe:{cwe['id'].lower()}"
        for tech_id in cwe.get("techniques", []):
            relations_to_add.append(Relation(
                from_id=cwe_eid,
                to_id=f"attack:technique:{tech_id}",
                rtype="EXPLOITED_BY", confidence=0.85,
                source="CWE-ATT&CK mapping (curated)",
                properties={"curated": True, "mapping_type": "weakness_to_technique"}
            ))

    # AgentHarm category → CWE relations
    for cat, cwes in CATEGORY_CWE_MAP.items():
        for cwe_id in cwes:
            relations_to_add.append(Relation(
                from_id=f"category:{cat}",
                to_id=f"cwe:{cwe_id.lower()}",
                rtype="EXPLOITED_BY", confidence=0.7,
                source="manual_mapping",
                properties={"curated": True, "mapping_type": "category_to_cwe"}
            ))

    if dry_run:
        for e in entities_to_add:
            print(f"  [DRY] entity: {e.id} ({e.etype}) — {e.properties.get('name', '')}")
        for r in relations_to_add:
            print(f"  [DRY] relation: {r.from_id} --{r.rtype}--> {r.to_id}")
        print(f"\n[DRY RUN] Would add {len(entities_to_add)} entities, {len(relations_to_add)} relations")
    else:
        db.upsert_entities(entities_to_add)
        db.upsert_relations(relations_to_add)
        print(f"Added {len(entities_to_add)} entities, {len(relations_to_add)} relations")

        # Verify
        ents = db.query('?[count(id)] := *entity{id}')
        rels = db.query('?[count(from_id)] := *relation{from_id}')
        print(f"Total entities: {ents[0].get('count(id)', '?')}")
        print(f"Total relations: {rels[0].get('count(from_id)', '?')}")


if __name__ == "__main__":
    main()
