"""
Demo CLI — 单标的决策闭环

用法：
  # 用内置示例跑（贵州茅台 600519.SH，预填好的 card）
  python3 -m invest.decision_cockpit.demo

  # 跳过魔鬼代言人（v7 允许 PM 可选）
  python3 -m invest.decision_cockpit.demo --skip-devil

  # 从 JSON 文件读 card
  python3 -m invest.decision_cockpit.demo --card-json my_card.json

输出：
  - 控制台打印 Markdown 报告
  - invest/decision_cockpit/records/<ticker>_<timestamp>.json
  - invest/decision_cockpit/records/<ticker>_<timestamp>.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 保证 `python3 -m invest.decision_cockpit.demo` 和 `python3 demo.py` 都能工作
_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[2]))  # nous/

from invest.decision_cockpit import Cockpit, DecisionCard


# ═══════════════════════════════════════════════════════════════════
# 内置示例 — 贵州茅台 600519.SH
# ═══════════════════════════════════════════════════════════════════

EXAMPLE_CARD = DecisionCard(
    ticker="600519.SH",
    pm_name="张经理",
    # --- 客观（系统 / 数据接口填） ---
    company_snapshot={
        "name": "贵州茅台", "industry": "白酒", "market_cap_yi": 21000,
        "listed_since": "2001-08",
    },
    financials={
        "roe_ttm": 0.332, "debt_to_asset": 0.19,
        "gross_margin": 0.92, "ocf_yoy": 0.08,
    },
    valuation={
        "pe_ttm": 22.4, "pe_percentile_5y": 0.18, "pb": 8.1,
        "dividend_yield": 0.036,
    },
    # --- 主观（PM 填） ---
    business_model=(
        "核心产品飞天茅台批价稳定在 2400 元以上，直销渠道贡献 60%+ 毛利。"
        "i茅台 APP 的直销占比持续提升是未来利润杠杆。"
    ),
    moat=(
        "品牌垄断地位在中国白酒高端价格带无人可替代；赤水河核心产区的"
        "地理稀缺性 + 长周期基酒储备（5 年以上）构成双重供给护城河。"
    ),
    competitive_landscape=(
        "高端白酒格局茅五泸三分，茅台稳固第一，近期 1500 元+ 价格带被"
        "五粮液普五追赶但仍有 800 元溢价。低度化趋势可能分流年轻用户但"
        "3-5 年内不构成威胁。"
    ),
    management="丁董任期稳定，经销体系改革推进；管理层激励与渠道利益仍需观察",
    catalysts=(
        "Q2 批价如果站稳 2600；i茅台直销占比过 65%；第三季度春节预付款"
        "提货情况领先去年 10%+"
    ),
    risks=[
        "宏观消费低迷导致高端白酒提价空间受限",
        "反腐 / 限酒令等监管冲击高端白酒礼品需求",
        "批价大幅波动（2300 以下）触发渠道信心崩塌",
        "大股东减持或国资运作导致治理不确定性",
    ],
    technicals="近 3 个月横盘箱体 1650-1780，量能温和；20/60 日均线粘合，未出现破位",
    policy_env="白酒消费税改革方向仍未明确，近期无大政策面冲击",
    thesis=(
        "在当前 22 倍 PE（历史 18 分位）的估值下，公司 ROE 33% 且现金流充沛，"
        "即使未来 3 年净利润复合增速回落到 10%，DCF 仍给出 15% 左右的年化回报"
        "空间；高端白酒格局稳定叠加 i茅台 直销红利是盈利弹性的核心支撑；"
        "下行保护来自极高的 ROIC 和分红率。3-5 年持有胜率较高。"
    ),
    exit_condition="批价跌破 2300 / PE 超过 40 / ROE 连续 2 年 < 25%",
)


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def load_card_from_json(path: Path) -> DecisionCard:
    obj = json.loads(path.read_text(encoding="utf-8"))
    return DecisionCard(**obj)


def main():
    ap = argparse.ArgumentParser(description="Decision Cockpit demo — single ticker")
    ap.add_argument("--card-json", type=Path, default=None,
                    help="从文件读 card（默认用内置贵州茅台示例）")
    ap.add_argument("--skip-devil", action="store_true",
                    help="跳过魔鬼代言人（v7 允许 PM 选择）")
    ap.add_argument("--no-persist", action="store_true",
                    help="不落盘到 records/")
    ap.add_argument("--md-only", action="store_true",
                    help="只打印 markdown，不打印 JSON 摘要")
    args = ap.parse_args()

    card = load_card_from_json(args.card_json) if args.card_json else EXAMPLE_CARD

    print("=" * 78)
    print(f"决策驾驶舱  ·  {card.ticker}  ·  {card.pm_name}")
    print("=" * 78)
    print(f"\n[1] 校验卡片完整性…")
    comp = card.completeness_report()
    print(f"    客观字段填充率: {comp['objective_filled_ratio']:.0%}")
    print(f"    主观字段问题数: {len(comp['subjective_issues'])}")

    print(f"\n[2] {'跳过魔鬼代言人' if args.skip_devil else '运行魔鬼代言人 (LLM stub fallback)'}…")
    print(f"\n[3] 运行多视角陪审团（价值 / 动量 / 事件催化）…")

    cockpit = Cockpit()
    record = cockpit.run(card, skip_devil=args.skip_devil, persist=not args.no_persist)

    print("\n" + "=" * 78)
    print(record.to_markdown())

    if not args.no_persist:
        print("\n" + "=" * 78)
        print(f"💾 已落盘 JSON + Markdown 到 {cockpit.records_dir}")

    # 一个简短的 JSON 概览（便于管道对接）
    if not args.md_only:
        print("\n" + "=" * 78)
        print("JSON 概览:")
        summary = {
            "ticker": record.card.ticker,
            "pm_name": record.card.pm_name,
            "completeness_is_complete": record.completeness["is_complete"],
            "devil_skipped": record.devil.skipped if record.devil else None,
            "devil_n_points": len(record.devil.points) if record.devil else 0,
            "jury_signal": record.jury.signal_label if record.jury else None,
            "jury_scores": record.jury.scores_by_perspective if record.jury else {},
            "jury_disagreement_range": record.jury.disagreement_range if record.jury else 0,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
