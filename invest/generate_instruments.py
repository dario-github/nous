"""
重新生成 csi300.txt instruments 文件，使用正确的日期格式 (YYYY-MM-DD)
"""
import pandas as pd
from pathlib import Path

# 读取原始数据
df = pd.read_csv("/Users/yan/clawd-agents/research/nous-invest/data/tushare_csi300_202310_202604.csv")

# 转换股票代码格式 (Tushare: 000001.SZ → Qlib: SZ000001)
def convert_code(ts_code):
    code, exchange = ts_code.split('.')
    if exchange == 'SZ':
        return f'SZ{code}'
    else:
        return f'SH{code}'

df['instrument'] = df['ts_code'].apply(convert_code)
df['date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')

# 计算每个股票的起止日期
instrument_dates = df.groupby('instrument')['date'].agg(['min', 'max']).reset_index()

# 格式化为 YYYY-MM-DD (Qlib 标准格式)
instrument_dates['min'] = instrument_dates['min'].dt.strftime('%Y-%m-%d')
instrument_dates['max'] = instrument_dates['max'].dt.strftime('%Y-%m-%d')

print(f"将生成 {len(instrument_dates)} 个股票的 instruments 配置")
print(f"\n前 10 个:")
print(instrument_dates.head(10))

# 生成 instruments 文件内容
lines = []
for _, row in instrument_dates.iterrows():
    # 格式: <instrument>\t<start_date>\t<end_date>
    # Qlib 使用 YYYY-MM-DD 格式
    lines.append(f"{row['instrument']}\t{row['min']}\t{row['max']}")

# 保存到文件
csi300_path = Path.home() / ".qlib/qlib_data/cn_data/instruments/csi300.txt"
with open(csi300_path, 'w') as f:
    f.write('\n'.join(lines) + '\n')

print(f"\n✅ 已保存到: {csi300_path}")
print(f"文件行数: {len(lines)}")

# 验证
print(f"\n验证（前 10 行）:")
with open(csi300_path) as f:
    for i, line in enumerate(f):
        if i >= 10:
            break
        print(f"  {line.strip()}")
