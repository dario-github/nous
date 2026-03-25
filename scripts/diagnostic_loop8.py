#!/usr/bin/env python3
"""Loop 8 Diagnostic: Identify specific FN and FP scenarios with LLM reasoning.

Runs the gate on:
1. Fraud harmful scenarios (TPR=70.8% → find the 7 FN)
2. Drugs harmful (TPR=80% → find the 4 FN)
3. Harassment benign (FPR=41.7% → find the 10 FP)
4. Copyright benign (FPR=37.5% → find the 9 FP)
5. Fraud benign (FPR=33.3% → find the 8 FP)

Outputs per-scenario verdicts with semantic gate reasoning.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.benchmarks.agentharm.loader import load_harmful, load_benign
from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
from nous.gate import gate
from nous.triviality_filter import TrivialityConfig
from nous.semantic_gate import SemanticGateConfig
from nous.providers.openai_provider import create_openai_provider

CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"

# Setup LLM provider
provider = create_openai_provider(model="qwen-turbo")

triviality_config = TrivialityConfig(enabled=True)
semantic_config = SemanticGateConfig(
    enabled=True,
    mode="active",
    model="qwen-turbo",
    timeout_ms=10000,
    provider=provider,
    block_upgrade_threshold=0.90,
    allow_downgrade_threshold=0.70,
)


def enhanced_tool_calls(scenario):
    base_calls = scenario_to_tool_calls(scenario)
    full_prompt = scenario.get("prompt", "")
    for tc in base_calls:
        tc["params"]["content"] = full_prompt
        tc["params"]["full_prompt"] = full_prompt
    return base_calls


def run_scenario(scenario, is_harmful):
    tool_calls = enhanced_tool_calls(scenario)
    results = []
    for tc in tool_calls:
        gr = gate(
            tc, db=None,
            constraints_dir=CONSTRAINTS_DIR,
            triviality_config=triviality_config,
            semantic_config=semantic_config,
        )
        results.append({
            "tool_name": tc.get("tool_name", "unknown"),
            "action_type": tc.get("action_type", "unknown"),
            "verdict": gr.verdict.action,
            "reason": gr.verdict.reason[:200] if gr.verdict.reason else "",
            "layer_path": gr.layer_path,
            "semantic_verdict": gr.semantic_verdict,
            "datalog_verdict": gr.datalog_verdict,
        })

    any_blocked = any(r["verdict"] in ("block", "confirm") for r in results)
    return {
        "scenario_id": scenario.get("id", ""),
        "category": scenario.get("category", "unknown"),
        "is_harmful": is_harmful,
        "prompt": scenario.get("prompt", "")[:200],
        "any_blocked": any_blocked,
        "is_error": is_harmful and not any_blocked,  # FN
        "is_fp": not is_harmful and any_blocked,       # FP
        "tool_results": results,
    }


def main():
    harmful = load_harmful()
    benign = load_benign()

    # Focus categories
    focus_fn = ["Fraud", "Drugs", "Hate"]  # Low TPR
    focus_fp = ["Harassment", "Copyright", "Fraud"]  # High FPR

    results = {"fn_cases": [], "fp_cases": [], "summary": {}}

    # FN analysis (harmful scenarios that weren't caught)
    for cat in focus_fn:
        cat_scenarios = [s for s in harmful if s.get("category") == cat]
        print(f"\n--- {cat} Harmful ({len(cat_scenarios)} scenarios) ---")
        for s in cat_scenarios:
            r = run_scenario(s, True)
            if r["is_error"]:
                results["fn_cases"].append(r)
                print(f"  FN: {r['scenario_id']} | {r['prompt'][:80]}")
                for tr in r["tool_results"]:
                    if tr["layer_path"] == "semantic":
                        sv = tr.get("semantic_verdict") or {}
                        print(f"    {tr['action_type']}: {tr['verdict']} "
                              f"(sem: {sv.get('action','?')}@{sv.get('confidence','?')} "
                              f"— {sv.get('reason','?')[:80]})")
            else:
                print(f"  OK: {r['scenario_id']}")
            time.sleep(0.3)  # Rate limit

    # FP analysis (benign scenarios that were wrongly blocked)
    for cat in focus_fp:
        cat_scenarios = [s for s in benign if s.get("category") == cat]
        print(f"\n--- {cat} Benign ({len(cat_scenarios)} scenarios) ---")
        for s in cat_scenarios:
            r = run_scenario(s, False)
            if r["is_fp"]:
                results["fp_cases"].append(r)
                print(f"  FP: {r['scenario_id']} | {r['prompt'][:80]}")
                for tr in r["tool_results"]:
                    if tr["layer_path"] == "semantic" and tr["verdict"] in ("block", "confirm"):
                        sv = tr.get("semantic_verdict") or {}
                        print(f"    {tr['action_type']}: {tr['verdict']} "
                              f"(sem: {sv.get('action','?')}@{sv.get('confidence','?')} "
                              f"— {sv.get('reason','?')[:80]})")
            else:
                print(f"  OK: {r['scenario_id']}")
            time.sleep(0.3)

    # Summary
    results["summary"] = {
        "total_fn": len(results["fn_cases"]),
        "total_fp": len(results["fp_cases"]),
        "fn_by_cat": {},
        "fp_by_cat": {},
    }
    for r in results["fn_cases"]:
        cat = r["category"]
        results["summary"]["fn_by_cat"][cat] = results["summary"]["fn_by_cat"].get(cat, 0) + 1
    for r in results["fp_cases"]:
        cat = r["category"]
        results["summary"]["fp_by_cat"][cat] = results["summary"]["fp_by_cat"].get(cat, 0) + 1

    # Save
    out = Path(__file__).parent.parent / "docs" / "loop8-diagnostic.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n\nSaved to {out}")
    print(f"FN: {results['summary']['total_fn']}, FP: {results['summary']['total_fp']}")
    print(f"FN by cat: {results['summary']['fn_by_cat']}")
    print(f"FP by cat: {results['summary']['fp_by_cat']}")


if __name__ == "__main__":
    main()
