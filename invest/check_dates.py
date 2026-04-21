"""
检查可用数据日期范围
"""
import pandas as pd
from pathlib import Path

# 检查一个样本文件
sample_file = Path.home() / ".qlib/qlib_data/cn_data/features/SH600000.csv"
if sample_file.exists():
    df = pd.read_csv(sample_file)
    print(f"样本文件: SH600000.csv")
    print(f"日期范围: {df['date'].min()} ~ {df['date'].max()}")
    print(f"总行数: {len(df)}")
    print(f"\n前 5 行:")
    print(df.head())
    print(f"\n后 5 行:")
    print(df.tail())

# 检查所有文件的日期范围
print("\n" + "=" * 60)
print("检查所有文件的日期范围")
features_dir = Path.home() / ".qlib/qlib_data/cn_data/features"
all_dates = []
for i, f in enumerate(features_dir.glob("*.csv")):
    if i >= 300:  # 只检查前300个
        break
    try:
        df = pd.read_csv(f, usecols=['date'])
        all_dates.extend(df['date'].tolist())
    except:
        pass

all_dates = pd.to_datetime(all_dates)
print(f"所有文件合并后的日期范围:")
print(f"最早: {all_dates.min()}")
print(f"最晚: {all_dates.max()}")
print(f"总交易日数: {all_dates.nunique()}")
