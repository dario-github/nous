"""
Nous Invest - Qlib回测框架
Module 5: 回测引擎 (Backtest Engine)
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

# Qlib imports (with fallback for missing dependencies)
try:
    from qlib.config import REG_CN
    from qlib.data import D
    from qlib.data.dataset.loader import QlibDataLoader
    from qlib.contrib.strategy import TopkDropoutStrategy
    from qlib.backtest import backtest as qlib_backtest_func
    from qlib.backtest.executor import SimulatorExecutor
    QLIB_AVAILABLE = True
except ImportError as e:
    QLIB_AVAILABLE = False
    print(f"[Warning] Qlib not fully available: {e}")
    # Create dummy classes for type hints
    class TopkDropoutStrategy:
        pass
    class SimulatorExecutor:
        pass


@dataclass
class BacktestConfig:
    """回测配置"""
    start_date: str = "2022-01-01"
    end_date: str = "2025-12-31"
    benchmark: str = "SH000905"  # 中证500
    topk: int = 20
    n_drop: int = 5
    hold_days: int = 5  # 周调仓
    
    # 成本设置
    open_cost: float = 0.0015  # 千1.5 开仓
    close_cost: float = 0.0015  # 千1.5 平仓
    min_cost: float = 5  # 最低佣金
    
    # 滑点
    slippage: float = 0.001  # 千1滑点
    
    # 容量限制
    max_position_per_stock: float = 0.15  # 单票最大15%
    total_capital: float = 5_000_000  # 500万初始资金


class QlibBacktester:
    """
    Qlib回测框架封装
    支持周频调仓、成本模拟、滑点估计
    """
    
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.results = {}
        
    def run_backtest(
        self,
        signal_df: pd.DataFrame,
        label_df: Optional[pd.DataFrame] = None,
        config: Optional[BacktestConfig] = None
    ) -> Dict[str, Any]:
        """
        运行回测
        
        Parameters
        ----------
        signal_df : pd.DataFrame
            预测分数 DataFrame with index=(date, instrument), columns=['score']
        label_df : pd.DataFrame, optional
            标签数据 for IC analysis
        config : BacktestConfig, optional
            回测配置
            
        Returns
        -------
        Dict[str, Any]
            回测结果
        """
        if config:
            self.config = config
        cfg = self.config
        
        # 准备回测参数
        strategy_config = {
            "class": "TopkDropoutStrategy",
            "module_path": "qlib.contrib.strategy",
            "kwargs": {
                "signal": signal_df,
                "topk": cfg.topk,
                "n_drop": cfg.n_drop,
                "hold_days": cfg.hold_days,
                "only_tradable": True,
            }
        }
        
        executor_config = {
            "class": "SimulatorExecutor",
            "module_path": "qlib.backtest.executor",
            "kwargs": {
                "time_per_step": "day",
                "generate_portfolio_metrics": True,
                "verbose": False,
            }
        }
        
        # 回测参数
        backtest_config = {
            "start_time": cfg.start_date,
            "end_time": cfg.end_date,
            "account": cfg.total_capital,
            "benchmark": cfg.benchmark,
            "exchange_kwargs": {
                "limit_threshold": 0.095,  # 涨跌停限制
                "deal_price": "close",  # 收盘价成交
                "open_cost": cfg.open_cost,
                "close_cost": cfg.close_cost,
                "min_cost": cfg.min_cost,
                "slippage": cfg.slippage,
            }
        }
        
        print(f"[Backtest] Running backtest from {cfg.start_date} to {cfg.end_date}")
        print(f"[Backtest] Benchmark: {cfg.benchmark}, TopK: {cfg.topk}, Hold: {cfg.hold_days} days")
        
        try:
            # 执行回测
            portfolio_metric, indicator = qlib_backtest_func(
                start_time=cfg.start_date,
                end_time=cfg.end_date,
                strategy=strategy_config,
                executor=executor_config,
                account=cfg.total_capital,
                benchmark=cfg.benchmark,
                exchange_kwargs=backtest_config["exchange_kwargs"],
            )
            
            # 分析结果
            analysis = dict()
            if label_df is not None:
                analysis["model"] = analysis_model.analyze_model(
                    pred_df=signal_df, label_df=label_df
                )
            
            # 提取绩效指标
            self.results = {
                "portfolio_metric": portfolio_metric,
                "indicator": indicator,
                "analysis": analysis,
                "config": cfg,
            }
            
            return self.results
            
        except Exception as e:
            print(f"[Backtest Error] {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
    
    def get_returns_series(self) -> pd.Series:
        """获取策略收益率序列"""
        if "indicator" not in self.results:
            return pd.Series()
        
        indicator = self.results["indicator"]
        if isinstance(indicator, dict) and "return" in indicator:
            return indicator["return"]
        return pd.Series()
    
    def get_benchmark_returns(self) -> pd.Series:
        """获取基准收益率序列"""
        if "indicator" not in self.results:
            return pd.Series()
        
        indicator = self.results["indicator"]
        if isinstance(indicator, dict) and "bench" in indicator:
            return indicator["bench"]
        return pd.Series()
    
    def summary(self) -> Dict[str, float]:
        """获取回测摘要"""
        if "indicator" not in self.results:
            return {}
        
        indicator = self.results["indicator"]
        if not isinstance(indicator, dict):
            return {}
        
        summary = {}
        
        # 年化收益率
        if "annualized_return" in indicator:
            summary["annual_return"] = indicator["annualized_return"]
        
        # 年化波动
        if "annualized_volatility" in indicator:
            summary["annual_volatility"] = indicator["annualized_volatility"]
        
        # 最大回撤
        if "max_drawdown" in indicator:
            summary["max_drawdown"] = indicator["max_drawdown"]
        
        # 夏普比率
        if "sharpe_ratio" in indicator:
            summary["sharpe_ratio"] = indicator["sharpe_ratio"]
        
        # 信息比率 (相对基准)
        if "information_ratio" in indicator:
            summary["information_ratio"] = indicator["information_ratio"]
        
        return summary


def create_signal_df(
    predictions: pd.DataFrame,
    score_col: str = "score"
) -> pd.DataFrame:
    """
    从预测结果创建Qlib格式的signal DataFrame
    
    Parameters
    ----------
    predictions : pd.DataFrame
        预测数据，必须包含 [date, instrument, score_col]
    score_col : str
        预测分数列名
        
    Returns
    -------
    pd.DataFrame
        Qlib格式 signal DataFrame
    """
    # 确保有必要的列
    required_cols = ["date", "instrument"]
    for col in required_cols:
        if col not in predictions.columns:
            raise ValueError(f"Missing required column: {col}")
    
    if score_col not in predictions.columns:
        raise ValueError(f"Missing score column: {score_col}")
    
    # 设置multi-index
    signal_df = predictions.copy()
    signal_df = signal_df.set_index(["date", "instrument"])[[score_col]]
    signal_df.columns = ["score"]
    
    return signal_df


def run_simple_backtest(
    signal_df: pd.DataFrame,
    start_date: str = "2023-01-01",
    end_date: str = "2025-12-31",
    topk: int = 20,
    hold_days: int = 5
) -> Dict[str, Any]:
    """
    简化版回测入口
    
    Parameters
    ----------
    signal_df : pd.DataFrame
        预测信号，index=(date, instrument), columns=['score']
    start_date : str
    end_date : str
    topk : int
        持仓数量
    hold_days : int
        调仓周期
        
    Returns
    -------
    Dict[str, Any]
        回测结果
    """
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        topk=topk,
        hold_days=hold_days
    )
    
    backtester = QlibBacktester(config)
    results = backtester.run_backtest(signal_df)
    
    # 打印摘要
    summary = backtester.summary()
    print("\n" + "="*50)
    print("回测结果摘要")
    print("="*50)
    for key, value in summary.items():
        print(f"{key:20s}: {value:.4f}")
    print("="*50)
    
    return results


if __name__ == "__main__":
    # 测试代码
    print("[QlibBacktest] Module loaded successfully")
    print(f"[QlibBacktest] Default config: {BacktestConfig()}")
