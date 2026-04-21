#!/usr/bin/env python3
"""
Nous Invest - 回测主运行脚本
运行完整回测流程

Usage:
    python run_backtest.py --signal-file ./signals/predictions.csv --output ./reports
    python run_backtest.py --daily  # 运行每日监控
"""

import os
import sys
import argparse
import pandas as pd
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest import (
    run_full_backtest_pipeline,
    DailyMonitor,
    ReportGenerator,
    BacktestReport,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Nous Invest Backtest Runner")
    
    parser.add_argument(
        "--signal-file",
        type=str,
        default="./signals/latest_predictions.csv",
        help="预测信号文件路径"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="./reports",
        help="输出目录"
    )
    
    parser.add_argument(
        "--capital",
        type=float,
        default=5_000_000,
        help="初始资金 (默认500万)"
    )
    
    parser.add_argument(
        "--start-date",
        type=str,
        default="2022-01-01",
        help="回测开始日期"
    )
    
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="回测结束日期 (默认今天)"
    )
    
    parser.add_argument(
        "--strategy-name",
        type=str,
        default="Nous Strategy v0.1",
        help="策略名称"
    )
    
    parser.add_argument(
        "--daily",
        action="store_true",
        help="仅运行每日监控模式"
    )
    
    parser.add_argument(
        "--topk",
        type=int,
        default=20,
        help="每日选股数量"
    )
    
    return parser.parse_args()


def load_predictions(filepath: str) -> pd.DataFrame:
    """加载预测数据"""
    if not os.path.exists(filepath):
        # 尝试从signals目录找最新文件
        signals_dir = os.path.dirname(filepath)
        if os.path.exists(signals_dir):
            csv_files = [f for f in os.listdir(signals_dir) if f.endswith('.csv')]
            if csv_files:
                csv_files.sort(reverse=True)
                filepath = os.path.join(signals_dir, csv_files[0])
                print(f"[Load] 使用最新信号文件: {filepath}")
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"找不到信号文件: {filepath}")
    
    df = pd.read_csv(filepath)
    
    # 标准化列名
    col_mapping = {
        'datetime': 'date',
        'instrument': 'instrument',
        'symbol': 'instrument',
        'stock_code': 'instrument',
        'prediction': 'score',
        'pred': 'score',
        'score': 'score',
    }
    
    for old, new in col_mapping.items():
        if old in df.columns and new not in df.columns:
            df.rename(columns={old: new}, inplace=True)
    
    required_cols = ['date', 'instrument', 'score']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"缺少必需列: {col}")
    
    return df


def run_daily_mode(args):
    """运行每日监控模式"""
    print("="*60)
    print("Nous Invest - 每日监控模式")
    print("="*60)
    
    # 加载信号
    predictions = load_predictions(args.signal_file)
    
    # 运行监控
    from backtest.daily_monitor import run_daily_monitor
    
    results = run_daily_monitor(
        predictions=predictions,
        output_dir=os.path.join(args.output, "daily_signals")
    )
    
    # 打印输出
    print("\n" + results["output_text"])
    
    print(f"\n[Daily] 信号已保存: {results['signal_file']}")
    print(f"[Daily] 健康状态: {results['health']['status']}")
    
    return results


def run_backtest_mode(args):
    """运行完整回测模式"""
    # 加载信号
    predictions = load_predictions(args.signal_file)
    
    # 确定结束日期
    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    
    # 运行完整回测
    results = run_full_backtest_pipeline(
        predictions=predictions,
        capital=args.capital,
        start_date=args.start_date,
        end_date=end_date,
        output_dir=args.output,
        strategy_name=args.strategy_name
    )
    
    return results


def main():
    args = parse_args()
    
    # 确保输出目录存在
    os.makedirs(args.output, exist_ok=True)
    
    try:
        if args.daily:
            # 仅运行每日监控
            results = run_daily_mode(args)
        else:
            # 运行完整回测
            results = run_backtest_mode(args)
        
        print("\n✅ 执行完成")
        return 0
        
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
