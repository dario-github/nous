#!/usr/bin/env python3
"""Multi-model CC-BOS comparison.

Tests semantic gate with different LLM backends on CC-BOS scenarios.
Only tests scenarios that involve the semantic gate (skips datalog-only).
"""
import json, os, sys, time
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.gate import gate
from nous.triviality_filter import TrivialityConfig
from nous.semantic_gate import SemanticGateConfig
from nous.providers.openai_provider import create_openai_provider

CCBOS_PATH = Path(__file__).parent.parent / "data" / "challenge" / "ccbos_v1.json"
CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"

# Models to test — covering different strengths
MODELS = [
    "gpt-5.4",            # strongest general reasoning
    "claude-sonnet-4-6",  # strong safety training
    "gemini-3.1-pro-preview",  # strong multilingual + reasoning
    "qwen3-32b",          # Chinese-native, might understand classical Chinese
    "DeepSeek-V3.1",      # current baseline
    "kimi-k2.5",          # Chinese-native alternative
]


def make_config(model: str) -> SemanticGateConfig:
    api_key = os.environ.get("OPENAI_API_KEY")
    provider = create_openai_provider(model=model, api_key=api_key)
    return SemanticGateConfig(
        enabled=True, mode="active", model=model,
        timeout_ms=20000, max_content_chars=4000, provider=provider,
    )


def scenario_to_tc(sc):
    tc = {"tool_name": sc["tool_name"], "params": dict(sc["tool_params"])}
    tc["params"]["content"] = sc["prompt"]
    tc["params"]["full_prompt"] = sc["prompt"]
    return tc


def run_model(model, scenarios, db=None):
    print(f"\n{'='*60}")
    print(f"MODEL: {model}")
    print(f"{'='*60}")
    
    sem_config = make_config(model)
    triv_config = TrivialityConfig()
    results = []
    
    for sc in scenarios:
        tc = scenario_to_tc(sc)
        try:
            gr = gate(tc, db=db, constraints_dir=CONSTRAINTS_DIR,
                      triviality_config=triv_config, semantic_config=sem_config)
            verdict = gr.verdict.action
            layer = gr.layer_path
            sem = gr.semantic_verdict
        except Exception as e:
            verdict = "error"
            layer = "error"
            sem = {"action": "error", "confidence": 0, "reason": str(e)[:100]}
        
        is_blocked = verdict in ("block", "confirm")
        correct = is_blocked == sc["is_harmful"]
        
        results.append({
            "id": sc["id"],
            "is_harmful": sc["is_harmful"],
            "verdict": verdict,
            "layer": layer,
            "correct": correct,
            "semantic": sem,
        })
        
        status = "✅" if correct else "❌"
        print(f"  {status} {sc['id']:35s} | {verdict:8s} | layer={layer}")
        if sem and isinstance(sem, dict):
            conf = sem.get("confidence", "?")
            action = sem.get("action", "?")
            print(f"      semantic: {action} (conf={conf})")
    
    harmful = [r for r in results if r["is_harmful"]]
    benign = [r for r in results if not r["is_harmful"]]
    tp = sum(1 for r in harmful if r["verdict"] in ("block", "confirm"))
    fn = len(harmful) - tp
    fp = sum(1 for r in benign if r["verdict"] in ("block", "confirm"))
    tn = len(benign) - fp
    
    tpr = tp / len(harmful) * 100 if harmful else 0
    fpr = fp / len(benign) * 100 if benign else 0
    
    print(f"\n  SUMMARY: TPR={tpr:.0f}% ({tp}/{len(harmful)}) | FPR={fpr:.0f}% ({fp}/{len(benign)})")
    
    return {"model": model, "tpr": tpr, "fpr": fpr, "tp": tp, "fn": fn, "fp": fp, "tn": tn, "results": results}


def main():
    with open(CCBOS_PATH) as f:
        scenarios = json.load(f)
    
    print(f"Loaded {len(scenarios)} CC-BOS scenarios")
    
    # Load KG
    db = None
    try:
        from nous.db import NousDB
        db_path = Path(__file__).parent.parent / "data" / "nous.db"
        if db_path.exists():
            db = NousDB(str(db_path))
            print(f"KG: {db.count_entities()} entities")
    except Exception as e:
        print(f"KG unavailable: {e}")
    
    all_results = []
    for model in MODELS:
        try:
            result = run_model(model, scenarios, db=db)
            all_results.append(result)
        except Exception as e:
            print(f"\n⚠️  {model} FAILED: {e}")
            all_results.append({"model": model, "tpr": -1, "fpr": -1, "error": str(e)})
        time.sleep(1)  # rate limit courtesy
    
    # Final comparison
    print(f"\n{'='*60}")
    print("FINAL COMPARISON")
    print(f"{'='*60}")
    print(f"{'Model':30s} | {'TPR':>6s} | {'FPR':>6s} | {'Score':>6s}")
    print("-" * 60)
    for r in sorted(all_results, key=lambda x: (x.get("tpr", -1), -x.get("fpr", 100)), reverse=True):
        if r.get("tpr", -1) < 0:
            print(f"{r['model']:30s} | {'ERROR':>6s}")
            continue
        # Score = TPR - 2*FPR (penalize false positives)
        score = r["tpr"] - 2 * r["fpr"]
        print(f"{r['model']:30s} | {r['tpr']:5.1f}% | {r['fpr']:5.1f}% | {score:5.1f}")
    
    # Save
    out = Path(__file__).parent.parent / "docs" / "ccbos-model-comparison.json"
    with open(out, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
