#!/usr/bin/env python3
"""CC-BOS Benchmark: Run CC-BOS adversarial scenarios through Nous gate.

20 scenarios (12 harmful + 5 benign controls + 3 harmful non-classical).
Measures how well Nous gate handles classical Chinese jailbreak patterns.

Usage:
  python3 scripts/run_ccbos_benchmark.py
  python3 scripts/run_ccbos_benchmark.py --repeat 3  # majority vote
"""
import json
import os
import sys
import time
import argparse
from collections import defaultdict, Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.gate import gate, GateResult
from nous.triviality_filter import TrivialityConfig
from nous.semantic_gate import SemanticGateConfig

CCBOS_PATH = Path(__file__).parent.parent / "data" / "challenge" / "ccbos_v1.json"
CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"
DOCS_DIR = Path(__file__).parent.parent / "docs"


def _make_semantic_config() -> SemanticGateConfig:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  No OPENAI_API_KEY — running L1+L2 only (no semantic gate)")
        return SemanticGateConfig(enabled=False)

    sem_model = os.environ.get("NOUS_SEMANTIC_MODEL", "DeepSeek-V3.1")
    print(f"Semantic gate model: {sem_model}")
    from nous.providers.openai_provider import create_openai_provider
    provider = create_openai_provider(model=sem_model, api_key=api_key)
    return SemanticGateConfig(
        enabled=True,
        mode="active",
        model=sem_model,
        timeout_ms=15000,
        max_content_chars=4000,
        provider=provider,
    )


def scenario_to_tool_call(scenario: dict) -> dict:
    """Convert CC-BOS scenario to tool_call format for Nous gate."""
    tc = {
        "tool_name": scenario["tool_name"],
        "params": dict(scenario["tool_params"]),
    }
    # Inject full prompt as content for semantic gate
    tc["params"]["content"] = scenario["prompt"]
    tc["params"]["full_prompt"] = scenario["prompt"]
    return tc


def run_benchmark(scenarios: list, repeat: int, sem_config, db=None):
    """Run all scenarios through gate, with optional majority voting."""
    results = []
    triv_config = TrivialityConfig()

    for sc in scenarios:
        tc = scenario_to_tool_call(sc)
        votes = []

        for r in range(repeat):
            gr = gate(
                tc, db=db,
                constraints_dir=CONSTRAINTS_DIR,
                triviality_config=triv_config,
                semantic_config=sem_config,
            )
            verdict = gr.verdict.action  # "allow" | "block" | "confirm"
            votes.append({
                "verdict": verdict,
                "layer_path": gr.layer_path,
                "rule_id": gr.verdict.rule_id,
                "reason": gr.verdict.reason[:200] if gr.verdict.reason else "",
                "semantic_verdict": gr.semantic_verdict,
            })

        # Majority vote
        verdict_counts = Counter(v["verdict"] for v in votes)
        final_verdict = verdict_counts.most_common(1)[0][0]
        is_blocked = final_verdict in ("block", "confirm")

        results.append({
            "id": sc["id"],
            "category": sc["category"],
            "is_harmful": sc["is_harmful"],
            "evasion_type": sc.get("evasion_type", ""),
            "cc_bos_dimension": sc.get("cc_bos_dimension", ""),
            "final_verdict": final_verdict,
            "is_blocked": is_blocked,
            "correct": (is_blocked == sc["is_harmful"]),
            "votes": votes,
            "prompt_preview": sc["prompt"][:80],
        })

    return results


def print_report(results: list):
    """Print human-readable report."""
    harmful = [r for r in results if r["is_harmful"]]
    benign = [r for r in results if not r["is_harmful"]]

    tp = sum(1 for r in harmful if r["is_blocked"])
    fn = sum(1 for r in harmful if not r["is_blocked"])
    tn = sum(1 for r in benign if not r["is_blocked"])
    fp = sum(1 for r in benign if r["is_blocked"])

    tpr = tp / len(harmful) * 100 if harmful else 0
    fpr = fp / len(benign) * 100 if benign else 0

    print("\n" + "=" * 70)
    print("CC-BOS BENCHMARK RESULTS")
    print("=" * 70)
    print(f"\nTotal: {len(results)} scenarios ({len(harmful)} harmful, {len(benign)} benign)")
    print(f"TPR (harmful blocked): {tp}/{len(harmful)} = {tpr:.1f}%")
    print(f"FPR (benign blocked):  {fp}/{len(benign)} = {fpr:.1f}%")
    print(f"Accuracy: {(tp + tn)}/{len(results)} = {(tp + tn) / len(results) * 100:.1f}%")

    print("\n--- HARMFUL (should be blocked) ---")
    for r in harmful:
        status = "✅ BLOCKED" if r["is_blocked"] else "❌ MISSED"
        layer = r["votes"][0]["layer_path"] if r["votes"] else "?"
        print(f"  {status} | {r['id']:30s} | {r['evasion_type']:25s} | layer={layer}")
        if not r["is_blocked"]:
            sem = r["votes"][0].get("semantic_verdict")
            if sem:
                print(f"           semantic: action={sem.get('action')} conf={sem.get('confidence')}")

    print("\n--- BENIGN (should be allowed) ---")
    for r in benign:
        status = "✅ ALLOWED" if not r["is_blocked"] else "❌ FALSE POS"
        layer = r["votes"][0]["layer_path"] if r["votes"] else "?"
        print(f"  {status} | {r['id']:30s} | layer={layer}")

    # Per-category breakdown
    print("\n--- PER EVASION TYPE ---")
    by_type = defaultdict(list)
    for r in harmful:
        by_type[r["evasion_type"]].append(r)
    for etype, rs in sorted(by_type.items()):
        blocked = sum(1 for r in rs if r["is_blocked"])
        print(f"  {etype:30s}: {blocked}/{len(rs)} blocked")

    return {
        "tp": tp, "fn": fn, "tn": tn, "fp": fp,
        "tpr": tpr, "fpr": fpr,
        "accuracy": (tp + tn) / len(results) * 100,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(CCBOS_PATH) as f:
        scenarios = json.load(f)

    print(f"Loaded {len(scenarios)} CC-BOS scenarios")

    if args.dry_run:
        for sc in scenarios:
            harm = "HARMFUL" if sc["is_harmful"] else "BENIGN"
            print(f"  [{harm}] {sc['id']}: {sc['prompt'][:60]}...")
        return

    # Load KG if available
    db = None
    try:
        from nous.db import NousDB
        db_path = Path(__file__).parent.parent / "data" / "nous.db"
        if db_path.exists():
            db = NousDB(str(db_path))
            print(f"KG loaded: {db.count_entities()} entities")
    except Exception as e:
        print(f"KG not available: {e}")

    sem_config = _make_semantic_config()
    print(f"Running with repeat={args.repeat}...")

    results = run_benchmark(scenarios, args.repeat, sem_config, db=db)
    summary = print_report(results)

    # Save results
    out_path = DOCS_DIR / "ccbos-results.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
