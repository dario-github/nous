#!/usr/bin/env python3
"""Generate challenge set for Phase 3 evaluation.

Adversarial cases designed to test signal robustness, boundary cases, and method-goal conflicts.
Writes to data/challenge/challenge_v1.json.
"""
import json
from pathlib import Path

OUT = Path(__file__).parent.parent / "data" / "challenge" / "challenge_v1.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

# Load parts (split for T10 compliance: ≤400 lines per file)
parts_dir = Path(__file__).parent / "challenge_parts"
harmful = []
benign = []
for p in sorted(parts_dir.glob("harmful_p*.json")):
    with open(p) as f:
        harmful.extend(json.load(f))
for p in sorted(parts_dir.glob("benign_p*.json")):
    with open(p) as f:
        benign.extend(json.load(f))

challenge_set = {
    "harmful": harmful,
    "benign": benign,
    "metadata": {
        "version": "1.0",
        "created": "2026-03-15",
        "created_by": "Loop 27 — Phase 3 challenge set construction",
        "purpose": "Adversarial evaluation — test signal robustness, boundary cases, method-goal conflicts",
        "total_harmful": len(harmful),
        "total_benign": len(benign),
        "challenge_types": {
            "signal_abuse": "Harmful prompts designed to trigger benign signals",
            "method_goal_conflict": "Benign goals with clearly illegal methods",
            "multi_category": "Scenarios touching multiple harm categories",
            "boundary": "Cases at the edge of harm definitions",
            "looks_harmful_benign": "Benign scenarios that look dangerous",
            "coded_language": "Harm disguised with euphemisms",
            "indirect_harm": "Harmful content through benign tools only",
            "social_engineering": "Plausible but malicious social manipulation",
        },
    },
}

with open(OUT, "w") as f:
    json.dump(challenge_set, f, indent=2, ensure_ascii=False)

from collections import Counter
h_types = Counter(s["challenge_type"] for s in harmful)
b_types = Counter(s["challenge_type"] for s in benign)
print(f"✅ Challenge set: {len(harmful)} harmful + {len(benign)} benign = {len(harmful)+len(benign)} total")
print(f"Harmful by type: {dict(h_types)}")
print(f"Benign by type:  {dict(b_types)}")
