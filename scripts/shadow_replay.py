#!/usr/bin/env python3
"""M2.10 Shadow Replay: compare Nous gate() vs TS ontology-gate trigger_log.

Reads trigger_log.jsonl, replays each entry through Nous gate(),
compares verdicts. Reports consistency rate.

Usage: python3 scripts/shadow_replay.py [--limit N] [--verbose]
"""
import json
import sys
import os
import argparse
from pathlib import Path
from collections import Counter

# Add nous src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from nous.gate import gate as nous_gate
from nous.constraint_parser import load_constraints
from nous.fact_extractor import extract_facts

TRIGGER_LOG = Path.home() / ".openclaw/ontology-gate/trigger_log.jsonl"
CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology/constraints"

def parse_ts_verdict(entry: dict) -> dict:
    """Extract TS engine verdict from trigger_log entry."""
    gates = entry.get("gates", [])
    rewrites = entry.get("rewrites", {})
    
    # Normalize gates: can be dicts like {'verdict':'require','rule':'T12'} or strings
    rule_ids = []
    for g in gates:
        if isinstance(g, dict):
            rule_ids.append(g.get("rule", str(g)))
        elif isinstance(g, str):
            rule_ids.append(g)
    
    if rule_ids:
        return {"matched": rule_ids, "has_rewrite": bool(rewrites), "rewrites": rewrites}
    elif rewrites:
        return {"matched": [], "has_rewrite": True, "rewrites": rewrites}
    else:
        return {"matched": [], "has_rewrite": False, "rewrites": {}}

def build_nous_input(entry: dict) -> dict:
    """Convert trigger_log entry to Nous gate input format."""
    ctx = entry.get("tool_context", {})
    tool_name = ctx.get("name", entry.get("tool", "unknown"))
    params_summary = ctx.get("params_summary", "")
    
    # Reconstruct minimal tool_call dict for Nous
    tool_call = {"tool": tool_name}
    
    # Parse params_summary to extract key params
    if params_summary:
        # Format: "tool:key=value,key2=value2"
        parts = params_summary.split(":", 1)
        if len(parts) > 1:
            param_str = parts[1]
            for kv in param_str.split(","):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    tool_call[k.strip()] = v.strip()
    
    # Add session context
    tool_call["session_tags"] = entry.get("session_tags", [])
    tool_call["session_key"] = entry.get("session_key", "")
    
    return tool_call

def compare(ts_verdict: dict, nous_result) -> str:
    """Compare TS and Nous verdicts. Returns: match/mismatch/partial."""
    ts_matched = set(ts_verdict["matched"])
    
    # Get Nous matched rule IDs
    nous_matched = set()
    if hasattr(nous_result, "matches"):
        for m in nous_result.matches:
            if hasattr(m, "constraint_id"):
                nous_matched.add(m.constraint_id)
    elif hasattr(nous_result, "matched_rules"):
        for r in nous_result.matched_rules:
            if hasattr(r, "id"):
                nous_matched.add(r.id)
    
    # Both empty = both allowed = match
    if not ts_matched and not nous_matched:
        return "match"
    
    # Exact same rules matched
    if ts_matched == nous_matched:
        return "match"
    
    # Partial overlap
    if ts_matched & nous_matched:
        return "partial"
    
    # Complete mismatch
    return "mismatch"

def main():
    parser = argparse.ArgumentParser(description="Nous shadow replay")
    parser.add_argument("--limit", type=int, default=0, help="Max entries to process")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--mismatches-only", action="store_true")
    args = parser.parse_args()
    
    if not TRIGGER_LOG.exists():
        print(f"❌ Trigger log not found: {TRIGGER_LOG}")
        sys.exit(1)
    
    # Load constraints
    constraints = load_constraints(str(CONSTRAINTS_DIR))
    print(f"📦 Loaded {len(constraints)} Nous constraints")
    
    entries = []
    with open(TRIGGER_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    
    if args.limit:
        entries = entries[:args.limit]
    
    print(f"📊 Replaying {len(entries)} trigger_log entries...\n")
    
    stats = Counter()
    mismatches = []
    
    for i, entry in enumerate(entries):
        ts_verdict = parse_ts_verdict(entry)
        nous_input = build_nous_input(entry)
        
        try:
            nous_result = nous_gate(nous_input)
            result = compare(ts_verdict, nous_result)
        except Exception as e:
            result = "error"
            if args.verbose:
                print(f"  ⚠️ #{i}: error: {e}")
        
        stats[result] += 1
        
        if result != "match":
            mismatch_info = {
                "index": i,
                "tool": entry.get("tool"),
                "ts_gates": ts_verdict["matched"],
                "ts_rewrites": ts_verdict["rewrites"],
                "nous_verdict": str(getattr(nous_result, "verdict", "?")),
                "nous_matches": [
                    getattr(m, "constraint_id", str(m)) 
                    for m in getattr(nous_result, "matches", [])
                ],
                "params": entry.get("tool_context", {}).get("params_summary", "")[:80],
            }
            mismatches.append(mismatch_info)
            
            if args.verbose or args.mismatches_only:
                print(f"  ❌ #{i} [{result}] tool={mismatch_info['tool']}")
                print(f"     TS: gates={mismatch_info['ts_gates']} rewrites={ts_verdict['rewrites']}")
                print(f"     Nous: verdict={mismatch_info['nous_verdict']} matches={mismatch_info['nous_matches']}")
                print(f"     params: {mismatch_info['params']}")
    
    # Summary
    total = sum(stats.values())
    match_rate = stats["match"] / total * 100 if total > 0 else 0
    
    print(f"\n{'='*60}")
    print(f"📊 Shadow Replay Results")
    print(f"{'='*60}")
    print(f"  Total entries:  {total}")
    print(f"  ✅ Match:       {stats['match']} ({match_rate:.1f}%)")
    print(f"  ⚠️  Partial:    {stats['partial']}")
    print(f"  ❌ Mismatch:    {stats['mismatch']}")
    print(f"  💥 Error:       {stats['error']}")
    print(f"  Consistency:    {match_rate:.1f}%")
    print(f"  Target:         >99%")
    print(f"  Status:         {'✅ PASS' if match_rate >= 99 else '⚠️ NEEDS INVESTIGATION'}")
    
    if mismatches and not args.mismatches_only:
        print(f"\n📋 Top mismatches (showing first 10):")
        for m in mismatches[:10]:
            print(f"  #{m['index']}: {m['tool']} | TS={m['ts_gates']} | Nous={m['nous_matches']}")
            print(f"    {m['params']}")
    
    # Write report
    report = {
        "date": entry.get("ts", "unknown")[:10] if entries else "unknown",
        "total": total,
        "match": stats["match"],
        "partial": stats["partial"],
        "mismatch": stats["mismatch"],
        "error": stats["error"],
        "consistency_pct": round(match_rate, 2),
        "pass": match_rate >= 99,
        "mismatches_sample": mismatches[:20],
    }
    
    report_path = Path(__file__).parent.parent / "docs" / "m2.10-shadow-replay.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n📄 Report saved to: {report_path}")

if __name__ == "__main__":
    main()
