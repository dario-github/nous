#!/usr/bin/env python3
"""Owner-Harm Benchmark: Run Nous gate on the new owner-harm test set.

Uses the same three-layer pipeline as run_agentharm_threelayer_v2.py
but with owner-harm data and owner-centric metrics.
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.gate import gate, GateResult
from nous.triviality_filter import TrivialityConfig

CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"
DATA_DIR = Path(__file__).parent.parent / "src" / "data" / "owner_harm"


def scenario_to_tool_calls(scenario: dict) -> list[dict]:
    """Convert owner-harm scenario to tool_call dicts for gate()."""
    prompt = scenario.get("prompt", "")
    target_fns = scenario.get("target_functions", [])
    
    tool_calls = []
    for fn in target_fns:
        tc = {
            "tool_name": fn,
            "action_type": fn,
            "params": {
                "content": prompt,
                "full_prompt": prompt,
            },
        }
        tool_calls.append(tc)
    
    if not tool_calls:
        tool_calls = [{
            "tool_name": "unknown",
            "action_type": "unknown",
            "params": {"content": prompt, "full_prompt": prompt},
        }]
    
    return tool_calls


def run_benchmark(scenarios, label, triviality_config=None):
    """Run gate on all scenarios, return per-scenario results."""
    results = []
    for scenario in scenarios:
        tool_calls = scenario_to_tool_calls(scenario)
        
        tc_results = []
        for tc in tool_calls:
            try:
                gr = gate(
                    tc,
                    constraints_dir=CONSTRAINTS_DIR,
                    triviality_config=triviality_config,
                )
                tc_results.append({
                    "func": tc["tool_name"],
                    "verdict": gr.verdict.action,
                    "layer": gr.layer_path,
                    "rule_id": gr.verdict.rule_id,
                    "reason": (gr.verdict.reason or "")[:120],
                })
            except Exception as e:
                tc_results.append({
                    "func": tc["tool_name"],
                    "verdict": "error",
                    "layer": "error",
                    "rule_id": None,
                    "reason": str(e)[:120],
                })
        
        any_blocked = any(r["verdict"] in ("block", "confirm") for r in tc_results)
        results.append({
            "id": scenario["id"],
            "name": scenario["name"],
            "category": scenario["category"],
            "any_blocked": any_blocked,
            "tool_results": tc_results,
        })
    
    return results


def print_metrics(harmful_results, benign_results):
    """Print owner-centric metrics."""
    # TPR: harmful cases that were blocked
    h_blocked = sum(1 for r in harmful_results if r["any_blocked"])
    h_total = len(harmful_results)
    tpr = h_blocked / h_total if h_total else 0
    
    # FPR: benign cases that were blocked  
    b_blocked = sum(1 for r in benign_results if r["any_blocked"])
    b_total = len(benign_results)
    fpr = b_blocked / b_total if b_total else 0
    
    print(f"\n{'='*60}")
    print(f"OWNER-HARM BENCHMARK RESULTS")
    print(f"{'='*60}")
    print(f"Harmful: {h_blocked}/{h_total} blocked (TPR = {tpr:.1%})")
    print(f"Benign:  {b_blocked}/{b_total} blocked (FPR = {fpr:.1%})")
    print(f"{'='*60}")
    
    # By category
    cats = defaultdict(lambda: {"blocked": 0, "total": 0})
    for r in harmful_results:
        cats[r["category"]]["total"] += 1
        if r["any_blocked"]:
            cats[r["category"]]["blocked"] += 1
    
    print(f"\nPer-category TPR (harmful):")
    for cat in sorted(cats.keys()):
        c = cats[cat]
        rate = c["blocked"] / c["total"] if c["total"] else 0
        print(f"  {cat:30s}: {c['blocked']:3d}/{c['total']:3d} ({rate:.0%})")
    
    # Layer funnel
    layers = defaultdict(int)
    for r in harmful_results:
        for tc in r["tool_results"]:
            layers[tc["layer"]] += 1
    
    print(f"\nLayer funnel (harmful):")
    for layer, count in sorted(layers.items()):
        print(f"  {layer}: {count}")
    
    # Missed harmful (not blocked)
    missed = [r for r in harmful_results if not r["any_blocked"]]
    if missed:
        print(f"\n⚠️  MISSED harmful cases ({len(missed)}):")
        for r in missed[:20]:
            verdicts = [tc["verdict"] for tc in r["tool_results"]]
            print(f"  [{r['category']}] {r['name']} → {verdicts}")
    
    # False positives (benign blocked)
    fps = [r for r in benign_results if r["any_blocked"]]
    if fps:
        print(f"\n⚠️  FALSE POSITIVES ({len(fps)}):")
        for r in fps[:20]:
            rules = [tc["rule_id"] for tc in r["tool_results"] if tc["verdict"] in ("block", "confirm")]
            print(f"  [{r['category']}] {r['name']} → rules: {rules}")


def main():
    print("Loading owner-harm dataset...")
    with open(DATA_DIR / "harmful.json") as f:
        harmful = json.load(f)
    with open(DATA_DIR / "benign.json") as f:
        benign = json.load(f)
    
    print(f"  Harmful: {len(harmful)} cases")
    print(f"  Benign:  {len(benign)} cases")
    
    # Config: L1 + L2 (no semantic gate — deterministic only)
    triviality_config = TrivialityConfig()
    
    print(f"\nRunning L1+L2 benchmark...")
    t0 = time.perf_counter()
    
    harmful_results = run_benchmark(harmful, "harmful", triviality_config)
    benign_results = run_benchmark(benign, "benign", triviality_config)
    
    elapsed = time.perf_counter() - t0
    print(f"Done in {elapsed:.1f}s ({elapsed/len(harmful+benign)*1000:.1f}ms/case)")
    
    print_metrics(harmful_results, benign_results)
    
    # Save full results
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": "L1+L2",
        "harmful_count": len(harmful),
        "benign_count": len(benign),
        "harmful_results": harmful_results,
        "benign_results": benign_results,
    }
    outpath = Path(__file__).parent.parent / "docs" / "owner-harm-benchmark-results.json"
    with open(outpath, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nFull results saved to: {outpath}")


if __name__ == "__main__":
    main()
