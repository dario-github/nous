"""
Nous Invest — Risk Management Module
风控模块: VaR / 回撤 / 暴露限制 / 止损机制

7亿规模私募级风控体系:
1. VaR Calculator — 多方法风险价值计算
2. DrawdownMonitor — 回撤监控与预警
3. ExposureLimiter — 实时暴露限制
4. RiskBudget — 风险预算分配
5. StopLossManager — 多级止损
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class RiskLevel(Enum):
    GREEN = "🟢 正常"
    YELLOW = "🟡 预警"
    ORANGE = "🟠 警告"
    RED = "🔴 危险"
    BLACK = "⛔ 紧急"


@dataclass
class RiskMetrics:
    """风控指标"""
    date: str
    # VaR
    var_95: float = 0.0  # 95% VaR (daily)
    var_99: float = 0.0  # 99% VaR (daily)
    cvar_95: float = 0.0  # 95% CVaR (条件VaR)
    cvar_99: float = 0.0

    # 回撤
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    drawdown_duration: int = 0  # 回撤持续天数

    # 波动率
    realized_vol_daily: float = 0.0
    realized_vol_annual: float = 0.0
    implied_vol_proxy: float = 0.0  # VIX / IV 代理

    # 尾部风险
    skewness: float = 0.0
    kurtosis: float = 0.0
    max_daily_loss: float = 0.0

    # 暴露
    beta: float = 0.0
    sector_max_exposure: float = 0.0
    factor_max_exposure: float = 0.0
    gross_leverage: float = 0.0
    net_leverage: float = 0.0

    # 风险等级
    overall_risk_level: RiskLevel = RiskLevel.GREEN
    risk_flags: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# 1. VaR Calculator
# ──────────────────────────────────────────────

class VaRCalculator:
    """
    风险价值 (Value at Risk) 计算器

    支持三种方法:
    1. 历史模拟法 (Historical Simulation)
    2. 参数法 (方差-协方差)
    3. 蒙特卡洛模拟
    """

    def __init__(self, aum: float = 700_000_000, lookback: int = 252):
        self.aum = aum
        self.lookback = lookback

    def historical_var(self,
                       returns: pd.Series,
                       confidence: float = 0.95,
                       horizon: int = 1) -> float:
        """
        历史模拟法 VaR

        Parameters
        ----------
        returns : pd.Series  日收益率序列
        confidence : float  置信度 (0.95 或 0.99)
        horizon : int  持有期 (天)

        Returns
        -------
        float  VaR 金额 (正值)
        """
        recent = returns.tail(self.lookback).dropna()
        if len(recent) < 30:
            return self.aum * 0.05  # fallback: 5%

        # 分位数
        quantile = 1 - confidence
        var_daily = np.percentile(recent, quantile * 100)
        var_horizon = var_daily * np.sqrt(horizon)

        return abs(var_horizon * self.aum)

    def parametric_var(self,
                       returns: pd.Series,
                       confidence: float = 0.95,
                       horizon: int = 1) -> float:
        """参数法 VaR (正态假设)"""
        from scipy import stats as sp_stats

        recent = returns.tail(self.lookback).dropna()
        if len(recent) < 30:
            return self.aum * 0.05

        mu = recent.mean()
        sigma = recent.std()

        z = sp_stats.norm.ppf(1 - confidence)
        var_daily = mu + z * sigma
        var_horizon = var_daily * np.sqrt(horizon)

        return abs(var_horizon * self.aum)

    def monte_carlo_var(self,
                        returns: pd.Series,
                        confidence: float = 0.95,
                        horizon: int = 1,
                        n_simulations: int = 10000) -> float:
        """蒙特卡洛 VaR"""
        recent = returns.tail(self.lookback).dropna()
        if len(recent) < 30:
            return self.aum * 0.05

        mu = recent.mean()
        sigma = recent.std()

        # 模拟路径
        np.random.seed(42)
        sim_returns = np.random.normal(mu, sigma, (n_simulations, horizon))
        path_returns = sim_returns.sum(axis=1)

        quantile = 1 - confidence
        var = np.percentile(path_returns, quantile * 100)

        return abs(var * self.aum)

    def cvar(self,
             returns: pd.Series,
             confidence: float = 0.95,
             horizon: int = 1) -> float:
        """条件 VaR (CVaR / Expected Shortfall)"""
        recent = returns.tail(self.lookback).dropna()
        if len(recent) < 30:
            return self.aum * 0.08

        quantile = 1 - confidence
        threshold = np.percentile(recent, quantile * 100)
        tail_returns = recent[recent <= threshold]

        if len(tail_returns) == 0:
            return self.aum * 0.05

        cvar_daily = tail_returns.mean() * np.sqrt(horizon)
        return abs(cvar_daily * self.aum)

    def full_report(self,
                    returns: pd.Series) -> Dict[str, float]:
        """输出完整 VaR 报告"""
        return {
            'var_95_1d': self.historical_var(returns, 0.95, 1),
            'var_99_1d': self.historical_var(returns, 0.99, 1),
            'var_95_5d': self.historical_var(returns, 0.95, 5),
            'var_99_5d': self.historical_var(returns, 0.99, 5),
            'var_95_10d': self.historical_var(returns, 0.95, 10),
            'cvar_95_1d': self.cvar(returns, 0.95, 1),
            'cvar_99_1d': self.cvar(returns, 0.99, 1),
            'parametric_var_95': self.parametric_var(returns, 0.95, 1),
            'monte_carlo_var_95': self.monte_carlo_var(returns, 0.95, 1),
        }


# ──────────────────────────────────────────────
# 2. Drawdown Monitor
# ──────────────────────────────────────────────

@dataclass
class DrawdownState:
    """回撤状态"""
    current_dd: float = 0.0  # 当前回撤 (负值)
    max_dd: float = 0.0  # 历史最大回撤
    high_water_mark: float = 1.0  # 历史最高净值
    dd_start_date: str = ""  # 本次回撤起始日
    dd_duration: int = 0  # 本次回撤持续天数
    recovery_target: float = 1.0  # 恢复目标净值


class DrawdownMonitor:
    """
    回撤监控与预警

    多级预警:
    - 🟢 正常: 回撤 < 5%
    - 🟡 预警: 回撤 5-10%
    - 🟠 警告: 回撤 10-15%
    - 🔴 危险: 回撤 15-20%
    - ⛔ 紧急: 回撤 > 20% → 触发强制减仓
    """

    THRESHOLDS = [
        (0.05, RiskLevel.GREEN, "正常运行"),
        (0.10, RiskLevel.YELLOW, "关注波动,收紧持仓"),
        (0.15, RiskLevel.ORANGE, "降低仓位至80%,暂停新建仓"),
        (0.20, RiskLevel.RED, "仓位降至50%,启动止损"),
        (float('inf'), RiskLevel.BLACK, "紧急清仓/强制平仓"),
    ]

    def __init__(self,
                 max_drawdown_limit: float = 0.15,
                 aum: float = 700_000_000):
        self.max_dd_limit = max_drawdown_limit
        self.aum = aum
        self.state = DrawdownState()

    def update(self,
               nav_series: pd.Series,
               date: Optional[str] = None) -> DrawdownState:
        """
        更新回撤状态

        Parameters
        ----------
        nav_series : Series  净值序列 (index: date)
        date : str  当前日期

        Returns
        -------
        DrawdownState
        """
        if len(nav_series) == 0:
            return self.state

        # 更新 HWM
        hwm = nav_series.expanding().max()
        self.state.high_water_mark = hwm.iloc[-1]

        # 计算回撤
        dd = (nav_series - hwm) / hwm
        self.state.current_dd = dd.iloc[-1]
        self.state.max_dd = dd.min()

        # 持续天数
        is_in_dd = dd < 0
        if is_in_dd.iloc[-1]:
            last_above = dd[dd >= 0]
            if len(last_above) > 0:
                self.state.dd_start_date = str(last_above.index[-1])
                self.state.dd_duration = (pd.Timestamp(date or nav_series.index[-1]) -
                                          pd.Timestamp(last_above.index[-1])).days
            else:
                self.state.dd_duration = len(dd)
        else:
            self.state.dd_duration = 0
            self.state.dd_start_date = ""

        # 恢复目标
        self.state.recovery_target = self.state.high_water_mark

        return self.state

    def get_risk_level(self) -> Tuple[RiskLevel, str]:
        """获取当前风险等级"""
        abs_dd = abs(self.state.current_dd)
        for threshold, level, action in self.THRESHOLDS:
            if abs_dd < threshold:
                return level, action
        return RiskLevel.BLACK, "未知状态"

    def get_position_adjustment(self) -> float:
        """
        根据回撤程度返回建议仓位比例

        Returns
        -------
        float  建议仓位比例 (0-1)
        """
        abs_dd = abs(self.state.current_dd)
        if abs_dd < 0.05:
            return 1.0
        elif abs_dd < 0.10:
            return 0.90
        elif abs_dd < 0.15:
            return 0.75
        elif abs_dd < 0.20:
            return 0.50
        else:
            return 0.25

    def generate_report(self) -> str:
        level, action = self.get_risk_level()
        pos_adj = self.get_position_adjustment()

        lines = [
            f"{'='*50}",
            f"📉 回撤监控报告",
            f"{'='*50}",
            f"当前回撤:     {self.state.current_dd:.2%}",
            f"历史最大回撤: {self.state.max_dd:.2%}",
            f"HWM:          {self.state.high_water_mark:.4f}",
            f"回撤天数:     {self.state.dd_duration} 天",
            f"风险等级:     {level.value}",
            f"建议操作:     {action}",
            f"建议仓位:     {pos_adj:.0%}",
            f"{'='*50}",
        ]
        return "\n".join(lines)


# ──────────────────────────────────────────────
# 3. Exposure Limiter
# ──────────────────────────────────────────────

@dataclass
class ExposureLimit:
    """暴露限制配置"""
    name: str
    limit: float  # 绝对值限制
    current: float = 0.0
    breach: bool = False

    @property
    def headroom(self) -> float:
        return max(0, self.limit - abs(self.current))


class ExposureLimiter:
    """
    实时暴露限制检查

    维度:
    - 单票集中度
    - 行业暴露
    - 风格因子暴露
    - Beta
    - 流动性 (单票占比 vs 日均成交额)
    """

    # 默认限制 (7亿AUM)
    DEFAULT_LIMITS = {
        'single_stock': 0.05,  # 单票 5%
        'sector': 0.15,  # 行业 15%
        'style_factor': 0.20,  # 风格因子 20%
        'beta': 0.10,  # Beta 偏移 ±0.10
        'illiquid_position': 0.02,  # 低流动性个股权重 2%
        'gross_leverage': 2.5,  # 总杠杆上限
        'net_leverage': 0.30,  # 净敞口上限
    }

    def __init__(self,
                 limits: Optional[Dict[str, float]] = None,
                 aum: float = 700_000_000):
        self.limits = {**self.DEFAULT_LIMITS, **(limits or {})}
        self.aum = aum

    def check_all(self,
                  weights_long: pd.Series,
                  weights_short: pd.Series,
                  sector_map: Dict[str, str],
                  factor_loadings: Optional[pd.DataFrame] = None,
                  betas: Optional[pd.Series] = None,
                  liquidity_data: Optional[Dict[str, float]] = None) -> List[ExposureLimit]:
        """
        全维度暴露检查

        Parameters
        ----------
        weights_long / weights_short : pd.Series
            多头/空头权重 (index: ts_code)
        sector_map : dict
            行业映射
        factor_loadings : DataFrame (optional)
            因子载荷
        betas : Series (optional)
            个股 beta
        liquidity_data : dict (optional)
            {ts_code: avg_daily_amount}

        Returns
        -------
        List[ExposureLimit]
        """
        checks = []

        # 1. 单票集中度
        all_weights = pd.concat([weights_long, -weights_short])
        max_single = all_weights.abs().max()
        checks.append(ExposureLimit(
            name='single_stock', limit=self.limits['single_stock'],
            current=max_single, breach=max_single > self.limits['single_stock']))

        # 2. 行业暴露
        net_weights = pd.Series(0.0, index=all_weights.index.unique())
        net_weights.loc[weights_long.index] += weights_long.values
        if len(weights_short) > 0:
            net_weights.loc[weights_short.index] -= weights_short.values

        sector_exp = {}
        for code in net_weights.index:
            sec = sector_map.get(code, 'UNKNOWN')
            sector_exp[sec] = sector_exp.get(sec, 0) + net_weights.get(code, 0)

        max_sector = max(abs(v) for v in sector_exp.values()) if sector_exp else 0
        checks.append(ExposureLimit(
            name='sector', limit=self.limits['sector'],
            current=max_sector, breach=max_sector > self.limits['sector']))

        # 3. 风格因子
        if factor_loadings is not None and len(net_weights) > 0:
            common = net_weights.index.intersection(factor_loadings.index)
            if len(common) > 0:
                for factor in factor_loadings.columns:
                    exp = abs(float((net_weights.loc[common] *
                                     factor_loadings.loc[common, factor]).sum()))
                    checks.append(ExposureLimit(
                        name=f'style_{factor}', limit=self.limits['style_factor'],
                        current=exp, breach=exp > self.limits['style_factor']))

        # 4. Beta
        if betas is not None:
            common_long = weights_long.index.intersection(betas.index)
            common_short = weights_short.index.intersection(betas.index)
            long_beta = float((weights_long.loc[common_long] * betas.loc[common_long]).sum())
            short_beta = float((weights_short.loc[common_short] * betas.loc[common_short]).sum())
            net_beta = abs(long_beta - short_beta)
            checks.append(ExposureLimit(
                name='beta', limit=self.limits['beta'],
                current=net_beta, breach=net_beta > self.limits['beta']))

        # 5. 流动性约束
        if liquidity_data:
            for code, w in weights_long.items():
                amt = liquidity_data.get(code, 0)
                if amt > 0:
                    position_value = w * self.aum
                    trade_ratio = position_value / amt
                    if trade_ratio > 0.05:  # 持仓 > 5% 日均成交额
                        checks.append(ExposureLimit(
                            name=f'illiquid_{code}', limit=self.limits['illiquid_position'],
                            current=w, breach=w > self.limits['illiquid_position']))

        # 6. 杠杆
        gross = weights_long.sum() + weights_short.sum()
        net = abs(weights_long.sum() - weights_short.sum())
        checks.append(ExposureLimit(
            name='gross_leverage', limit=self.limits['gross_leverage'],
            current=gross, breach=gross > self.limits['gross_leverage']))
        checks.append(ExposureLimit(
            name='net_leverage', limit=self.limits['net_leverage'],
            current=net, breach=net > self.limits['net_leverage']))

        return checks

    def generate_limit_report(self, checks: List[ExposureLimit]) -> str:
        """生成暴露限制报告"""
        lines = [
            f"{'='*50}",
            f"🔒 暴露限制检查",
            f"{'='*50}",
        ]

        breaches = [c for c in checks if c.breach]
        passing = [c for c in checks if not c.breach]

        if breaches:
            lines.append("\n⚠️ 超限项目:")
            for c in breaches:
                lines.append(f"  ❌ {c.name:25s}: {c.current:+.4f} (限制: ±{c.limit:.4f})")

        lines.append(f"\n✅ 合规项目 ({len(passing)}/{len(checks)}):")
        for c in passing[:15]:
            lines.append(f"  ✓  {c.name:25s}: {c.current:+.4f} (余量: {c.headroom:.4f})")

        if len(passing) > 15:
            lines.append(f"  ... 等共 {len(passing)} 项合规")

        lines.append(f"\n{'='*50}")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# 4. Risk Budget
# ──────────────────────────────────────────────

class RiskBudget:
    """
    风险预算分配

    基于 Marginal Contribution to Risk (MCTR) 分配风险
    """

    def __init__(self,
                 target_vol: float = 0.12,
                 aum: float = 700_000_000):
        self.target_vol = target_vol
        self.aum = aum

    def allocate(self,
                 returns_df: pd.DataFrame,
                 weights: pd.Series) -> Dict[str, float]:
        """
        计算各资产的风险贡献

        Parameters
        ----------
        returns_df : DataFrame  (index: date, columns: ts_code)
        weights : Series (index: ts_code)

        Returns
        -------
        Dict {ts_code: risk_contribution_pct}
        """
        common = weights.index.intersection(returns_df.columns)
        if len(common) < 2:
            return {}

        R = returns_df[common].tail(252).dropna()
        w = weights.loc[common]

        cov = R.cov() * 252  # 年化协方差
        portfolio_vol = np.sqrt(w @ cov.values @ w)

        if portfolio_vol == 0:
            return {}

        # 边际风险贡献
        mctr = cov.values @ w.values / portfolio_vol
        # 风险贡献
        ctr = w.values * mctr
        # 百分比
        pct = ctr / ctr.sum()

        return dict(zip(common, np.round(pct, 4)))

    def scale_to_target(self,
                        weights: pd.Series,
                        returns_df: pd.DataFrame) -> pd.Series:
        """
        缩放权重使组合波动率等于目标

        Returns
        -------
        pd.Series  缩放后的权重
        """
        common = weights.index.intersection(returns_df.columns)
        if len(common) < 2:
            return weights

        R = returns_df[common].tail(252).dropna()
        w = weights.loc[common]
        cov = R.cov() * 252
        current_vol = np.sqrt(w @ cov.values @ w)

        if current_vol > 0:
            scale = self.target_vol / current_vol
            return w * min(scale, 1.0)  # 只缩不放

        return weights


# ──────────────────────────────────────────────
# 5. Stop Loss Manager
# ──────────────────────────────────────────────

@dataclass
class StopLossConfig:
    """止损配置"""
    # 基金级
    fund_max_drawdown: float = 0.15  # 基金最大回撤 15%
    fund_daily_loss: float = 0.03  # 单日最大亏损 3%
    fund_weekly_loss: float = 0.05  # 单周最大亏损 5%

    # 策略级
    strategy_drawdown: float = 0.10  # 策略最大回撤 10%
    strategy_signal_decay: float = 0.30  # 信号衰减阈值 30%

    # 个股级
    stock_max_loss: float = 0.08  # 个股最大亏损 8%
    stock_stop_profit: float = 0.20  # 个股止盈 20%

    # 时间止损
    time_stop_days: int = 20  # 超过N天未盈利则退出
    time_stop_max_hold: int = 60  # 最长持仓天数


class StopLossManager:
    """
    多级止损管理

    止损机制:
    1. 基金级: 回撤/日亏损 → 全局降仓
    2. 策略级: 策略效果衰减 → 策略暂停
    3. 个股级: 单票亏损/时间止损 → 个股清仓
    """

    def __init__(self,
                 config: Optional[StopLossConfig] = None,
                 aum: float = 700_000_000):
        self.config = config or StopLossConfig()
        self.aum = aum

    def check_fund_level(self,
                         fund_nav: pd.Series,
                         date: Optional[str] = None) -> Dict[str, bool]:
        """
        基金级止损检查

        Returns
        -------
        Dict {check_name: triggered}
        """
        results = {}

        # 回撤检查
        hwm = fund_nav.expanding().max()
        dd = (fund_nav - hwm) / hwm
        current_dd = abs(dd.iloc[-1])
        results['max_drawdown'] = current_dd >= self.config.fund_max_drawdown

        # 单日亏损
        daily_ret = fund_nav.pct_change()
        if len(daily_ret) > 0:
            results['daily_loss'] = abs(daily_ret.iloc[-1]) >= self.config.fund_daily_loss

        # 周亏损
        if len(fund_nav) >= 5:
            weekly_ret = fund_nav.iloc[-1] / fund_nav.iloc[-5] - 1
            results['weekly_loss'] = abs(weekly_ret) >= self.config.fund_weekly_loss

        return results

    def check_stock_level(self,
                          stock_entry_price: Dict[str, float],
                          stock_current_price: Dict[str, float],
                          stock_hold_days: Dict[str, int]) -> Dict[str, List[str]]:
        """
        个股级止损检查

        Returns
        -------
        Dict {action: [codes]}  e.g. {'stop_loss': ['000001.SZ'], 'stop_profit': ['600519.SH']}
        """
        actions = {
            'stop_loss': [],
            'stop_profit': [],
            'time_stop': [],
            'max_hold': [],
        }

        for code in stock_entry_price:
            if code not in stock_current_price:
                continue

            entry = stock_entry_price[code]
            current = stock_current_price[code]
            pnl = (current - entry) / entry

            if pnl <= -self.config.stock_max_loss:
                actions['stop_loss'].append(code)
            elif pnl >= self.config.stock_stop_profit:
                actions['stop_profit'].append(code)

            days = stock_hold_days.get(code, 0)
            if days >= self.config.time_stop_max_hold:
                actions['max_hold'].append(code)
            elif days >= self.config.time_stop_days and pnl <= 0:
                actions['time_stop'].append(code)

        return actions

    def generate_action_plan(self,
                             fund_checks: Dict[str, bool],
                             stock_actions: Dict[str, List[str]]) -> str:
        """生成止损操作计划"""
        lines = [
            f"{'='*50}",
            f"🛑 止损操作计划",
            f"{'='*50}",
        ]

        # 基金级
        lines.append("\n📊 基金级:")
        triggered = [k for k, v in fund_checks.items() if v]
        if triggered:
            lines.append(f"  ⚠️ 触发: {', '.join(triggered)}")
            if 'max_drawdown' in triggered:
                lines.append("  → 建议: 全局仓位降至50%")
            if 'daily_loss' in triggered:
                lines.append("  → 建议: 暂停新建仓，T+1评估")
            if 'weekly_loss' in triggered:
                lines.append("  → 建议: 审查策略有效性")
        else:
            lines.append("  ✅ 全部正常")

        # 个股级
        lines.append("\n📋 个股级:")
        total_actions = sum(len(v) for v in stock_actions.values())
        if total_actions > 0:
            for action, codes in stock_actions.items():
                if codes:
                    lines.append(f"  {action}: {', '.join(codes[:10])}")
        else:
            lines.append("  ✅ 无需操作")

        lines.append(f"\n{'='*50}")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# 6. Risk Manager (Facade)
# ──────────────────────────────────────────────

class RiskManager:
    """
    风控主控模块

    整合 VaR / 回撤 / 暴露 / 止损
    """

    def __init__(self,
                 aum: float = 700_000_000,
                 var_lookback: int = 252,
                 max_drawdown: float = 0.15,
                 exposure_limits: Optional[Dict[str, float]] = None):
        self.var_calc = VaRCalculator(aum=aum, lookback=var_lookback)
        self.dd_monitor = DrawdownMonitor(max_drawdown_limit=max_drawdown, aum=aum)
        self.exposure_limiter = ExposureLimiter(limits=exposure_limits, aum=aum)
        self.risk_budget = RiskBudget(aum=aum)
        self.stop_loss = StopLossManager(aum=aum)
        self.aum = aum

    def daily_risk_check(self,
                         fund_returns: pd.Series,
                         fund_nav: pd.Series,
                         weights_long: pd.Series,
                         weights_short: pd.Series,
                         sector_map: Dict[str, str],
                         factor_loadings: Optional[pd.DataFrame] = None,
                         betas: Optional[pd.Series] = None,
                         liquidity_data: Optional[Dict[str, float]] = None,
                         date: Optional[str] = None) -> RiskMetrics:
        """
        每日风控检查

        Returns
        -------
        RiskMetrics
        """
        # VaR
        var_95 = self.var_calc.historical_var(fund_returns, 0.95)
        var_99 = self.var_calc.historical_var(fund_returns, 0.99)
        cvar_95 = self.var_calc.cvar(fund_returns, 0.95)
        cvar_99 = self.var_calc.cvar(fund_returns, 0.99)

        # 回撤
        self.dd_monitor.update(fund_nav, date)
        dd_state = self.dd_monitor.state

        # 波动率
        vol_daily = fund_returns.tail(60).std()
        vol_annual = vol_daily * np.sqrt(252)

        # 尾部风险
        recent = fund_returns.tail(252)
        skewness = recent.skew()
        kurtosis = recent.kurtosis()
        max_daily_loss = recent.min()

        # 暴露检查
        exposure_checks = self.exposure_limiter.check_all(
            weights_long, weights_short, sector_map,
            factor_loadings, betas, liquidity_data)

        max_sector_exp = max(
            (abs(c.current) for c in exposure_checks if c.name == 'sector'),
            default=0)
        max_factor_exp = max(
            (abs(c.current) for c in exposure_checks
             if c.name.startswith('style_')),
            default=0)

        has_breach = any(c.breach for c in exposure_checks)
        risk_flags = [c.name for c in exposure_checks if c.breach]

        # 综合风险等级
        level, _ = self.dd_monitor.get_risk_level()
        if has_breach:
            level = RiskLevel.RED if level.value <= RiskLevel.ORANGE.value else level

        metrics = RiskMetrics(
            date=date or pd.Timestamp.now().strftime('%Y%m%d'),
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            current_drawdown=dd_state.current_dd,
            max_drawdown=dd_state.max_dd,
            drawdown_duration=dd_state.dd_duration,
            realized_vol_daily=vol_daily,
            realized_vol_annual=vol_annual,
            skewness=skewness,
            kurtosis=kurtosis,
            max_daily_loss=max_daily_loss,
            sector_max_exposure=max_sector_exp,
            factor_max_exposure=max_factor_exp,
            gross_leverage=weights_long.sum() + weights_short.sum(),
            net_leverage=weights_long.sum() - weights_short.sum(),
            overall_risk_level=level,
            risk_flags=risk_flags,
        )

        return metrics

    def generate_daily_report(self, metrics: RiskMetrics) -> str:
        """生成每日风控报告"""
        lines = [
            f"{'='*60}",
            f"🛡️ 每日风控报告 — {metrics.date}",
            f"{'='*60}",
            "",
            f"📊 VaR (AUM: ¥{self.aum/1e8:.1f}亿)",
            f"  95% VaR (1D):  ¥{metrics.var_95/1e4:,.0f}万 ({metrics.var_95/self.aum:.2%})",
            f"  99% VaR (1D):  ¥{metrics.var_99/1e4:,.0f}万 ({metrics.var_99/self.aum:.2%})",
            f"  95% CVaR (1D): ¥{metrics.cvar_95/1e4:,.0f}万",
            "",
            f"📉 回撤",
            f"  当前回撤: {metrics.current_drawdown:.2%}",
            f"  最大回撤: {metrics.max_drawdown:.2%}",
            f"  持续天数: {metrics.drawdown_duration}",
            "",
            f"📈 波动率",
            f"  日波动率: {metrics.realized_vol_daily:.4f}",
            f"  年化波动率: {metrics.realized_vol_annual:.2%}",
            "",
            f"📐 暴露",
            f"  Gross Leverage: {metrics.gross_leverage:.2f}",
            f"  Net Leverage:   {metrics.net_leverage:.2f}",
            f"  行业最大暴露:   {metrics.sector_max_exposure:.2%}",
            f"  因子最大暴露:   {metrics.factor_max_exposure:.2%}",
            "",
            f"🚨 风险等级: {metrics.overall_risk_level.value}",
        ]

        if metrics.risk_flags:
            lines.append(f"  触发项: {', '.join(metrics.risk_flags)}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)
