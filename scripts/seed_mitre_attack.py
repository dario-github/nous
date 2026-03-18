#!/usr/bin/env python3
"""Seed MITRE ATT&CK Enterprise tactics & top techniques into Nous KG.

Usage: PYTHONPATH=src python3 scripts/seed_mitre_attack.py [--dry-run]
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# MITRE ATT&CK Enterprise Tactics + Top Techniques (curated, not exhaustive)
TACTICS = [
    {"id": "TA0043", "name": "Reconnaissance", "desc": "Gathering information to plan future operations"},
    {"id": "TA0042", "name": "Resource Development", "desc": "Establishing resources to support operations"},
    {"id": "TA0001", "name": "Initial Access", "desc": "Trying to get into your network"},
    {"id": "TA0002", "name": "Execution", "desc": "Trying to run malicious code"},
    {"id": "TA0003", "name": "Persistence", "desc": "Trying to maintain foothold"},
    {"id": "TA0004", "name": "Privilege Escalation", "desc": "Trying to gain higher-level permissions"},
    {"id": "TA0005", "name": "Defense Evasion", "desc": "Trying to avoid being detected"},
    {"id": "TA0006", "name": "Credential Access", "desc": "Stealing credentials"},
    {"id": "TA0007", "name": "Discovery", "desc": "Trying to figure out environment"},
    {"id": "TA0008", "name": "Lateral Movement", "desc": "Moving through environment"},
    {"id": "TA0009", "name": "Collection", "desc": "Gathering data of interest"},
    {"id": "TA0011", "name": "Command and Control", "desc": "Communicating with compromised systems"},
    {"id": "TA0010", "name": "Exfiltration", "desc": "Stealing data"},
    {"id": "TA0040", "name": "Impact", "desc": "Manipulate, interrupt, or destroy systems and data"},
]

# Top techniques per tactic (2-4 each, most commonly seen)
TECHNIQUES = [
    # Reconnaissance
    {"id": "T1595", "name": "Active Scanning", "tactic": "TA0043", "desc": "Scanning victim infrastructure (ports, services, vulns)"},
    {"id": "T1589", "name": "Gather Victim Identity", "tactic": "TA0043", "desc": "Gathering credentials, emails, names"},
    {"id": "T1593", "name": "Search Open Websites", "tactic": "TA0043", "desc": "OSINT from social media, search engines"},
    # Initial Access
    {"id": "T1566", "name": "Phishing", "tactic": "TA0001", "desc": "Sending phishing messages to gain access"},
    {"id": "T1190", "name": "Exploit Public-Facing App", "tactic": "TA0001", "desc": "Exploiting vulnerabilities in internet-facing apps"},
    {"id": "T1078", "name": "Valid Accounts", "tactic": "TA0001", "desc": "Using legitimate credentials"},
    # Execution
    {"id": "T1059", "name": "Command & Scripting Interpreter", "tactic": "TA0002", "desc": "Using cmd/powershell/bash/python to execute"},
    {"id": "T1203", "name": "Exploitation for Client Execution", "tactic": "TA0002", "desc": "Exploiting client app vulnerabilities"},
    # Persistence
    {"id": "T1053", "name": "Scheduled Task/Job", "tactic": "TA0003", "desc": "Using scheduled tasks for persistence"},
    {"id": "T1136", "name": "Create Account", "tactic": "TA0003", "desc": "Creating accounts to maintain access"},
    # Privilege Escalation
    {"id": "T1068", "name": "Exploitation for Privilege Escalation", "tactic": "TA0004", "desc": "Exploiting vulns to elevate privileges"},
    {"id": "T1548", "name": "Abuse Elevation Control", "tactic": "TA0004", "desc": "Bypassing UAC/sudo mechanisms"},
    # Defense Evasion
    {"id": "T1027", "name": "Obfuscated Files or Info", "tactic": "TA0005", "desc": "Encoding/encrypting payloads to avoid detection"},
    {"id": "T1070", "name": "Indicator Removal", "tactic": "TA0005", "desc": "Deleting logs, timestamps, artifacts"},
    {"id": "T1562", "name": "Impair Defenses", "tactic": "TA0005", "desc": "Disabling security tools"},
    # Credential Access
    {"id": "T1110", "name": "Brute Force", "tactic": "TA0006", "desc": "Brute forcing passwords"},
    {"id": "T1003", "name": "OS Credential Dumping", "tactic": "TA0006", "desc": "Dumping credentials from OS (LSASS, SAM)"},
    # Discovery
    {"id": "T1046", "name": "Network Service Discovery", "tactic": "TA0007", "desc": "Scanning for network services (nmap)"},
    {"id": "T1082", "name": "System Information Discovery", "tactic": "TA0007", "desc": "Gathering system info (hostname, OS, arch)"},
    # Lateral Movement
    {"id": "T1021", "name": "Remote Services", "tactic": "TA0008", "desc": "Using SSH/RDP/SMB to move laterally"},
    {"id": "T1080", "name": "Taint Shared Content", "tactic": "TA0008", "desc": "Planting malware on shared drives"},
    # Collection
    {"id": "T1005", "name": "Data from Local System", "tactic": "TA0009", "desc": "Collecting files from local filesystem"},
    {"id": "T1114", "name": "Email Collection", "tactic": "TA0009", "desc": "Collecting emails for data theft"},
    # C2
    {"id": "T1071", "name": "Application Layer Protocol", "tactic": "TA0011", "desc": "Using HTTP/HTTPS/DNS for C2"},
    {"id": "T1105", "name": "Ingress Tool Transfer", "tactic": "TA0011", "desc": "Transferring tools into compromised env"},
    # Exfiltration
    {"id": "T1041", "name": "Exfiltration Over C2 Channel", "tactic": "TA0010", "desc": "Sending data over C2 channel"},
    {"id": "T1567", "name": "Exfiltration Over Web Service", "tactic": "TA0010", "desc": "Using cloud storage/web services for exfil"},
    # Impact
    {"id": "T1486", "name": "Data Encrypted for Impact", "tactic": "TA0040", "desc": "Ransomware — encrypting data for ransom"},
    {"id": "T1489", "name": "Service Stop", "tactic": "TA0040", "desc": "Stopping critical services for disruption"},
    {"id": "T1531", "name": "Account Access Removal", "tactic": "TA0040", "desc": "Locking out legitimate users"},
]

# AgentHarm category → relevant ATT&CK tactic mappings
CATEGORY_TACTIC_MAP = {
    "Cybercrime": ["TA0001", "TA0002", "TA0005", "TA0006", "TA0010"],
    "Fraud": ["TA0043", "TA0001", "TA0009"],
    "Harassment": ["TA0043", "TA0009"],  # reconnaissance + collection
    "Disinformation": ["TA0040"],  # impact
    "Drugs": [],  # no direct ATT&CK mapping
    "Copyright": ["TA0009", "TA0010"],  # collection + exfiltration
    "Hate": ["TA0040"],  # impact
    "Sexual": [],
    "Weapons": [],
    "Physical_harm": ["TA0040"],
    "Other": [],
}


def main():
    dry_run = "--dry-run" in sys.argv

    from nous.db import NousDB
    from nous.schema import Entity, Relation
    db = NousDB()

    entities_to_add = []
    relations_to_add = []

    # Add tactics as entities
    for tactic in TACTICS:
        eid = f"attack:tactic:{tactic['id']}"
        entities_to_add.append(Entity(
            id=eid, etype="attack_tactic",
            labels=["mitre", "attack", "tactic"],
            properties={"mitre_id": tactic["id"], "name": tactic["name"],
                       "description": tactic["desc"], "valid_from": "2013-01-01"},
            source="MITRE ATT&CK Enterprise v15", confidence=1.0
        ))

    # Add techniques as entities
    for tech in TECHNIQUES:
        eid = f"attack:technique:{tech['id']}"
        entities_to_add.append(Entity(
            id=eid, etype="attack_technique",
            labels=["mitre", "attack", "technique"],
            properties={"mitre_id": tech["id"], "name": tech["name"],
                       "description": tech["desc"], "tactic_id": tech["tactic"],
                       "valid_from": "2013-01-01"},
            source="MITRE ATT&CK Enterprise v15", confidence=1.0
        ))

    # Add CONTAINS relations (tactic → technique)
    for tech in TECHNIQUES:
        relations_to_add.append(Relation(
            from_id=f"attack:tactic:{tech['tactic']}",
            to_id=f"attack:technique:{tech['id']}",
            rtype="CONTAINS", confidence=1.0,
            source="MITRE ATT&CK",
            properties={"curated": True}
        ))

    # Add category → tactic mappings
    for cat, tactics in CATEGORY_TACTIC_MAP.items():
        for tactic_id in tactics:
            relations_to_add.append(Relation(
                from_id=f"category:{cat}",
                to_id=f"attack:tactic:{tactic_id}",
                rtype="EXPLOITED_BY", confidence=0.8,
                source="manual_mapping",
                properties={"curated": True}
            ))

    if dry_run:
        for e in entities_to_add:
            print(f"  [DRY] entity: {e.id} ({e.etype})")
        for r in relations_to_add:
            print(f"  [DRY] relation: {r.from_id} --{r.rtype}-> {r.to_id}")
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
