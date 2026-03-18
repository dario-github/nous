#!/usr/bin/env python3
"""Run capability probes through Nous gate and compute capability score.

Usage:
  python3 scripts/run_capability_benchmark.py               # run all probes
  python3 scripts/run_capability_benchmark.py --repeat 3     # majority vote
  python3 scripts/run_capability_benchmark.py --level L3     # only L3 (hardest)
  python3 scripts/run_capability_benchmark.py --domain security_research
  python3 scripts/run_capability_benchmark.py --dry-run      # list probes

Output: docs/capability-results.json
"""
import json
import os
import sys
import time
import argparse
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.gate import gate
from nous.triviality_filter import TrivialityConfig
from nous.semantic_gate import SemanticGateConfig

PROBES_PATH = Path(__file__).parent / "capability_probes" / "probes_v1.json"
CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"
DOCS_DIR = Path(__file__).parent.parent / "docs"


def _make_semantic_config() -> SemanticGateConfig:
    """Create active semantic gate config."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  No OPENAI_API_KEY — running L1+L2 only (no semantic gate)")
        return SemanticGateConfig(enabled=False)
    sem_model = os.environ.get("NOUS_SEMANTIC_MODEL", "DeepSeek-V3.1")
    print(f"Semantic gate: {sem_model}")
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


def probe_to_tool_calls(probe: dict) -> list[dict]:
    """Convert a capability probe into tool calls for gate evaluation.

    Uses the same structure as AgentHarm adapter: one tool call per target_function,
    each carrying the full prompt. This ensures probes go through the full 3-layer
    pipeline (Datalog → triviality → semantic gate).
    """
    from nous.benchmarks.agentharm.adapter import get_action_type
    
    target_funcs = probe.get("target_functions", [])
    if not target_funcs:
        # Fallback: single generic tool call
        return [{
            "action": "execute_task",
            "action_type": "exec_command",
            "tool_name": "execute_task",
            "params": {"full_prompt": probe["prompt"]},
            "prompt": probe["prompt"]
        }]
    
    tool_calls = []
    for func_name in target_funcs:
        action_type = get_action_type(func_name) if func_name not in (
            "exec_command", "write_file", "read_data", "send_message",
            "publish_post", "web_search", "web_fetch", "download",
            "upload", "generate_content", "delete_file", "exec_destructive",
            "financial_transfer", "transform"
        ) else func_name
        
        tool_calls.append({
            "action_type": action_type,
            "action": func_name,
            "tool_name": func_name,
            "params": {"full_prompt": probe["prompt"]},
            "prompt": probe["prompt"],
        })
    return tool_calls


def run_probe_once(probe, triv_config, sem_config):
    """Run gate on a single probe. Returns (blocked, details).
    
    A probe is blocked if ANY of its tool calls is blocked (same logic as AgentHarm).
    """
    tool_calls = probe_to_tool_calls(probe)
    for tc in tool_calls:
        result = gate(tc, constraints_dir=CONSTRAINTS_DIR,
                      triviality_config=triv_config, semantic_config=sem_config)
        v = result.verdict
        if v.action == "block":
            return True, {
                "tool_call": tc.get("action", "?"),
                "reason": str(v.reason)[:300],
                "layer": str(result.layer_path),
                "rule_id": str(v.rule_id)
            }
    return False, {"layer": str(result.layer_path), "n_calls": len(tool_calls)}


def run_probe_majority(probe, triv_config, sem_config, repeat=1):
    """Run probe multiple times, majority vote."""
    blocked_count = 0
    details_list = []
    for _ in range(repeat):
        blocked, details = run_probe_once(probe, triv_config, sem_config)
        if blocked:
            blocked_count += 1
            details_list.append(details)
        if repeat > 1:
            time.sleep(0.3)
    majority_blocked = blocked_count > repeat // 2
    return majority_blocked, details_list


def main():
    parser = argparse.ArgumentParser(description="Capability probe benchmark")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--level", type=str, default=None, help="Filter by level: L1/L2/L3")
    parser.add_argument("--domain", type=str, default=None, help="Filter by domain")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--probes", type=str, default=None, help="Path to probes JSON")
    args = parser.parse_args()

    probes_path = Path(args.probes) if args.probes else PROBES_PATH
    with open(probes_path) as f:
        probes = json.load(f)

    # Filter
    if args.level:
        probes = [p for p in probes if p["level"] == args.level]
    if args.domain:
        probes = [p for p in probes if p["domain"] == args.domain]

    if args.dry_run:
        print(f"Capability probes: {len(probes)}")
        for p in probes:
            print(f"  {p['id']} [{p['domain']}/{p['level']}] overlap={p['overlap_category']}")
            print(f"    {p['prompt'][:100]}...")
        return

    print(f"Running {len(probes)} capability probes (repeat={args.repeat})")
    triv_config = TrivialityConfig()
    sem_config = _make_semantic_config()

    results = []
    blocked_ids = []
    allowed_ids = []
    domain_stats = defaultdict(lambda: {"total": 0, "blocked": 0})
    level_stats = defaultdict(lambda: {"total": 0, "blocked": 0})

    for i, probe in enumerate(probes):
        pid = probe["id"]
        domain = probe["domain"]
        level = probe["level"]

        blocked, details = run_probe_majority(probe, triv_config, sem_config, args.repeat)

        verdict_str = "BLOCKED ❌" if blocked else "ALLOWED ✅"
        print(f"  [{i+1}/{len(probes)}] {pid} ({domain}/{level}): {verdict_str}")
        if blocked:
            blocked_ids.append(pid)
            print(f"    → {details[0].get('reason', '?')[:120]}")
        else:
            allowed_ids.append(pid)

        results.append({
            "id": pid,
            "domain": domain,
            "level": level,
            "overlap_category": probe["overlap_category"],
            "blocked": blocked,
            "details": details,
            "expected": probe["expected_verdict"]
        })

        domain_stats[domain]["total"] += 1
        level_stats[level]["total"] += 1
        if blocked:
            domain_stats[domain]["blocked"] += 1
            level_stats[level]["blocked"] += 1

    # Compute scores
    total = len(probes)
    n_allowed = len(allowed_ids)
    n_blocked = len(blocked_ids)
    allow_rate = n_allowed / total if total > 0 else 0

    # Unexpected blocks (expected=allow but got blocked)
    unexpected_blocks = [r for r in results if r["blocked"] and r["expected"] == "allow"]

    print(f"\n{'='*60}")
    print(f"CAPABILITY SCORE: {allow_rate:.2%} ({n_allowed}/{total} allowed)")
    print(f"Blocked: {n_blocked} | Unexpected blocks: {len(unexpected_blocks)}")

    print(f"\nBy domain:")
    for domain, stats in sorted(domain_stats.items()):
        rate = 1 - stats["blocked"] / stats["total"]
        bar = "█" * int(rate * 20) + "░" * (20 - int(rate * 20))
        print(f"  {domain:30s} {bar} {rate:.0%} ({stats['total']-stats['blocked']}/{stats['total']})")

    print(f"\nBy level:")
    for level, stats in sorted(level_stats.items()):
        rate = 1 - stats["blocked"] / stats["total"]
        print(f"  {level}: {rate:.0%} ({stats['total']-stats['blocked']}/{stats['total']})")

    if unexpected_blocks:
        print(f"\n⚠️  UNEXPECTED BLOCKS (capability regression):")
        for r in unexpected_blocks:
            print(f"  {r['id']}: {r['details'][0].get('reason', '?')[:120]}")

    # Save results
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "repeat": args.repeat,
        "total_probes": total,
        "allowed": n_allowed,
        "blocked": n_blocked,
        "allow_rate": round(allow_rate, 4),
        "capability_score": round(allow_rate, 4),  # binary gate: cap = allow_rate
        "unexpected_blocks": len(unexpected_blocks),
        "by_domain": {d: {"allow_rate": round(1 - s["blocked"]/s["total"], 4),
                          "total": s["total"], "blocked": s["blocked"]}
                      for d, s in domain_stats.items()},
        "by_level": {l: {"allow_rate": round(1 - s["blocked"]/s["total"], 4),
                         "total": s["total"], "blocked": s["blocked"]}
                     for l, s in level_stats.items()},
        "details": results
    }

    out_path = DOCS_DIR / "capability-results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
