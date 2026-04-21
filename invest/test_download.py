"""
快速测试下载 - 50只中证500股票
"""
import tushare as ts
import pandas as pd
import time
import json
from pathlib import Path

token = Path.home().joinpath(".config/tushare/token").read_text().strip()
ts.set_token(token)
pro = ts.pro_api()

# 读取股票列表
with open("data/stock_index_map.json") as f:
    stock_map = json.load(f)

# 只取50只测试
test_stocks = stock_map['csi500'][:50]
print(f"测试下载: {len(test_stocks)} 只 (中证500前50)")

start_date = "20260301"
end_date = "20260415"

all_data = []
for ts_code in test_stocks:
    try:
        df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if len(df) > 0:
            all_data.append(df)
            print(f"✅ {ts_code}: {len(df)} rows")
        else:
            print(f"⚠️ {ts_code}: no data")
    except Exception as e:
        print(f"❌ {ts_code}: {e}")
    time.sleep(0.3)

if all_data:
    df = pd.concat(all_data, ignore_index=True)
    print(f"\n✅ 测试下载完成: {len(df)} 条记录")
    df.to_csv("data/test_csi500_50stocks.csv", index=False)
else:
    print("\n❌ 无数据")
