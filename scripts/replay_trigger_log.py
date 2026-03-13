#!/usr/bin/env python3
"""Replay trigger_log.jsonl through Nous gate() — 产出真实评估数据

用法: python3 nous/scripts/replay_trigger_log.py [--limit N] [--verbose]

输出:
  - nous/logs/replay_results.jsonl — 每条 tool call 的 Nous verdict
  - 终端汇总统计
"""
import json
import sys
import time
import argparse
from pathlib import Path

# 确保 nous 在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.gate import gate, GateResult
from nous.db import NousDB

TRIGGER_LOG = Path.home() / ".openclaw/ontology-gate/trigger_log.jsonl"
OUTPUT_DIR = Path(__file__).parent.parent / "logs"
OUTPUT_FILE = OUTPUT_DIR / "replay_results.jsonl"


def parse_tool_call(entry: dict) -> dict:
    """从 trigger_log entry 重建 tool_call dict"""
    ctx = entry.get("tool_context", {})
    params_summary = ctx.get("params_summary", "")

    # 从 params_summary 提取参数（格式: "tool:key=val,key=val"）
    params = {}
    if ":" in params_summary:
        parts = params_summary.split(":", 1)
        if len(parts) > 1:
            for kv in parts[1].split(","):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    params[k.strip()] = v.strip()

    return {
        "tool_name": entry.get("tool", ctx.get("name", "unknown")),
        "params": params,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max entries to replay (0=all)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not TRIGGER_LOG.exists():
        print(f"❌ Trigger log not found: {TRIGGER_LOG}")
        sys.exit(1)

    # 读取所有 entries
    entries = []
    with open(TRIGGER_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if args.limit > 0:
        entries = entries[:args.limit]

    print(f"📊 Replay {len(entries)} tool calls through Nous gate()")
    print(f"   Source: {TRIGGER_LOG}")
    print()

    # 初始化 Nous
    db_path = Path(__file__).parent.parent / "data" / "nous.db"
    db = NousDB(str(db_path)) if db_path.exists() else None
    constraints_dir = Path(__file__).parent.parent / "ontology" / "constraints"

    # Replay
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    stats = {
        "total": 0,
        "allow": 0,
        "block": 0,
        "confirm": 0,
        "warn": 0,
        "rewrite": 0,
        "error": 0,
        "latencies_us": [],
        "by_tool": {},
        "gates_fired": {},
    }

    start_all = time.perf_counter()

    with open(OUTPUT_FILE, "w") as out:
        for i, entry in enumerate(entries):
            tool_call = parse_tool_call(entry)
            t0 = time.perf_counter_ns()

            try:
                result: GateResult = gate(
                    tool_call=tool_call,
                    db=db,
                    constraints_dir=constraints_dir,
                    session_key=entry.get("session_key", f"replay:{i}"),
                )
                verdict = result.verdict.action
                rule_id = result.verdict.rule_id
                latency_us = (time.perf_counter_ns() - t0) // 1000

                # 对比 TS engine 结果
                ts_gates = entry.get("gates", [])
                ts_blocked = any(g.get("verdict") == "block" for g in ts_gates) if ts_gates else False
                nous_blocked = verdict == "block"
                consistent = ts_blocked == nous_blocked

            except Exception as e:
                verdict = "error"
                rule_id = None
                latency_us = (time.perf_counter_ns() - t0) // 1000
                ts_blocked = False
                nous_blocked = False
                consistent = True
                stats["error"] += 1
                if args.verbose:
                    print(f"  ⚠️ #{i} {tool_call['tool_name']}: {e}")

            stats["total"] += 1
            stats[verdict] = stats.get(verdict, 0) + 1
            stats["latencies_us"].append(latency_us)

            tool = tool_call["tool_name"]
            if tool not in stats["by_tool"]:
                stats["by_tool"][tool] = {"total": 0, "block": 0, "confirm": 0, "allow": 0}
            stats["by_tool"][tool]["total"] += 1
            stats["by_tool"][tool][verdict] = stats["by_tool"][tool].get(verdict, 0) + 1

            if rule_id and verdict != "allow":
                stats["gates_fired"][rule_id] = stats["gates_fired"].get(rule_id, 0) + 1

            record = {
                "ts": entry.get("ts"),
                "tool": tool,
                "nous_verdict": verdict,
                "nous_rule_id": rule_id,
                "nous_latency_us": latency_us,
                "ts_engine_gates": ts_gates,
                "ts_engine_blocked": ts_blocked,
                "consistent": consistent,
                "cost_breakdown": result.cost_breakdown.to_dict() if hasattr(result, 'cost_breakdown') and result.cost_breakdown else None,
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            results.append(record)

            if args.verbose and verdict != "allow":
                print(f"  #{i} {tool}: {verdict} (rule={rule_id}, {latency_us}μs)")

    total_time = time.perf_counter() - start_all

    # 统计汇总
    lats = sorted(stats["latencies_us"])
    p50 = lats[len(lats)//2] if lats else 0
    p95 = lats[int(len(lats)*0.95)] if lats else 0
    p99 = lats[int(len(lats)*0.99)] if lats else 0

    inconsistent = sum(1 for r in results if not r["consistent"])
    consistency_rate = ((len(results) - inconsistent) / len(results) * 100) if results else 0

    print("=" * 60)
    print(f"📊 Nous Replay 报告")
    print("=" * 60)
    print(f"  总调用数:       {stats['total']}")
    print(f"  总耗时:         {total_time:.2f}s ({stats['total']/total_time:.0f} calls/s)")
    print()
    print(f"  Verdict 分布:")
    for v in ["allow", "block", "confirm", "warn", "rewrite", "error"]:
        if stats.get(v, 0) > 0:
            pct = stats[v] / stats["total"] * 100
            print(f"    {v:12s}: {stats[v]:5d} ({pct:.1f}%)")
    print()
    print(f"  延迟 (μs):      P50={p50}  P95={p95}  P99={p99}")
    print()
    print(f"  与 TS engine 一致率: {consistency_rate:.1f}% ({inconsistent} 不一致)")
    print()

    if stats["gates_fired"]:
        print(f"  触发的规则:")
        for rule, count in sorted(stats["gates_fired"].items(), key=lambda x: -x[1]):
            print(f"    {rule}: {count} 次")
        print()

    # Top 10 工具
    print(f"  Top 10 工具:")
    sorted_tools = sorted(stats["by_tool"].items(), key=lambda x: -x[1]["total"])[:10]
    for tool, s in sorted_tools:
        non_allow = s["total"] - s.get("allow", 0)
        print(f"    {tool:25s}: {s['total']:4d} calls, {non_allow} gated")

    print()
    print(f"  结果写入: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
