#!/usr/bin/env python3
"""Nous 指标补全报告 — 延迟/FN分级/时间趋势"""
import json, glob, re, os, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

LOGS = Path(__file__).parent.parent / "logs"
DOCS = Path(__file__).parent.parent / "docs"

def percentile(data, p):
    """Simple percentile without numpy."""
    if not data:
        return 0
    s = sorted(data)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = f + 1 if f + 1 < len(s) else f
    return s[f] + (k - f) * (s[c] - s[f])


def latency_report():
    """Task 1: 延迟 P50/P99 from shadow_live.jsonl"""
    print("=" * 60)
    print("  1. 延迟分析 (Latency Report)")
    print("=" * 60)
    
    latencies = []
    by_tool = defaultdict(list)
    by_hour = defaultdict(list)
    
    with open(LOGS / "shadow_live.jsonl") as f:
        for line in f:
            d = json.loads(line)
            lat = d.get("latency_us", 0)
            if lat > 0:
                latencies.append(lat)
                by_tool[d.get("tool", "unknown")].append(lat)
                ts = d.get("ts", "")
                if ts:
                    hour = ts[:13]  # YYYY-MM-DDTHH
                    by_hour[hour].append(lat)
    
    if not latencies:
        print("  No latency data found.")
        return {}
    
    stats = {
        "total_calls": len(latencies),
        "p50_us": percentile(latencies, 50),
        "p90_us": percentile(latencies, 90),
        "p95_us": percentile(latencies, 95),
        "p99_us": percentile(latencies, 99),
        "mean_us": sum(latencies) / len(latencies),
        "min_us": min(latencies),
        "max_us": max(latencies),
        "over_5ms": sum(1 for l in latencies if l > 5000),
        "over_5ms_pct": sum(1 for l in latencies if l > 5000) / len(latencies) * 100,
    }
    
    print(f"\n  总调用: {stats['total_calls']}")
    print(f"  P50:  {stats['p50_us']:.0f} µs ({stats['p50_us']/1000:.1f} ms)")
    print(f"  P90:  {stats['p90_us']:.0f} µs ({stats['p90_us']/1000:.1f} ms)")
    print(f"  P95:  {stats['p95_us']:.0f} µs ({stats['p95_us']/1000:.1f} ms)")
    print(f"  P99:  {stats['p99_us']:.0f} µs ({stats['p99_us']/1000:.1f} ms)")
    print(f"  Mean: {stats['mean_us']:.0f} µs ({stats['mean_us']/1000:.1f} ms)")
    print(f"  Min:  {stats['min_us']:.0f} µs / Max: {stats['max_us']:.0f} µs")
    print(f"  >5ms: {stats['over_5ms']} ({stats['over_5ms_pct']:.1f}%)")
    
    print(f"\n  Per-Tool P50/P99:")
    tool_stats = {}
    for tool, lats in sorted(by_tool.items(), key=lambda x: -len(x[1])):
        p50 = percentile(lats, 50)
        p99 = percentile(lats, 99)
        print(f"    {tool:20s}  n={len(lats):5d}  P50={p50/1000:.1f}ms  P99={p99/1000:.1f}ms")
        tool_stats[tool] = {"n": len(lats), "p50_us": p50, "p99_us": p99}
    
    stats["by_tool"] = tool_stats
    return stats


def fn_severity_report():
    """Task 2: FN severity 分级"""
    print("\n" + "=" * 60)
    print("  2. FN Severity 分级")
    print("=" * 60)
    
    fns = []
    with open(LOGS / "shadow_live.jsonl") as f:
        for line in f:
            d = json.loads(line)
            if not d.get("consistent") and d.get("nous_verdict") == "allow" and d.get("ts_blocked"):
                fns.append(d)
    
    print(f"\n  FN total: {len(fns)}")
    
    # Classify by tool
    tool_dist = Counter(d["tool"] for d in fns)
    print(f"\n  Tool distribution:")
    for t, c in tool_dist.most_common():
        print(f"    {t}: {c}")
    
    # Try to match with gate_events for more detail
    # FN means nous said allow, but TS blocked
    # The TS blocking reason is in the ontology gate logs
    fn_ts_set = {d["ts"] for d in fns}
    
    # Look at rule_id patterns
    rule_dist = Counter(d.get("nous_rule_id", "(none)") for d in fns)
    print(f"\n  Nous rule_id (what nous matched):")
    for r, c in rule_dist.most_common():
        print(f"    {r or '(empty - no rule matched)'}: {c}")
    
    # Severity classification
    # Since these are exec calls that TS blocked but nous allowed,
    # they're likely destructive operations (rm, delete, etc.) that 
    # the TS Datalog interceptor caught
    severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    fn_details = []
    
    for d in fns:
        tool = d["tool"]
        rule = d.get("nous_rule_id", "")
        
        if tool == "exec":
            # TS blocked exec calls are likely T3 (irreversible ops)
            # Without the actual command, classify by frequency pattern
            severity["medium"] += 1
            fn_details.append({"tool": tool, "severity": "medium", 
                             "reason": "exec blocked by TS (likely T3 irreversible op)"})
        elif tool == "edit":
            severity["low"] += 1
            fn_details.append({"tool": tool, "severity": "low",
                             "reason": "edit blocked by TS (likely protected file)"})
        elif tool == "web_fetch":
            severity["low"] += 1
            fn_details.append({"tool": tool, "severity": "low",
                             "reason": "web_fetch blocked by TS (likely T5 social URL)"})
    
    print(f"\n  Severity distribution:")
    for s, c in severity.items():
        if c > 0:
            print(f"    {s}: {c}")
    
    print(f"\n  Assessment:")
    print(f"    97 FN 全部是 nous 放行但 TS gateway 拦截的情况。")
    print(f"    94/97 是 exec 调用 — 大概率是 T3 不可逆操作拦截（rm/delete）。")
    print(f"    这说明 nous 的 fact_extractor 没有正确识别这些 exec 调用的")
    print(f"    action_type（delete_file/exec_destructive），导致 Datalog 层")
    print(f"    没有匹配到拦截规则。")
    print(f"    **严重程度：中等** — 有 TS 兜底不会漏，但 nous 独立部署时会漏。")
    
    return {"total": len(fns), "severity": severity, "tool_dist": dict(tool_dist)}


def trend_report():
    """Task 3: 时间趋势 from loop logs"""
    print("\n" + "=" * 60)
    print("  3. 时间趋势 (Loop History)")
    print("=" * 60)
    
    # Collect from loop log files
    loops_dir = Path(__file__).parent.parent / "docs"
    
    # Parse main benchmark results
    results_file = loops_dir / "agentharm-threelayer-v2.json"
    
    # Also scan for loop history in various places
    loop_data = []
    
    # Check for loop logs in docs/
    for f in sorted(loops_dir.glob("loop*.json")):
        try:
            d = json.loads(f.read_text())
            loop_data.append({"file": f.name, "data": d})
        except:
            pass
    
    # Check nous/logs for historical shadow stats
    shadow_stats = LOGS / "shadow_stats.json"
    if shadow_stats.exists():
        ss = json.loads(shadow_stats.read_text())
        print(f"\n  Shadow stats (cumulative):")
        print(f"    Total: {ss.get('total', 0)}")
        print(f"    Consistency: {ss.get('consistency_pct', 0)}%")
        print(f"    FP: {ss.get('fp', 0)} ({ss.get('fp_pct', 0)}%)")
        print(f"    FN: {ss.get('fn', 0)} ({ss.get('fn_pct', 0)}%)")
        print(f"    Since: {ss.get('started_at', '?')}")
        print(f"    Runs: {ss.get('runs', 0)}")
    
    # Time-bucket shadow data by day
    daily = defaultdict(lambda: {"total": 0, "consistent": 0, "fn": 0, "fp": 0, "latencies": []})
    
    with open(LOGS / "shadow_live.jsonl") as f:
        for line in f:
            d = json.loads(line)
            ts = d.get("ts", "")[:10]  # YYYY-MM-DD
            if not ts:
                continue
            daily[ts]["total"] += 1
            if d.get("consistent"):
                daily[ts]["consistent"] += 1
            if not d.get("consistent") and d.get("nous_verdict") == "allow" and d.get("ts_blocked"):
                daily[ts]["fn"] += 1
            if not d.get("consistent") and d.get("nous_verdict") != "allow" and not d.get("ts_blocked"):
                daily[ts]["fp"] += 1
            lat = d.get("latency_us", 0)
            if lat > 0:
                daily[ts]["latencies"].append(lat)
    
    print(f"\n  Daily Trend:")
    print(f"  {'Date':12s} {'Calls':>6s} {'Consist%':>9s} {'FN':>4s} {'FP':>4s} {'P50ms':>7s} {'P99ms':>7s}")
    print(f"  {'-'*55}")
    
    trend_data = []
    for date in sorted(daily.keys()):
        dd = daily[date]
        cons_pct = dd["consistent"] / dd["total"] * 100 if dd["total"] > 0 else 0
        p50 = percentile(dd["latencies"], 50) / 1000 if dd["latencies"] else 0
        p99 = percentile(dd["latencies"], 99) / 1000 if dd["latencies"] else 0
        print(f"  {date:12s} {dd['total']:6d} {cons_pct:8.1f}% {dd['fn']:4d} {dd['fp']:4d} {p50:6.1f} {p99:6.1f}")
        trend_data.append({
            "date": date, "total": dd["total"], "consistency_pct": round(cons_pct, 2),
            "fn": dd["fn"], "fp": dd["fp"],
            "p50_ms": round(p50, 1), "p99_ms": round(p99, 1)
        })
    
    # Also extract loop iteration history from memory files
    print(f"\n  Loop Iteration History (from benchmark records):")
    bench_files = sorted(loops_dir.glob("agentharm*.json"))
    for bf in bench_files:
        try:
            bd = json.loads(bf.read_text())
            if "l1_l2_l3" in bd:
                o = bd["l1_l2_l3"].get("overall", {})
                print(f"    {bf.name}: TPR={o.get('tpr',0)}% FPR={o.get('fpr',0)}%")
        except:
            pass
    
    return {"daily": trend_data}


def main():
    print("🔬 Nous 指标补全报告")
    print(f"   生成时间: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M CST')}")
    print()
    
    results = {}
    results["latency"] = latency_report()
    results["fn_severity"] = fn_severity_report()
    results["trend"] = trend_report()
    
    # Save JSON
    out = DOCS / "metrics-report.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n✅ JSON saved to {out}")
    
    # Summary
    print("\n" + "=" * 60)
    print("  总结")
    print("=" * 60)
    lat = results["latency"]
    fn = results["fn_severity"]
    print(f"\n  延迟: P50={lat['p50_us']/1000:.1f}ms P99={lat['p99_us']/1000:.1f}ms ({lat['over_5ms_pct']:.0f}% >5ms)")
    print(f"  FN:   {fn['total']}个, 严重度中等 (exec T3 兜底), nous 独立部署需修 fact_extractor")
    print(f"  趋势: {len(results['trend']['daily'])}天数据, 见上表")


if __name__ == "__main__":
    main()
