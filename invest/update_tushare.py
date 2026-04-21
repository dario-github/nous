"""
Tushare → Qlib 数据更新脚本
分批下载，遵守 200次/分钟限流
"""
import time
import tushare as ts
import pandas as pd
from pathlib import Path
import qlib
from qlib.config import REG_CN
from qlib.data import D

# Tushare token
with open(Path.home() / ".config/tushare/token") as f:
    TOKEN = f.read().strip()
ts.set_token(TOKEN)
pro = ts.pro_api()

# Qlib 初始化
qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region=REG_CN)

# 获取 CSI300 成分股列表
csi300 = pro.index_weight(index_code="000300.SH", trade_date="20260331")
stock_list = csi300["con_code"].unique().tolist()
print(f"CSI300 成分股数量: {len(stock_list)}")

# 目标日期范围
date_range = pd.date_range(start="2023-10-01", end="2026-04-16", freq="D")
trade_dates = [d.strftime("%Y%m%d") for d in date_range]
print(f"目标日期范围: 2023-10-01 ~ 2026-04-16, 共 {len(trade_dates)} 天")

# 批量下载
def download_stock_daily(stock_code, start_date, end_date):
    """下载单只股票日线数据"""
    try:
        df = pro.daily(ts_code=stock_code, start_date=start_date, end_date=end_date)
        time.sleep(0.31)  # ~200 req/min = 0.3s per request
        return df
    except Exception as e:
        print(f"  Error downloading {stock_code}: {e}")
        time.sleep(1)
        return None

# 分批处理 (每批 50 只，中间休息)
batch_size = 50
all_data = []

for i, stock in enumerate(stock_list):
    batch_idx = i // batch_size
    if i % batch_size == 0:
        print(f"\n=== Batch {batch_idx+1} ({i}-{min(i+batch_size, len(stock_list))-1}) ===")
    
    print(f"[{i+1}/{len(stock_list)}] {stock} ...", end=" ")
    df = download_stock_daily(stock, "20231001", "20260416")
    
    if df is not None and len(df) > 0:
        all_data.append(df)
        print(f"✓ {len(df)} rows")
    else:
        print("✗")
    
    # 每批结束休息，避免限流
    if (i + 1) % batch_size == 0:
        print(f"⏸️  Batch complete, sleeping 10s...")
        time.sleep(10)

# 合并数据
if all_data:
    print("\n=== Merging data ===")
    full_df = pd.concat(all_data, ignore_index=True)
    print(f"Total rows: {len(full_df)}")
    print(full_df.head())
    
    # 保存为 CSV 供后续 Qlib 转换
    output_path = Path("data/tushare_csi300_202310_202604.csv")
    output_path.parent.mkdir(exist_ok=True)
    full_df.to_csv(output_path, index=False)
    print(f"✅ Saved to {output_path}")
else:
    print("No data downloaded")
