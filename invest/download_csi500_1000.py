"""
下载中证500和中证1000日线数据（分批，避免限流）
"""
import tushare as ts
import pandas as pd
import time
import json
from pathlib import Path

# Tushare token
token = Path.home().joinpath(".config/tushare/token").read_text().strip()
ts.set_token(token)
pro = ts.pro_api()

# 读取股票列表
with open("data/stock_index_map.json") as f:
    stock_map = json.load(f)

csi500_list = stock_map['csi500']
csi1000_list = stock_map['csi1000']

print(f"中证500: {len(csi500_list)} 只")
print(f"中证1000: {len(csi1000_list)} 只")

# 检查已有数据
existing_csv = "data/tushare_csi300_202310_202604.csv"
if Path(existing_csv).exists():
    df_existing = pd.read_csv(existing_csv)
    existing_stocks = set(df_existing['ts_code'].unique())
    print(f"已有沪深300数据: {len(existing_stocks)} 只股票, {len(df_existing)} 条记录")
else:
    existing_stocks = set()
    print("未找到已有数据")

# 需要下载的新股票（排除已下载的沪深300）
new_stocks_500 = [s for s in csi500_list if s not in existing_stocks]
new_stocks_1000 = [s for s in csi1000_list if s not in existing_stocks]

print(f"\n中证500需下载: {len(new_stocks_500)} 只")
print(f"中证1000需下载: {len(new_stocks_1000)} 只")
print(f"总计需下载: {len(new_stocks_500) + len(new_stocks_1000)} 只")

# 下载参数
start_date = "20231009"
end_date = "20260415"
batch_size = 50  # 每批50只
sleep_time = 12  # 每批休息12秒（限流200次/分钟）

all_data = []

# 下载函数
def download_batch(stock_list, index_name):
    total = len(stock_list)
    for i in range(0, total, batch_size):
        batch = stock_list[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        
        print(f"\n[{index_name}] Batch {batch_num}/{total_batches}: {batch[0]} ~ {batch[-1]} ({len(batch)} stocks)")
        
        for ts_code in batch:
            try:
                df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                if len(df) > 0:
                    all_data.append(df)
                    print(f"  {ts_code}: {len(df)} rows")
                else:
                    print(f"  {ts_code}: no data")
            except Exception as e:
                print(f"  {ts_code}: ERROR - {e}")
            
            time.sleep(0.3)  # 每次请求间隔
        
        if i + batch_size < total:
            print(f"  -> 休息 {sleep_time} 秒...")
            time.sleep(sleep_time)

# 下载中证500
if new_stocks_500:
    print("=" * 60)
    print("开始下载中证500数据...")
    print("=" * 60)
    download_batch(new_stocks_500, "CSI500")

# 下载中证1000
if new_stocks_1000:
    print("=" * 60)
    print("开始下载中证1000数据...")
    print("=" * 60)
    download_batch(new_stocks_1000, "CSI1000")

# 合并所有数据
print("\n" + "=" * 60)
print("合并数据...")
print("=" * 60)

if all_data:
    df_new = pd.concat(all_data, ignore_index=True)
    print(f"新下载数据: {len(df_new)} 条")
    
    # 合并到已有数据
    if Path(existing_csv).exists():
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        print(f"合并后总数据: {len(df_combined)} 条")
        print(f"合并后股票数: {df_combined['ts_code'].nunique()}")
    else:
        df_combined = df_new
    
    # 保存
    output_file = "data/tushare_combined_1800_202310_202604.csv"
    df_combined.to_csv(output_file, index=False)
    print(f"\n✅ 数据已保存: {output_file}")
else:
    print("没有新数据下载")

print("\n🎉 全部完成!")
