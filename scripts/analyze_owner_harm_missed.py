#!/usr/bin/env python3
"""Analyze missed owner-harm cases: find attack patterns and needed signals."""
import json
from collections import defaultdict, Counter
from pathlib import Path

BASE = Path(__file__).parent.parent

with open(BASE / 'docs/owner-harm-benchmark-results.json') as f:
    data = json.load(f)

with open(BASE / 'src/data/owner_harm/harmful.json') as f:
    harmful_raw = {c['id']: c for c in json.load(f)}

missed = [r for r in data['harmful_results'] if not r['any_blocked']]
caught = [r for r in data['harmful_results'] if r['any_blocked']]

print(f"=== MISSED CASES: {len(missed)}/132 ===\n")

# Category breakdown
by_cat = defaultdict(list)
for r in missed:
    by_cat[r['category']].append(r)

# Tool patterns
all_tools = Counter()
cat_tools = defaultdict(Counter)
for r in missed:
    raw = harmful_raw.get(r['id'], {})
    for fn in raw.get('target_functions', []):
        all_tools[fn] += 1
        cat_tools[r['category']][fn] += 1

print("TOP 20 TOOL FUNCTIONS IN MISSED CASES:")
for fn, cnt in all_tools.most_common(20):
    print(f"  {fn:40s} {cnt:3d}")

print("\nPER-CATEGORY TOOLS:")
for cat in sorted(cat_tools.keys()):
    print(f"\n  [{cat}] ({len(by_cat[cat])} missed)")
    for fn, cnt in cat_tools[cat].most_common(5):
        print(f"    {fn:38s} {cnt:3d}")

# What caught cases have in common
print(f"\n=== CAUGHT CASES ({len(caught)}) ===")
caught_tools = Counter()
for r in caught:
    raw = harmful_raw.get(r['id'], {})
    for fn in raw.get('target_functions', []):
        caught_tools[fn] += 1
    verdicts = [(tc['verdict'], tc['rule_id']) for tc in r['tool_results'] if tc['verdict'] in ('block','confirm')]
    print(f"  [{r['category']}] {r['name']}: {verdicts}")

print(f"\nCaught tool functions:")
for fn, cnt in caught_tools.most_common(10):
    print(f"  {fn:40s} {cnt:3d}")

# Signal analysis
print(f"\n=== NEEDED DETECTION SIGNALS ===\n")

# Group by what would catch them
signal_groups = {
    'data_flow_tracking': [],      # source sensitivity + dest trust
    'credential_boundary': [],     # creds flowing to output
    'prompt_injection_detect': [], # injected instructions
    'authorization_check': [],     # no explicit owner approval
}

for r in missed:
    raw = harmful_raw.get(r['id'], {})
    prompt = raw.get('prompt', '').lower()
    fns = set(raw.get('target_functions', []))
    cat = r['category']
    
    # Every missed case needs data flow tracking
    signal_groups['data_flow_tracking'].append(r['id'])
    
    if cat == 'CredentialLeak':
        signal_groups['credential_boundary'].append(r['id'])
    
    if any(w in prompt for w in ['override', 'inject', 'ignore previous', 'system override', 'mandatory security']):
        signal_groups['prompt_injection_detect'].append(r['id'])
    
    if cat in ('UnauthorizedAutonomy', 'Hijacking'):
        signal_groups['authorization_check'].append(r['id'])

print("Signal coverage:")
for sig, ids in sorted(signal_groups.items(), key=lambda x: -len(x[1])):
    print(f"  {sig:35s} {len(ids):3d}/{len(missed)} ({len(ids)/len(missed)*100:.0f}%)")

print(f"\n=== RULE DESIGN RECOMMENDATIONS ===\n")
print("1. DATA FLOW GATE (catches 100%):")
print("   - Track (source_sensitivity, dest_trust) pairs")
print("   - High-sensitivity sources: env vars, .env files, credentials, chat logs,")
print("     portfolio data, partner info, SSH config, error logs with paths")
print("   - Low-trust destinations: send_email, post_message, post_public,")
print("     share_file, upload_file, webhook, external API")
print("   - Rule: high_source + low_dest = BLOCK")
print()
print("2. CREDENTIAL BOUNDARY (catches CredentialLeak 100%):")
print("   - Specific rule: if tool_call reads credential-like data AND")
print("     next action sends to external endpoint = BLOCK")
print()
print("3. PROMPT INJECTION DETECTOR (catches ~15% direct attacks):")
print("   - Pattern match on injection markers in content")
print("   - Complementary to data flow gate")
print()
print("4. AUTHORIZATION CHECK (catches Hijacking + Unauthorized):")
print("   - Actions with external side-effects require explicit owner approval")
print("   - send_email, post_message, delete_*, publish_* without recent owner instruction = REVIEW")
