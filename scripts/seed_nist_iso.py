#!/usr/bin/env python3
"""Seed NIST CSF 2.0 + ISO 27001:2022 security controls into Nous KG.

Phase 1c of KG Expansion Plan.
Usage: cd . && PYTHONPATH=src python3 scripts/seed_nist_iso.py [--dry-run]

Sources:
  - NIST CSF 2.0: https://www.nist.gov/cyberframework
  - ISO 27001:2022 Annex A controls
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.db import NousDB
from nous.schema import Entity, Relation

# ── NIST CSF 2.0 Functions & Categories ───────────────────────────────────

NIST_FUNCTIONS = [
    {"id": "GV", "name": "Govern", "desc": "Establish and monitor cybersecurity risk management strategy, expectations, and policy"},
    {"id": "ID", "name": "Identify", "desc": "Understand organizational context and cybersecurity risk to systems, people, assets, data"},
    {"id": "PR", "name": "Protect", "desc": "Implement safeguards to ensure delivery of critical services"},
    {"id": "DE", "name": "Detect", "desc": "Develop and implement activities to identify occurrence of cybersecurity events"},
    {"id": "RS", "name": "Respond", "desc": "Take action regarding a detected cybersecurity incident"},
    {"id": "RC", "name": "Recover", "desc": "Maintain plans for resilience and restore capabilities impaired by cybersecurity incidents"},
]

NIST_CATEGORIES = [
    # Govern
    {"id": "GV.OC", "function": "GV", "name": "Organizational Context", "desc": "Circumstances surrounding cybersecurity risk management decisions"},
    {"id": "GV.RM", "function": "GV", "name": "Risk Management Strategy", "desc": "Priorities, constraints, risk tolerance, and assumptions for operational risk decisions"},
    {"id": "GV.RR", "function": "GV", "name": "Roles, Responsibilities, and Authorities", "desc": "Cybersecurity roles and authorities established and communicated"},
    {"id": "GV.PO", "function": "GV", "name": "Policy", "desc": "Organizational cybersecurity policy established, communicated, enforced"},
    {"id": "GV.OV", "function": "GV", "name": "Oversight", "desc": "Results of organization-wide cybersecurity risk management reviewed"},
    {"id": "GV.SC", "function": "GV", "name": "Cybersecurity Supply Chain Risk Management", "desc": "Supply chain risk identified, assessed, managed"},
    # Identify
    {"id": "ID.AM", "function": "ID", "name": "Asset Management", "desc": "Data, personnel, devices, systems, facilities managed consistent with risk"},
    {"id": "ID.RA", "function": "ID", "name": "Risk Assessment", "desc": "Organization understands cybersecurity risk to operations, assets, individuals"},
    {"id": "ID.IM", "function": "ID", "name": "Improvement", "desc": "Improvements identified from evaluations, exercises, incidents"},
    # Protect
    {"id": "PR.AA", "function": "PR", "name": "Identity Management, Authentication, and Access Control", "desc": "Access limited to authorized users, services, hardware"},
    {"id": "PR.AT", "function": "PR", "name": "Awareness and Training", "desc": "Organization's personnel provided cybersecurity awareness and training"},
    {"id": "PR.DS", "function": "PR", "name": "Data Security", "desc": "Data managed consistent with risk strategy to protect confidentiality, integrity, availability"},
    {"id": "PR.PS", "function": "PR", "name": "Platform Security", "desc": "Hardware, software, services managed consistent with risk strategy"},
    {"id": "PR.IR", "function": "PR", "name": "Technology Infrastructure Resilience", "desc": "Security architectures managed to protect asset confidentiality, integrity, availability"},
    # Detect
    {"id": "DE.CM", "function": "DE", "name": "Continuous Monitoring", "desc": "Assets monitored to find anomalies, IoCs, and other potentially adverse events"},
    {"id": "DE.AE", "function": "DE", "name": "Adverse Event Analysis", "desc": "Anomalies, IoCs, and other potentially adverse events analyzed"},
    # Respond
    {"id": "RS.MA", "function": "RS", "name": "Incident Management", "desc": "Responses to detected incidents managed"},
    {"id": "RS.AN", "function": "RS", "name": "Incident Analysis", "desc": "Investigations conducted to ensure effective response and support forensics"},
    {"id": "RS.CO", "function": "RS", "name": "Incident Response Reporting and Communication", "desc": "Response activities coordinated with internal and external stakeholders"},
    {"id": "RS.MI", "function": "RS", "name": "Incident Mitigation", "desc": "Activities performed to prevent expansion and mitigate effects"},
    # Recover
    {"id": "RC.RP", "function": "RC", "name": "Incident Recovery Plan Execution", "desc": "Restoration activities performed to ensure operational availability"},
    {"id": "RC.CO", "function": "RC", "name": "Incident Recovery Communication", "desc": "Restoration activities coordinated with internal and external parties"},
]

# ── ISO 27001:2022 Annex A Key Controls ───────────────────────────────────
# Organized by themes (ISO 27002:2022 structure)

ISO_CONTROLS = [
    # Organizational controls (A.5)
    {"id": "A.5.1",  "name": "Policies for information security", "theme": "Organizational",
     "desc": "Information security policy and topic-specific policies shall be defined, approved, published, communicated"},
    {"id": "A.5.2",  "name": "Information security roles and responsibilities", "theme": "Organizational",
     "desc": "Information security roles and responsibilities shall be defined and allocated"},
    {"id": "A.5.7",  "name": "Threat intelligence", "theme": "Organizational",
     "desc": "Information relating to information security threats shall be collected and analysed"},
    {"id": "A.5.8",  "name": "Information security in project management", "theme": "Organizational",
     "desc": "Information security shall be integrated into project management"},
    {"id": "A.5.23", "name": "Information security for use of cloud services", "theme": "Organizational",
     "desc": "Processes for acquisition, use, management and exit from cloud services"},
    {"id": "A.5.29", "name": "Information security during disruption", "theme": "Organizational",
     "desc": "Organization shall plan how to maintain information security at an appropriate level during disruption"},
    {"id": "A.5.30", "name": "ICT readiness for business continuity", "theme": "Organizational",
     "desc": "ICT readiness shall be planned, implemented, maintained and tested"},
    # People controls (A.6)
    {"id": "A.6.1",  "name": "Screening", "theme": "People",
     "desc": "Background verification checks on all candidates shall be carried out"},
    {"id": "A.6.3",  "name": "Information security awareness, education and training", "theme": "People",
     "desc": "Personnel shall receive appropriate awareness education, training"},
    # Physical controls (A.7)
    {"id": "A.7.4",  "name": "Physical security monitoring", "theme": "Physical",
     "desc": "Premises shall be continuously monitored for unauthorized physical access"},
    # Technological controls (A.8)
    {"id": "A.8.1",  "name": "User endpoint devices", "theme": "Technological",
     "desc": "Information stored on, processed by or accessible via user endpoint devices shall be protected"},
    {"id": "A.8.2",  "name": "Privileged access rights", "theme": "Technological",
     "desc": "Allocation and use of privileged access rights shall be restricted and managed"},
    {"id": "A.8.3",  "name": "Information access restriction", "theme": "Technological",
     "desc": "Access to information and other associated assets shall be restricted"},
    {"id": "A.8.5",  "name": "Secure authentication", "theme": "Technological",
     "desc": "Secure authentication technologies and procedures shall be established"},
    {"id": "A.8.7",  "name": "Protection against malware", "theme": "Technological",
     "desc": "Protection against malware shall be implemented and supported by user awareness"},
    {"id": "A.8.8",  "name": "Management of technical vulnerabilities", "theme": "Technological",
     "desc": "Information about technical vulnerabilities shall be obtained; exposure evaluated and mitigated"},
    {"id": "A.8.9",  "name": "Configuration management", "theme": "Technological",
     "desc": "Configurations including security configurations shall be established, documented, reviewed"},
    {"id": "A.8.12", "name": "Data leakage prevention", "theme": "Technological",
     "desc": "Data leakage prevention measures shall be applied to systems, networks, and devices"},
    {"id": "A.8.15", "name": "Logging", "theme": "Technological",
     "desc": "Logs that record activities, exceptions, faults shall be produced, stored, protected, analysed"},
    {"id": "A.8.16", "name": "Monitoring activities", "theme": "Technological",
     "desc": "Networks, systems and applications shall be monitored for anomalous behaviour"},
    {"id": "A.8.20", "name": "Networks security", "theme": "Technological",
     "desc": "Networks and network devices shall be secured, managed and controlled"},
    {"id": "A.8.24", "name": "Use of cryptography", "theme": "Technological",
     "desc": "Rules for the effective use of cryptography including key management shall be defined"},
    {"id": "A.8.25", "name": "Secure development life cycle", "theme": "Technological",
     "desc": "Rules for the secure development of software and systems shall be established"},
    {"id": "A.8.28", "name": "Secure coding", "theme": "Technological",
     "desc": "Secure coding principles shall be applied to software development"},
]

# ── Regulation / Framework Entities ───────────────────────────────────────

REGULATION_ENTITIES = [
    Entity(
        id="regulation:nist-csf-2.0",
        etype="regulation",
        labels=["regulation", "framework", "cybersecurity"],
        properties={
            "full_name": "NIST Cybersecurity Framework 2.0",
            "publisher": "National Institute of Standards and Technology",
            "version": "2.0",
            "year": 2024,
            "scope": "All organizations (expanded from critical infrastructure)",
            "url": "https://www.nist.gov/cyberframework",
        },
        source="seed:nist-iso-v1",
    ),
    Entity(
        id="regulation:iso-27001-2022",
        etype="regulation",
        labels=["regulation", "standard", "information-security"],
        properties={
            "full_name": "ISO/IEC 27001:2022 Information Security Management Systems",
            "publisher": "International Organization for Standardization",
            "version": "2022",
            "year": 2022,
            "scope": "Information security management systems",
            "annex_a_controls": 93,
        },
        source="seed:nist-iso-v1",
    ),
    Entity(
        id="regulation:eu-ai-act",
        etype="regulation",
        labels=["regulation", "ai-governance"],
        properties={
            "full_name": "EU Artificial Intelligence Act",
            "publisher": "European Parliament and Council",
            "year": 2024,
            "scope": "AI systems placed on the EU market",
            "key_concept": "Risk-based classification: Unacceptable/High/Limited/Minimal risk",
            "relevance_to_nous": "Agent safety systems are High-Risk AI under Article 6",
        },
        source="seed:nist-iso-v1",
    ),
    Entity(
        id="regulation:nist-ai-rmf",
        etype="regulation",
        labels=["regulation", "framework", "ai-governance"],
        properties={
            "full_name": "NIST AI Risk Management Framework 1.0",
            "publisher": "National Institute of Standards and Technology",
            "year": 2023,
            "scope": "AI risk management across the AI lifecycle",
            "key_functions": ["Govern", "Map", "Measure", "Manage"],
            "relevance_to_nous": "Nous implements Map (risk identification) + Measure (safety metrics) + Manage (gate enforcement)",
        },
        source="seed:nist-iso-v1",
    ),
    Entity(
        id="regulation:gdpr",
        etype="regulation",
        labels=["regulation", "privacy", "data-protection"],
        properties={
            "full_name": "General Data Protection Regulation",
            "publisher": "European Union",
            "year": 2018,
            "scope": "Personal data processing of EU residents",
            "key_principles": ["Lawfulness", "Purpose limitation", "Data minimization",
                             "Accuracy", "Storage limitation", "Security"],
        },
        source="seed:nist-iso-v1",
    ),
]


def build_entities():
    """Build all entities for Phase 1c."""
    entities = list(REGULATION_ENTITIES)

    # NIST CSF functions
    for f in NIST_FUNCTIONS:
        entities.append(Entity(
            id=f"security_control:nist-csf-{f['id'].lower()}",
            etype="security_control",
            labels=["security_control", "nist-csf", "function"],
            properties={
                "framework": "NIST CSF 2.0",
                "level": "function",
                "function_id": f["id"],
                "name": f["name"],
                "description": f["desc"],
            },
            source="seed:nist-iso-v1",
        ))

    # NIST CSF categories
    for c in NIST_CATEGORIES:
        entities.append(Entity(
            id=f"security_control:nist-csf-{c['id'].lower().replace('.', '-')}",
            etype="security_control",
            labels=["security_control", "nist-csf", "category"],
            properties={
                "framework": "NIST CSF 2.0",
                "level": "category",
                "category_id": c["id"],
                "function_id": c["function"],
                "name": c["name"],
                "description": c["desc"],
            },
            source="seed:nist-iso-v1",
        ))

    # ISO 27001 controls
    for ctrl in ISO_CONTROLS:
        entities.append(Entity(
            id=f"security_control:iso27001-{ctrl['id'].lower().replace('.', '-')}",
            etype="security_control",
            labels=["security_control", "iso-27001", ctrl["theme"].lower()],
            properties={
                "framework": "ISO 27001:2022",
                "control_id": ctrl["id"],
                "theme": ctrl["theme"],
                "name": ctrl["name"],
                "description": ctrl["desc"],
            },
            source="seed:nist-iso-v1",
        ))

    return entities


def build_relations():
    """Build all relations for Phase 1c."""
    relations = []

    # NIST CSF: regulation REQUIRES function
    for f in NIST_FUNCTIONS:
        relations.append(Relation(
            from_id="regulation:nist-csf-2.0",
            to_id=f"security_control:nist-csf-{f['id'].lower()}",
            rtype="REQUIRES",
            source="seed:nist-iso-v1",
        ))

    # NIST CSF: function CONTAINS category
    for c in NIST_CATEGORIES:
        relations.append(Relation(
            from_id=f"security_control:nist-csf-{c['function'].lower()}",
            to_id=f"security_control:nist-csf-{c['id'].lower().replace('.', '-')}",
            rtype="CONTAINS",
            source="seed:nist-iso-v1",
        ))

    # ISO 27001: regulation REQUIRES control
    for ctrl in ISO_CONTROLS:
        relations.append(Relation(
            from_id="regulation:iso-27001-2022",
            to_id=f"security_control:iso27001-{ctrl['id'].lower().replace('.', '-')}",
            rtype="REQUIRES",
            source="seed:nist-iso-v1",
        ))

    # ── Cross-framework mappings ──────────────────────────────────────────
    # NIST CSF category → ISO 27001 control (many-to-many, curated)

    CSF_TO_ISO = [
        # Identity Management → Access Control
        ("nist-csf-pr-aa", "iso27001-a-8-2"),   # IDAM → Privileged access
        ("nist-csf-pr-aa", "iso27001-a-8-3"),   # IDAM → Info access restriction
        ("nist-csf-pr-aa", "iso27001-a-8-5"),   # IDAM → Secure authentication
        # Data Security → DLP + Crypto
        ("nist-csf-pr-ds", "iso27001-a-8-12"),  # Data Security → DLP
        ("nist-csf-pr-ds", "iso27001-a-8-24"),  # Data Security → Cryptography
        # Platform Security → Endpoint + Config + Vuln + Malware + Secure Dev
        ("nist-csf-pr-ps", "iso27001-a-8-1"),   # Platform → Endpoint
        ("nist-csf-pr-ps", "iso27001-a-8-7"),   # Platform → Malware protection
        ("nist-csf-pr-ps", "iso27001-a-8-8"),   # Platform → Vuln management
        ("nist-csf-pr-ps", "iso27001-a-8-9"),   # Platform → Config management
        ("nist-csf-pr-ps", "iso27001-a-8-25"),  # Platform → Secure SDLC
        ("nist-csf-pr-ps", "iso27001-a-8-28"),  # Platform → Secure coding
        # Continuous Monitoring → Logging + Monitoring
        ("nist-csf-de-cm", "iso27001-a-8-15"),  # Monitoring → Logging
        ("nist-csf-de-cm", "iso27001-a-8-16"),  # Monitoring → Monitoring activities
        # Infra Resilience → Network security + BCP
        ("nist-csf-pr-ir", "iso27001-a-8-20"),  # Infra → Network security
        # Awareness → Training
        ("nist-csf-pr-at", "iso27001-a-6-3"),   # Awareness → Training
        # Risk Assessment → Threat intelligence
        ("nist-csf-id-ra", "iso27001-a-5-7"),   # Risk → Threat intel
        # Policy → Policy
        ("nist-csf-gv-po", "iso27001-a-5-1"),   # Policy → Policies
        # Roles → Roles
        ("nist-csf-gv-rr", "iso27001-a-5-2"),   # Roles → Roles
        # Recovery → BCP
        ("nist-csf-rc-rp", "iso27001-a-5-29"),  # Recovery → Disruption security
        ("nist-csf-rc-rp", "iso27001-a-5-30"),  # Recovery → ICT readiness
    ]

    for csf_id, iso_id in CSF_TO_ISO:
        relations.append(Relation(
            from_id=f"security_control:{csf_id}",
            to_id=f"security_control:{iso_id}",
            rtype="MAPS_TO",
            properties={"mapping_type": "cross-framework"},
            source="seed:nist-iso-v1",
        ))

    # ── CWE → Security Control MITIGATED_BY mappings ─────────────────────
    # Which controls mitigate which vulnerability classes

    CWE_MITIGATIONS = [
        # XSS mitigated by secure coding + secure SDLC
        ("vulnerability_class:CWE-79", "iso27001-a-8-28"),   # XSS → Secure coding
        ("vulnerability_class:CWE-79", "iso27001-a-8-25"),   # XSS → Secure SDLC
        # SQL Injection → Secure coding
        ("vulnerability_class:CWE-89", "iso27001-a-8-28"),
        ("vulnerability_class:CWE-89", "iso27001-a-8-25"),
        # OOB Write → Secure coding
        ("vulnerability_class:CWE-787", "iso27001-a-8-28"),
        # CSRF → Secure coding
        ("vulnerability_class:CWE-352", "iso27001-a-8-28"),
        # Path traversal → Access restriction
        ("vulnerability_class:CWE-22", "iso27001-a-8-3"),
        # OS Command Injection → Secure coding + Config mgmt
        ("vulnerability_class:CWE-78", "iso27001-a-8-28"),
        ("vulnerability_class:CWE-78", "iso27001-a-8-9"),
        # Auth bypass → Secure auth + Privileged access
        ("vulnerability_class:CWE-862", "iso27001-a-8-5"),
        ("vulnerability_class:CWE-862", "iso27001-a-8-2"),
        # Deserialization → Secure coding
        ("vulnerability_class:CWE-502", "iso27001-a-8-28"),
        # Hardcoded credentials → Config management
        ("vulnerability_class:CWE-798", "iso27001-a-8-9"),
        ("vulnerability_class:CWE-798", "iso27001-a-8-24"),  # + Crypto
        # NULL pointer → Secure coding
        ("vulnerability_class:CWE-476", "iso27001-a-8-28"),
        # Use after free → Secure coding
        ("vulnerability_class:CWE-416", "iso27001-a-8-28"),
        # Improper input validation → Secure coding + SDLC
        ("vulnerability_class:CWE-20", "iso27001-a-8-28"),
        ("vulnerability_class:CWE-20", "iso27001-a-8-25"),
    ]

    for cwe_id, ctrl_id in CWE_MITIGATIONS:
        relations.append(Relation(
            from_id=cwe_id,
            to_id=f"security_control:{ctrl_id}",
            rtype="MITIGATED_BY",
            source="seed:nist-iso-v1",
        ))

    # ── AgentHarm Category → NIST CSF Function mappings ──────────────────

    CATEGORY_CSF = [
        ("category:Cybercrime", "nist-csf-pr"),    # Protect
        ("category:Cybercrime", "nist-csf-de"),    # Detect
        ("category:Fraud", "nist-csf-pr"),         # Protect
        ("category:Fraud", "nist-csf-id"),         # Identify
        ("category:Harassment", "nist-csf-rs"),    # Respond
        ("category:Disinformation", "nist-csf-de"),# Detect
        ("category:Copyright", "nist-csf-gv"),     # Govern
        ("category:Drugs", "nist-csf-gv"),         # Govern
        ("category:Sexual", "nist-csf-gv"),        # Govern
        ("category:Weapons", "nist-csf-gv"),       # Govern
        ("category:Physical_harm", "nist-csf-gv"), # Govern
        ("category:Hate", "nist-csf-rs"),          # Respond
    ]

    for cat_id, csf_id in CATEGORY_CSF:
        relations.append(Relation(
            from_id=cat_id,
            to_id=f"security_control:{csf_id}",
            rtype="ADDRESSED_BY",
            source="seed:nist-iso-v1",
        ))

    return relations


def main():
    parser = argparse.ArgumentParser(description="Seed NIST CSF 2.0 + ISO 27001 into Nous KG")
    parser.add_argument("--db", default=str(Path(os.environ.get("NOUS_DB", "nous.db"))), help="DB path")
    parser.add_argument("--dry-run", action="store_true", help="Print counts only")
    args = parser.parse_args()

    entities = build_entities()
    relations = build_relations()

    if args.dry_run:
        etypes = {}
        for e in entities:
            etypes[e.etype] = etypes.get(e.etype, 0) + 1
        rtypes = {}
        for r in relations:
            rtypes[r.rtype] = rtypes.get(r.rtype, 0) + 1
        print(f"Would seed {len(entities)} entities:")
        for t, c in sorted(etypes.items()):
            print(f"  {t}: {c}")
        print(f"Would seed {len(relations)} relations:")
        for t, c in sorted(rtypes.items()):
            print(f"  {t}: {c}")
        return

    db = NousDB(args.db)
    before_e = db.count_entities()
    before_r = db.count_relations()

    db.upsert_entities(entities)
    db.upsert_relations(relations)

    after_e = db.count_entities()
    after_r = db.count_relations()

    print(f"✅ Phase 1c: NIST CSF 2.0 + ISO 27001 Seeding Complete")
    print(f"   Entities: {before_e} → {after_e} (+{after_e - before_e})")
    print(f"   Relations: {before_r} → {after_r} (+{after_r - before_r})")
    print(f"   New entity types: security_control, regulation")
    print(f"   New relation types: REQUIRES, MAPS_TO, MITIGATED_BY, ADDRESSED_BY")

    # Verify
    nist = db.find_entity("regulation:nist-csf-2.0")
    iso = db.find_entity("regulation:iso-27001-2022")
    print(f"\n   Verify NIST CSF: {'FOUND' if nist else 'NOT FOUND'}")
    print(f"   Verify ISO 27001: {'FOUND' if iso else 'NOT FOUND'}")

    # Count new types
    sc = db.find_by_type("security_control")
    reg = db.find_by_type("regulation")
    print(f"   security_control entities: {len(sc)}")
    print(f"   regulation entities: {len(reg)}")


if __name__ == "__main__":
    main()
