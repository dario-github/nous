"""Nous — M4.3 30 天报告生成器 (generate_report.py)

调用 dashboard.aggregate_metrics() 聚合数据，
生成 Markdown 报告到 nous/docs/monthly-report-YYYY-MM.md。

用法：
    python generate_report.py [--db PATH] [--days 30] [--output PATH] [--memory]
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 加入 src/
_SRC = Path(__file__).parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# 加入 scripts/（导入 dashboard）
_SCRIPTS = Path(__file__).parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from nous.db import NousDB
from dashboard import aggregate_metrics


# ── 报告模板渲染 ──────────────────────────────────────────────────────────


def render_report(metrics: dict, month: Optional[str] = None) -> str:
    """
    将 metrics dict 渲染为 Markdown 报告字符串。

    Args:
        metrics: aggregate_metrics() 返回的 dict
        month:   报告月份（YYYY-MM，默认当前月）

    Returns:
        完整 Markdown 字符串
    """
    if month is None:
        month = datetime.now(timezone.utc).strftime("%Y-%m")

    gen_at = metrics.get("generated_at", "unknown")
    days = metrics.get("window_days", 30)

    lat = metrics.get("latency", {})
    dec = metrics.get("decisions", {})
    rules = metrics.get("rules", {})
    kg = metrics.get("knowledge_graph", {})
    prop = metrics.get("proposals", {})

    total = dec.get("total", 0)
    by_verdict = dec.get("by_verdict", {})
    block_count = by_verdict.get("block", 0) + by_verdict.get("confirm", 0)
    block_rate = round(block_count / max(total, 1) * 100, 1)
    allow_count = by_verdict.get("allow", 0)
    p99 = lat.get("p99_ms", 0.0)
    p50 = lat.get("p50_ms", 0.0)

    # 规则效力表格
    triggered_ids = rules.get("triggered_ids", [])
    total_rules = rules.get("total_enabled", 0)
    coverage = rules.get("coverage_pct", 0.0)
    fp_rate = dec.get("fp_rate_pct", 0.0)
    fn_rate = dec.get("fn_rate_pct", 0.0)

    # 提议统计
    prop_total = prop.get("total", 0)
    prop_approved = prop.get("approved", 0)
    prop_rejected = prop.get("rejected", 0)
    prop_pending = prop.get("pending", 0)
    approve_rate = prop.get("approve_rate_pct", 0.0)

    # 知识图谱
    entity_count = kg.get("entity_count", 0)
    relation_count = kg.get("relation_count", 0)

    # ── 生成报告内容 ──────────────────────────────────────────────────
    lines = [
        f"# Nous 月度运行报告 — {month}",
        "",
        f"> 生成时间：{gen_at}  ",
        f"> 统计窗口：最近 {days} 天",
        "",
        "---",
        "",
        "## 1. 概览",
        "",
        f"| 指标 | 数值 | 目标 | 状态 |",
        f"|------|------|------|------|",
        f"| 总决策数 | {total} | — | — |",
        f"| 拦截率（block+confirm） | {block_rate}% | <15% | {'✅' if block_rate < 15 else '⚠️'} |",
        f"| gate P99 延迟 | {p99} ms | <5ms | {'✅' if p99 < 5 else '⚠️'} |",
        f"| gate P50 延迟 | {p50} ms | <2ms | {'✅' if p50 < 2 else '⚠️'} |",
        f"| FP 率 | {fp_rate}% | <2% | {'✅' if fp_rate < 2 else '⚠️'} |",
        f"| FN 率 | {fn_rate}% | =0% | {'✅' if fn_rate == 0 else '🚨'} |",
        "",
        "### 决策分布",
        "",
    ]

    # 决策分布表
    if by_verdict:
        lines += [
            "| Verdict | 数量 | 占比 |",
            "|---------|------|------|",
        ]
        for v, cnt in sorted(by_verdict.items(), key=lambda x: -x[1]):
            pct = round(cnt / max(total, 1) * 100, 1)
            lines.append(f"| {v} | {cnt} | {pct}% |")
    else:
        lines.append("_暂无决策数据_")

    lines += [
        "",
        "---",
        "",
        "## 2. 规则效力",
        "",
        f"- 启用规则总数：{total_rules}",
        f"- 触发规则数：{len(triggered_ids)}",
        f"- 规则覆盖率：{coverage}%",
        "",
    ]

    if triggered_ids:
        lines += [
            "| 规则 ID | 状态 | FP 率参考 |",
            "|---------|------|-----------|",
        ]
        for rid in triggered_ids:
            lines.append(f"| {rid} | ✅ 已触发 | 见决策日志 |")
    else:
        lines.append("_窗口内无规则触发_")

    lines += [
        "",
        "> **注**：每条规则的详细 FP 率需结合 decision_log 的 outcome 回填数据分析。",
        "",
        "---",
        "",
        "## 3. 自治理活动",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 总提议数 | {prop_total} |",
        f"| 批准 | {prop_approved} ({approve_rate}%) |",
        f"| 拒绝 | {prop_rejected} ({prop.get('reject_rate_pct', 0.0)}%) |",
        f"| 待审核 | {prop_pending} |",
        "",
    ]

    if prop_total == 0:
        lines.append("_本月无自治理提议。系统运行稳定，无需规则调整。_")
    elif prop_pending > 0:
        lines.append(f"⚠️  **{prop_pending} 条提议待审核**，请运行 `nous review list` 处理。")
    else:
        lines.append("✅ 所有提议已处理。")

    lines += [
        "",
        "---",
        "",
        "## 4. 知识图谱增长",
        "",
        f"| 指标 | 当前值 |",
        f"|------|--------|",
        f"| Entity 数量 | {entity_count} |",
        f"| Relation 数量 | {relation_count} |",
        "",
        "> **目标**：Entity ≥200（M2 验收标准）。",
        f"> **当前状态**：{'✅ 达标' if entity_count >= 200 else f'⚠️ 未达标（差 {200 - entity_count} 个）'}",
        "",
        "---",
        "",
        "## 5. 下月建议",
        "",
    ]

    # 动态生成建议
    suggestions = []

    if fn_rate > 0:
        suggestions.append(
            f"🚨 **FN 率 {fn_rate}% > 0%**：存在安全遗漏，需立即分析 fn 记录并补充规则。"
        )
    if fp_rate >= 2:
        suggestions.append(
            f"⚠️ **FP 率 {fp_rate}% ≥ 2%**：过度拦截影响可用性，建议审查 T3/T5 规则范围。"
        )
    if p99 >= 5:
        suggestions.append(
            f"⚠️ **P99 {p99}ms ≥ 5ms**：延迟超标，建议检查约束数量和 DB 负载。"
        )
    if entity_count < 200:
        suggestions.append(
            f"📚 **Entity {entity_count} < 200**：知识图谱尚未达到 M2 目标，继续运行 `nous-daily-sync`。"
        )
    if prop_pending > 0:
        suggestions.append(
            f"📋 **{prop_pending} 条提议待审核**：运行 `nous review list` 并处理待审提议。"
        )
    if coverage < 77:
        suggestions.append(
            f"📊 **规则覆盖率 {coverage}% < 77%**：部分规则从未触发，考虑 TTL 衰减或规则删除。"
        )

    if not suggestions:
        suggestions.append("✅ 所有指标达标，继续保持当前运行状态。下月可考虑扩充知识图谱规模。")

    for s in suggestions:
        lines.append(f"- {s}")

    lines += [
        "",
        "---",
        "",
        f"*此报告由 Nous generate_report.py 自动生成 · {gen_at}*",
        "",
    ]

    return "\n".join(lines)


# ── 写入文件 ───────────────────────────────────────────────────────────────


def generate_report(
    db: NousDB,
    days: int = 30,
    output_path: Optional[Path] = None,
    month: Optional[str] = None,
) -> tuple[str, Path]:
    """
    生成报告并写入文件。

    Args:
        db:          NousDB 实例
        days:        统计窗口天数
        output_path: 输出路径（默认 nous/docs/monthly-report-YYYY-MM.md）
        month:       报告月份标识（默认当前月）

    Returns:
        (report_content, output_path)
    """
    if month is None:
        month = datetime.now(timezone.utc).strftime("%Y-%m")

    if output_path is None:
        docs_dir = Path(__file__).parent.parent / "docs"
        docs_dir.mkdir(exist_ok=True)
        output_path = docs_dir / f"monthly-report-{month}.md"

    metrics = aggregate_metrics(db, days=days)
    content = render_report(metrics, month=month)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    return content, output_path


# ── CLI ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Nous 30 天报告生成器")
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
        "--output",
        type=Path,
        default=None,
        help="报告输出路径（默认：nous/docs/monthly-report-YYYY-MM.md）",
    )
    parser.add_argument(
        "--month",
        type=str,
        default=None,
        help="报告月份（YYYY-MM，默认当前月）",
    )
    parser.add_argument(
        "--memory",
        action="store_true",
        help="使用内存 DB（测试用）",
    )

    args = parser.parse_args()

    db_path = ":memory:" if args.memory else args.db
    db = NousDB(db_path)
    try:
        content, out_path = generate_report(
            db,
            days=args.days,
            output_path=args.output,
            month=args.month,
        )
        print(f"[Nous] ✅ 报告已生成: {out_path}")
        print(f"[Nous] 报告大小: {len(content)} 字符")
    finally:
        db.close()


if __name__ == "__main__":
    main()
