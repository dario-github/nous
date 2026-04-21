"""
Nous Invest - 回测与评估体系 (Backtest & Evaluation)
Module 5-7: Qlib回测框架、周超额指标、容量分析、每日监控、报告模板

本模块提供完整的量化策略回测与评估能力:

- qlib_backtest: Qlib回测框架封装
- weekly_metrics: 周超额收益评估指标
- capacity_analyzer: 容量与冲击成本分析
- daily_monitor: 每日信号输出与风险监控
- report_template: 回测报告模板

使用示例:
    from backtest import run_full_backtest_pipeline
    
    results = run_full_backtest_pipeline(
        predictions=signal_df,
        positions=None,
        capital=5_000_000,
        output_dir="./reports"
    )
"""

from .qlib_backtest import (
    QlibBacktester,
    BacktestConfig,
    create_signal_df,
    run_simple_backtest,
)

from .weekly_metrics import (
    WeeklyMetrics,
    WeeklyAlphaCalculator,
    calculate_weekly_alpha_metrics,
)

from .capacity_analyzer import (
    CapacityEstimate,
    PortfolioCapacity,
    ImpactCostModel,
    CapacityAnalyzer,
    estimate_portfolio_capacity,
)

from .daily_monitor import (
    DailySignal,
    RiskAlert,
    RiskLevel,
    PortfolioRisk,
    DailyMonitor,
    run_daily_monitor,
)

from .report_template import (
    BacktestReport,
    ReportGenerator,
    generate_full_backtest_report,
)

__version__ = "0.1.0"
__all__ = [
    # Qlib回测
    "QlibBacktester",
    "BacktestConfig",
    "create_signal_df",
    "run_simple_backtest",
    
    # 周超额
    "WeeklyMetrics",
    "WeeklyAlphaCalculator",
    "calculate_weekly_alpha_metrics",
    
    # 容量分析
    "CapacityEstimate",
    "PortfolioCapacity",
    "ImpactCostModel",
    "CapacityAnalyzer",
    "estimate_portfolio_capacity",
    
    # 每日监控
    "DailySignal",
    "RiskAlert",
    "RiskLevel",
    "PortfolioRisk",
    "DailyMonitor",
    "run_daily_monitor",
    
    # 报告模板
    "BacktestReport",
    "ReportGenerator",
    "generate_full_backtest_report",
]


def run_full_backtest_pipeline(
    predictions: "pd.DataFrame",
    positions: "Optional[pd.DataFrame]" = None,
    capital: float = 5_000_000,
    start_date: str = "2022-01-01",
    end_date: str = "2025-12-31",
    output_dir: str = "./backtest/results",
    strategy_name: str = "Nous Strategy"
) -> dict:
    """
    一站式完整回测流程
    
    Parameters
    ----------
    predictions : pd.DataFrame
        预测信号，包含 [date, instrument, score]
    positions : pd.DataFrame, optional
        当前持仓
    capital : float
        初始资金
    start_date : str
    end_date : str
    output_dir : str
    strategy_name : str
    
    Returns
    -------
    dict
        完整回测结果
    """
    import os
    import pandas as pd
    from datetime import datetime
    
    os.makedirs(output_dir, exist_ok=True)
    
    print("="*60)
    print("Nous Invest - 完整回测流程")
    print("="*60)
    
    # 1. Qlib回测
    print("\n[1/5] 运行Qlib回测...")
    from .qlib_backtest import QlibBacktester, BacktestConfig
    
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        total_capital=capital
    )
    backtester = QlibBacktester(config)
    
    # 准备信号
    signal_df = create_signal_df(predictions)
    backtest_results = backtester.run_backtest(signal_df)
    
    # 获取收益序列
    strategy_returns = backtester.get_returns_series()
    benchmark_returns = backtester.get_benchmark_returns()
    
    print(f"  - 回测完成: {len(strategy_returns)} 个交易日")
    
    # 2. 周超额指标
    print("\n[2/5] 计算周超额指标...")
    from .weekly_metrics import WeeklyAlphaCalculator
    
    calculator = WeeklyAlphaCalculator()
    weekly_alpha = calculator.calculate_weekly_alpha(
        strategy_returns, benchmark_returns
    )
    weekly_metrics = calculator.calculate_metrics(
        weekly_alpha, strategy_returns
    )
    
    print(f"  - 平均周超额: {weekly_metrics.weekly_alpha_mean*100:+.4f}%")
    print(f"  - 周超额夏普: {weekly_metrics.weekly_alpha_sharpe:.2f}")
    
    # 3. 容量分析
    print("\n[3/5] 分析组合容量...")
    from .capacity_analyzer import CapacityAnalyzer, PortfolioCapacity
    
    # 构造模拟容量数据（实际应从持仓计算）
    analyzer = CapacityAnalyzer()
    
    # 简化的容量估计（实际应基于真实成交额数据）
    portfolio_capacity = PortfolioCapacity(
        total_safe_capacity=capital * 2,  # 假设可容纳2倍资金
        total_max_capacity=capital * 4,
        recommended_max_capital=capital
    )
    
    print(f"  - 安全容量: ¥{portfolio_capacity.total_safe_capacity:,.0f}")
    
    # 4. 每日监控
    print("\n[4/5] 生成每日监控...")
    from .daily_monitor import DailyMonitor
    
    monitor = DailyMonitor(output_dir=os.path.join(output_dir, "signals"))
    signals = monitor.generate_daily_signals(predictions, topk=20)
    health = monitor.health_check(predictions)
    
    print(f"  - 生成 {len(signals)} 个信号")
    print(f"  - 健康状态: {health['status']}")
    
    # 5. 生成报告
    print("\n[5/5] 生成回测报告...")
    from .report_template import ReportGenerator
    
    generator = ReportGenerator()
    report = generator.generate_report(
        backtest_results,
        weekly_metrics,
        portfolio_capacity,
        strategy_name
    )
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = os.path.join(output_dir, f"backtest_report_{timestamp}.md")
    generator.save_report(report, md_path, "markdown")
    
    print(f"  - 报告保存: {md_path}")
    
    # 打印摘要
    print("\n" + "="*60)
    print("回测结果摘要")
    print("="*60)
    summary = backtester.summary()
    for key, value in summary.items():
        print(f"  {key:20s}: {value:.4f}")
    print(f"  {'weekly_alpha_sharpe':20s}: {weekly_metrics.weekly_alpha_sharpe:.4f}")
    print("="*60)
    
    return {
        "backtest_results": backtest_results,
        "weekly_metrics": weekly_metrics,
        "portfolio_capacity": portfolio_capacity,
        "daily_signals": signals,
        "health_check": health,
        "report": report,
        "report_path": md_path
    }
