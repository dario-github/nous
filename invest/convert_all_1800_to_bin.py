"""
快速转换全部1800只股票到 Qlib bin 格式
"""
import pandas as pd
import numpy as np
from pathlib import Path
import struct
from qlib.config import REG_CN
import qlib

# 加载 calendar
qlib.init(provider_uri='~/.qlib/qlib_data/cn_data', region=REG_CN, skip_if_reg=True)
from qlib.data.storage.file_storage import FileCalendarStorage
calendars = FileCalendarStorage(freq='day', future=False).data
print(f"Calendar: {len(calendars)} days, {calendars[0]} ~ {calendars[-1]}")

# 读取全部1800只股票数据
df = pd.read_csv('data/tushare_all_1800_202310_202604.csv')
print(f"\n读取数据: {len(df)} 行, {df['ts_code'].nunique()} 只股票")

# 转换代码格式
def convert_code(ts_code):
    code, exchange = ts_code.split('.')
    return f'{exchange}{code}'

df['instrument'] = df['ts_code'].apply(convert_code)
df['date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')

# 准备 Qlib 格式
df['open'] = df['open'].astype(float)
df['close'] = df['close'].astype(float)
df['high'] = df['high'].astype(float)
df['low'] = df['low'].astype(float)
df['volume'] = df['vol'].astype(float)
df['money'] = df['amount'].astype(float)
df['factor'] = 1.0

features_dir = Path.home() / '.qlib/qlib_data/cn_data/features'

# 按股票分组处理
grouped = df.groupby('instrument')
total = len(grouped)
print(f"\n开始转换 {total} 只股票到 bin 格式...")

success = 0
for i, (instrument, group) in enumerate(grouped):
    group = group.sort_values('date')
    
    # 创建股票目录
    stock_dir = features_dir / instrument
    stock_dir.mkdir(exist_ok=True)
    
    # 计算 start_index
    start_date = group['date'].min()
    start_idx = None
    for idx, cal_date in enumerate(calendars):
        if pd.Timestamp(cal_date) >= start_date:
            start_idx = idx
            break
    
    if start_idx is None:
        continue
    
    # 日期到值的映射
    date_values = {}
    for _, row in group.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d')
        date_values[date_str] = row
    
    # 为每个字段创建 bin 文件
    fields = ['open', 'close', 'high', 'low', 'volume', 'money', 'factor']
    for field in fields:
        values = []
        for j in range(start_idx, len(calendars)):
            cal_date_str = pd.Timestamp(calendars[j]).strftime('%Y-%m-%d')
            if cal_date_str in date_values:
                val = float(date_values[cal_date_str][field])
                values.append(val)
            else:
                if pd.Timestamp(calendars[j]) > group['date'].max():
                    break
                values.append(np.nan)
        
        if values:
            bin_file = stock_dir / f'{field}.day.bin'
            with open(bin_file, 'wb') as f:
                f.write(struct.pack('<f', float(start_idx)))
                for val in values:
                    f.write(struct.pack('<f', float(val) if not np.isnan(val) else np.nan))
    
    success += 1
    if (i + 1) % 100 == 0:
        print(f"  已处理 {i + 1}/{total}...")

print(f"\n✅ 成功转换 {success}/{total} 只股票")

# 更新 instruments 文件
print("\n更新 instruments/csi300.txt...")
inst_file = Path.home() / '.qlib/qlib_data/cn_data/instruments/csi300.txt'

# 计算每只股票的起止日期
inst_dates = df.groupby('instrument')['date'].agg(['min', 'max']).reset_index()
inst_dates['min'] = inst_dates['min'].dt.strftime('%Y-%m-%d')
inst_dates['max'] = inst_dates['max'].dt.strftime('%Y-%m-%d')

with open(inst_file, 'w') as f:
    for _, row in inst_dates.iterrows():
        f.write(f"{row['instrument']}\t{row['min']}\t{row['max']}\n")

print(f"✅ Instruments 更新完成: {len(inst_dates)} 只股票")
print(f"   日期范围: {inst_dates['min'].min()} ~ {inst_dates['max'].max()}")
