"""
扩展 Qlib calendars 和 instruments 文件以包含最新数据
"""
import pandas as pd
from pathlib import Path
import tushare as ts

# Tushare token
token = Path.home().joinpath(".config/tushare/token").read_text().strip()
ts.set_token(token)
pro = ts.pro_api()

# 1. 更新日历
print("=== 更新交易日历 ===")
calendar_file = Path.home() / ".qlib/qlib_data/cn_data/calendars/day.txt"

# 读取现有日历
with open(calendar_file) as f:
    existing_dates = set(line.strip() for line in f if line.strip())

# 获取新交易日历 (2023-09-29 ~ 2026-04-16)
df_cal = pro.trade_cal(exchange='SSE', start_date='20230929', end_date='20260416', is_open='1')
new_dates = set(df_cal['cal_date'].tolist())

# 合并并排序
all_dates = sorted(existing_dates | new_dates)

# 写回
with open(calendar_file, 'w') as f:
    for d in all_dates:
        f.write(f"{d}\n")

print(f"日历更新: {len(existing_dates)} → {len(all_dates)} 天")
print(f"新增日期: {len(new_dates - existing_dates)} 天")
print(f"日期范围: {all_dates[0]} ~ {all_dates[-1]}")

# 2. 更新 instruments (CSI300)
print("\n=== 更新股票列表 (CSI300) ===")
inst_file = Path.home() / ".qlib/qlib_data/cn_data/instruments/csi300.txt"

# 读取现有 instruments
existing_insts = {}
with open(inst_file) as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) >= 3:
            existing_insts[parts[0]] = (parts[1], parts[2])

# 获取当前 CSI300 成分股
csi300 = pro.index_weight(index_code='000300.SH', trade_date='20260415')

# 获取每只股票的上市日期
def get_list_date(ts_code):
    try:
        df = pro.stock_basic(ts_code=ts_code, fields='ts_code,list_date')
        if len(df) > 0:
            return df.iloc[0]['list_date']
    except:
        pass
    return '20050101'  # fallback

# 转换并更新
new_insts = {}
for _, row in csi300.iterrows():
    ts_code = row['con_code']
    code, exchange = ts_code.split('.')
    if exchange == 'SZ':
        qlib_code = f'SZ{code}'
    else:
        qlib_code = f'SH{code}'
    
    # 获取或推断上市日期
    list_date = get_list_date(ts_code)
    
    # 结束日期设为最新 (2026-04-16)
    new_insts[qlib_code] = (list_date, '20260416')

# 合并并更新结束日期
all_insts = existing_insts.copy()
for code in all_insts:
    if code in new_insts:
        # 更新结束日期为新值，保留原有上市日期
        _, new_end = new_insts[code]
        old_start, _ = all_insts[code]
        all_insts[code] = (old_start, new_end)

# 添加新股票
for code in new_insts:
    if code not in all_insts:
        all_insts[code] = new_insts[code]

# 写回
with open(inst_file, 'w') as f:
    for code, (start, end) in sorted(all_insts.items()):
        f.write(f"{code}\t{start}\t{end}\n")

print(f"股票数量: {len(existing_insts)} → {len(all_insts)}")
print(f"结束日期已更新至: 2026-04-16")

# 验证
print(f"\n验证 SZ300750:")
print(f"  更新后: {all_insts.get('SZ300750', 'NOT FOUND')}")

print("\n✅ Qlib 数据元信息更新完成")
