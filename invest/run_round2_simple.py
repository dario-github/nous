"""
Nous Invest — 第二轮简化版：直接用 LightGBM 训练，绕过 Alpha158 特征计算
使用原始 OHLCV + 简单技术指标
"""
import multiprocessing
multiprocessing.set_start_method('fork', force=True)

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import lightgbm as lgb
import json

# 加载 tushare 数据
df = pd.read_csv("data/tushare_csi300_202310_202604.csv")
print(f"原始数据: {len(df)} 行")

# 数据预处理
df['date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
df['instrument'] = df['ts_code'].apply(lambda x: x.replace('.SH', '').replace('.SZ', ''))
df = df.sort_values(['ts_code', 'date'])

# 计算简单技术指标（价量因子）
def calc_factors(group):
    group = group.copy()
    group = group.sort_values('date')
    
    # 收益率
    group['return_1d'] = group['close'].pct_change()
    group['return_5d'] = group['close'].pct_change(5)
    group['return_20d'] = group['close'].pct_change(20)
    
    # 移动平均线
    group['ma5'] = group['close'].rolling(5).mean()
    group['ma20'] = group['close'].rolling(20).mean()
    group['ma60'] = group['close'].rolling(60).mean()
    group['ma5_ratio'] = group['close'] / group['ma5'] - 1
    group['ma20_ratio'] = group['close'] / group['ma20'] - 1
    
    # 波动率
    group['volatility_20d'] = group['return_1d'].rolling(20).std() * np.sqrt(252)
    
    # 成交量指标
    group['vol_ma5'] = group['vol'].rolling(5).mean()
    group['vol_ratio'] = group['vol'] / group['vol_ma5']
    
    # 价格位置
    group['high_20d'] = group['high'].rolling(20).max()
    group['low_20d'] = group['low'].rolling(20).min()
    group['price_position'] = (group['close'] - group['low_20d']) / (group['high_20d'] - group['low_20d'] + 1e-10)
    
    # 目标：未来 5 天收益率
    group['target'] = group['close'].shift(-5) / group['close'] - 1
    
    return group

print("\n计算技术指标...")
df = df.groupby('ts_code', group_keys=False).apply(calc_factors)
df = df.reset_index(drop=True)
df = df.dropna()
print(f"处理后数据: {len(df)} 行")
print(f"列名: {df.columns.tolist()}")

# 划分训练/验证/测试
train_end = pd.Timestamp('2024-06-30')
valid_end = pd.Timestamp('2025-03-31')

train_df = df[df['date'] <= train_end]
valid_df = df[(df['date'] > train_end) & (df['date'] <= valid_end)]
test_df = df[df['date'] > valid_end]

print(f"\n数据集划分:")
print(f"  训练: {len(train_df)} 行 ({train_df['date'].min().date()} ~ {train_df['date'].max().date()})")
print(f"  验证: {len(valid_df)} 行 ({valid_df['date'].min().date()} ~ {valid_df['date'].max().date()})")
print(f"  测试: {len(test_df)} 行 ({test_df['date'].min().date()} ~ {test_df['date'].max().date()})")

# 特征列表
features = [
    'return_1d', 'return_5d', 'return_20d',
    'ma5_ratio', 'ma20_ratio',
    'volatility_20d', 'vol_ratio', 'price_position'
]

# 训练模型
print("\n🧠 训练 LightGBM...")
dtrain = lgb.Dataset(train_df[features], label=train_df['target'])
dvalid = lgb.Dataset(valid_df[features], label=valid_df['target'], reference=dtrain)

params = {
    'objective': 'regression',
    'metric': 'mse',
    'learning_rate': 0.05,
    'num_leaves': 31,
    'max_depth': 6,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'verbose': -1,
}

model = lgb.train(
    params, dtrain,
    num_boost_round=500,
    valid_sets=[dvalid],
    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)]
)
print(f"✅ 模型训练完成，best iteration: {model.best_iteration}")

# 预测
print("\n📈 生成预测...")
test_df['pred'] = model.predict(test_df[features])

# IC 计算
print("\n" + "=" * 60)
print("📊 IC / ICIR 评估")
print("=" * 60)

daily_ic = test_df.groupby('date').apply(
    lambda g: stats.spearmanr(g['pred'], g['target'])[0]
)
ic_mean = daily_ic.mean()
ic_std = daily_ic.std()
icir = ic_mean / ic_std if ic_std > 0 else 0
annual_ir = ic_mean / ic_std * np.sqrt(252) if ic_std > 0 else 0
ic_positive_ratio = (daily_ic > 0).mean()

print(f"IC 均值:      {ic_mean:.4f}")
print(f"IC 标准差:    {ic_std:.4f}")
print(f"ICIR:         {icir:.4f}")
print(f"年化 IR:      {annual_ir:.4f}")
print(f"IC > 0 比例:  {ic_positive_ratio:.2%}")
print(f"测试期:       {test_df['date'].min().date()} ~ {test_df['date'].max().date()}")
print(f"交易日数量:   {len(daily_ic)}")

# 最新选股信号
print("\n" + "=" * 60)
print("🎯 最新选股信号 (Top 20)")
print("=" * 60)

latest_date = test_df['date'].max()
latest_df = test_df[test_df['date'] == latest_date].sort_values('pred', ascending=False)

print(f"\n日期: {latest_date.date()}")
print(f"共 {len(latest_df)} 只股票有预测")
print("\nTop 20:")
for i, (_, row) in enumerate(latest_df.head(20).iterrows(), 1):
    print(f"  {i:2d}. {row['ts_code']:>10s}  score: {row['pred']:+.4f}  close: {row['close']:.2f}")

# 保存结果
signals_dir = Path('signals')
signals_dir.mkdir(exist_ok=True)

signal_file = signals_dir / f"signal_{latest_date.strftime('%Y%m%d')}_round2_simple.csv"
latest_df[['ts_code', 'date', 'pred', 'close']].to_csv(signal_file, index=False)
print(f"\n💾 信号已保存: {signal_file}")

metrics_file = signals_dir / f"metrics_{latest_date.strftime('%Y%m%d')}_round2_simple.json"
metrics = {
    'date': latest_date.strftime('%Y-%m-%d'),
    'ic_mean': float(ic_mean),
    'ic_std': float(ic_std),
    'icir': float(icir),
    'annual_ir': float(annual_ir),
    'ic_positive_ratio': float(ic_positive_ratio),
    'test_period': {
        'start': str(test_df['date'].min().date()),
        'end': str(test_df['date'].max().date()),
    },
    'num_trading_days': int(len(daily_ic)),
    'num_predictions': int(len(test_df)),
}
with open(metrics_file, 'w') as f:
    json.dump(metrics, f, indent=2)
print(f"📊 指标已保存: {metrics_file}")

print("\n✅ 第二轮简化版完成!")
