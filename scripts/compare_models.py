#!/usr/bin/env python3
"""Compare semantic gate models: MiniMax M2.7 vs Grok.

Usage:
    # Requires: NOUS_API_KEY (MiniMax), XAI_API_KEY (Grok)
    python3 scripts/compare_models.py [--split val|test|all] [--repeat 1]

Tests both models on the same benchmark split and reports:
- TPR, FPR, accuracy, latency
- Per-category breakdown
- Cost estimate
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.providers.openai_provider import create_openai_provider


def load_split(split_name: str) -> list:
    """Load benchmark split data."""
    base = Path(__file__).parent.parent / "data" / "splits"
    split_file = base / f"{split_name}.json"
    if not split_file.exists():
        print(f"Split file not found: {split_file}")
        sys.exit(1)
    with open(split_file) as f:
        data = json.load(f)
    cases = []
    for item in data.get("harmful", []):
        cases.append({**item, "expected": "BLOCK"})
    for item in data.get("benign", []):
        cases.append({**item, "expected": "ALLOW"})
    return cases


def run_model(model_name: str, base_url: str, api_key: str, cases: list) -> dict:
    """Run semantic gate with a specific model on all cases."""
    from nous.gate import semantic_gate

    provider = create_openai_provider(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
    )

    results = []
    total_time = 0
    for case in cases:
        prompt = case.get("prompt", case.get("behavior", ""))
        functions = case.get("target_functions", [])

        start = time.time()
        try:
            verdict = semantic_gate.evaluate(
                prompt=prompt,
                target_functions=functions,
                llm_provider=provider,
            )
            elapsed = time.time() - start
            total_time += elapsed

            results.append({
                "id": case["id"],
                "category": case.get("category", "?"),
                "expected": case["expected"],
                "verdict": verdict.decision,
                "correct": (verdict.decision == case["expected"]),
                "latency_ms": int(elapsed * 1000),
            })
        except Exception as e:
            elapsed = time.time() - start
            total_time += elapsed
            results.append({
                "id": case["id"],
                "category": case.get("category", "?"),
                "expected": case["expected"],
                "verdict": "ERROR",
                "correct": False,
                "latency_ms": int(elapsed * 1000),
                "error": str(e),
            })

    # Compute metrics
    harmful = [r for r in results if r["expected"] == "BLOCK"]
    benign = [r for r in results if r["expected"] == "ALLOW"]

    tp = sum(1 for r in harmful if r["verdict"] == "BLOCK")
    fn = sum(1 for r in harmful if r["verdict"] != "BLOCK")
    fp = sum(1 for r in benign if r["verdict"] == "BLOCK")
    tn = sum(1 for r in benign if r["verdict"] != "BLOCK")

    tpr = tp / len(harmful) if harmful else 0
    fpr = fp / len(benign) if benign else 0
    accuracy = (tp + tn) / len(results) if results else 0
    avg_latency = total_time / len(results) * 1000 if results else 0

    return {
        "model": model_name,
        "total": len(results),
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "tpr": tpr, "fpr": fpr, "accuracy": accuracy,
        "avg_latency_ms": int(avg_latency),
        "total_time_s": round(total_time, 1),
        "results": results,
    }


def print_report(metrics: dict):
    """Print a model's metrics."""
    m = metrics
    print(f"\n{'='*50}")
    print(f"Model: {m['model']}")
    print(f"{'='*50}")
    print(f"  Cases: {m['total']} (H:{m['tp']+m['fn']} B:{m['fp']+m['tn']})")
    print(f"  TPR: {m['tpr']:.1%} ({m['tp']}/{m['tp']+m['fn']})")
    print(f"  FPR: {m['fpr']:.1%} ({m['fp']}/{m['fp']+m['tn']})")
    print(f"  Accuracy: {m['accuracy']:.1%}")
    print(f"  Avg Latency: {m['avg_latency_ms']}ms")
    print(f"  Total Time: {m['total_time_s']}s")

    # Per-category breakdown
    cats = {}
    for r in m["results"]:
        cat = r["category"]
        if cat not in cats:
            cats[cat] = {"correct": 0, "total": 0}
        cats[cat]["total"] += 1
        if r["correct"]:
            cats[cat]["correct"] += 1

    print(f"\n  Per-category:")
    for cat, v in sorted(cats.items()):
        print(f"    {cat}: {v['correct']}/{v['total']} ({v['correct']/v['total']:.0%})")

    # Errors
    errors = [r for r in m["results"] if r.get("error")]
    if errors:
        print(f"\n  Errors ({len(errors)}):")
        for e in errors[:5]:
            print(f"    {e['id']}: {e['error'][:80]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="val", help="Benchmark split (val/test/all)")
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()

    # Load cases
    cases = load_split(args.split)
    print(f"Loaded {len(cases)} cases from '{args.split}' split")

    # Model configs
    models = []

    # MiniMax M2.7
    minimax_key = os.environ.get("NOUS_API_KEY") or os.environ.get("OPENAI_API_KEY")
    minimax_url = os.environ.get("NOUS_BASE_URL")
    if minimax_key:
        models.append(("MiniMax-M2.7", minimax_url, minimax_key))
    else:
        print("⚠️  No NOUS_API_KEY — skipping MiniMax M2.7")

    # Grok
    xai_key = os.environ.get("XAI_API_KEY")
    if xai_key:
        models.append(("grok-4.1-fast", "https://api.x.ai/v1", xai_key))
    else:
        print("⚠️  No XAI_API_KEY — skipping Grok")

    if not models:
        print("No models configured. Set NOUS_API_KEY and/or XAI_API_KEY.")
        sys.exit(1)

    all_metrics = []
    for model_name, base_url, api_key in models:
        print(f"\n🔄 Running {model_name}...")
        metrics = run_model(model_name, base_url, api_key, cases)
        print_report(metrics)
        all_metrics.append(metrics)

    # Side-by-side comparison
    if len(all_metrics) >= 2:
        print(f"\n{'='*50}")
        print("COMPARISON")
        print(f"{'='*50}")
        for m in all_metrics:
            print(f"  {m['model']:20s} TPR={m['tpr']:.1%} FPR={m['fpr']:.1%} Acc={m['accuracy']:.1%} Lat={m['avg_latency_ms']}ms")

        # Disagreements
        r1 = {r["id"]: r for r in all_metrics[0]["results"]}
        r2 = {r["id"]: r for r in all_metrics[1]["results"]}
        disagreements = []
        for cid in r1:
            if cid in r2 and r1[cid]["verdict"] != r2[cid]["verdict"]:
                disagreements.append({
                    "id": cid,
                    "category": r1[cid]["category"],
                    "expected": r1[cid]["expected"],
                    f"{all_metrics[0]['model']}": r1[cid]["verdict"],
                    f"{all_metrics[1]['model']}": r2[cid]["verdict"],
                })
        if disagreements:
            print(f"\n  Disagreements ({len(disagreements)}):")
            for d in disagreements:
                print(f"    {d['id']} ({d['category']}): expected={d['expected']} | " +
                      " vs ".join(f"{k}={v}" for k, v in d.items() if k not in ("id", "category", "expected")))


if __name__ == "__main__":
    main()
