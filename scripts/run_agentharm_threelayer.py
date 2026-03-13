#!/usr/bin/env python3
"""AgentHarm Three-Layer Benchmark Runner

Run AgentHarm benchmark with configurable layer combinations:
- L1 only (baseline, equivalent to Loop 1)
- L1 + L2 (triviality filter)
- L1 + L2 + L3 (full three-layer, requires LLM provider)

Outputs per-action-type breakdown for precise analysis.
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.benchmarks.agentharm.loader import load_harmful, load_benign
from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls, FUNCTION_ACTION_MAP
from nous.gate import gate, GateResult
from nous.triviality_filter import TrivialityConfig

# Correct constraints directory (relative to this script)
CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"


def run_with_config(scenarios, is_harmful, triviality_config=None, label=""):
    """Run gate on all scenarios, return detailed results."""
    results = []
    for scenario in scenarios:
        tool_calls = scenario_to_tool_calls(scenario)
        tc_results = []
        for tc in tool_calls:
            gr = gate(
                tc,
                db=None,
                constraints_dir=CONSTRAINTS_DIR,
                triviality_config=triviality_config,
            )
            tc_results.append({
                "func_name": tc.get("tool_name", "unknown"),
                "action_type": tc.get("action_type", "unknown"),
                "verdict": gr.verdict.action,
                "layer_path": gr.layer_path,
                "rule_id": gr.verdict.rule_id,
            })
        
        any_blocked = any(r["verdict"] in ("block", "confirm") for r in tc_results)
        results.append({
            "scenario_id": scenario.get("id", ""),
            "category": scenario.get("category", "unknown"),
            "is_harmful": is_harmful,
            "any_blocked": any_blocked,
            "tool_results": tc_results,
        })
    return results


def analyze_results(harmful_results, benign_results):
    """Compute per-action-type and overall metrics."""
    # Overall
    h_total = len(harmful_results)
    h_blocked = sum(1 for r in harmful_results if r["any_blocked"])
    b_total = len(benign_results)
    b_blocked = sum(1 for r in benign_results if r["any_blocked"])
    
    tpr = h_blocked / h_total * 100 if h_total else 0
    fpr = b_blocked / b_total * 100 if b_total else 0
    
    # Per action_type breakdown
    action_stats = defaultdict(lambda: {
        "harmful_total": 0, "harmful_blocked": 0,
        "benign_total": 0, "benign_blocked": 0,
        "layer_paths": defaultdict(int),
    })
    
    for results, is_harmful in [(harmful_results, True), (benign_results, False)]:
        for r in results:
            for tc in r["tool_results"]:
                at = tc["action_type"]
                key = "harmful" if is_harmful else "benign"
                action_stats[at][f"{key}_total"] += 1
                if tc["verdict"] in ("block", "confirm"):
                    action_stats[at][f"{key}_blocked"] += 1
                action_stats[at]["layer_paths"][tc["layer_path"]] += 1
    
    # Per category breakdown (scenario level)
    cat_stats = defaultdict(lambda: {
        "harmful_total": 0, "harmful_blocked": 0,
        "benign_total": 0, "benign_blocked": 0,
    })
    for results, is_harmful in [(harmful_results, True), (benign_results, False)]:
        for r in results:
            cat = r["category"]
            key = "harmful" if is_harmful else "benign"
            cat_stats[cat][f"{key}_total"] += 1
            if r["any_blocked"]:
                cat_stats[cat][f"{key}_blocked"] += 1
    
    return {
        "overall": {
            "tpr": round(tpr, 1),
            "fpr": round(fpr, 1),
            "harmful_blocked": h_blocked,
            "harmful_total": h_total,
            "benign_blocked": b_blocked,
            "benign_total": b_total,
        },
        "per_action_type": {
            at: {
                "h_blocked": s["harmful_blocked"],
                "h_total": s["harmful_total"],
                "h_rate": round(s["harmful_blocked"] / s["harmful_total"] * 100, 1) if s["harmful_total"] else 0,
                "b_blocked": s["benign_blocked"],
                "b_total": s["benign_total"],
                "b_rate": round(s["benign_blocked"] / s["benign_total"] * 100, 1) if s["benign_total"] else 0,
                "layer_paths": dict(s["layer_paths"]),
            }
            for at, s in sorted(action_stats.items())
        },
        "per_category": {
            cat: {
                "h_blocked": s["harmful_blocked"],
                "h_total": s["harmful_total"],
                "h_tpr": round(s["harmful_blocked"] / s["harmful_total"] * 100, 1) if s["harmful_total"] else 0,
                "b_blocked": s["benign_blocked"],
                "b_total": s["benign_total"],
                "b_fpr": round(s["benign_blocked"] / s["benign_total"] * 100, 1) if s["benign_total"] else 0,
            }
            for cat, s in sorted(cat_stats.items())
        },
    }


def main():
    print("Loading AgentHarm dataset...")
    harmful = load_harmful()
    benign = load_benign()
    print(f"  Harmful: {len(harmful)} scenarios")
    print(f"  Benign:  {len(benign)} scenarios")
    
    # === Config 1: L1 only (baseline reproduction) ===
    print("\n=== Config 1: L1 Only (Datalog baseline) ===")
    t0 = time.perf_counter()
    h_l1 = run_with_config(harmful, True, triviality_config=None)
    b_l1 = run_with_config(benign, False, triviality_config=None)
    t1 = time.perf_counter()
    m_l1 = analyze_results(h_l1, b_l1)
    print(f"  TPR: {m_l1['overall']['tpr']}% ({m_l1['overall']['harmful_blocked']}/{m_l1['overall']['harmful_total']})")
    print(f"  FPR: {m_l1['overall']['fpr']}% ({m_l1['overall']['benign_blocked']}/{m_l1['overall']['benign_total']})")
    print(f"  Time: {t1-t0:.2f}s")
    
    # === Config 2: L1 + L2 (triviality filter) ===
    print("\n=== Config 2: L1 + L2 (Triviality Filter) ===")
    triv_config = TrivialityConfig()
    t0 = time.perf_counter()
    h_l2 = run_with_config(harmful, True, triviality_config=triv_config)
    b_l2 = run_with_config(benign, False, triviality_config=triv_config)
    t2 = time.perf_counter()
    m_l2 = analyze_results(h_l2, b_l2)
    print(f"  TPR: {m_l2['overall']['tpr']}% ({m_l2['overall']['harmful_blocked']}/{m_l2['overall']['harmful_total']})")
    print(f"  FPR: {m_l2['overall']['fpr']}% ({m_l2['overall']['benign_blocked']}/{m_l2['overall']['benign_total']})")
    print(f"  Time: {t2-t0:.2f}s")
    
    # === Delta analysis ===
    print("\n=== Delta: L1 → L1+L2 ===")
    tpr_delta = m_l2["overall"]["tpr"] - m_l1["overall"]["tpr"]
    fpr_delta = m_l2["overall"]["fpr"] - m_l1["overall"]["fpr"]
    print(f"  TPR delta: {tpr_delta:+.1f}%")
    print(f"  FPR delta: {fpr_delta:+.1f}%")
    
    # === Per action_type comparison ===
    print("\n=== Per Action Type (L2 layer_path breakdown) ===")
    for at, stats in m_l2["per_action_type"].items():
        paths = stats["layer_paths"]
        trivial_count = paths.get("trivial_allow", 0)
        total = sum(paths.values())
        if trivial_count > 0:
            print(f"  {at}: {trivial_count}/{total} trivially allowed ({stats['b_rate']}% benign blocked)")
    
    # === Per category comparison ===
    print("\n=== Per Category TPR/FPR (L1 → L1+L2) ===")
    for cat in sorted(set(list(m_l1["per_category"].keys()) + list(m_l2["per_category"].keys()))):
        l1_cat = m_l1["per_category"].get(cat, {})
        l2_cat = m_l2["per_category"].get(cat, {})
        l1_tpr = l1_cat.get("h_tpr", 0)
        l2_tpr = l2_cat.get("h_tpr", 0)
        l1_fpr = l1_cat.get("b_fpr", 0)
        l2_fpr = l2_cat.get("b_fpr", 0)
        tpr_d = l2_tpr - l1_tpr
        fpr_d = l2_fpr - l1_fpr
        if tpr_d != 0 or fpr_d != 0:
            print(f"  {cat}: TPR {l1_tpr}→{l2_tpr} ({tpr_d:+.1f}), FPR {l1_fpr}→{l2_fpr} ({fpr_d:+.1f})")
        else:
            print(f"  {cat}: TPR {l2_tpr}%, FPR {l2_fpr}% (unchanged)")
    
    # Save full results
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "l1_only": m_l1,
        "l1_l2": m_l2,
        "delta": {"tpr": tpr_delta, "fpr": fpr_delta},
    }
    out_path = Path(__file__).parent.parent / "docs" / "agentharm-threelayer-2026-03-13.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\nFull results saved to {out_path}")


if __name__ == "__main__":
    main()
