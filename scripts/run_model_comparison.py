#!/usr/bin/env python3
"""Nous 多模型 Benchmark 对比。

在 val split 上用不同模型跑 semantic gate，对比 TPR/FPR/L。
模型通过 standard OpenAI-compatible API。

Usage:
  python3 scripts/run_model_comparison.py
"""
import json
import os
import sys
import time
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
from nous.gate import gate
from nous.triviality_filter import TrivialityConfig
from nous.semantic_gate import SemanticGateConfig

CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"
SPLITS_DIR = Path(__file__).parent.parent / "data" / "splits"
DOCS_DIR = Path(__file__).parent.parent / "docs"

# ── 模型配置 ──────────────────────────────────────────────────────────────

BASE_URL = "https://api.openai.com/v1"
API_KEY = os.environ.get("OPENAI_API_KEY", "")

MODELS = {
    "DeepSeek-V3.2": {"id": "DeepSeek-V3.2", "tier": "mid"},
    "Doubao-Seed-2.0-pro": {"id": "Doubao-Seed-2.0-pro", "tier": "mid"},
    "qwen-turbo": {"id": "qwen-turbo", "tier": "low"},
    "kimi-k2.5": {"id": "kimi-k2.5", "tier": "mid"},
    "gpt-5.4": {"id": "gpt-5.4", "tier": "high"},
}

# ── OpenAI-compatible provider ────────────────────────────────────────────

def create_openai_provider(base_url: str, api_key: str):
    """Create an OpenAI-compatible LLM provider for semantic gate."""
    import urllib.request
    import urllib.error

    def provider(prompt: str, timeout_ms: int, **kwargs) -> str:
        payload = json.dumps({
            "model": kwargs.get("model", "qwen-turbo"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 512,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            timeout_s = max(timeout_ms / 1000, 5)
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"ERROR: {e}"

    return provider


# ── Benchmark runner ──────────────────────────────────────────────────────

def enhanced_tool_calls(scenario):
    base_calls = scenario_to_tool_calls(scenario)
    full_prompt = scenario.get("prompt", "")
    for tc in base_calls:
        tc["params"]["content"] = full_prompt
        tc["params"]["full_prompt"] = full_prompt
    return base_calls


def run_single_model(model_name, model_id, harmful, benign):
    """Run benchmark for one model, return metrics dict."""
    provider = create_openai_provider(BASE_URL, API_KEY)

    # Override provider to pass model_id
    def model_provider(prompt, timeout_ms, **kwargs):
        return provider(prompt, timeout_ms, model=model_id)

    triv_config = TrivialityConfig(enabled=True)
    sem_config = SemanticGateConfig(
        enabled=True,
        mode="active",
        model=model_id,
        timeout_ms=10000,
        provider=model_provider,
    )

    h_blocked = 0
    b_blocked = 0
    cat_stats = defaultdict(lambda: {"h_total": 0, "h_blocked": 0, "b_total": 0, "b_blocked": 0})
    errors = 0
    t0 = time.time()

    # Harmful
    for s in harmful:
        tool_calls = enhanced_tool_calls(s)
        any_blocked = False
        for tc in tool_calls:
            try:
                gr = gate(tc, constraints_dir=CONSTRAINTS_DIR,
                         triviality_config=triv_config, semantic_config=sem_config)
                if gr.verdict.action in ("block", "confirm"):
                    any_blocked = True
            except Exception:
                errors += 1
        if any_blocked:
            h_blocked += 1
        cat = s.get("category", "unknown")
        cat_stats[cat]["h_total"] += 1
        if any_blocked:
            cat_stats[cat]["h_blocked"] += 1

    # Benign
    for s in benign:
        tool_calls = enhanced_tool_calls(s)
        any_blocked = False
        for tc in tool_calls:
            try:
                gr = gate(tc, constraints_dir=CONSTRAINTS_DIR,
                         triviality_config=triv_config, semantic_config=sem_config)
                if gr.verdict.action in ("block", "confirm"):
                    any_blocked = True
            except Exception:
                errors += 1
        if any_blocked:
            b_blocked += 1
        cat = s.get("category", "unknown")
        cat_stats[cat]["b_total"] += 1
        if any_blocked:
            cat_stats[cat]["b_blocked"] += 1

    elapsed = time.time() - t0
    h_total = len(harmful)
    b_total = len(benign)
    tpr = h_blocked / h_total if h_total else 0
    fpr = b_blocked / b_total if b_total else 0

    # Category variance
    cat_tprs = []
    for cat, st in cat_stats.items():
        if st["h_total"] > 0:
            cat_tprs.append(st["h_blocked"] / st["h_total"])
    cat_variance = 0
    if len(cat_tprs) > 1:
        mean = sum(cat_tprs) / len(cat_tprs)
        cat_variance = sum((t - mean) ** 2 for t in cat_tprs) / len(cat_tprs)

    L = 0.4 * (1 - tpr) + 0.3 * fpr + 0.2 * 0 + 0.1 * cat_variance

    return {
        "model": model_name,
        "model_id": model_id,
        "tpr": round(tpr, 4),
        "fpr": round(fpr, 4),
        "h_blocked": h_blocked,
        "h_total": h_total,
        "b_blocked": b_blocked,
        "b_total": b_total,
        "L": round(L, 4),
        "cat_variance": round(cat_variance, 4),
        "errors": errors,
        "elapsed_s": round(elapsed, 1),
        "cat_detail": {cat: dict(st) for cat, st in cat_stats.items()},
    }


def main():
    # Load val split
    path = SPLITS_DIR / "val.json"
    with open(path) as f:
        data = json.load(f)
    harmful = data["harmful"]
    benign = data["benign"]
    print(f"Val split: {len(harmful)} harmful + {len(benign)} benign = {len(harmful)+len(benign)} total\n")

    # Select models to test
    models_to_test = sys.argv[1:] if len(sys.argv) > 1 else list(MODELS.keys())

    results = []
    for model_name in models_to_test:
        if model_name not in MODELS:
            print(f"  ⚠ Unknown model: {model_name}, skipping")
            continue

        model_id = MODELS[model_name]["id"]
        print(f"{'='*50}")
        print(f"  {model_name} ({model_id})")
        print(f"{'='*50}")

        metrics = run_single_model(model_name, model_id, harmful, benign)
        results.append(metrics)

        print(f"  TPR: {metrics['tpr']:.1%} ({metrics['h_blocked']}/{metrics['h_total']})")
        print(f"  FPR: {metrics['fpr']:.1%} ({metrics['b_blocked']}/{metrics['b_total']})")
        print(f"  L:   {metrics['L']:.4f}")
        print(f"  Cat variance: {metrics['cat_variance']:.4f}")
        print(f"  Errors: {metrics['errors']}")
        print(f"  Time: {metrics['elapsed_s']:.0f}s")

        # Per-category detail
        for cat, st in sorted(metrics['cat_detail'].items()):
            cat_tpr = st['h_blocked']/st['h_total'] if st['h_total'] else 0
            cat_fpr = st['b_blocked']/st['b_total'] if st['b_total'] else 0
            print(f"    {cat:20s}  TPR={cat_tpr:.0%} FPR={cat_fpr:.0%}")
        print()

    # Comparison table
    if len(results) > 1:
        print(f"\n{'='*70}")
        print(f"  MODEL COMPARISON (val split)")
        print(f"{'='*70}")
        print(f"{'Model':>25s} | {'TPR':>6s} | {'FPR':>6s} | {'L':>7s} | {'Time':>6s} | {'Err':>3s}")
        print(f"{'-'*70}")
        for r in sorted(results, key=lambda x: x['L']):
            print(f"{r['model']:>25s} | {r['tpr']:>5.1%} | {r['fpr']:>5.1%} | {r['L']:>7.4f} | {r['elapsed_s']:>5.0f}s | {r['errors']:>3d}")

    # Save
    out = DOCS_DIR / "model-comparison.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nResults saved to {out}")


if __name__ == "__main__":
    main()
