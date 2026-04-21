"""
Nous Invest - 容量/冲击成本估计
Module 6: Capacity & Impact Cost Analysis

容量评估体系:
- 单票容量估计 (基于日均成交额)
- 组合容量上限
- 冲击成本模型 (Almgren, etc.)
- 流动性评分
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class CapacityEstimate:
    """容量估计结果"""
    stock_code: str
    stock_name: str = ""
    
    # 基础流动性指标
    avg_daily_volume: float = 0.0  # 日均成交量 (股)
    avg_daily_amount: float = 0.0  # 日均成交额 (元)
    avg_turnover_rate: float = 0.0  # 日均换手率
    
    # 容量估计
    safe_capacity: float = 0.0  # 安全容量 (建议最大持仓金额)
    max_capacity: float = 0.0   # 最大容量 (理论上限)
    
    # 冲击成本
    impact_cost_10bp: float = 0.0   # 买入10%日均成交量的冲击成本
    impact_cost_20bp: float = 0.0   # 买入20%日均成交量的冲击成本
    
    # 流动性评分 (0-100)
    liquidity_score: float = 0.0
    
    # 风险标签
    risk_tags: List[str] = None


@dataclass
class PortfolioCapacity:
    """组合容量估计"""
    total_safe_capacity: float = 0.0  # 组合安全容量
    total_max_capacity: float = 0.0     # 组合最大容量
    
    # 分层容量
    large_cap_capacity: float = 0.0     # 大盘股容量
    mid_cap_capacity: float = 0.0       # 中盘股容量  
    small_cap_capacity: float = 0.0     # 小盘股容量
    
    # 集中度分析
    top5_concentration: float = 0.0     # Top5持仓占比
    top10_concentration: float = 0.0    # Top10持仓占比
    
    # 建议
    recommended_max_capital: float = 0.0  # 建议最大资金
    recommended_position_count: int = 20   # 建议持仓数量


class ImpactCostModel:
    """
    冲击成本模型
    
    基于Almgren等人的市场冲击模型，考虑:
    - 临时冲击 (temporary impact): 执行导致的短期价格偏离
    - 永久冲击 (permanent impact): 对长期价格的影响
    """
    
    def __init__(
        self,
        temporary_impact_coeff: float = 0.5,  # 临时冲击系数
        permanent_impact_coeff: float = 0.1,   # 永久冲击系数
        volatility_factor: float = 1.0         # 波动率因子
    ):
        self.temp_coeff = temporary_impact_coeff
        self.perm_coeff = permanent_impact_coeff
        self.vol_factor = volatility_factor
    
    def estimate_impact_cost(
        self,
        trade_amount: float,          # 交易金额 (元)
        daily_avg_amount: float,     # 日均成交额 (元)
        daily_volatility: float,      # 日波动率
        execution_time_days: int = 1  # 执行时间 (天)
    ) -> Dict[str, float]:
        """
        估计冲击成本
        
        Parameters
        ----------
        trade_amount : float
            计划交易金额
        daily_avg_amount : float
            标的日均成交额
        daily_volatility : float
            标的日收益率波动率
        execution_time_days : int
            计划执行天数
            
        Returns
        -------
        Dict[str, float]
            冲击成本分解
        """
        if daily_avg_amount <= 0:
            return {"total": 1.0, "temporary": 0.5, "permanent": 0.5}
        
        # 交易占比
        trade_ratio = trade_amount / daily_avg_amount
        
        # 临时冲击 (与交易量平方根成正比，与时间平方根成反比)
        temporary = (
            self.temp_coeff * 
            daily_volatility * 
            np.sqrt(trade_ratio / execution_time_days)
        )
        
        # 永久冲击 (与交易量成正比)
        permanent = self.perm_coeff * daily_volatility * trade_ratio
        
        # 总冲击
        total = temporary + permanent
        
        return {
            "total": total,
            "temporary": temporary,
            "permanent": permanent,
            "trade_ratio": trade_ratio
        }
    
    def optimal_execution_time(
        self,
        trade_amount: float,
        daily_avg_amount: float,
        daily_volatility: float,
        urgency_factor: float = 1.0
    ) -> int:
        """
        计算最优执行时间
        
        Parameters
        ----------
        trade_amount : float
            交易金额
        daily_avg_amount : float
            日均成交额
        daily_volatility : float
            日波动率
        urgency_factor : float
            紧急程度因子 (1.0为标准，越大越急)
            
        Returns
        -------
        int
            建议执行天数
        """
        if daily_avg_amount <= 0:
            return 1
        
        trade_ratio = trade_amount / daily_avg_amount
        
        # 基础天数: 交易占比越高，需要越多天数
        base_days = max(1, int(trade_ratio * 5))
        
        # 根据紧急程度调整
        optimal_days = max(1, int(base_days / urgency_factor))
        
        # 上限: 最多5天
        return min(optimal_days, 5)


class CapacityAnalyzer:
    """
    容量分析器
    
    分析单票容量和组合容量，提供投资建议
    """
    
    # 容量阈值配置
    LIQUIDITY_THRESHOLDS = {
        "excellent": {"min_amount": 500_000_000, "max_trade_ratio": 0.05},  # 5亿+, 可买5%
        "good": {"min_amount": 200_000_000, "max_trade_ratio": 0.03},        # 2亿+, 可买3%
        "moderate": {"min_amount": 50_000_000, "max_trade_ratio": 0.02},    # 5000万+, 可买2%
        "poor": {"min_amount": 10_000_000, "max_trade_ratio": 0.01},       # 1000万+, 可买1%
        "avoid": {"min_amount": 0, "max_trade_ratio": 0.005},             # 避开
    }
    
    def __init__(self, impact_model: Optional[ImpactCostModel] = None):
        self.impact_model = impact_model or ImpactCostModel()
    
    def analyze_single_stock(
        self,
        stock_code: str,
        avg_daily_amount: float,      # 日均成交额 (元)
        avg_daily_volume: float,    # 日均成交量 (股)
        volatility: float,          # 波动率
        market_cap: float = 0.0,    # 市值 (元)
        stock_name: str = ""
    ) -> CapacityEstimate:
        """
        分析单票容量
        
        Parameters
        ----------
        stock_code : str
            股票代码
        avg_daily_amount : float
            日均成交额
        avg_daily_volume : float
            日均成交量
        volatility : float
            波动率
        market_cap : float
            市值
        stock_name : str
            股票名称
            
        Returns
        -------
        CapacityEstimate
            容量估计结果
        """
        estimate = CapacityEstimate(
            stock_code=stock_code,
            stock_name=stock_name,
            avg_daily_volume=avg_daily_volume,
            avg_daily_amount=avg_daily_amount,
            avg_turnover_rate=avg_daily_volume / (market_cap / avg_daily_amount) if market_cap > 0 else 0
        )
        
        # 确定流动性等级
        liquidity_level = self._classify_liquidity(avg_daily_amount)
        threshold = self.LIQUIDITY_THRESHOLDS[liquidity_level]
        
        # 计算安全容量
        max_trade_ratio = threshold["max_trade_ratio"]
        estimate.safe_capacity = avg_daily_amount * max_trade_ratio
        estimate.max_capacity = avg_daily_amount * max_trade_ratio * 2  # 最大是安全的2倍
        
        # 计算冲击成本
        impact_10 = self.impact_model.estimate_impact_cost(
            avg_daily_amount * 0.10, avg_daily_amount, volatility, 1
        )
        impact_20 = self.impact_model.estimate_impact_cost(
            avg_daily_amount * 0.20, avg_daily_amount, volatility, 2
        )
        
        estimate.impact_cost_10bp = impact_10["total"] * 10000  # 转为bps
        estimate.impact_cost_20bp = impact_20["total"] * 10000
        
        # 流动性评分 (0-100)
        if avg_daily_amount >= 500_000_000:
            estimate.liquidity_score = 90 + min(10, avg_daily_amount / 1_000_000_000)
        elif avg_daily_amount >= 200_000_000:
            estimate.liquidity_score = 70 + (avg_daily_amount - 200_000_000) / 300_000_000 * 20
        elif avg_daily_amount >= 50_000_000:
            estimate.liquidity_score = 50 + (avg_daily_amount - 50_000_000) / 150_000_000 * 20
        elif avg_daily_amount >= 10_000_000:
            estimate.liquidity_score = 30 + (avg_daily_amount - 10_000_000) / 40_000_000 * 20
        else:
            estimate.liquidity_score = max(0, avg_daily_amount / 10_000_000 * 30)
        
        # 风险标签
        risk_tags = []
        if liquidity_level == "avoid":
            risk_tags.append("流动性差")
        if liquidity_level == "poor":
            risk_tags.append("谨慎交易")
        if estimate.impact_cost_10bp > 50:
            risk_tags.append("冲击成本高")
        if volatility > 0.05:
            risk_tags.append("高波动")
        
        estimate.risk_tags = risk_tags
        
        return estimate
    
    def analyze_portfolio(
        self,
        stock_estimates: List[CapacityEstimate],
        target_positions: int = 20,
        capital: float = 5_000_000
    ) -> PortfolioCapacity:
        """
        分析组合容量
        
        Parameters
        ----------
        stock_estimates : List[CapacityEstimate]
            各股票容量估计
        target_positions : int
            目标持仓数
        capital : float
            计划投入资金
            
        Returns
        -------
        PortfolioCapacity
            组合容量分析
        """
        portfolio = PortfolioCapacity()
        
        if not stock_estimates:
            return portfolio
        
        # 计算总容量
        total_safe = sum(e.safe_capacity for e in stock_estimates)
        total_max = sum(e.max_capacity for e in stock_estimates)
        
        portfolio.total_safe_capacity = total_safe
        portfolio.total_max_capacity = total_max
        
        # 分层统计 (基于成交额)
        large_cap = [e for e in stock_estimates if e.avg_daily_amount >= 500_000_000]
        mid_cap = [e for e in stock_estimates if 100_000_000 <= e.avg_daily_amount < 500_000_000]
        small_cap = [e for e in stock_estimates if e.avg_daily_amount < 100_000_000]
        
        portfolio.large_cap_capacity = sum(e.safe_capacity for e in large_cap)
        portfolio.mid_cap_capacity = sum(e.safe_capacity for e in mid_cap)
        portfolio.small_cap_capacity = sum(e.safe_capacity for e in small_cap)
        
        # 集中度分析
        sorted_by_capacity = sorted(stock_estimates, key=lambda x: x.safe_capacity, reverse=True)
        
        if len(sorted_by_capacity) >= 5:
            top5_cap = sum(e.safe_capacity for e in sorted_by_capacity[:5])
            portfolio.top5_concentration = top5_cap / total_safe if total_safe > 0 else 0
        
        if len(sorted_by_capacity) >= 10:
            top10_cap = sum(e.safe_capacity for e in sorted_by_capacity[:10])
            portfolio.top10_concentration = top10_cap / total_safe if total_safe > 0 else 0
        
        # 建议最大资金
        # 假设每只股票平均持仓，不超过其安全容量的50%
        avg_position_size = capital / target_positions
        feasible_stocks = sum(1 for e in stock_estimates if e.safe_capacity >= avg_position_size * 0.5)
        
        if feasible_stocks >= target_positions:
            portfolio.recommended_max_capital = min(total_safe * 0.5, capital)
        else:
            # 可交易股票不足，降低建议资金
            portfolio.recommended_max_capital = total_safe * 0.3
        
        portfolio.recommended_position_count = min(target_positions, len(stock_estimates))
        
        return portfolio
    
    def _classify_liquidity(self, avg_daily_amount: float) -> str:
        """分类流动性等级"""
        for level, threshold in self.LIQUIDITY_THRESHOLDS.items():
            if avg_daily_amount >= threshold["min_amount"]:
                return level
        return "avoid"
    
    def generate_capacity_report(
        self,
        portfolio: PortfolioCapacity,
        stock_estimates: List[CapacityEstimate]
    ) -> str:
        """生成容量分析报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("容量与冲击成本分析报告")
        lines.append("=" * 60)
        lines.append("")
        
        # 组合容量
        lines.append("【组合容量估计】")
        lines.append(f"  安全容量上限:    ¥{portfolio.total_safe_capacity:,.0f}")
        lines.append(f"  最大容量上限:    ¥{portfolio.total_max_capacity:,.0f}")
        lines.append(f"  建议最大资金:    ¥{portfolio.recommended_max_capital:,.0f}")
        lines.append(f"  建议持仓数量:    {portfolio.recommended_position_count} 只")
        lines.append("")
        
        # 分层容量
        lines.append("【分层容量分布】")
        lines.append(f"  大盘股 (>5亿):   ¥{portfolio.large_cap_capacity:,.0f}")
        lines.append(f"  中盘股 (1-5亿):  ¥{portfolio.mid_cap_capacity:,.0f}")
        lines.append(f"  小盘股 (<1亿):   ¥{portfolio.small_cap_capacity:,.0f}")
        lines.append("")
        
        # 集中度
        lines.append("【集中度分析】")
        lines.append(f"  Top5 容量占比:   {portfolio.top5_concentration*100:.1f}%")
        lines.append(f"  Top10 容量占比:  {portfolio.top10_concentration*100:.1f}%")
        lines.append("")
        
        # 个股明细 (前10)
        lines.append("【个股容量明细 (Top 10)】")
        sorted_stocks = sorted(stock_estimates, key=lambda x: x.liquidity_score, reverse=True)[:10]
        for s in sorted_stocks:
            tags = ", ".join(s.risk_tags) if s.risk_tags else "OK"
            lines.append(f"  {s.stock_code:10s} | 日均成交: ¥{s.avg_daily_amount:>12,.0f} | 安全容量: ¥{s.safe_capacity:>10,.0f} | 评分: {s.liquidity_score:.0f} | {tags}")
        lines.append("")
        
        # 风险提示
        low_liquidity = [s for s in stock_estimates if s.liquidity_score < 50]
        if low_liquidity:
            lines.append("【流动性风险提示】")
            lines.append(f"  发现 {len(low_liquidity)} 只流动性较差的股票:")
            for s in low_liquidity[:5]:
                lines.append(f"    - {s.stock_code}: 日均成交 ¥{s.avg_daily_amount:,.0f}, 冲击成本 {s.impact_cost_10bp:.1f} bps")
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


def estimate_portfolio_capacity(
    stock_data: pd.DataFrame,
    capital: float = 5_000_000,
    target_positions: int = 20
) -> Tuple[PortfolioCapacity, List[CapacityEstimate]]:
    """
    一站式组合容量估计
    
    Parameters
    ----------
    stock_data : pd.DataFrame
        股票数据，包含 [code, name, avg_amount, avg_volume, volatility, market_cap]
    capital : float
        计划投资金额
    target_positions : int
        目标持仓数
        
    Returns
    -------
    Tuple[PortfolioCapacity, List[CapacityEstimate]]
        (组合容量, 个股容量列表)
    """
    analyzer = CapacityAnalyzer()
    
    # 分析个股
    estimates = []
    for _, row in stock_data.iterrows():
        estimate = analyzer.analyze_single_stock(
            stock_code=row.get("code", ""),
            stock_name=row.get("name", ""),
            avg_daily_amount=row.get("avg_amount", 0),
            avg_daily_volume=row.get("avg_volume", 0),
            volatility=row.get("volatility", 0.02),
            market_cap=row.get("market_cap", 0)
        )
        estimates.append(estimate)
    
    # 分析组合
    portfolio = analyzer.analyze_portfolio(estimates, target_positions, capital)
    
    return portfolio, estimates


if __name__ == "__main__":
    print("[CapacityAnalyzer] Module loaded successfully")
    
    # 测试数据
    test_data = pd.DataFrame({
        "code": ["000001.SZ", "000002.SZ", "000333.SZ", "600519.SH", "300750.SZ"],
        "name": ["平安银行", "万科A", "美的集团", "贵州茅台", "宁德时代"],
        "avg_amount": [800_000_000, 600_000_000, 1_200_000_000, 2_500_000_000, 1_500_000_000],
        "avg_volume": [50_000_000, 30_000_000, 20_000_000, 1_000_000, 5_000_000],
        "volatility": [0.025, 0.030, 0.020, 0.018, 0.035],
        "market_cap": [300_000_000_000, 200_000_000_000, 400_000_000_000, 2_000_000_000_000, 800_000_000_000]
    })
    
    portfolio, estimates = estimate_portfolio_capacity(test_data, capital=5_000_000, target_positions=20)
    
    analyzer = CapacityAnalyzer()
    print(analyzer.generate_capacity_report(portfolio, estimates))
