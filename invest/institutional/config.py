"""
Nous Invest — Institutional System Configuration
7亿规模私募机构级配置
"""

# ── 基金基本信息 ──
FUND_CONFIG = {
    "name": "Nous Long-Short Market Neutral Fund",
    "code": "SXXXXX",
    "aum": 700_000_000,  # 7亿
    "inception_date": "2026-01-01",
    "strategy": "市场中性 (Long-Short Equity)",
    "benchmark": "中证500指数",
    "custodian": "待定",
    "risk_level": "R4",
}

# ── 投资约束 ──
INVESTMENT_CONSTRAINTS = {
    # 选股池
    "min_daily_amount": 500_000_000,  # 日均成交额 > 5亿
    "min_market_cap": 20_000_000_000,  # 市值 > 200亿
    "max_market_cap": 200_000_000_000,  # 市值 < 2000亿
    "min_free_float": 0.15,  # 自由流通比例 > 15%

    # 持仓
    "max_single_weight": 0.05,  # 单票 ≤ 5%
    "min_long_stocks": 40,  # 多头最少 40只
    "min_short_stocks": 20,  # 空头最少 20只
    "target_gross_leverage": 2.0,  # 目标总杠杆
    "target_net_exposure": 0.0,  # 目标净敞口(中性)

    # 暴露
    "max_sector_exposure": 0.15,  # 单行业 ≤ 15%
    "max_factor_exposure": 0.20,  # 单风格因子 ≤ 20%
    "beta_tolerance": 0.10,  # Beta 偏移 ≤ ±0.10
}

# ── 风控参数 ──
RISK_CONFIG = {
    # VaR
    "var_confidence": 0.95,
    "var_horizon_days": 1,
    "var_lookback": 252,

    # 回撤
    "max_drawdown_limit": 0.15,  # 最大回撤 15%
    "dd_warning_level": 0.05,  # 预警 5%
    "dd_alert_level": 0.10,  # 警告 10%
    "dd_critical_level": 0.15,  # 危险 15%

    # 止损
    "fund_daily_loss_limit": 0.03,  # 单日亏损 3%
    "fund_weekly_loss_limit": 0.05,  # 单周亏损 5%
    "stock_max_loss": 0.08,  # 个股止损 8%
    "stock_take_profit": 0.20,  # 个股止盈 20%
    "max_hold_days": 60,  # 最长持仓
    "time_stop_days": 20,  # 时间止损

    # 波动率
    "target_annual_vol": 0.12,  # 目标年化波动率 12%
    "vol_scaling": True,  # 波动率缩放
}

# ── 合规参数 ──
COMPLIANCE_CONFIG = {
    # 信息披露
    "monthly_nav_deadline_days": 5,
    "quarterly_report_deadline_days": 30,
    "annual_report_deadline_days": 90,
    "material_event_deadline_days": 2,

    # 投资限制 (法规)
    "regulatory_single_stock_max": 0.10,
    "regulatory_leverage_max": 2.0,
    "regulatory_illiquid_max": 0.20,

    # 审计
    "audit_log_dir": "logs/audit",
    "audit_retention_days": 365 * 5,  # 审计日志保留5年
}

# ── 交易参数 ──
TRADING_CONFIG = {
    "rebalance_frequency": "weekly",  # weekly / biweekly / monthly
    "execution_slippage_bps": 5,  # 执行滑点 5bps
    "commission_rate": 0.0003,  # 佣金万三
    "stamp_tax": 0.001,  # 印花税千一(卖出)
    "impact_cost_budget_bps": 10,  # 冲击成本预算 10bps
    "max_participation_rate": 0.15,  # 最大参与率 15%
}

# ── 对冲配置 ──
HEDGE_CONFIG = {
    "primary_instrument": "IF",  # 沪深300期货
    "secondary_instrument": "IC",  # 中证500期货
    "hedge_ratio_method": "beta",  # beta / regression / rolling
    "hedge_rebalance": "weekly",
    "roll_strategy": "front_month",  # front_month / next_month
    "futures_multiplier": {
        "IF": 300,
        "IH": 300,
        "IC": 200,
        "IM": 200,
    },
}
