#!/usr/bin/env python3
"""Run AgentHarm benchmark with Intent Decomposition layer.

Compares gate results with and without intent extraction.
Usage:
  python3 scripts/run_intent_benchmark.py val [model]
"""
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
from nous.gate import gate
from nous.intent_extractor import IntentFact, extract_intent
from nous.triviality_filter import TrivialityConfig
from nous.semantic_gate import SemanticGateConfig

CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"
SPLITS_DIR = Path(__file__).parent.parent / "data" / "splits"
DOCS_DIR = Path(__file__).parent.parent / "docs"


def load_split(split_name: str):
    data = json.loads((SPLITS_DIR / f"{split_name}.json").read_text())
    return data["harmful"], data["benign"]


def create_provider(model: str, api_key: str):
    from nous.providers.openai_provider import create_openai_provider
    return create_openai_provider(model=model, api_key=api_key)


def run_scenario_with_intent(scenario: dict, is_harmful: bool, provider, model: str,
                              sem_config: SemanticGateConfig, triv_config: TrivialityConfig):
    """Run a single scenario with intent extraction."""
    tool_calls = scenario_to_tool_calls(scenario)
    prompt = scenario.get("prompt", "")
    tool_names = [tc.get("tool_name") or tc.get("name", "") for tc in tool_calls]

    # Extract intent ONCE per scenario
    intent = extract_intent(
        prompt=prompt,
        tool_names=tool_names,
        provider=provider,
        model=model,
        timeout_ms=30000,
    )

    # Run gate for each tool_call WITH intent
    results_with_intent = []
    for tc in tool_calls:
        result = gate(
            tool_call=tc,
            constraints_dir=CONSTRAINTS_DIR,
            triviality_config=triv_config,
            semantic_config=sem_config,
            intent=intent,
        )
        results_with_intent.append(result)

    # Run gate for each tool_call WITHOUT intent (baseline)
    results_without_intent = []
    for tc in tool_calls:
        result = gate(
            tool_call=tc,
            constraints_dir=CONSTRAINTS_DIR,
            triviality_config=triv_config,
            semantic_config=sem_config,
            intent=None,
        )
        results_without_intent.append(result)

    # Scenario is blocked if ANY tool_call is blocked
    blocked_with = any(r.verdict.action == "block" for r in results_with_intent)
    blocked_without = any(r.verdict.action == "block" for r in results_without_intent)

    return {
        "id": scenario.get("id", "?"),
        "name": scenario.get("name", "?"),
        "category": scenario.get("category", "?"),
        "is_harmful": is_harmful,
        "blocked_with_intent": blocked_with,
        "blocked_without_intent": blocked_without,
        "intent_goal": intent.goal,
        "intent_nature": intent.content_nature,
        "intent_beneficiary": intent.beneficiary,
        "intent_error": intent.error,
        "intent_latency_ms": intent.latency_ms,
        "layer_paths_with": [r.layer_path for r in results_with_intent],
        "layer_paths_without": [r.layer_path for r in results_without_intent],
    }


def compute_metrics(results: list[dict], label: str):
    """Compute TPR/FPR from results."""
    harmful = [r for r in results if r["is_harmful"]]
    benign = [r for r in results if not r["is_harmful"]]

    tp = sum(1 for r in harmful if r["blocked_with_intent"])
    fn = sum(1 for r in harmful if not r["blocked_with_intent"])
    fp = sum(1 for r in benign if r["blocked_with_intent"])
    tn = sum(1 for r in benign if not r["blocked_with_intent"])

    tpr = tp / (tp + fn) if (tp + fn) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

    # Baseline (without intent)
    tp_base = sum(1 for r in harmful if r["blocked_without_intent"])
    fn_base = sum(1 for r in harmful if not r["blocked_without_intent"])
    fp_base = sum(1 for r in benign if r["blocked_without_intent"])
    tn_base = sum(1 for r in benign if not r["blocked_without_intent"])
    tpr_base = tp_base / (tp_base + fn_base) if (tp_base + fn_base) > 0 else 0
    fpr_base = fp_base / (fp_base + tn_base) if (fp_base + tn_base) > 0 else 0

    # Per category
    cats = sorted(set(r["category"] for r in results))
    cat_stats = {}
    for cat in cats:
        cat_h = [r for r in harmful if r["category"] == cat]
        cat_b = [r for r in benign if r["category"] == cat]
        cat_tp = sum(1 for r in cat_h if r["blocked_with_intent"])
        cat_fn = sum(1 for r in cat_h if not r["blocked_with_intent"])
        cat_fp = sum(1 for r in cat_b if r["blocked_with_intent"])
        cat_tn = sum(1 for r in cat_b if not r["blocked_with_intent"])
        cat_tpr = cat_tp / (cat_tp + cat_fn) if (cat_tp + cat_fn) > 0 else 0
        cat_fpr = cat_fp / (cat_fp + cat_tn) if (cat_fp + cat_tn) > 0 else 0
        cat_stats[cat] = {"tpr": cat_tpr, "fpr": cat_fpr}

    print(f"\n{'='*60}")
    print(f"  {label} — Intent Decomposition Results")
    print(f"{'='*60}")
    print(f"  WITH Intent:    TPR={tpr*100:.1f}% ({tp}/{tp+fn})  FPR={fpr*100:.1f}% ({fp}/{fp+tn})")
    print(f"  WITHOUT Intent: TPR={tpr_base*100:.1f}% ({tp_base}/{tp_base+fn_base})  FPR={fpr_base*100:.1f}% ({fp_base}/{fp_base+tn_base})")
    print(f"\n  Per Category (WITH intent):")
    for cat in cats:
        s = cat_stats[cat]
        print(f"    {cat:20s}  TPR={s['tpr']*100:.1f}%  FPR={s['fpr']*100:.1f}%")

    # Show changed results
    changed = [r for r in results if r["blocked_with_intent"] != r["blocked_without_intent"]]
    if changed:
        print(f"\n  ⚡ Changed decisions ({len(changed)}):")
        for r in changed:
            direction = "BLOCK→ALLOW" if r["blocked_without_intent"] else "ALLOW→BLOCK"
            correct_label = "harmful" if r["is_harmful"] else "benign"
            emoji = "✅" if (r["is_harmful"] == r["blocked_with_intent"]) else "❌"
            print(f"    {emoji} {r['id']:6s} ({r['category']}) {r['name']}: {direction}")
            print(f"       intent: goal={r['intent_goal']}, nature={r['intent_nature']}")

    # Missed harmful
    missed = [r for r in harmful if not r["blocked_with_intent"]]
    if missed:
        print(f"\n  ⚠️ Missed harmful ({len(missed)}):")
        for r in missed:
            print(f"    {r['id']} ({r['category']}) {r['name']} — goal={r['intent_goal']}")

    # False positives
    fps = [r for r in benign if r["blocked_with_intent"]]
    if fps:
        print(f"\n  ⚠️ False positives ({len(fps)}):")
        for r in fps:
            print(f"    {r['id']} ({r['category']}) {r['name']} — goal={r['intent_goal']}")

    return {
        "tpr": tpr, "fpr": fpr,
        "tpr_base": tpr_base, "fpr_base": fpr_base,
        "cat_stats": cat_stats,
        "changed": len(changed),
    }


def main():
    split = sys.argv[1] if len(sys.argv) > 1 else "val"
    model = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("NOUS_SEMANTIC_MODEL", "DeepSeek-V3.2")

    api_key = os.environ.get("NEWAPI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("No API key. Set NEWAPI_API_KEY or OPENAI_API_KEY.")
        sys.exit(1)

    provider = create_provider(model, api_key)

    sem_config = SemanticGateConfig(
        enabled=True,
        mode="active",
        model=model,
        timeout_ms=30000,
        provider=provider,
    )
    triv_config = TrivialityConfig()

    harmful, benign = load_split(split)
    print(f"Split: {split} | Model: {model}")
    print(f"Harmful: {len(harmful)} | Benign: {len(benign)}")

    results = []
    t_start = time.time()

    for i, scenario in enumerate(harmful):
        print(f"\r  Processing harmful {i+1}/{len(harmful)}...", end="", flush=True)
        r = run_scenario_with_intent(scenario, True, provider, model, sem_config, triv_config)
        results.append(r)

    for i, scenario in enumerate(benign):
        print(f"\r  Processing benign {i+1}/{len(benign)}... ", end="", flush=True)
        r = run_scenario_with_intent(scenario, False, provider, model, sem_config, triv_config)
        results.append(r)

    elapsed = time.time() - t_start
    print(f"\r  Done in {elapsed:.1f}s" + " " * 40)

    metrics = compute_metrics(results, f"{split} ({model})")

    # Save results
    out_path = DOCS_DIR / f"intent-benchmark-{split}.json"
    with open(out_path, "w") as f:
        json.dump({"split": split, "model": model, "elapsed_s": elapsed, "metrics": metrics, "results": results}, f, indent=2)
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
