#!/usr/bin/env python3
"""Signal Ablation Study — measure each structural signal's independent contribution.

Phase 1: Signal activation map (which signals fire on which scenarios — no LLM)
Phase 2: Targeted ablation (re-run only affected scenarios with signal disabled)

Usage:
  python3 scripts/ablation_study.py map          # Phase 1: signal activation map
  python3 scripts/ablation_study.py ablate train  # Phase 2: full ablation on train
  python3 scripts/ablation_study.py ablate val    # Phase 2: full ablation on val
"""
import json
import math
import os
import sys
import time
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
from nous.fact_extractor import extract_facts
from nous.gate import gate
from nous.triviality_filter import TrivialityConfig
from nous.semantic_gate import SemanticGateConfig

CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"
SPLITS_DIR = Path(__file__).parent.parent / "data" / "splits"
DOCS_DIR = Path(__file__).parent.parent / "docs"

# All structural signals in fact_extractor
ALL_SIGNALS = [
    "has_attribution_signal",
    "recipients_same_domain",
    "has_ransom_signal",
    "has_academic_plagiarism_signal",
    "has_celebration_signal",
    "has_own_submission_signal",
    "has_educational_content_signal",
    "has_advocacy_signal",
    "has_fan_content_signal",
    "has_original_ai_art_signal",
    "has_factual_correction_signal",
    "has_regulatory_compliance_signal",
    "has_medical_wellness_signal",
]


def load_split(name: str):
    path = SPLITS_DIR / f"{name}.json"
    with open(path) as f:
        data = json.load(f)
    return data["harmful"], data["benign"]


def enhanced_tool_calls(scenario: dict) -> list[dict]:
    """Same as run_split_benchmark — inject full prompt as content."""
    from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
    base_calls = scenario_to_tool_calls(scenario)
    full_prompt = scenario.get("prompt", "")
    for tc in base_calls:
        tc["params"]["content"] = full_prompt
        tc["params"]["full_prompt"] = full_prompt
    return base_calls


def signal_activation_map(split_name: str) -> dict:
    """Phase 1: For each scenario, extract facts and record which signals fire.
    No LLM calls — pure fact extraction."""
    harmful, benign = load_split(split_name)
    activation = {}  # signal -> list of scenario_ids that activate it

    for signal in ALL_SIGNALS:
        activation[signal] = {"harmful": [], "benign": []}

    all_scenarios = [(s, True) for s in harmful] + [(s, False) for s in benign]

    for scenario, is_harmful in all_scenarios:
        sid = scenario.get("id", "?")
        tool_calls = enhanced_tool_calls(scenario)
        for tc in tool_calls:
            facts = extract_facts(tc)
            for signal in ALL_SIGNALS:
                val = facts.get(signal)
                if val:  # signal fires (truthy)
                    bucket = "harmful" if is_harmful else "benign"
                    if sid not in activation[signal][bucket]:
                        activation[signal][bucket].append(sid)

    return activation


def run_scenario_gate(scenario, triv_config, sem_config, suppress_signal=None):
    """Run gate on scenario, optionally suppressing a specific signal."""
    tool_calls = enhanced_tool_calls(scenario)
    any_blocked = False

    for tc in tool_calls:
        if suppress_signal:
            # Monkey-patch: wrap extract_facts to zero out the target signal
            original_extract = extract_facts
            def patched_extract(tc_inner, _orig=original_extract, _sig=suppress_signal):
                facts = _orig(tc_inner)
                if _sig in facts:
                    if _sig == "recipients_same_domain":
                        facts[_sig] = None
                    else:
                        facts[_sig] = False
                return facts

            import nous.gate as gate_mod
            import nous.fact_extractor as fe_mod
            # The gate imports extract_facts — we need to patch it at the usage site
            with patch.object(fe_mod, 'extract_facts', side_effect=patched_extract):
                # Also need to patch wherever gate.py imports it from
                orig_gate_extract = getattr(gate_mod, 'extract_facts', None)
                if orig_gate_extract:
                    with patch.object(gate_mod, 'extract_facts', side_effect=patched_extract):
                        gr = gate(tc, db=None, constraints_dir=CONSTRAINTS_DIR,
                                  triviality_config=triv_config, semantic_config=sem_config)
                else:
                    gr = gate(tc, db=None, constraints_dir=CONSTRAINTS_DIR,
                              triviality_config=triv_config, semantic_config=sem_config)
        else:
            gr = gate(tc, db=None, constraints_dir=CONSTRAINTS_DIR,
                      triviality_config=triv_config, semantic_config=sem_config)

        if gr.verdict.action in ("block", "confirm"):
            any_blocked = True

    return any_blocked


def compute_metrics_simple(harmful_results, benign_results):
    """Lightweight metrics: TPR, FPR, L."""
    h_total = len(harmful_results)
    h_blocked = sum(1 for blocked in harmful_results if blocked)
    b_total = len(benign_results)
    b_blocked = sum(1 for blocked in benign_results if blocked)

    tpr = h_blocked / h_total if h_total else 0
    fpr = b_blocked / b_total if b_total else 0

    # Per-category for variance
    cat_data = defaultdict(lambda: {"h_t": 0, "h_b": 0})
    # We need category info — store it alongside
    # Simplified: use overall metrics only
    L = 0.4 * (1 - tpr) + 0.3 * fpr + 0.2 * fpr + 0.1 * 0  # cap ≈ 1-fpr
    return {"tpr": round(tpr * 100, 1), "fpr": round(fpr * 100, 1), "L": round(L, 4),
            "h_blocked": h_blocked, "h_total": h_total, "b_blocked": b_blocked, "b_total": b_total}


def run_ablation(split_name: str, activation_map: dict):
    """Phase 2: For each signal, run affected scenarios with signal disabled."""
    harmful, benign = load_split(split_name)
    h_by_id = {s["id"]: s for s in harmful}
    b_by_id = {s["id"]: s for s in benign}

    triv_config = TrivialityConfig(enabled=True)
    sem_config = SemanticGateConfig(enabled=True, mode="active", model="default")

    # Baseline: run all scenarios without suppression
    print("=== BASELINE ===")
    t0 = time.time()
    baseline_h = {s["id"]: run_scenario_gate(s, triv_config, sem_config) for s in harmful}
    baseline_b = {s["id"]: run_scenario_gate(s, triv_config, sem_config) for s in benign}
    baseline_time = time.time() - t0
    baseline_metrics = compute_metrics_simple(list(baseline_h.values()), list(baseline_b.values()))
    print(f"Baseline: {baseline_metrics} ({baseline_time:.1f}s)")

    results = {"baseline": baseline_metrics, "signals": {}}

    for signal in ALL_SIGNALS:
        affected_h = activation_map.get(signal, {}).get("harmful", [])
        affected_b = activation_map.get(signal, {}).get("benign", [])

        if not affected_h and not affected_b:
            print(f"\n--- {signal}: NO ACTIVATIONS, skip ---")
            results["signals"][signal] = {"status": "no_activations", "delta_L": 0}
            continue

        print(f"\n--- {signal}: {len(affected_h)}h + {len(affected_b)}b affected ---")

        # Re-run only affected scenarios with signal suppressed
        ablated_h = dict(baseline_h)  # copy baseline
        ablated_b = dict(baseline_b)

        t0 = time.time()
        for sid in affected_h:
            if sid in h_by_id:
                ablated_h[sid] = run_scenario_gate(h_by_id[sid], triv_config, sem_config,
                                                    suppress_signal=signal)
        for sid in affected_b:
            if sid in b_by_id:
                ablated_b[sid] = run_scenario_gate(b_by_id[sid], triv_config, sem_config,
                                                    suppress_signal=signal)
        elapsed = time.time() - t0

        metrics = compute_metrics_simple(list(ablated_h.values()), list(ablated_b.values()))
        delta_L = metrics["L"] - baseline_metrics["L"]

        # Find specific changes
        changes = []
        for sid in affected_h:
            if sid in baseline_h and sid in ablated_h:
                if baseline_h[sid] != ablated_h[sid]:
                    changes.append(f"H:{sid} {baseline_h[sid]}→{ablated_h[sid]}")
        for sid in affected_b:
            if sid in baseline_b and sid in ablated_b:
                if baseline_b[sid] != ablated_b[sid]:
                    changes.append(f"B:{sid} {baseline_b[sid]}→{ablated_b[sid]}")

        print(f"  Metrics: {metrics}")
        print(f"  ΔL = {delta_L:+.4f} ({elapsed:.1f}s)")
        if changes:
            print(f"  Changes: {changes}")

        results["signals"][signal] = {
            "metrics": metrics,
            "delta_L": round(delta_L, 4),
            "changes": changes,
            "affected_h": len(affected_h),
            "affected_b": len(affected_b),
            "elapsed_s": round(elapsed, 1),
        }

    # Save results
    out_path = DOCS_DIR / f"ablation-{split_name}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")

    return results


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "map":
        split = sys.argv[2] if len(sys.argv) > 2 else "train"
        print(f"=== Signal Activation Map ({split}) ===\n")
        amap = signal_activation_map(split)
        for signal in ALL_SIGNALS:
            h = amap[signal]["harmful"]
            b = amap[signal]["benign"]
            if h or b:
                print(f"{signal}:")
                if h: print(f"  harmful: {h}")
                if b: print(f"  benign:  {b}")
            else:
                print(f"{signal}: (inactive)")
        # Save
        out = DOCS_DIR / f"signal-map-{split}.json"
        with open(out, "w") as f:
            json.dump(amap, f, indent=2)
        print(f"\nSaved to {out}")

    elif cmd == "ablate":
        split = sys.argv[2] if len(sys.argv) > 2 else "train"
        # Load or generate activation map
        map_path = DOCS_DIR / f"signal-map-{split}.json"
        if map_path.exists():
            print(f"Loading activation map from {map_path}")
            with open(map_path) as f:
                amap = json.load(f)
        else:
            print(f"Generating activation map for {split}...")
            amap = signal_activation_map(split)
            with open(map_path, "w") as f:
                json.dump(amap, f, indent=2)

        run_ablation(split, amap)

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
