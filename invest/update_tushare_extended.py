"""
扩展股票池下载脚本 - CSI300 + CSI500 + CSI1000
分批下载，遵守 200次/分钟限流
"""
import time
import tushare as ts
import pandas as pd
from pathlib import Path
import json

# Tushare token
with open(Path.home() / ".config/tushare/token") as f:
    TOKEN = f.read().strip()
ts.set_token(TOKEN)
pro = ts.pro_api()

# 定义三个指数
INDEX_CODES = {
    "csi300": "000300.SH",   # 沪深300 - 已有
    "csi500": "000905.SH",   # 中证500 - 新增
    "csi1000": "000852.SH",  # 中证1000 - 新增
}

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


def get_constituent_stocks(index_code, trade_date="20260415"):
    """获取指数成分股列表"""
    try:
        df = pro.index_weight(index_code=index_code, trade_date=trade_date)
        stocks = df["con_code"].unique().tolist()
        print(f"  {index_code}: {len(stocks)} 只成分股")
        return stocks
    except Exception as e:
        print(f"  Error fetching {index_code}: {e}")
        return []


def download_stock_daily(stock_code, start_date, end_date, retry=3):
    """下载单只股票日线数据"""
    for attempt in range(retry):
        try:
            df = pro.daily(ts_code=stock_code, start_date=start_date, end_date=end_date)
            time.sleep(0.31)  # ~200 req/min = 0.3s per request
            return df
        except Exception as e:
            print(f"    Error downloading {stock_code} (attempt {attempt+1}/{retry}): {e}")
            time.sleep(2 ** attempt)  # 指数退避
    return None


def download_stocks_batch(stock_list, index_name, start_date="20231001", end_date="20260416", batch_size=50):
    """分批下载股票数据"""
    print(f"\n{'='*60}")
    print(f"下载 {index_name} 成分股数据 ({len(stock_list)} 只)")
    print(f"{'='*60}")
    
    all_data = []
    failed_stocks = []
    
    for i, stock in enumerate(stock_list):
        batch_idx = i // batch_size
        if i % batch_size == 0:
            print(f"\n--- Batch {batch_idx+1} ({i+1}-{min(i+batch_size, len(stock_list))}) ---")
        
        print(f"  [{i+1}/{len(stock_list)}] {stock} ...", end=" ", flush=True)
        df = download_stock_daily(stock, start_date, end_date)
        
        if df is not None and len(df) > 0:
            all_data.append(df)
            print(f"✓ {len(df)} rows")
        else:
            print("✗")
            failed_stocks.append(stock)
        
        # 每批结束休息，避免限流
        if (i + 1) % batch_size == 0 and i < len(stock_list) - 1:
            print(f"  ⏸️ 休息 10s...")
            time.sleep(10)
    
    return all_data, failed_stocks


def main():
    print("="*60)
    print("扩展股票池: 沪深300 + 中证500 + 中证1000")
    print("="*60)
    
    # Step 1: 获取三个指数的成分股
    print("\n📋 Step 1: 获取成分股列表")
    all_stocks = {}
    stock_to_index = {}  # 记录每只股票属于哪个指数
    
    for index_name, index_code in INDEX_CODES.items():
        stocks = get_constituent_stocks(index_code)
        all_stocks[index_name] = stocks
        for stock in stocks:
            if stock not in stock_to_index:
                stock_to_index[stock] = []
            stock_to_index[stock].append(index_name)
    
    # 去重后的总股票池
    unique_stocks = list(stock_to_index.keys())
    print(f"\n📊 统计:")
    print(f"  CSI300:  {len(all_stocks['csi300'])} 只")
    print(f"  CSI500:  {len(all_stocks['csi500'])} 只")
    print(f"  CSI1000: {len(all_stocks['csi1000'])} 只")
    print(f"  去重后总数: {len(unique_stocks)} 只")
    
    # 保存成分股映射
    stock_index_map = {
        "csi300": all_stocks["csi300"],
        "csi500": all_stocks["csi500"],
        "csi1000": all_stocks["csi1000"],
        "stock_to_index": stock_to_index,
        "total_unique": len(unique_stocks),
    }
    with open(DATA_DIR / "stock_index_map.json", "w") as f:
        json.dump(stock_index_map, f, indent=2, ensure_ascii=False)
    print(f"\n💾 成分股映射已保存: {DATA_DIR / 'stock_index_map.json'}")
    
    # Step 2: 分批下载 CSI500
    print("\n" + "="*60)
    print("📥 Step 2a: 下载中证500成分股数据")
    print("="*60)
    csi500_data, csi500_failed = download_stocks_batch(
        all_stocks["csi500"], "CSI500", 
        start_date="20231001", end_date="20260416",
        batch_size=50
    )
    
    # 保存中证500数据
    if csi500_data:
        csi500_df = pd.concat(csi500_data, ignore_index=True)
        csi500_path = DATA_DIR / "tushare_csi500_202310_202604.csv"
        csi500_df.to_csv(csi500_path, index=False)
        print(f"\n✅ CSI500 数据已保存: {csi500_path} ({len(csi500_df)} rows)")
        # 保存失败列表供重试
        if csi500_failed:
            with open(LOGS_DIR / "csi500_failed.json", "w") as f:
                json.dump(csi500_failed, f)
            print(f"⚠️  失败 {len(csi500_failed)} 只，已保存到 {LOGS_DIR / 'csi500_failed.json'}")
    
    # 休息一段时间
    print("\n⏸️  休息 30s 后继续下载 CSI1000...")
    time.sleep(30)
    
    # 下载 CSI1000
    print("\n" + "="*60)
    print("📥 Step 2b: 下载中证1000成分股数据")
    print("="*60)
    csi1000_data, csi1000_failed = download_stocks_batch(
        all_stocks["csi1000"], "CSI1000",
        start_date="20231001", end_date="20260416",
        batch_size=50
    )
    
    # 保存中证1000数据
    if csi1000_data:
        csi1000_df = pd.concat(csi1000_data, ignore_index=True)
        csi1000_path = DATA_DIR / "tushare_csi1000_202310_202604.csv"
        csi1000_df.to_csv(csi1000_path, index=False)
        print(f"\n✅ CSI1000 数据已保存: {csi1000_path} ({len(csi1000_df)} rows)")
        if csi1000_failed:
            with open(LOGS_DIR / "csi1000_failed.json", "w") as f:
                json.dump(csi1000_failed, f)
            print(f"⚠️  失败 {len(csi1000_failed)} 只，已保存到 {LOGS_DIR / 'csi1000_failed.json'}")
    
    # Step 3: 汇总
    print("\n" + "="*60)
    print("📊 下载完成汇总")
    print("="*60)
    print(f"CSI500:  {len(csi500_data) if csi500_data else 0}/{len(all_stocks['csi500'])} 只成功")
    print(f"CSI1000: {len(csi1000_data) if csi1000_data else 0}/{len(all_stocks['csi1000'])} 只成功")
    
    print("\n✅ 数据下载阶段完成!")
    print("\n下一步: 运行 convert_to_qlib.py 合并数据到 Qlib")


if __name__ == "__main__":
    main()
