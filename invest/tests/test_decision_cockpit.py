"""
Nous Invest — decision_cockpit 端到端 smoke tests

不测 LLM 能力（用 stub），只确保：
  - Card schema 的完整性检查正确
  - Cockpit.run() 闭环能跑不崩
  - skip_devil 语义正确
  - 分歧极差 / signal label 逻辑正确
  - JSON + Markdown 输出格式正常
"""
import sys
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from invest.decision_cockpit import DecisionCard, Cockpit, DecisionRecord
from invest.decision_cockpit.jury import Jury, JurorVote


# ═══════════════════════════════════════════════════════════════════
# Card
# ═══════════════════════════════════════════════════════════════════

def _minimal_full_card() -> DecisionCard:
    """字段填充率 100%，且主观字段全达标（留宽裕冗余字数）。"""
    return DecisionCard(
        ticker="600000.SH", pm_name="tester",
        company_snapshot={"name": "x"},
        financials={"roe": 0.1},
        valuation={"pe": 15.0},
        business_model="商业模式描述用来让字数满足最小门槛的 20 字冗余。",
        moat=("护城河描述长度超过最小门槛 30 字；假设这是真实内容，"
              "包括品牌、规模、用户粘性、技术壁垒四大维度。"),
        competitive_landscape=("竞争格局描述超过最小门槛 30 字；举例龙一龙二龙三"
                               "市占率稳定，CR3 超过 60%，短期内格局稳固。"),
        management="管理层描述，超过最小门槛十五字。",
        catalysts="催化剂描述超过最小门槛 20 字，包含两个近期可见事件列举。",
        risks=["风险 1", "风险 2"],
        technicals="技术面观察超过最小门槛十五字。",
        policy_env="政策环境描述超过最小门槛十五字。",
        thesis=(
            "这是一段不少于一百字的投资假设和结论，覆盖估值、增长、护城河、"
            "下行保护四个维度的综合判断，并给出 3-5 年持有期的年化收益预期"
            "与关键假设的可证伪条件，并说明如果这些条件被证伪该如何应对、"
            "如何止损、如何在组合层面重新分配仓位以保护整体账户风险。"
        ),
        exit_condition="价格跌破关键位 / 或基本面指标恶化阈值触发。",
    )


def test_card_completeness_full():
    card = _minimal_full_card()
    report = card.completeness_report()
    assert report["is_complete"] is True
    assert report["objective_filled_ratio"] == 1.0
    assert report["subjective_issues"] == []


def test_card_completeness_empty_fields():
    """空卡 → 应标记出所有 subjective 字段缺失。"""
    card = DecisionCard(ticker="600000.SH", pm_name="t")
    report = card.completeness_report()
    assert report["is_complete"] is False
    assert report["objective_filled_ratio"] == 0.0
    assert len(report["subjective_issues"]) >= 8  # 9 个主观 field + risks count


def test_card_completeness_short_thesis():
    """thesis 只有 50 字 → 应当命中长度不足。"""
    card = _minimal_full_card()
    card.thesis = "短 thesis，不足一百字。"
    report = card.completeness_report()
    assert report["is_complete"] is False
    assert any("thesis" in issue for issue in report["subjective_issues"])


# ═══════════════════════════════════════════════════════════════════
# Cockpit
# ═══════════════════════════════════════════════════════════════════

def test_cockpit_full_run_not_crashing(tmp_path):
    """端到端闭环：card → gate → devil → jury → record。"""
    card = _minimal_full_card()
    cockpit = Cockpit(records_dir=tmp_path)
    record = cockpit.run(card, skip_devil=False)

    assert isinstance(record, DecisionRecord)
    assert record.completeness["is_complete"] is True
    assert record.devil is not None
    assert record.devil.skipped is False
    assert len(record.devil.points) == 3  # 永远给 3 条（LLM 或 fallback）
    assert record.jury is not None
    assert len(record.jury.votes) == 3
    for v in record.jury.votes:
        assert v.perspective in ("value", "momentum", "catalyst")
        assert -3 <= v.score <= 3


def test_cockpit_skip_devil_records_skip_reason(tmp_path):
    card = _minimal_full_card()
    cockpit = Cockpit(records_dir=tmp_path)
    record = cockpit.run(card, skip_devil=True)

    assert record.devil is not None
    assert record.devil.skipped is True
    assert record.devil.skip_reason != ""


def test_cockpit_persistence_produces_json_and_md(tmp_path):
    card = _minimal_full_card()
    cockpit = Cockpit(records_dir=tmp_path)
    record = cockpit.run(card, persist=True)

    files = list(tmp_path.glob("*"))
    assert any(f.suffix == ".json" for f in files)
    assert any(f.suffix == ".md" for f in files)

    md = next(f for f in files if f.suffix == ".md").read_text(encoding="utf-8")
    assert card.ticker in md
    assert "决策档案" in md
    assert "陪审团" in md


def test_cockpit_markdown_has_all_12_dimensions(tmp_path):
    card = _minimal_full_card()
    record = Cockpit(records_dir=tmp_path).run(card, persist=False)
    md = record.to_markdown()
    # 12 + exit_condition 一共 13 段
    for header in ["公司概览", "商业模式", "护城河", "财务健康度", "估值水平",
                   "竞争格局", "管理层", "催化剂", "风险矩阵",
                   "技术面", "政策环境", "关键假设与结论", "退出条件"]:
        assert header in md, f"markdown 缺失维度: {header}"


# ═══════════════════════════════════════════════════════════════════
# Jury disagreement label
# ═══════════════════════════════════════════════════════════════════

def _mock_vote(perspective: str, score: int) -> JurorVote:
    return JurorVote(perspective=perspective, score=score, reasoning="test", concerns=[])


def test_jury_label_strong_bullish():
    j = Jury(disagreement_alert_threshold=4)
    assert j._label(n_bull=3, n_bear=0, rng=0) == "strong_bullish"


def test_jury_label_strong_bearish():
    j = Jury(disagreement_alert_threshold=4)
    assert j._label(n_bull=0, n_bear=3, rng=0) == "strong_bearish"


def test_jury_label_disagreement_flagged():
    """+2 / -2 / 0 的组合应触发 disagreement_flagged（rng=4）。"""
    j = Jury(disagreement_alert_threshold=4)
    assert j._label(n_bull=1, n_bear=1, rng=4) == "disagreement_flagged"


def test_jury_label_moderate_bullish():
    j = Jury(disagreement_alert_threshold=4)
    assert j._label(n_bull=2, n_bear=0, rng=2) == "moderate_bullish"


def test_jury_label_weak_pause():
    j = Jury(disagreement_alert_threshold=4)
    assert j._label(n_bull=1, n_bear=0, rng=2) == "weak_pause"


if __name__ == "__main__":
    import subprocess
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
