"""
Nous Invest - 每日信号输出与风险监控
Module 7: Daily Signal Output & Risk Monitoring

每日监控体系:
- 信号生成与输出
- 风险指标监控
- 预警系统
- 健康检查
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import os


class RiskLevel(Enum):
    """风险等级"""
    NORMAL = "正常"
    WARNING = "警告"
    CRITICAL = "严重"
    EMERGENCY = "紧急"


@dataclass
class DailySignal:
    """每日信号数据结构"""
    date: str
    stock_code: str
    stock_name: str = ""
    score: float = 0.0
    rank: int = 0
    
    # 信号元数据
    signal_source: str = ""  # 信号来源模型
    confidence: float = 0.0   # 置信度
    
    # 特征值
    features: Dict[str, float] = field(default_factory=dict)


@dataclass
class RiskAlert:
    """风险预警"""
    timestamp: datetime
    level: RiskLevel
    category: str
    message: str
    details: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "category": self.category,
            "message": self.message,
            "details": self.details
        }


@dataclass
class PortfolioRisk:
    """组合风险指标"""
    date: str
    
    # 敞口指标
    total_exposure: float = 0.0       # 总敞口
    long_exposure: float = 0.0        # 多头敞口
    short_exposure: float = 0.0       # 空头敞口
    
    # 集中度
    top5_concentration: float = 0.0   # Top5集中度
    top10_concentration: float = 0.0  # Top10集中度
    sector_concentration: float = 0.0 # 行业集中度
    
    # 风险指标
    portfolio_beta: float = 1.0       # 组合Beta
    portfolio_volatility: float = 0.0 # 组合波动率
    var_95: float = 0.0               # 95% VaR
    expected_shortfall: float = 0.0   # 期望损失
    
    # 流动性
    avg_liquidity_score: float = 0.0  # 平均流动性评分
    days_to_liquidate: int = 0        # 平仓所需天数


class DailyMonitor:
    """
    每日监控器
    
    功能:
    1. 信号输出格式化
    2. 风险指标计算
    3. 预警生成
    4. 健康检查
    """
    
    # 预警阈值配置
    RISK_THRESHOLDS = {
        "concentration": {
            "top5_warning": 0.40,
            "top5_critical": 0.50,
            "sector_warning": 0.30,
            "sector_critical": 0.50,
        },
        "drawdown": {
            "warning": 0.10,    # 10%回撤警告
            "critical": 0.15,   # 15%回撤严重
            "emergency": 0.20,  # 20%回撤紧急
        },
        "liquidity": {
            "warning": 50,      # 流动性评分<50警告
            "critical": 30,     # <30严重
        },
        "volatility": {
            "warning": 0.25,    # 日波动>25%警告
            "critical": 0.35,  # >35%严重
        }
    }
    
    def __init__(self, output_dir: str = "./signals"):
        self.output_dir = output_dir
        self.alerts: List[RiskAlert] = []
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_daily_signals(
        self,
        predictions: pd.DataFrame,
        topk: int = 20,
        date: Optional[str] = None
    ) -> List[DailySignal]:
        """
        生成每日TopK信号
        
        Parameters
        ----------
        predictions : pd.DataFrame
            预测分数，columns=['date', 'instrument', 'score', ...]
        topk : int
            选取前K只股票
        date : str, optional
            指定日期，默认最新日期
            
        Returns
        -------
        List[DailySignal]
            每日信号列表
        """
        if date is None:
            date = predictions["date"].max()
        
        # 筛选当日数据
        day_data = predictions[predictions["date"] == date].copy()
        
        # 按分数排序
        day_data = day_data.sort_values("score", ascending=False)
        
        # 取TopK
        top_stocks = day_data.head(topk).reset_index(drop=True)
        
        # 构造信号
        signals = []
        for rank, (_, row) in enumerate(top_stocks.iterrows(), 1):
            signal = DailySignal(
                date=str(date),
                stock_code=row.get("instrument", ""),
                stock_name=row.get("name", ""),
                score=float(row.get("score", 0)),
                rank=rank,
                signal_source=row.get("model", "unknown"),
                confidence=float(row.get("confidence", 0.5)),
                features={k: float(v) for k, v in row.items() if k not in ["date", "instrument", "score", "name", "model", "confidence"]}
            )
            signals.append(signal)
        
        return signals
    
    def calculate_portfolio_risk(
        self,
        positions: pd.DataFrame,     # 持仓数据
        returns: pd.DataFrame,       # 历史收益
        market_data: Optional[pd.DataFrame] = None
    ) -> PortfolioRisk:
        """
        计算组合风险指标
        
        Parameters
        ----------
        positions : pd.DataFrame
            当前持仓，columns=['code', 'weight', 'sector', ...]
        returns : pd.DataFrame
            历史收益率矩阵
        market_data : pd.DataFrame, optional
            市场数据
            
        Returns
        -------
        PortfolioRisk
            组合风险指标
        """
        today = datetime.now().strftime("%Y-%m-%d")
        risk = PortfolioRisk(date=today)
        
        if positions.empty:
            return risk
        
        # 敞口计算
        weights = positions["weight"].values if "weight" in positions.columns else np.ones(len(positions)) / len(positions)
        risk.total_exposure = weights.sum()
        risk.long_exposure = weights[weights > 0].sum() if any(weights > 0) else 0
        risk.short_exposure = abs(weights[weights < 0].sum()) if any(weights < 0) else 0
        
        # 集中度
        sorted_weights = np.sort(weights)[::-1]
        risk.top5_concentration = sorted_weights[:5].sum() if len(weights) >= 5 else weights.sum()
        risk.top10_concentration = sorted_weights[:10].sum() if len(weights) >= 10 else weights.sum()
        
        # 行业集中度
        if "sector" in positions.columns:
            sector_weights = positions.groupby("sector")["weight"].sum()
            risk.sector_concentration = sector_weights.max()
        
        # 波动率和VaR
        if not returns.empty:
            # 组合收益
            portfolio_returns = returns.dot(weights[:len(returns.columns)])
            risk.portfolio_volatility = portfolio_returns.std() * np.sqrt(252)
            
            # 95% VaR (历史模拟)
            risk.var_95 = np.percentile(portfolio_returns, 5)
            
            # 期望损失 (CVaR)
            risk.expected_shortfall = portfolio_returns[portfolio_returns <= risk.var_95].mean()
        
        return risk
    
    def check_risk_alerts(
        self,
        portfolio_risk: Optional[PortfolioRisk],
        current_drawdown: float = 0.0,
        weekly_metrics: Optional[Dict] = None
    ) -> List[RiskAlert]:
        """
        检查风险预警
        
        Parameters
        ----------
        portfolio_risk : PortfolioRisk, optional
            组合风险指标
        current_drawdown : float
            当前回撤
        weekly_metrics : dict, optional
            周度指标
            
        Returns
        -------
        List[RiskAlert]
            预警列表
        """
        alerts = []
        now = datetime.now()
        
        # 集中度预警 (仅当portfolio_risk存在时)
        if portfolio_risk is not None:
            thresholds = self.RISK_THRESHOLDS["concentration"]
            
            if portfolio_risk.top5_concentration > thresholds["top5_critical"]:
                alerts.append(RiskAlert(
                    timestamp=now,
                    level=RiskLevel.CRITICAL,
                    category="集中度",
                    message=f"Top5集中度 {portfolio_risk.top5_concentration:.1%} 超过 {thresholds['top5_critical']:.1%}",
                    details={"top5": portfolio_risk.top5_concentration}
                ))
            elif portfolio_risk.top5_concentration > thresholds["top5_warning"]:
                alerts.append(RiskAlert(
                    timestamp=now,
                    level=RiskLevel.WARNING,
                    category="集中度",
                    message=f"Top5集中度 {portfolio_risk.top5_concentration:.1%} 超过 {thresholds['top5_warning']:.1%}",
                    details={"top5": portfolio_risk.top5_concentration}
                ))
            
            # 行业集中度
            if portfolio_risk.sector_concentration > thresholds["sector_critical"]:
                alerts.append(RiskAlert(
                    timestamp=now,
                    level=RiskLevel.CRITICAL,
                    category="行业集中度",
                    message=f"最大行业占比 {portfolio_risk.sector_concentration:.1%} 超过 {thresholds['sector_critical']:.1%}",
                    details={"sector": portfolio_risk.sector_concentration}
                ))
        
        # 回撤预警
        dd_thresholds = self.RISK_THRESHOLDS["drawdown"]
        
        if current_drawdown > dd_thresholds["emergency"]:
            alerts.append(RiskAlert(
                timestamp=now,
                level=RiskLevel.EMERGENCY,
                category="回撤",
                message=f"当前回撤 {current_drawdown:.1%} 超过 {dd_thresholds['emergency']:.1%}，触发紧急预警",
                details={"drawdown": current_drawdown}
            ))
        elif current_drawdown > dd_thresholds["critical"]:
            alerts.append(RiskAlert(
                timestamp=now,
                level=RiskLevel.CRITICAL,
                category="回撤",
                message=f"当前回撤 {current_drawdown:.1%} 超过 {dd_thresholds['critical']:.1%}",
                details={"drawdown": current_drawdown}
            ))
        elif current_drawdown > dd_thresholds["warning"]:
            alerts.append(RiskAlert(
                timestamp=now,
                level=RiskLevel.WARNING,
                category="回撤",
                message=f"当前回撤 {current_drawdown:.1%} 超过 {dd_thresholds['warning']:.1%}",
                details={"drawdown": current_drawdown}
            ))
        
        # 周超额夏普预警
        if weekly_metrics and "weekly_alpha_sharpe" in weekly_metrics:
            sharpe = weekly_metrics["weekly_alpha_sharpe"]
            if sharpe < 0:
                alerts.append(RiskAlert(
                    timestamp=now,
                    level=RiskLevel.WARNING,
                    category="绩效",
                    message=f"周超额夏普为负 ({sharpe:.2f})，策略表现不佳",
                    details={"sharpe": sharpe}
                ))
        
        self.alerts = alerts
        return alerts
    
    def health_check(
        self,
        signal_df: pd.DataFrame,
        required_stocks: int = 20,
        max_missing_ratio: float = 0.1
    ) -> Dict[str, any]:
        """
        系统健康检查
        
        Parameters
        ----------
        signal_df : pd.DataFrame
            信号数据
        required_stocks : int
            要求的最小股票数
        max_missing_ratio : float
            最大允许缺失比例
            
        Returns
        -------
        Dict
            健康检查结果
        """
        checks = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "checks": {}
        }
        
        # 检查1: 数据覆盖
        if signal_df.empty:
            checks["status"] = "critical"
            checks["checks"]["data_coverage"] = {
                "status": "fail",
                "message": "信号数据为空"
            }
        else:
            latest_date = signal_df["date"].max()
            today = datetime.now().strftime("%Y-%m-%d")
            
            if str(latest_date) != today:
                checks["checks"]["data_freshness"] = {
                    "status": "warning",
                    "message": f"最新数据日期 {latest_date} 不等于今天 {today}"
                }
            else:
                checks["checks"]["data_freshness"] = {
                    "status": "pass",
                    "message": f"数据已更新至 {latest_date}"
                }
            
            # 检查信号数量
            day_count = len(signal_df[signal_df["date"] == latest_date])
            if day_count < required_stocks:
                checks["checks"]["signal_count"] = {
                    "status": "warning",
                    "message": f"信号数量 {day_count} 少于要求 {required_stocks}"
                }
            else:
                checks["checks"]["signal_count"] = {
                    "status": "pass",
                    "message": f"信号数量 {day_count} OK"
                }
        
        # 检查评分分布
        if "score" in signal_df.columns:
            scores = signal_df["score"]
            if scores.std() < 0.001:
                checks["checks"]["signal_variance"] = {
                    "status": "warning",
                    "message": "信号方差过小，可能所有股票得分相近"
                }
            else:
                checks["checks"]["signal_variance"] = {
                    "status": "pass",
                    "message": f"信号标准差 {scores.std():.4f}"
                }
        
        # 整体状态
        fail_count = sum(1 for c in checks["checks"].values() if c["status"] == "fail")
        warning_count = sum(1 for c in checks["checks"].values() if c["status"] == "warning")
        
        if fail_count > 0:
            checks["status"] = "critical"
        elif warning_count > 0:
            checks["status"] = "warning"
        
        return checks
    
    def save_signals(
        self,
        signals: List[DailySignal],
        filename: Optional[str] = None
    ) -> str:
        """
        保存信号到文件
        
        Returns
        -------
        str
            保存的文件路径
        """
        if filename is None:
            date = signals[0].date if signals else datetime.now().strftime("%Y%m%d")
            filename = f"signals_{date}.json"
        
        filepath = os.path.join(self.output_dir, filename)
        
        # 转为字典
        data = {
            "generated_at": datetime.now().isoformat(),
            "count": len(signals),
            "signals": [
                {
                    "date": s.date,
                    "stock_code": s.stock_code,
                    "stock_name": s.stock_name,
                    "score": s.score,
                    "rank": s.rank,
                    "confidence": s.confidence,
                    "features": s.features
                }
                for s in signals
            ]
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def format_signal_output(
        self,
        signals: List[DailySignal],
        portfolio_risk: Optional[PortfolioRisk] = None,
        alerts: Optional[List[RiskAlert]] = None
    ) -> str:
        """
        格式化信号输出文本
        
        Returns
        -------
        str
            格式化文本
        """
        lines = []
        
        # 标题
        lines.append("=" * 60)
        lines.append("Nous Invest - 每日选股信号")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)
        lines.append("")
        
        # 预警区
        if alerts:
            lines.append("【风险预警】")
            for alert in alerts:
                emoji = {"正常": "✅", "警告": "⚠️", "严重": "🚨", "紧急": "🔴"}.get(alert.level.value, "")
                lines.append(f"  {emoji} [{alert.category}] {alert.message}")
            lines.append("")
        
        # 信号列表
        lines.append(f"【Top {len(signals)} 选股信号】")
        lines.append(f"{'排名':<6}{'代码':<12}{'名称':<10}{'分数':>10}{'置信度':>10}")
        lines.append("-" * 60)
        
        for s in signals:
            name = s.stock_name[:8] if s.stock_name else "-"
            lines.append(f"{s.rank:<6}{s.stock_code:<12}{name:<10}{s.score:>10.4f}{s.confidence:>10.1%}")
        
        lines.append("")
        
        # 组合风险
        if portfolio_risk:
            lines.append("【组合风险指标】")
            lines.append(f"  总敞口:      {portfolio_risk.total_exposure:>8.2%}")
            lines.append(f"  Top5集中度:  {portfolio_risk.top5_concentration:>8.2%}")
            lines.append(f"  组合波动率:  {portfolio_risk.portfolio_volatility:>8.2%}")
            lines.append(f"  95% VaR:     {portfolio_risk.var_95:>8.4f}")
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


def run_daily_monitor(
    predictions: pd.DataFrame,
    positions: Optional[pd.DataFrame] = None,
    returns: Optional[pd.DataFrame] = None,
    current_drawdown: float = 0.0,
    output_dir: str = "./signals"
) -> Dict:
    """
    一站式每日监控
    
    Parameters
    ----------
    predictions : pd.DataFrame
        预测数据
    positions : pd.DataFrame, optional
        当前持仓
    returns : pd.DataFrame, optional
        历史收益
    current_drawdown : float
        当前回撤
    output_dir : str
        输出目录
        
    Returns
    -------
    Dict
        监控结果
    """
    monitor = DailyMonitor(output_dir=output_dir)
    
    # 生成信号
    signals = monitor.generate_daily_signals(predictions, topk=20)
    
    # 计算风险
    portfolio_risk = None
    if positions is not None and returns is not None:
        portfolio_risk = monitor.calculate_portfolio_risk(positions, returns)
    
    # 检查预警
    alerts = monitor.check_risk_alerts(portfolio_risk, current_drawdown)
    
    # 健康检查
    health = monitor.health_check(predictions)
    
    # 保存信号
    signal_file = monitor.save_signals(signals)
    
    # 格式化输出
    output_text = monitor.format_signal_output(signals, portfolio_risk, alerts)
    
    return {
        "signals": signals,
        "portfolio_risk": portfolio_risk,
        "alerts": alerts,
        "health": health,
        "signal_file": signal_file,
        "output_text": output_text
    }


if __name__ == "__main__":
    print("[DailyMonitor] Module loaded successfully")
    
    # 测试数据
    test_predictions = pd.DataFrame({
        "date": ["2026-04-16"] * 25,
        "instrument": [f"{i:06d}.SZ" for i in range(1, 26)],
        "score": np.random.randn(25).cumsum(),
        "name": [f"股票{i}" for i in range(1, 26)],
        "confidence": np.random.uniform(0.5, 0.9, 25)
    })
    
    result = run_daily_monitor(test_predictions, current_drawdown=0.08)
    
    print(result["output_text"])
    print("\n健康检查:", result["health"]["status"])
