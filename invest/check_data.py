"""
检查原始数据的股票数量
"""
import pandas as pd

df = pd.read_csv("/Users/yan/clawd-agents/research/nous-invest/data/tushare_csi300_202310_202604.csv")
print(f"总数据行数: {len(df)}")
print(f"唯一股票数量: {df['ts_code'].nunique()}")
print(f"\n股票代码列表（前 30 个）:")
print(df['ts_code'].unique()[:30])
print(f"\n日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
print(f"\n每个股票的数据条数统计:")
counts = df.groupby('ts_code').size()
print(f"  平均: {counts.mean():.1f}")
print(f"  最小: {counts.min()}")
print(f"  最大: {counts.max()}")
