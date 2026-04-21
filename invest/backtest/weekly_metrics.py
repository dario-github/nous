"""
Nous Invest - 周超额评估指标
Module 6: Weekly Alpha Metrics

周超额评估体系 (对齐私募标准)
- 周超额收益 (Weekly Alpha)
- 周超额夏普 (Weekly Sharpe)
- 最大回撤 (Max Drawdown)
- 胜率/盈亏比
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class WeeklyMetrics:
    """周超额指标数据类"""
    # 收益指标
    weekly_alpha_mean: float = 0.0  # 平均周超额
    weekly_alpha_std: float = 0.0   # 周超额波动
    weekly_alpha_sharpe: float = 0.0  # 周超额夏普
    
    # 风险指标
    max_drawdown: float = 0.0  # 最大回撤
    max_drawdown_duration: int = 0  # 最长回撤天数
    
    # 胜率指标
    win_rate: float = 0.0  # 胜率 (周超额>0的占比)
    profit_loss_ratio: float = 0.0  # 盈亏比
    
    # 连续指标
    consecutive_wins: int = 0  # 最长连胜周数
    consecutive_losses: int = 0  # 最长连败周数
    
    # 分年度指标
    yearly_metrics: Dict[int, Dict] = None
    
    # 月度分布
    monthly_alpha: pd.Series = None


class WeeklyAlphaCalculator:
    """
    周超额收益计算器
    
    核心逻辑:
    1. 将日收益率聚合为周收益率 (周五到周五)
    2. 计算策略周收益 - 基准周收益 = 周超额
    3. 基于周超额计算夏普、回撤等指标
    """
    
    def __init__(self, trading_days: Optional[List[str]] = None):
        self.trading_days = trading_days
        
    def calculate_weekly_returns(
        self,
        daily_returns: pd.Series,
        freq: str = "W-FRI"  # 周五为周结束
    ) -> pd.Series:
        """
        将日收益率聚合为周收益率
        
        Parameters
        ----------
        daily_returns : pd.Series
            日收益率序列，index为日期
        freq : str
            周频设置，默认周五结束
            
        Returns
        -------
        pd.Series
            周收益率序列
        """
        # 确保索引是datetime
        if not isinstance(daily_returns.index, pd.DatetimeIndex):
            daily_returns.index = pd.to_datetime(daily_returns.index)
        
        # 收益率累加 (log return)
        log_returns = np.log1p(daily_returns)
        weekly_log_returns = log_returns.resample(freq).sum()
        weekly_returns = np.expm1(weekly_log_returns)
        
        return weekly_returns.dropna()
    
    def calculate_weekly_alpha(
        self,
        strategy_daily_returns: pd.Series,
        benchmark_daily_returns: pd.Series,
        freq: str = "W-FRI"
    ) -> pd.Series:
        """
        计算周超额收益序列
        
        Parameters
        ----------
        strategy_daily_returns : pd.Series
            策略日收益率
        benchmark_daily_returns : pd.Series
            基准日收益率
        freq : str
            周频
            
        Returns
        -------
        pd.Series
            周超额收益序列 (策略周收益 - 基准周收益)
        """
        # 计算周收益
        strategy_weekly = self.calculate_weekly_returns(strategy_daily_returns, freq)
        benchmark_weekly = self.calculate_weekly_returns(benchmark_daily_returns, freq)
        
        # 对齐日期
        common_dates = strategy_weekly.index.intersection(benchmark_weekly.index)
        strategy_weekly = strategy_weekly.loc[common_dates]
        benchmark_weekly = benchmark_weekly.loc[common_dates]
        
        # 计算超额
        weekly_alpha = strategy_weekly - benchmark_weekly
        
        return weekly_alpha
    
    def calculate_metrics(
        self,
        weekly_alpha: pd.Series,
        strategy_daily_returns: Optional[pd.Series] = None
    ) -> WeeklyMetrics:
        """
        计算完整周超额指标
        
        Parameters
        ----------
        weekly_alpha : pd.Series
            周超额收益序列
        strategy_daily_returns : pd.Series, optional
            策略日收益率 (用于计算最大回撤)
            
        Returns
        -------
        WeeklyMetrics
            周超额指标
        """
        metrics = WeeklyMetrics()
        
        if len(weekly_alpha) == 0:
            return metrics
        
        # 基础统计
        metrics.weekly_alpha_mean = weekly_alpha.mean()
        metrics.weekly_alpha_std = weekly_alpha.std()
        
        # 周超额夏普 (年化)
        # 假设一年52周，无风险利率为0
        if metrics.weekly_alpha_std > 0:
            metrics.weekly_alpha_sharpe = (
                metrics.weekly_alpha_mean / metrics.weekly_alpha_std * np.sqrt(52)
            )
        
        # 胜率
        positive_weeks = (weekly_alpha > 0).sum()
        metrics.win_rate = positive_weeks / len(weekly_alpha)
        
        # 盈亏比
        gains = weekly_alpha[weekly_alpha > 0]
        losses = weekly_alpha[weekly_alpha < 0]
        if len(losses) > 0 and losses.abs().mean() > 0:
            metrics.profit_loss_ratio = gains.mean() / losses.abs().mean()
        
        # 连续胜负
        metrics.consecutive_wins = self._max_consecutive(weekly_alpha > 0)
        metrics.consecutive_losses = self._max_consecutive(weekly_alpha < 0)
        
        # 最大回撤 (基于日收益)
        if strategy_daily_returns is not None:
            metrics.max_drawdown = self._calculate_max_drawdown(strategy_daily_returns)
            metrics.max_drawdown_duration = self._calculate_drawdown_duration(strategy_daily_returns)
        
        # 分年度计算
        metrics.yearly_metrics = self._calculate_yearly_metrics(weekly_alpha)
        
        # 月度分布
        metrics.monthly_alpha = self._calculate_monthly_alpha(weekly_alpha)
        
        return metrics
    
    def _max_consecutive(self, bool_series: pd.Series) -> int:
        """计算最长连续True数量"""
        # 将布尔序列转为字符串，寻找最长连续1
        s = bool_series.astype(int)
        max_consecutive = 0
        current = 0
        
        for val in s:
            if val == 1:
                current += 1
                max_consecutive = max(max_consecutive, current)
            else:
                current = 0
        
        return max_consecutive
    
    def _calculate_max_drawdown(self, daily_returns: pd.Series) -> float:
        """计算最大回撤"""
        cumulative = (1 + daily_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min()
    
    def _calculate_drawdown_duration(self, daily_returns: pd.Series) -> int:
        """计算最长回撤持续天数"""
        cumulative = (1 + daily_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        
        # 找到回撤期
        in_drawdown = drawdown < 0
        max_duration = 0
        current_duration = 0
        
        for val in in_drawdown:
            if val:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0
        
        return max_duration
    
    def _calculate_yearly_metrics(
        self,
        weekly_alpha: pd.Series
    ) -> Dict[int, Dict]:
        """计算分年度指标"""
        yearly = {}
        
        for year in weekly_alpha.index.year.unique():
            year_data = weekly_alpha[weekly_alpha.index.year == year]
            if len(year_data) > 0:
                yearly[year] = {
                    "mean": year_data.mean(),
                    "std": year_data.std(),
                    "sharpe": year_data.mean() / year_data.std() * np.sqrt(52) if year_data.std() > 0 else 0,
                    "win_rate": (year_data > 0).sum() / len(year_data),
                    "count": len(year_data)
                }
        
        return yearly
    
    def _calculate_monthly_alpha(self, weekly_alpha: pd.Series) -> pd.Series:
        """计算月度超额分布"""
        monthly = weekly_alpha.resample("ME").mean()
        return monthly.dropna()
    
    def generate_report(self, metrics: WeeklyMetrics) -> str:
        """生成周超额报告文本"""
        lines = []
        lines.append("=" * 60)
        lines.append("周超额评估报告 (Weekly Alpha Report)")
        lines.append("=" * 60)
        lines.append("")
        
        # 核心指标
        lines.append("【核心指标】")
        lines.append(f"  平均周超额:    {metrics.weekly_alpha_mean*100:+.4f}%")
        lines.append(f"  周超额波动:    {metrics.weekly_alpha_std*100:.4f}%")
        lines.append(f"  周超额夏普:    {metrics.weekly_alpha_sharpe:.4f}")
        lines.append("")
        
        # 风险指标
        lines.append("【风险指标】")
        lines.append(f"  最大回撤:      {metrics.max_drawdown*100:.2f}%")
        lines.append(f"  回撤持续:      {metrics.max_drawdown_duration} 天")
        lines.append("")
        
        # 胜率指标
        lines.append("【胜率指标】")
        lines.append(f"  周胜率:        {metrics.win_rate*100:.1f}%")
        lines.append(f"  盈亏比:        {metrics.profit_loss_ratio:.2f}")
        lines.append(f"  最长连胜:      {metrics.consecutive_wins} 周")
        lines.append(f"  最长连败:      {metrics.consecutive_losses} 周")
        lines.append("")
        
        # 分年度
        if metrics.yearly_metrics:
            lines.append("【分年度表现】")
            for year, data in sorted(metrics.yearly_metrics.items()):
                lines.append(f"  {year}: 周超额={data['mean']*100:+.4f}%, 夏普={data['sharpe']:.2f}, 胜率={data['win_rate']*100:.1f}%")
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


def calculate_weekly_alpha_metrics(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    freq: str = "W-FRI"
) -> Tuple[WeeklyMetrics, pd.Series]:
    """
    一站式周超额指标计算
    
    Parameters
    ----------
    strategy_returns : pd.Series
        策略日收益率
    benchmark_returns : pd.Series
        基准日收益率
    freq : str
        周频设置
        
    Returns
    -------
    Tuple[WeeklyMetrics, pd.Series]
        (指标对象, 周超额序列)
    """
    calculator = WeeklyAlphaCalculator()
    
    # 计算周超额
    weekly_alpha = calculator.calculate_weekly_alpha(
        strategy_returns, benchmark_returns, freq
    )
    
    # 计算指标
    metrics = calculator.calculate_metrics(weekly_alpha, strategy_returns)
    
    return metrics, weekly_alpha


if __name__ == "__main__":
    # 测试代码
    print("[WeeklyMetrics] Module loaded successfully")
    
    # 生成测试数据
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", "2024-12-31", freq="B")
    
    strategy_returns = pd.Series(np.random.normal(0.0005, 0.02, len(dates)), index=dates)
    benchmark_returns = pd.Series(np.random.normal(0.0002, 0.015, len(dates)), index=dates)
    
    # 计算指标
    metrics, weekly_alpha = calculate_weekly_alpha_metrics(strategy_returns, benchmark_returns)
    
    # 打印报告
    calculator = WeeklyAlphaCalculator()
    print(calculator.generate_report(metrics))
