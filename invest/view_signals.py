#!/usr/bin/env python3
"""
Nous Invest - 信号查看工具
快速查看最新选股信号和模型指标
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

SIGNALS_DIR = Path(__file__).parent / 'signals'


def get_latest_signals(n: int = 20):
    """获取最新信号"""
    signal_files = list(SIGNALS_DIR.glob('signal_*_round2_simple.csv'))
    if not signal_files:
        print("❌ 未找到信号文件")
        return None, None
    
    latest_file = max(signal_files, key=lambda p: p.stat().st_mtime)
    date_str = latest_file.stem.split('_')[1]
    
    df = pd.read_csv(latest_file)
    df = df.sort_values('pred', ascending=False)
    
    return latest_file, df.head(n)


def get_latest_metrics():
    """获取最新指标"""
    metrics_files = list(SIGNALS_DIR.glob('metrics_*_round2_simple.json'))
    if not metrics_files:
        return None
    
    latest_file = max(metrics_files, key=lambda p: p.stat().st_mtime)
    
    with open(latest_file) as f:
        return json.load(f)


def print_summary():
    """打印信号摘要"""
    print("=" * 70)
    print("🎯 Nous Invest - 最新选股信号")
    print("=" * 70)
    
    # 加载信号
    signal_file, signals = get_latest_signals(n=20)
    if signals is None:
        return
    
    date_str = signal_file.stem.split('_')[1]
    signal_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    
    # 加载指标
    metrics = get_latest_metrics()
    
    print(f"\n📅 信号日期: {signal_date}")
    print(f"📊 股票数量: {len(signals)}\n")
    
    if metrics:
        print("📈 模型指标:")
        print(f"   IC Mean:       {metrics.get('ic_mean', 0):+.4f}")
        print(f"   ICIR:          {metrics.get('icir', 0):+.4f}")
        print(f"   年化 IR:       {metrics.get('annual_ir', 0):+.4f}")
        print(f"   IC > 0 比例:   {metrics.get('ic_positive_ratio', 0):.1%}")
        print()
    
    print("🏆 Top 20 选股信号:")
    print("-" * 70)
    print(f"{'排名':<4} {'股票代码':<12} {'预测分数':<10} {'收盘价':<10} {'信号强度'}")
    print("-" * 70)
    
    for i, (_, row) in enumerate(signals.iterrows(), 1):
        score = row['pred']
        strength = "🔥🔥🔥" if score > 0.03 else "🔥🔥" if score > 0.02 else "🔥" if score > 0.01 else "📊"
        print(f"{i:<4} {row['ts_code']:<12} {score:+.6f}  {row['close']:<10.2f} {strength}")
    
    print("-" * 70)
    
    # 统计
    avg_score = signals['pred'].mean()
    positive_pct = (signals['pred'] > 0).mean()
    print(f"\n📊 统计:")
    print(f"   平均预测分数: {avg_score:+.4f}")
    print(f"   看涨比例: {positive_pct:.1%}")
    
    print("\n" + "=" * 70)


def export_signal_list(format: str = 'txt'):
    """导出信号列表"""
    signal_file, signals = get_latest_signals(n=50)
    if signals is None:
        return
    
    date_str = signal_file.stem.split('_')[1]
    
    if format == 'txt':
        output_file = SIGNALS_DIR / f'top_signals_{date_str}.txt'
        with open(output_file, 'w') as f:
            f.write(f"Nous Invest - Top Signals ({date_str})\n")
            f.write("=" * 50 + "\n\n")
            for i, (_, row) in enumerate(signals.iterrows(), 1):
                f.write(f"{i:2d}. {row['ts_code']}  score={row['pred']:+.4f}\n")
        print(f"✅ 已导出: {output_file}")
    
    elif format == 'json':
        output_file = SIGNALS_DIR / f'top_signals_{date_str}.json'
        signals_data = signals[['ts_code', 'pred', 'close']].to_dict('records')
        with open(output_file, 'w') as f:
            json.dump({
                'date': date_str,
                'signals': signals_data
            }, f, indent=2)
        print(f"✅ 已导出: {output_file}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Nous Invest Signal Viewer')
    parser.add_argument('--export', choices=['txt', 'json'], help='Export format')
    parser.add_argument('--top', type=int, default=20, help='Number of top signals to show')
    args = parser.parse_args()
    
    if args.export:
        export_signal_list(args.export)
    else:
        print_summary()
