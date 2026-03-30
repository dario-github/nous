#!/usr/bin/env python3
"""Run Nous gate against InjecAgent external benchmark (30 harmful scenarios).

Usage:
  cd /home/yan/clawd/nous
  python3 scripts/run_injecagent_benchmark.py [--l1-only]

Outputs TPR and per-category breakdown.
"""
import json
import os
import sys
import time
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.gate import gate
from nous.triviality_filter import TrivialityConfig
from nous.semantic_gate import SemanticGateConfig

CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"
EXTERNAL_DATA = Path(__file__).parent.parent / "data" / "challenge" / "external_adapted_v1.json"

# Mapping from InjecAgent target_functions to Nous action types
FUNC_TO_ACTION = {
    "execute_command": "exec_destructive",
    "run_command": "exec_destructive",
    "bash": "exec_destructive",
    "terminal": "exec_destructive",
    "delete_file": "delete_file",
    "remove_file": "delete_file",
    "read_file": "read_file",
    "read_env_vars": "read_file",
    "send_email": "send_message",
    "post_tweet": "publish_post",
    "post_on_twitter": "publish_post",
    "make_http_request": "send_message",
    "upload_file": "write_file",
    "write_file": "write_file",
    "modify_file": "write_file",
    "call_api": "send_message",
    "get_contacts": "read_data",
    "query_database": "read_data",
    "list_directory": "read_file",
    "download_pdf": "read_file",
    "get_ssh_config": "read_file",
    "create_webhook": "send_message",
    "send_slack_message": "send_message",
    "send_sms": "send_message",
    "git_push": "exec_destructive",
    "create_github_issue": "publish_post",
}


def scenario_to_tool_call(scenario: dict) -> dict:
    """Convert InjecAgent scenario to Nous gate() format."""
    # Use the most dangerous action type from target_functions
    action_priority = {
        "exec_destructive": 5,
        "delete_file": 4,
        "publish_post": 3,
        "write_file": 3,
        "send_message": 2,
        "read_data": 1,
        "read_file": 1,
        "web_search": 0,
    }
    
    action_type = "web_search"  # default benign
    for fn in scenario.get("target_functions", []):
        mapped = FUNC_TO_ACTION.get(fn, "web_search")
        if action_priority.get(mapped, 0) > action_priority.get(action_type, 0):
            action_type = mapped
    
    return {
        "action_type": action_type,
        "tool_name": scenario.get("target_functions", ["unknown"])[0] if scenario.get("target_functions") else "unknown",
        "args": {
            "prompt": scenario["prompt"],
            "category": scenario.get("category", ""),
        },
        "context": f"InjecAgent scenario: {scenario.get('name', 'unknown')} | attack: {scenario.get('original_attack_type', '')}",
    }


def make_semantic_config(l1_only: bool = False) -> SemanticGateConfig:
    """Create semantic gate config."""
    if l1_only:
        return SemanticGateConfig(enabled=False)
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  No OPENAI_API_KEY — running L1+L2 only")
        return SemanticGateConfig(enabled=False)
    
    from nous.providers.openai_provider import create_openai_provider
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    sem_model = os.environ.get("NOUS_SEMANTIC_MODEL", "DeepSeek-V3.1")
    print(f"Semantic gate: {sem_model} @ {base_url}")
    provider = create_openai_provider(model=sem_model, api_key=api_key, base_url=base_url)
    return SemanticGateConfig(enabled=True, provider=provider, threshold=0.85, upgrade_only=True)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--l1-only", action="store_true", help="L1+L2 only, no semantic")
    args = parser.parse_args()

    # Load data
    with open(EXTERNAL_DATA) as f:
        data = json.load(f)
    
    scenarios = data["scenarios"]
    print(f"\n=== InjecAgent External Benchmark ===")
    print(f"Source: {data['metadata']['source']}")
    print(f"Total scenarios: {len(scenarios)}")
    print(f"Mode: {'L1+L2 only' if args.l1_only else 'L1+L2+L3'}")
    print()
    
    # Setup
    sem_config = make_semantic_config(l1_only=args.l1_only)
    triv_config = TrivialityConfig()
    
    results = []
    category_results = defaultdict(lambda: {"tp": 0, "fn": 0})
    
    for i, sc in enumerate(scenarios):
        tool_call = scenario_to_tool_call(sc)
        expected = sc["expected_verdict"]  # all "block"
        
        try:
            result = gate(
                tool_call=tool_call,
                constraints_dir=CONSTRAINTS_DIR,
                triviality_config=triv_config,
                semantic_config=sem_config,
            )
            # GateResult has a Verdict object
            verdict_obj = result.verdict
            verdict_action = verdict_obj.action if hasattr(verdict_obj, 'action') else str(verdict_obj)
            layer_path = result.layer_path or []
            rule_id = verdict_obj.rule_id if hasattr(verdict_obj, 'rule_id') else ""
            
            correct = (verdict_action == "block") == (expected == "block")
            
            if verdict_action == "block":
                category_results[sc["category"]]["tp"] += 1
            else:
                category_results[sc["category"]]["fn"] += 1
            
            status = "✓" if correct else "✗"
            print(f"  [{i+1:2d}] {status} {sc['name'][:40]:<40} | action={tool_call['action_type']:<18} | verdict={verdict_action} | rule={rule_id}")
            
            results.append({
                "id": sc["id"],
                "name": sc["name"],
                "category": sc["category"],
                "action_type": tool_call["action_type"],
                "expected": expected,
                "verdict": verdict_action,
                "layer_path": layer_path,
                "rule": rule_id,
                "correct": correct,
            })
            
        except Exception as e:
            print(f"  [{i+1:2d}] ERROR {sc['name'][:40]} — {e}")
            results.append({
                "id": sc["id"],
                "name": sc["name"],
                "expected": expected,
                "verdict": "error",
                "correct": False,
            })
    
    # Summary
    n_correct = sum(1 for r in results if r["correct"])
    n_total = len(results)
    tpr = n_correct / n_total if n_total > 0 else 0.0
    
    print(f"\n{'='*60}")
    print(f"RESULTS (InjecAgent, N={n_total})")
    print(f"  TPR: {n_correct}/{n_total} = {tpr:.1%}")
    print(f"\nPer-category:")
    for cat, counts in sorted(category_results.items()):
        n = counts["tp"] + counts["fn"]
        rate = counts["tp"] / n if n > 0 else 0.0
        print(f"  {cat:<30} {counts['tp']}/{n} = {rate:.0%}")
    
    # Save results
    out_path = Path(__file__).parent.parent / "data" / "challenge" / "injecagent_results.json"
    with open(out_path, "w") as f:
        json.dump({
            "metadata": {
                "source": "InjecAgent",
                "mode": "L1L2" if args.l1_only else "L1L2L3",
                "n_scenarios": n_total,
                "tpr": round(tpr, 4),
                "n_correct": n_correct,
            },
            "results": results,
            "per_category": {k: v for k, v in category_results.items()},
        }, f, indent=2)
    print(f"\nResults saved: {out_path}")


if __name__ == "__main__":
    main()
