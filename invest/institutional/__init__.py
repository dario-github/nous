"""
Nous Invest — Institutional Grade System (7亿AUM)
机构级系统架构: 市场中性 + 容量约束 + 风控 + 合规披露

Modules:
    market_neutral  — Long-Short 市场中性基础框架
    risk            — 风控模块 (VaR / 回撤 / 暴露限制)
    compliance      — 合规披露 (AMAC 月报/季报/年报模板)
"""

__version__ = "1.0.0"
__aum_target__ = 700_000_000  # 7亿
