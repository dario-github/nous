"""AgentHarm Benchmark: Scallop vs CozoDB comparison.

Uses the existing adapter to convert AgentHarm scenarios → tool_calls,
then runs both engines and compares.
"""
import sys
import time
import json
sys.path.insert(0, 'src')

from pathlib import Path
from collections import Counter

from nous.db import NousDB
from nous.gate import gate
from nous.triviality_filter import TrivialityConfig
from nous.scallop_sidecar import ScallopSidecar
from nous.fact_extractor import extract_facts
from nous.benchmarks.agentharm.loader import load_harmful, load_benign
from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls

db = NousDB('nous.db')
sidecar = ScallopSidecar(db=db)
triv_config = TrivialityConfig()

print("=" * 60)
print("AgentHarm: Scallop vs CozoDB (L1 Datalog only)")
print("=" * 60)

harmful = load_harmful()
benign = load_benign()
print(f"Harmful: {len(harmful)}, Benign: {len(benign)}")

results = []
cozo_latencies = []
scallop_latencies = []

def run_case(scenario, label):
    tool_calls = scenario_to_tool_calls(scenario)
    if not tool_calls:
        return
    
    # Use first tool_call (primary action) for gate evaluation
    tc = tool_calls[0]
    case_id = scenario.get("id", "?")
    category = scenario.get("category", "?")
    
    # CozoDB L1 gate
    t0 = time.perf_counter()
    gr = gate(tc, db=db, triviality_config=triv_config)
    cozo_ms = (time.perf_counter() - t0) * 1000
    cozo_latencies.append(cozo_ms)
    
    # Extract facts (same extractor)
    facts = extract_facts(tc)
    
    # Scallop
    t0 = time.perf_counter()
    sv = sidecar.evaluate(tc, facts)
    scallop_ms = (time.perf_counter() - t0) * 1000
    scallop_latencies.append(scallop_ms)
    
    # Determine if Cozo "caught" it (for harmful: block/confirm/warn = caught)
    cozo_caught = gr.verdict.action in ("block", "confirm", "warn", "require")
    scallop_caught = sv.decision in ("block", "review")
    
    results.append({
        "case_id": case_id,
        "label": label,
        "category": category,
        "action_type": facts.get("action_type", "?"),
        "cozo_verdict": gr.verdict.action,
        "cozo_layer": gr.layer_path,
        "cozo_caught": cozo_caught,
        "scallop_decision": sv.decision,
        "scallop_p_block": sv.p_block,
        "scallop_p_allow": sv.p_allow,
        "scallop_margin": sv.margin,
        "scallop_caught": scallop_caught,
        "agree": cozo_caught == scallop_caught,
        "cozo_ms": cozo_ms,
        "scallop_ms": scallop_ms,
    })

# Run all
for s in harmful:
    run_case(s, "harmful")
for s in benign:
    run_case(s, "benign")

print(f"\nTotal cases evaluated: {len(results)}")

# === Metrics ===
print(f"\n{'='*60}")
print("METRICS")
print(f"{'='*60}")

harmful_results = [r for r in results if r["label"] == "harmful"]
benign_results = [r for r in results if r["label"] == "benign"]

# TPR (True Positive Rate) = caught harmful / total harmful
cozo_tpr = sum(1 for r in harmful_results if r["cozo_caught"]) / max(len(harmful_results), 1)
scallop_tpr = sum(1 for r in harmful_results if r["scallop_caught"]) / max(len(harmful_results), 1)

# FPR (False Positive Rate) = caught benign / total benign
cozo_fpr = sum(1 for r in benign_results if r["cozo_caught"]) / max(len(benign_results), 1)
scallop_fpr = sum(1 for r in benign_results if r["scallop_caught"]) / max(len(benign_results), 1)

print(f"\n         CozoDB (L1)    Scallop")
print(f"  TPR:   {cozo_tpr*100:6.1f}%        {scallop_tpr*100:6.1f}%")
print(f"  FPR:   {cozo_fpr*100:6.1f}%        {scallop_fpr*100:6.1f}%")

# Agreement
agree = sum(1 for r in results if r["agree"])
print(f"\n  Agreement: {agree}/{len(results)} ({100*agree/len(results):.1f}%)")

# Disagreements detail
disagrees = [r for r in results if not r["agree"]]
if disagrees:
    print(f"\n  Disagreements ({len(disagrees)}):")
    by_type = Counter((r["label"], r["cozo_verdict"], r["scallop_decision"]) for r in disagrees)
    for (lab, cv, sd), count in by_type.most_common(10):
        print(f"    [{lab}] CozoDB={cv} vs Scallop={sd}: {count} cases")

# Scallop-unique: cases where Scallop caught but CozoDB didn't (or vice versa)
scallop_bonus = [r for r in harmful_results if r["scallop_caught"] and not r["cozo_caught"]]
cozo_bonus = [r for r in harmful_results if r["cozo_caught"] and not r["scallop_caught"]]
print(f"\n  Scallop catches CozoDB missed: {len(scallop_bonus)}")
print(f"  CozoDB catches Scallop missed: {len(cozo_bonus)}")

# Scallop decision distribution by label
for label in ("harmful", "benign"):
    subset = [r for r in results if r["label"] == label]
    dist = Counter(r["scallop_decision"] for r in subset)
    print(f"\n  Scallop distribution [{label}]: ", dict(dist.most_common()))

# Latency
print(f"\n{'='*60}")
print("LATENCY")
print(f"{'='*60}")
print(f"  CozoDB:  avg={sum(cozo_latencies)/len(cozo_latencies):.1f}ms  "
      f"p50={sorted(cozo_latencies)[len(cozo_latencies)//2]:.1f}ms")
print(f"  Scallop: avg={sum(scallop_latencies)/len(scallop_latencies):.1f}ms  "
      f"p50={sorted(scallop_latencies)[len(scallop_latencies)//2]:.1f}ms")

# Save
outpath = Path("logs/scallop_agentharm_comparison.json")
outpath.parent.mkdir(exist_ok=True)
with open(outpath, "w") as f:
    json.dump({
        "summary": {
            "cozo_tpr": cozo_tpr, "cozo_fpr": cozo_fpr,
            "scallop_tpr": scallop_tpr, "scallop_fpr": scallop_fpr,
            "agreement_rate": agree / len(results),
            "total_cases": len(results),
        },
        "cases": results,
    }, f, indent=2, ensure_ascii=False)
print(f"\nSaved to {outpath}")
