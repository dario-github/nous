#!/usr/bin/env python3
"""Run AgentHarm benchmark with uncensored Qwen3.5-35B-A3B as L3 judge.

Tests hypothesis: does removing alignment improve safety judgment accuracy?

Usage:
  python3 scripts/run_uncensored_benchmark.py test
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
from nous.gate import gate
from nous.triviality_filter import TrivialityConfig
from nous.semantic_gate import SemanticGateConfig

CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"
SPLITS_DIR = Path(__file__).parent.parent / "data" / "splits"


def create_uncensored_provider(model: str, base_url: str, api_key: str = "sk-none"):
    """Create provider for uncensored model with thinking disabled."""
    import openai
    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    def provider(prompt: str, timeout_ms: int, model_override: str) -> str:
        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2048,
                    temperature=0.0,
                    timeout=max(timeout_ms / 1000, 30.0),
                    extra_body={"chat_template_kwargs": {"enable_thinking": False}}
                )
                content = resp.choices[0].message.content or ""
                if not content.strip():
                    raise ValueError("Empty response")
                return content
            except Exception as e:
                if attempt < 2:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise
    return provider


def load_split(split_name: str):
    path = SPLITS_DIR / f"{split_name}.json"
    with open(path) as f:
        data = json.load(f)
    return data["harmful"], data["benign"]


def enhanced_tool_calls(scenario):
    """Inject full prompt as content for semantic gate."""
    calls = scenario_to_tool_calls(scenario)
    prompt_text = scenario.get("prompt", "")
    for tc in calls:
        if "arguments" not in tc:
            tc["arguments"] = {}
        tc["arguments"]["_full_prompt"] = prompt_text
    return calls


def run_benchmark(split_name: str, provider, provider_name: str):
    harmful, benign = load_split(split_name)
    print(f"\n{'='*60}")
    print(f"Running {split_name} split with {provider_name}")
    print(f"  harmful={len(harmful)}, benign={len(benign)}")
    print(f"{'='*60}\n")

    sem_cfg = SemanticGateConfig(
        enabled=True, mode="active", model="uncensored",
        timeout_ms=30000, max_content_chars=8000,
        provider=provider, repeat=1, upgrade_only=False
    )
    triv_cfg = TrivialityConfig()

    results = {"harmful": [], "benign": []}

    import sys as _sys
    for label, scenarios in [("harmful", harmful), ("benign", benign)]:
        for i, sc in enumerate(scenarios):
            t0 = time.time()
            calls = enhanced_tool_calls(sc)
            blocked = False
            for tc in calls:
                verdict = gate(
                    tc, constraints_dir=CONSTRAINTS_DIR,
                    triviality_config=triv_cfg,
                    semantic_config=sem_cfg,
                )
                if verdict.verdict in ("block", "confirm"):
                    blocked = True
                    break

            elapsed = time.time() - t0
            results[label].append({
                "id": sc.get("id", f"{label}-{i}"),
                "blocked": blocked,
                "category": sc.get("category", "unknown"),
            })
            status = "BLOCKED" if blocked else "ALLOWED"
            expected = "BLOCKED" if label == "harmful" else "ALLOWED"
            match = "✅" if status == expected else "❌"
            print(f"  [{i+1}/{len(scenarios)}] [{label}] {sc.get('id','?')}: {status} {match} ({elapsed:.1f}s)", flush=True)

    # Compute metrics
    h_blocked = sum(1 for r in results["harmful"] if r["blocked"])
    h_total = len(results["harmful"])
    b_blocked = sum(1 for r in results["benign"] if r["blocked"])
    b_total = len(results["benign"])

    tpr = h_blocked / h_total if h_total else 0
    fpr = b_blocked / b_total if b_total else 0

    # Clopper-Pearson CI
    from scipy import stats
    def clopper_pearson(k, n, alpha=0.05):
        if n == 0: return (0, 1)
        lo = stats.beta.ppf(alpha/2, k, n-k+1) if k > 0 else 0.0
        hi = stats.beta.ppf(1-alpha/2, k+1, n-k) if k < n else 1.0
        return (round(lo, 4), round(hi, 4))

    tpr_ci = clopper_pearson(h_blocked, h_total)
    fpr_ci = clopper_pearson(b_blocked, b_total)

    print(f"\n{'='*60}")
    print(f"RESULTS — {provider_name} on {split_name}")
    print(f"  TPR: {tpr:.1%} [{tpr_ci[0]:.1%}, {tpr_ci[1]:.1%}] ({h_blocked}/{h_total})")
    print(f"  FPR: {fpr:.1%} [{fpr_ci[0]:.1%}, {fpr_ci[1]:.1%}] ({b_blocked}/{b_total})")
    print(f"{'='*60}")

    return {
        "provider": provider_name,
        "split": split_name,
        "tpr": round(tpr, 4), "fpr": round(fpr, 4),
        "tpr_ci": list(tpr_ci), "fpr_ci": list(fpr_ci),
        "h_blocked": h_blocked, "h_total": h_total,
        "b_blocked": b_blocked, "b_total": b_total,
        "details": results,
    }


if __name__ == "__main__":
    split = sys.argv[1] if len(sys.argv) > 1 else "test"

    # Uncensored Qwen3.5-35B-A3B
    uncensored = create_uncensored_provider(
        model="Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive-Q8_0.gguf",
        base_url="http://go.nblink.cc:17202/v1",
    )

    result = run_benchmark(split, uncensored, "Qwen3.5-35B-A3B-Uncensored")

    out_path = Path(__file__).parent.parent / "docs" / "uncensored-baseline-results.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")
