"""
分批下载中证500和中证1000（后台持续运行）
保存进度，支持断点续传
"""
import tushare as ts
import pandas as pd
import time
import json
from pathlib import Path
from datetime import datetime

token = Path.home().joinpath(".config/tushare/token").read_text().strip()
ts.set_token(token)
pro = ts.pro_api()

# 配置
BATCH_SIZE = 50
SLEEP_BETWEEN_BATCH = 15
SLEEP_BETWEEN_REQUEST = 0.25
START_DATE = "20231009"
END_DATE = "20260415"

# 进度文件
PROGRESS_FILE = Path("data/download_progress.json")

def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"completed": [], "failed": []}

def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def download_stock(ts_code):
    """下载单只股票数据"""
    try:
        df = pro.daily(ts_code=ts_code, start_date=START_DATE, end_date=END_DATE)
        return df if len(df) > 0 else None
    except Exception as e:
        print(f"    ❌ {ts_code}: {e}")
        return None

def main():
    # 读取股票列表
    with open("data/stock_index_map.json") as f:
        stock_map = json.load(f)
    
    # 加载已有数据
    existing_csv = "data/tushare_csi300_202310_202604.csv"
    if Path(existing_csv).exists():
        df_existing = pd.read_csv(existing_csv)
        existing_stocks = set(df_existing['ts_code'].unique())
        print(f"已有数据: {len(existing_stocks)} 只股票")
    else:
        df_existing = None
        existing_stocks = set()
    
    # 需要下载的新股票
    csi500_stocks = [s for s in stock_map['csi500'] if s not in existing_stocks]
    csi1000_stocks = [s for s in stock_map['csi1000'] if s not in existing_stocks]
    
    all_new_stocks = csi500_stocks + csi1000_stocks
    print(f"需要下载: {len(all_new_stocks)} 只股票")
    print(f"  - 中证500: {len(csi500_stocks)}")
    print(f"  - 中证1000: {len(csi1000_stocks)}")
    
    # 加载进度
    progress = load_progress()
    remaining = [s for s in all_new_stocks if s not in progress['completed']]
    print(f"已完成: {len(progress['completed'])}, 剩余: {len(remaining)}")
    
    if not remaining:
        print("✅ 所有股票已下载完成!")
        return
    
    # 分批下载
    all_data = []
    total = len(remaining)
    
    for i in range(0, total, BATCH_SIZE):
        batch = remaining[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Batch {batch_num}/{total_batches}: {batch[0]} ~ {batch[-1]}")
        
        batch_data = []
        for ts_code in batch:
            df = download_stock(ts_code)
            if df is not None:
                batch_data.append(df)
                progress['completed'].append(ts_code)
                print(f"  ✅ {ts_code}: {len(df)} rows")
            else:
                progress['failed'].append(ts_code)
                print(f"  ⚠️ {ts_code}: no data")
            
            time.sleep(SLEEP_BETWEEN_REQUEST)
        
        if batch_data:
            all_data.extend(batch_data)
        
        # 保存进度
        save_progress(progress)
        
        # 定期保存数据（每5批）
        if batch_num % 5 == 0 and all_data:
            temp_df = pd.concat(all_data, ignore_index=True)
            temp_file = f"data/download_temp_batch{batch_num}.csv"
            temp_df.to_csv(temp_file, index=False)
            print(f"  💾 临时保存: {temp_file} ({len(temp_df)} 条)")
            all_data = []  # 清空内存
        
        if i + BATCH_SIZE < total:
            print(f"  -> 休息 {SLEEP_BETWEEN_BATCH} 秒...")
            time.sleep(SLEEP_BETWEEN_BATCH)
    
    # 合并所有临时文件
    print("\n" + "="*60)
    print("合并所有数据...")
    print("="*60)
    
    temp_files = list(Path("data").glob("download_temp_batch*.csv"))
    if temp_files or all_data:
        dfs = []
        if df_existing is not None:
            dfs.append(df_existing)
        
        for f in sorted(temp_files):
            dfs.append(pd.read_csv(f))
            print(f"  加载: {f.name}")
        
        if all_data:
            dfs.append(pd.concat(all_data, ignore_index=True))
        
        final_df = pd.concat(dfs, ignore_index=True)
        final_df = final_df.drop_duplicates(subset=['ts_code', 'trade_date'], keep='last')
        
        output_file = "data/tushare_all_1800_202310_202604.csv"
        final_df.to_csv(output_file, index=False)
        print(f"\n✅ 完成! 保存到: {output_file}")
        print(f"   总记录数: {len(final_df)}")
        print(f"   股票数: {final_df['ts_code'].nunique()}")
    
    # 清理临时文件
    for f in temp_files:
        f.unlink()
    
    print("\n🎉 全部完成!")

if __name__ == '__main__':
    main()
