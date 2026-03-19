#!/usr/bin/env python3
"""AgentHarm Three-Layer Benchmark Runner (v2)

Configs:
- L1 only (Datalog baseline)
- L1 + L2 (triviality filter)
- L1 + L2 + L3 (full three-layer with real LLM semantic gate)

Key improvement over v1:
- Enhanced adapter injects full prompt as content for semantic gate
- Real OpenAI LLM provider for L3
- Per-action-type + per-category + layer funnel analysis
"""
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.benchmarks.agentharm.loader import load_harmful, load_benign
from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
from nous.gate import gate, GateResult
from nous.triviality_filter import TrivialityConfig
from nous.semantic_gate import SemanticGateConfig

CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"


def enhanced_tool_calls(scenario: dict) -> list[dict]:
    """Enhanced adapter: inject full prompt as content for semantic gate."""
    base_calls = scenario_to_tool_calls(scenario)
    full_prompt = scenario.get("prompt", "")
    for tc in base_calls:
        # Inject full prompt as content — this is what the semantic gate analyzes
        tc["params"]["content"] = full_prompt
        tc["params"]["full_prompt"] = full_prompt
    return base_calls


def run_config(scenarios, is_harmful, triviality_config=None,
               semantic_config=None, enhanced=False, db=None):
    """Run gate on all scenarios with given config."""
    results = []
    for scenario in scenarios:
        if enhanced:
            tool_calls = enhanced_tool_calls(scenario)
        else:
            tool_calls = scenario_to_tool_calls(scenario)

        tc_results = []
        for tc in tool_calls:
            gr = gate(
                tc, db=db,
                constraints_dir=CONSTRAINTS_DIR,
                triviality_config=triviality_config,
                semantic_config=semantic_config,
            )
            tc_results.append({
                "func_name": tc.get("tool_name", "unknown"),
                "action_type": tc.get("action_type", "unknown"),
                "verdict": gr.verdict.action,
                "layer_path": gr.layer_path,
                "rule_id": gr.verdict.rule_id,
                "reason": gr.verdict.reason[:120] if gr.verdict.reason else "",
                "semantic_verdict": gr.semantic_verdict,
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


def analyze(harmful_results, benign_results):
    """Compute metrics with layer funnel analysis."""
    h_total = len(harmful_results)
    h_blocked = sum(1 for r in harmful_results if r["any_blocked"])
    b_total = len(benign_results)
    b_blocked = sum(1 for r in benign_results if r["any_blocked"])

    tpr = h_blocked / h_total * 100 if h_total else 0
    fpr = b_blocked / b_total * 100 if b_total else 0

    # Hard metrics: only count "block" verdicts (not "confirm")
    h_hard_blocked = sum(1 for r in harmful_results if any(
        tc["verdict"] == "block" for tc in r["tool_results"]))
    b_hard_blocked = sum(1 for r in benign_results if any(
        tc["verdict"] == "block" for tc in r["tool_results"]))
    hard_tpr = h_hard_blocked / h_total * 100 if h_total else 0
    hard_fpr = b_hard_blocked / b_total * 100 if b_total else 0

    # Layer funnel
    funnel = defaultdict(int)
    action_stats = defaultdict(lambda: {
        "h_total": 0, "h_blocked": 0,
        "b_total": 0, "b_blocked": 0,
        "layer_paths": defaultdict(int),
    })
    cat_stats = defaultdict(lambda: {
        "h_total": 0, "h_blocked": 0,
        "b_total": 0, "b_blocked": 0,
    })

    # Semantic gate action stats
    sem_actions = {"allow": 0, "block": 0, "confirm": 0, "none": 0}

    for results, is_h in [(harmful_results, True), (benign_results, False)]:
        key = "h" if is_h else "b"
        for r in results:
            cat_stats[r["category"]][f"{key}_total"] += 1
            if r["any_blocked"]:
                cat_stats[r["category"]][f"{key}_blocked"] += 1
            for tc in r["tool_results"]:
                at = tc["action_type"]
                action_stats[at][f"{key}_total"] += 1
                if tc["verdict"] in ("block", "confirm"):
                    action_stats[at][f"{key}_blocked"] += 1
                action_stats[at]["layer_paths"][tc["layer_path"]] += 1
                funnel[tc["layer_path"]] += 1
                if tc["semantic_verdict"]:
                    sem_actions[tc["semantic_verdict"].get("action", "none")] += 1
                else:
                    sem_actions["none"] += 1

    return {
        "overall": {
            "tpr": round(tpr, 1), "fpr": round(fpr, 1),
            "hard_tpr": round(hard_tpr, 1), "hard_fpr": round(hard_fpr, 1),
            "h_blocked": h_blocked, "h_total": h_total,
            "b_blocked": b_blocked, "b_total": b_total,
            "h_hard_blocked": h_hard_blocked, "b_hard_blocked": b_hard_blocked,
        },
        "funnel": dict(funnel),
        "semantic_actions": dict(sem_actions),
        "per_action_type": {
            at: {
                "h_rate": round(s["h_blocked"] / s["h_total"] * 100, 1) if s["h_total"] else 0,
                "b_rate": round(s["b_blocked"] / s["b_total"] * 100, 1) if s["b_total"] else 0,
                "h_n": f"{s['h_blocked']}/{s['h_total']}",
                "b_n": f"{s['b_blocked']}/{s['b_total']}",
                "paths": dict(s["layer_paths"]),
            }
            for at, s in sorted(action_stats.items())
        },
        "per_category": {
            cat: {
                "h_tpr": round(s["h_blocked"] / s["h_total"] * 100, 1) if s["h_total"] else 0,
                "b_fpr": round(s["b_blocked"] / s["b_total"] * 100, 1) if s["b_total"] else 0,
                "h_n": f"{s['h_blocked']}/{s['h_total']}",
                "b_n": f"{s['b_blocked']}/{s['b_total']}",
            }
            for cat, s in sorted(cat_stats.items())
        },
    }


def print_comparison(label, m1, m2, m1_name="L1", m2_name="L1+L2+L3"):
    """Print a comparison table."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  {'Metric':<15} {m1_name:>12} {m2_name:>12} {'Delta':>10}")
    print(f"  {'-'*49}")
    for key in ["tpr", "fpr", "hard_tpr", "hard_fpr"]:
        v1 = m1["overall"].get(key, 0)
        v2 = m2["overall"].get(key, 0)
        d = v2 - v1
        label = key.upper().replace("_", " ")
        print(f"  {label:<15} {v1:>11.1f}% {v2:>11.1f}% {d:>+9.1f}%")

    print(f"\n  Layer Funnel ({m2_name}):")
    for path, count in sorted(m2.get("funnel", {}).items()):
        print(f"    {path}: {count} tool calls")

    if any(v > 0 for k, v in m2.get("semantic_actions", {}).items() if k != "none"):
        print(f"\n  Semantic Gate Actions:")
        for action, count in sorted(m2.get("semantic_actions", {}).items()):
            if count > 0:
                print(f"    {action}: {count}")

    print(f"\n  Per Category:")
    print(f"  {'Category':<18} {'TPR':>8} {'→':>2} {'TPR':>8} {'FPR':>8} {'→':>2} {'FPR':>8}")
    for cat in sorted(set(list(m1["per_category"].keys()) + list(m2["per_category"].keys()))):
        c1 = m1["per_category"].get(cat, {"h_tpr": 0, "b_fpr": 0})
        c2 = m2["per_category"].get(cat, {"h_tpr": 0, "b_fpr": 0})
        print(f"  {cat:<18} {c1['h_tpr']:>7.1f}% → {c2['h_tpr']:>7.1f}%  {c1['b_fpr']:>7.1f}% → {c2['b_fpr']:>7.1f}%")


def _load_kg_db():
    """Load a KG database with seeded data + OWL reasoning for Markov Blanket testing."""
    from nous.db import NousDB
    db = NousDB(path=":memory:")

    # Import seed data directly
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from seed_mitre_attack import TACTICS, TECHNIQUES
        from nous.schema import Entity, Relation
        import time as _t

        now = _t.time()
        entities = []
        relations = []

        for tac in TACTICS:
            entities.append(Entity(
                id=f"tactic:{tac['id']}", etype="tactic",
                labels=[tac["name"]], props={"desc": tac["desc"]},
                confidence=1.0, source="mitre-attack",
                created_at=now, updated_at=now,
            ))

        for tech in TECHNIQUES:
            entities.append(Entity(
                id=f"technique:{tech['id']}", etype="technique",
                labels=[tech["name"]], props={"desc": tech.get("desc", "")},
                confidence=1.0, source="mitre-attack",
                created_at=now, updated_at=now,
            ))
            tac_ids = tech.get("tactics", [])
            if not tac_ids and tech.get("tactic"):
                tac_ids = [tech["tactic"]]
            for tac_id in tac_ids:
                relations.append(Relation(
                    from_id=f"technique:{tech['id']}", to_id=f"tactic:{tac_id}",
                    rtype="BELONGS_TO", props={},
                    confidence=1.0, source="mitre-attack", created_at=now,
                ))

        db.upsert_entities(entities)
        db.upsert_relations(relations)
        print(f"  Seeded {len(entities)} entities, {len(relations)} relations")
    except Exception as e:
        print(f"  [warn] seed failed: {e}")

    # Run OWL reasoning
    try:
        from nous.owl_rules import add_subclass, materialize_inferences
        # Add subclass axioms: technique subtypes
        add_subclass(db, "technique", "cyber_operation")
        add_subclass(db, "cyber_operation", "harmful_action")
        add_subclass(db, "tactic", "attack_phase")
        stats = materialize_inferences(db)
        print(f"  OWL: {stats}")
    except Exception as e:
        print(f"  [warn] OWL reasoning: {e}")

    return db


def main():
    print("="*60)
    print("  AgentHarm Three-Layer Benchmark")
    print("="*60)

    # Load KG if --with-kg flag
    kg_db = None
    if "--with-kg" in sys.argv:
        print("\n[KG] Loading knowledge graph with Markov Blanket support...")
        kg_db = _load_kg_db()
        entity_result = kg_db.query("?[id] := *entity{id}")
        entity_count = len(entity_result) if isinstance(entity_result, list) else len(entity_result.get("rows", []))
        rel_result = kg_db.query("?[f,t,r] := *relation{from_id: f, to_id: t, rtype: r}")
        rel_count = len(rel_result) if isinstance(rel_result, list) else len(rel_result.get("rows", []))
        print(f"  KG loaded: {entity_count} entities, {rel_count} relations")

    harmful = load_harmful()
    benign = load_benign()
    print(f"\nDataset: {len(harmful)} harmful + {len(benign)} benign scenarios")

    # === L1 baseline ===
    print("\n[1/3] Running L1 Only (Datalog baseline)...")
    t0 = time.perf_counter()
    h1 = run_config(harmful, True)
    b1 = run_config(benign, False)
    m1 = analyze(h1, b1)
    print(f"  TPR={m1['overall']['tpr']}% FPR={m1['overall']['fpr']}% ({time.perf_counter()-t0:.1f}s)")

    # === L1+L2 ===
    print("\n[2/3] Running L1+L2 (Triviality Filter)...")
    triv = TrivialityConfig()
    t0 = time.perf_counter()
    h2 = run_config(harmful, True, triviality_config=triv)
    b2 = run_config(benign, False, triviality_config=triv)
    m2 = analyze(h2, b2)
    print(f"  TPR={m2['overall']['tpr']}% FPR={m2['overall']['fpr']}% ({time.perf_counter()-t0:.1f}s)")

    # === L1+L2+L3 (real LLM) ===
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("\n[3/3] SKIPPED — no OPENAI_API_KEY")
        m3 = None
    else:
        sem_model = os.environ.get("NOUS_SEMANTIC_MODEL", "DeepSeek-V3.1")
        print(f"\n[3/3] Running L1+L2+L3 (Semantic Gate with {sem_model})...")
        from nous.providers.openai_provider import create_openai_provider
        provider = create_openai_provider(model=sem_model, api_key=api_key)
        sem_config = SemanticGateConfig(
            enabled=True,
            mode="active",
            model=sem_model,
            timeout_ms=15000,
            max_content_chars=4000,
            provider=provider,
        )
        t0 = time.perf_counter()
        h3 = run_config(harmful, True, triviality_config=triv,
                        semantic_config=sem_config, enhanced=True, db=kg_db)
        b3 = run_config(benign, False, triviality_config=triv,
                        semantic_config=sem_config, enhanced=True, db=kg_db)
        elapsed = time.perf_counter() - t0
        m3 = analyze(h3, b3)
        print(f"  TPR={m3['overall']['tpr']}% FPR={m3['overall']['fpr']}% "
              f"hard_TPR={m3['overall'].get('hard_tpr',0)}% "
              f"hard_FPR={m3['overall'].get('hard_fpr',0)}% ({elapsed:.1f}s)")

    # === Comparison ===
    print_comparison("L1 → L1+L2", m1, m2, "L1", "L1+L2")
    if m3:
        print_comparison("L1 → L1+L2+L3", m1, m3, "L1", "L1+L2+L3")

    # Save
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "l1": m1,
        "l1_l2": m2,
        "l1_l2_l3": m3,
    }
    out_path = Path(__file__).parent.parent / "docs" / "agentharm-threelayer-v2.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\nResults saved to {out_path}")

    # Also save raw scenarios for FP analysis
    if m3:
        raw_path = Path(__file__).parent.parent / "docs" / "agentharm-raw-scenarios.json"
        raw_output = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "harmful_scenarios": h3,
            "benign_scenarios": b3,
        }
        raw_path.write_text(json.dumps(raw_output, indent=2, ensure_ascii=False))
        print(f"Raw scenarios saved to {raw_path}")


if __name__ == "__main__":
    main()
