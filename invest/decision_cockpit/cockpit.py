"""
Cockpit — 决策驾驶舱主编排器

v7 §二 四能力的"单 ticker 闭环"：
  1. PM 填的决策卡进来
  2. 校验 schema 完整性（此版做内嵌规则，未来可接 nous.gate 热加载 YAML）
  3. [可选] 魔鬼代言人 — 记录不打扰
  4. 多视角陪审团 — 显式分歧
  5. 打包成 DecisionRecord，落盘为 JSON + Markdown

红线遵守：
- card 是 PM 填的 → 进来什么样，我们保留什么样（不替 PM 修改主观字段）
- 魔鬼代言人可选（skip_devil=True 时跳过，记原因）
- 不替 PM 投票（jury 显式展示三路，不合成"综合建议"）
- 数据本地（records 落到用户指定目录，默认 invest/decision_cockpit/records/）
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from .card import DecisionCard, DIMENSIONS, CardField
from .devil import DevilAdvocate, DevilCritique, LLMProvider
from .jury import Jury, JuryVerdict


# ═══════════════════════════════════════════════════════════════════
# Record
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DecisionRecord:
    """一次决策的完整档案。合规/审计用。"""

    card: DecisionCard
    completeness: Dict
    devil: Optional[DevilCritique] = None
    jury: Optional[JuryVerdict] = None
    gate_verdict: Optional[Dict] = None   # 预留：接 nous.gate 的位置
    meta: Dict = field(default_factory=lambda: {"version": "v1.0"})

    # ─ 序列化 ─
    def to_dict(self) -> dict:
        return {
            "card": self.card.to_dict(),
            "completeness": self.completeness,
            "devil": self.devil.to_dict() if self.devil else None,
            "jury": self.jury.to_dict() if self.jury else None,
            "gate_verdict": self.gate_verdict,
            "meta": self.meta,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, default=str)

    def to_markdown(self) -> str:
        """给孙总看的版本。"""
        lines: list[str] = []
        lines.append(f"# 决策档案 · {self.card.ticker}")
        lines.append(f"**PM**: {self.card.pm_name}   "
                     f"**时间**: {self.card.timestamp}   "
                     f"**卡版本**: {self.card.card_version}\n")

        # 完整性
        c = self.completeness
        ok = "✅" if c.get("is_complete") else "⚠️"
        lines.append(f"## {ok} Schema 完整性")
        lines.append(f"- 客观字段填充率: {c.get('objective_filled_ratio', 0):.0%}")
        issues = c.get("subjective_issues", [])
        if issues:
            lines.append(f"- 主观字段问题 ({len(issues)} 个):")
            for iss in issues:
                lines.append(f"  - {iss}")
        else:
            lines.append("- 主观字段: 全部达到字数下限 ✓")
        lines.append("")

        # 决策卡 12 维度
        lines.append("## 📋 决策卡")
        for field_enum, label, kind in DIMENSIONS:
            val = getattr(self.card, field_enum.value, "")
            kind_tag = "🤖 auto" if kind == "objective" else "✍️ PM"
            lines.append(f"### {label}  `{kind_tag}`")
            if isinstance(val, dict):
                if val:
                    for k, v in val.items():
                        lines.append(f"- {k}: {v}")
                else:
                    lines.append("- _（未填）_")
            elif isinstance(val, list):
                if val:
                    for v in val:
                        lines.append(f"- {v}")
                else:
                    lines.append("- _（空）_")
            else:
                lines.append(val if val else "_（未填）_")
            lines.append("")
        # exit_condition 单独展示
        lines.append("### 退出条件 `✍️ PM`")
        lines.append(self.card.exit_condition if self.card.exit_condition else "_（未填）_")
        lines.append("")

        # 魔鬼代言人
        lines.append("## 👺 魔鬼代言人（可选，仅记录）")
        if self.devil is None:
            lines.append("_（未运行）_")
        elif self.devil.skipped:
            lines.append(f"_（跳过：{self.devil.skip_reason}）_")
        else:
            lines.append(f"使用模型：`{self.devil.model_used}`")
            lines.append("")
            for i, pt in enumerate(self.devil.points, 1):
                lines.append(f"{i}. {pt}")
        lines.append("")

        # 陪审团
        lines.append("## ⚖️ 多视角陪审团（显式分歧）")
        if self.jury is None:
            lines.append("_（未运行）_")
        else:
            lines.append(f"- **Signal label**: `{self.jury.signal_label}`")
            lines.append(f"- 看多 {self.jury.n_bullish} / 看空 {self.jury.n_bearish} / 中性 {self.jury.n_neutral}")
            lines.append(f"- 分歧极差: {self.jury.disagreement_range}")
            lines.append("")
            lines.append("| 视角 | 分 (-3..+3) | 理由 | 关注点 |")
            lines.append("|---|---|---|---|")
            for v in self.jury.votes:
                concerns = "; ".join(v.concerns) if v.concerns else "—"
                lines.append(f"| {v.perspective} | {v.score:+d} | {v.reasoning} | {concerns} |")
        lines.append("")

        lines.append("---")
        lines.append("> 本档案**仅辅助**投研决策；**最终决策权与责任在 PM**。")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Cockpit orchestrator
# ═══════════════════════════════════════════════════════════════════

class Cockpit:
    def __init__(
        self,
        llm: Optional[LLMProvider] = None,
        devil_model: str = "qwen-turbo",
        jury_model: str = "qwen-turbo",
        records_dir: Optional[Path] = None,
    ):
        self.devil = DevilAdvocate(llm=llm, model=devil_model)
        self.jury = Jury(llm=llm, model=jury_model)
        self.records_dir = records_dir or (Path(__file__).resolve().parent / "records")

    # ─ 主流程 ─

    def run(
        self,
        card: DecisionCard,
        *,
        skip_devil: bool = False,
        skip_jury: bool = False,
        persist: bool = True,
    ) -> DecisionRecord:
        """一次完整的决策闭环。

        Notes
        -----
        - 校验不 block：只写 completeness 报告入档。后续可接 nous.gate 做硬 block。
        - skip_devil=True 时 devil 记为 skipped，可追溯
        - skip_jury=True 时 jury=None（通常不建议跳过）
        """
        completeness = card.completeness_report()
        devil_critique = self.devil.run(card, skip=skip_devil) if not skip_devil else \
            DevilCritique(
                ticker=card.ticker, pm_name=card.pm_name,
                timestamp=datetime.now().isoformat(),
                skipped=True, skip_reason="call-time skip=True",
            )
        jury_verdict = None if skip_jury else self.jury.run(card)

        record = DecisionRecord(
            card=card,
            completeness=completeness,
            devil=devil_critique,
            jury=jury_verdict,
        )

        if persist:
            self._persist(record)
        return record

    # ─ 落盘 ─

    def _persist(self, record: DecisionRecord) -> None:
        self.records_dir.mkdir(parents=True, exist_ok=True)
        stamp = record.card.timestamp.replace(":", "").replace(".", "")[:15]
        base = self.records_dir / f"{record.card.ticker}_{stamp}"
        base.with_suffix(".json").write_text(record.to_json(), encoding="utf-8")
        base.with_suffix(".md").write_text(record.to_markdown(), encoding="utf-8")
