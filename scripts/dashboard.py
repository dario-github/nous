"""Nous — M4.2 指标仪表盘 (dashboard.py)

聚合 30 天 DB 指标，终端表格展示 + --json 输出。

指标：
    - gate P99/P50 延迟（来自 decision_log.latency_us）
    - 规则覆盖率（触发过的规则 / 全部规则）
    - entity count
    - decision_log count（按 verdict 分组）
    - fp/fn 率（based on outcome）
    - 提议质量（approve/reject/pending 比例）

用法：
    python dashboard.py [--db PATH] [--days 30] [--json]
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

# 加入 src/ 以导入 nous 包
_SRC = Path(__file__).parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from nous.db import NousDB


# ── 聚合逻辑 ──────────────────────────────────────────────────────────────


def aggregate_metrics(db: NousDB, days: int = 30) -> dict:
    """
    从 DB 聚合 30 天指标，返回 dict。

    Args:
        db:   NousDB 实例
        days: 时间窗口（默认 30 天）

    Returns:
        metrics dict，包含所有仪表盘指标
    """
    since = time.time() - days * 86400

    # ── 1. gate 延迟（P50 / P99）────────────────────────────────────────
    latency_rows = db._query_with_params(
        "?[latency_us] := *decision_log{ts, session_key, latency_us}, ts >= $since",
        {"since": since},
    )
    latencies = sorted(row.get("latency_us", 0) for row in latency_rows)
    n = len(latencies)

    if n == 0:
        p50_ms = 0.0
        p99_ms = 0.0
    else:
        p50_idx = max(0, int(n * 0.50) - 1)
        p99_idx = max(0, int(n * 0.99) - 1)
        p50_ms = round(latencies[p50_idx] / 1000.0, 3)   # μs → ms
        p99_ms = round(latencies[p99_idx] / 1000.0, 3)

    # ── 2. decision_log 按 verdict 分组 ───────────────────────────────
    verdict_rows = db._query_with_params(
        "?[outcome, count(ts)] := *decision_log{ts, session_key, outcome}, ts >= $since",
        {"since": since},
    )
    verdict_counts: dict[str, int] = {}
    for row in verdict_rows:
        verdict = row.get("outcome", "unknown") or "unknown"
        # Cozo count 列名为 "count(ts)"
        cnt_val = row.get("count(ts)", 0)
        try:
            cnt = int(cnt_val)
        except (TypeError, ValueError):
            cnt = 0
        verdict_counts[verdict] = cnt

    total_decisions = sum(verdict_counts.values())

    # ── 3. fp/fn 率 ──────────────────────────────────────────────────
    fp_count = verdict_counts.get("fp", 0)
    fn_count = verdict_counts.get("fn", 0)
    fp_rate = round(fp_count / max(total_decisions, 1) * 100, 2)
    fn_rate = round(fn_count / max(total_decisions, 1) * 100, 2)

    # ── 4. 规则覆盖率 ─────────────────────────────────────────────────
    # 已触发过的规则（从 decision_log.gates 聚合）
    all_gates_rows = db._query_with_params(
        "?[gates] := *decision_log{ts, session_key, gates}, ts >= $since",
        {"since": since},
    )
    triggered_rules: set[str] = set()
    for row in all_gates_rows:
        gates = row.get("gates", [])
        if isinstance(gates, list):
            triggered_rules.update(g for g in gates if g)
        elif isinstance(gates, str):
            try:
                lst = json.loads(gates)
                if isinstance(lst, list):
                    triggered_rules.update(g for g in lst if g)
            except Exception:
                pass

    # 全部规则数
    all_constraint_rows = db.query(
        "?[id] := *constraint{id, enabled}, enabled = true"
    )
    total_rules = len(all_constraint_rows)
    triggered_count = len(triggered_rules)
    rule_coverage_pct = round(
        triggered_count / max(total_rules, 1) * 100, 1
    )

    # ── 5. entity count ───────────────────────────────────────────────
    entity_count = db.count_entities()
    relation_count = db.count_relations()

    # ── 6. 提议质量 ───────────────────────────────────────────────────
    proposal_rows = db.query(
        "?[id, status] := *proposal{id, status}"
    )
    proposal_counts: dict[str, int] = {}
    for row in proposal_rows:
        s = row.get("status", "unknown") or "unknown"
        proposal_counts[s] = proposal_counts.get(s, 0) + 1

    total_proposals = sum(proposal_counts.values())
    approved = proposal_counts.get("approved", 0)
    rejected = proposal_counts.get("rejected", 0)
    pending = proposal_counts.get("pending", 0)
    approve_rate = round(approved / max(total_proposals, 1) * 100, 1)
    reject_rate = round(rejected / max(total_proposals, 1) * 100, 1)

    return {
        "window_days": days,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "latency": {
            "p50_ms": p50_ms,
            "p99_ms": p99_ms,
            "sample_count": n,
        },
        "decisions": {
            "total": total_decisions,
            "by_verdict": verdict_counts,
            "fp_rate_pct": fp_rate,
            "fn_rate_pct": fn_rate,
        },
        "rules": {
            "total_enabled": total_rules,
            "triggered": triggered_count,
            "coverage_pct": rule_coverage_pct,
            "triggered_ids": sorted(triggered_rules),
        },
        "knowledge_graph": {
            "entity_count": entity_count,
            "relation_count": relation_count,
        },
        "proposals": {
            "total": total_proposals,
            "approved": approved,
            "rejected": rejected,
            "pending": pending,
            "approve_rate_pct": approve_rate,
            "reject_rate_pct": reject_rate,
        },
    }


# ── 终端表格输出 ──────────────────────────────────────────────────────────

_SEP = "─" * 60


def _row(label: str, value: str, width: int = 38) -> str:
    return f"  {label:<{width}} {value}"


def print_dashboard(metrics: dict) -> None:
    """将 metrics dict 渲染为终端可读的对齐表格"""
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║           Nous 运行指标仪表盘                            ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  生成时间: {metrics['generated_at']}")
    print(f"  统计窗口: 最近 {metrics['window_days']} 天")
    print()

    # 延迟
    lat = metrics["latency"]
    print(f"  {'── Gate 延迟 ──':}")
    print(_row("P50 延迟:", f"{lat['p50_ms']} ms"))
    print(_row("P99 延迟:", f"{lat['p99_ms']} ms  {'✅' if lat['p99_ms'] < 5 else '⚠️ >5ms'}"))
    print(_row("采样数:", str(lat["sample_count"])))
    print()

    # 决策日志
    dec = metrics["decisions"]
    print(f"  {'── 决策日志 ──':}")
    print(_row("总决策数:", str(dec["total"])))
    for verdict, cnt in sorted(dec["by_verdict"].items()):
        pct = round(cnt / max(dec["total"], 1) * 100, 1)
        print(_row(f"  {verdict}:", f"{cnt} ({pct}%)"))
    print(_row("FP 率:", f"{dec['fp_rate_pct']}%  {'✅' if dec['fp_rate_pct'] < 2 else '⚠️ >2%'}"))
    print(_row("FN 率:", f"{dec['fn_rate_pct']}%  {'✅' if dec['fn_rate_pct'] == 0 else '🚨 >0%'}"))
    print()

    # 规则覆盖率
    rules = metrics["rules"]
    print(f"  {'── 规则覆盖率 ──':}")
    print(_row("启用规则数:", str(rules["total_enabled"])))
    print(_row("触发规则数:", str(rules["triggered"])))
    print(_row("覆盖率:", f"{rules['coverage_pct']}%"))
    if rules["triggered_ids"]:
        print(_row("触发规则:", ", ".join(rules["triggered_ids"][:5])
              + ("..." if len(rules["triggered_ids"]) > 5 else "")))
    print()

    # 知识图谱
    kg = metrics["knowledge_graph"]
    print(f"  {'── 知识图谱 ──':}")
    print(_row("Entity 数量:", str(kg["entity_count"])))
    print(_row("Relation 数量:", str(kg["relation_count"])))
    print()

    # 提议质量
    prop = metrics["proposals"]
    print(f"  {'── 自治理提议 ──':}")
    print(_row("总提议数:", str(prop["total"])))
    print(_row("  approved:", f"{prop['approved']} ({prop['approve_rate_pct']}%)"))
    print(_row("  rejected:", f"{prop['rejected']} ({prop['reject_rate_pct']}%)"))
    print(_row("  pending:", str(prop["pending"])))
    print()
    print(_SEP)
    print()


# ── CLI ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Nous 指标仪表盘")
    parser.add_argument(
        "--db",
        type=str,
        default=str(Path(__file__).parent.parent / "nous.db"),
        help="NousDB 路径（默认：nous/nous.db）",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="统计窗口（天数，默认 30）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )
    parser.add_argument(
        "--memory",
        action="store_true",
        help="使用内存 DB（用于测试）",
    )

    args = parser.parse_args()

    db_path = ":memory:" if args.memory else args.db
    db = NousDB(db_path)
    try:
        metrics = aggregate_metrics(db, days=args.days)
        if args.json:
            print(json.dumps(metrics, ensure_ascii=False, indent=2))
        else:
            print_dashboard(metrics)
    finally:
        db.close()


if __name__ == "__main__":
    main()
