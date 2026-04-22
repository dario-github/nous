"""
结构化决策卡 — v7 能力 1

12 维度 checklist（v7 §2.1）：
  公司概览 / 商业模式 / 护城河 / 财务健康度 / 估值水平 / 竞争格局 /
  管理层 / 催化剂 / 风险矩阵 / 技术面 / 政策环境 / 关键假设与结论

字段分"客观"（系统自动填）和"主观"（PM 必须亲填）两类。
红线：PM 先独立判断，系统后出手——所以本 module 只提供 schema，
       不替 PM 自动生成主观字段。objective_filler 只填客观数据。
"""
from __future__ import annotations

import dataclasses as dc
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class CardField(str, Enum):
    """枚举所有字段，便于 gate / jury 引用。"""

    # ── Objective（系统自动填） ──
    COMPANY_SNAPSHOT = "company_snapshot"     # 公司概览：名称/代码/行业/市值
    FINANCIALS = "financials"                  # 财务健康度：ROE/负债率/现金流
    VALUATION = "valuation"                    # 估值水平：PE/PB/历史分位

    # ── Subjective（PM 必须自己写） ──
    BUSINESS_MODEL = "business_model"          # 商业模式（一句话）
    MOAT = "moat"                              # 护城河
    COMPETITIVE_LANDSCAPE = "competitive_landscape"  # 竞争格局
    MANAGEMENT = "management"                  # 管理层
    CATALYSTS = "catalysts"                    # 催化剂
    RISKS = "risks"                            # 风险矩阵（list）
    TECHNICALS = "technicals"                  # 技术面（PM 自己写观察，不是自动）
    POLICY_ENV = "policy_env"                  # 政策环境
    THESIS = "thesis"                          # 关键假设与结论
    EXIT_CONDITION = "exit_condition"          # 退出条件


#: 12 维度的展示顺序与中文标签
DIMENSIONS: List[tuple[CardField, str, str]] = [
    (CardField.COMPANY_SNAPSHOT, "公司概览", "objective"),
    (CardField.BUSINESS_MODEL, "商业模式", "subjective"),
    (CardField.MOAT, "护城河", "subjective"),
    (CardField.FINANCIALS, "财务健康度", "objective"),
    (CardField.VALUATION, "估值水平", "objective"),
    (CardField.COMPETITIVE_LANDSCAPE, "竞争格局", "subjective"),
    (CardField.MANAGEMENT, "管理层", "subjective"),
    (CardField.CATALYSTS, "催化剂", "subjective"),
    (CardField.RISKS, "风险矩阵", "subjective"),
    (CardField.TECHNICALS, "技术面", "subjective"),
    (CardField.POLICY_ENV, "政策环境", "subjective"),
    (CardField.THESIS, "关键假设与结论", "subjective"),
]
# 注：EXIT_CONDITION 是 subjective 但放在 THESIS 下面一起展示


#: 主观字段最少字数门槛 — 防"空壳卡"
SUBJECTIVE_MIN_LEN = {
    CardField.BUSINESS_MODEL: 20,
    CardField.MOAT: 30,
    CardField.COMPETITIVE_LANDSCAPE: 30,
    CardField.MANAGEMENT: 15,
    CardField.CATALYSTS: 20,
    CardField.TECHNICALS: 15,
    CardField.POLICY_ENV: 15,
    CardField.THESIS: 100,        # 最重要，100 字起
    CardField.EXIT_CONDITION: 20,
}
#: 风险矩阵特殊：至少 2 条
MIN_RISKS_COUNT = 2


@dataclass
class DecisionCard:
    """12 维度决策卡。缺失字段 = 空字符串 / 空 dict / 空 list。"""

    ticker: str
    pm_name: str

    # Objective (system-filled)
    company_snapshot: Dict[str, Any] = field(default_factory=dict)
    financials: Dict[str, Any] = field(default_factory=dict)
    valuation: Dict[str, Any] = field(default_factory=dict)

    # Subjective (PM-filled)
    business_model: str = ""
    moat: str = ""
    competitive_landscape: str = ""
    management: str = ""
    catalysts: str = ""
    risks: List[str] = field(default_factory=list)
    technicals: str = ""
    policy_env: str = ""
    thesis: str = ""
    exit_condition: str = ""

    # Meta
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    card_version: str = "v1.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    # ────────────────────────────────────────────────
    # Completeness checks（不做 gate，只做 schema 级）
    # ────────────────────────────────────────────────

    def objective_filled_ratio(self) -> float:
        """客观字段填充率（0..1）。"""
        objective_fields = [CardField.COMPANY_SNAPSHOT, CardField.FINANCIALS, CardField.VALUATION]
        filled = sum(1 for f in objective_fields if getattr(self, f.value))
        return filled / len(objective_fields)

    def subjective_issues(self) -> List[str]:
        """主观字段的问题列表（空就是全过）。"""
        issues: List[str] = []
        for f, min_len in SUBJECTIVE_MIN_LEN.items():
            val = getattr(self, f.value, "")
            if not isinstance(val, str) or len(val.strip()) < min_len:
                issues.append(f"subjective.{f.value} 少于 {min_len} 字")
        if len(self.risks) < MIN_RISKS_COUNT:
            issues.append(f"subjective.risks 少于 {MIN_RISKS_COUNT} 条")
        return issues

    def completeness_report(self) -> Dict[str, Any]:
        """一份 schema 级完整性报告，给 gate 用。"""
        obj_ratio = self.objective_filled_ratio()
        issues = self.subjective_issues()
        return {
            "ticker": self.ticker,
            "pm_name": self.pm_name,
            "objective_filled_ratio": obj_ratio,
            "subjective_issues": issues,
            "is_complete": obj_ratio >= 1.0 and len(issues) == 0,
        }
