"""
Tushare 增量数据更新脚本 - 用于每日 Loop
只下载新日期范围的数据，避免重复下载
"""
import os
import time
import tushare as ts
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

# Setup paths
DATA_DIR = Path(__file__).parent / 'data'
DATA_DIR.mkdir(exist_ok=True)
DATA_FILE = DATA_DIR / 'tushare_csi300_202310_202604.csv'

# Tushare token
token_path = Path.home() / ".config/tushare/token"
if not token_path.exists():
    raise FileNotFoundError(f"Tushare token not found at {token_path}")

with open(token_path) as f:
    TOKEN = f.read().strip()
ts.set_token(TOKEN)
pro = ts.pro_api()


def get_last_date_from_existing_data():
    """从现有数据获取最后日期"""
    if not DATA_FILE.exists():
        return None
    
    try:
        df = pd.read_csv(DATA_FILE, usecols=['trade_date'])
        if len(df) == 0:
            return None
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        return df['trade_date'].max()
    except Exception as e:
        print(f"⚠️ 无法读取现有数据: {e}")
        return None


def get_csi300_stocks(trade_date: str = None):
    """获取 CSI300 成分股列表"""
    if trade_date is None:
        trade_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')
    
    try:
        csi300 = pro.index_weight(index_code="000300.SH", trade_date=trade_date)
        stock_list = csi300["con_code"].unique().tolist()
        print(f"📊 CSI300 成分股数量: {len(stock_list)} (参考日期: {trade_date})")
        return stock_list
    except Exception as e:
        print(f"⚠️ 获取 CSI300 成分股失败: {e}")
        # Fallback: 使用硬编码的主要股票
        return [
            '000001.SZ', '000002.SZ', '000063.SZ', '000100.SZ', '000333.SZ',
            '000568.SZ', '000651.SZ', '000725.SZ', '000768.SZ', '000858.SZ',
            '000895.SZ', '002001.SZ', '002007.SZ', '002024.SZ', '002142.SZ',
            '002236.SZ', '002352.SZ', '002594.SZ', '002714.SZ', '002841.SZ',
            '300014.SZ', '300015.SZ', '300033.SZ', '300059.SZ', '300122.SZ',
            '300142.SZ', '300274.SZ', '300408.SZ', '300413.SZ', '300433.SZ',
            '300498.SZ', '300750.SZ', '600000.SH', '600009.SH', '600016.SH',
            '600028.SH', '600030.SH', '600031.SH', '600036.SH', '600048.SH',
            '600050.SH', '600104.SH', '600276.SH', '600309.SH', '600406.SH',
            '600436.SH', '600438.SH', '600519.SH', '600585.SH', '600690.SH',
            '600745.SH', '600809.SH', '600837.SH', '600887.SH', '600900.SH',
            '600919.SH', '601012.SH', '601066.SH', '601088.SH', '601166.SH',
            '601211.SH', '601288.SH', '601318.SH', '601319.SH', '601328.SH',
            '601390.SH', '601398.SH', '601601.SH', '601628.SH', '601668.SH',
            '601688.SH', '601818.SH', '601857.SH', '601888.SH', '601899.SH',
            '601901.SH', '601933.SH', '601985.SH', '601988.SH', '601989.SH',
            '603288.SH', '603369.SH', '603501.SH', '603659.SH', '603986.SH',
            '688981.SH', '688111.SH'
        ]


def download_stock_daily(stock_code: str, start_date: str, end_date: str):
    """下载单只股票日线数据"""
    try:
        df = pro.daily(ts_code=stock_code, start_date=start_date, end_date=end_date)
        time.sleep(0.31)  # ~200 req/min = 0.3s per request
        return df
    except Exception as e:
        print(f"  ⚠️ Error downloading {stock_code}: {e}")
        time.sleep(1)
        return None


def update_daily_data():
    """增量更新每日数据"""
    print("=" * 60)
    print("📥 Tushare 增量数据更新")
    print("=" * 60)
    
    # 确定日期范围
    last_date = get_last_date_from_existing_data()
    
    if last_date is None:
        # 没有现有数据，全量下载
        print("📦 未检测到现有数据，执行全量下载")
        start_date = "20231001"
    else:
        # 增量下载：从最后日期后一天开始
        next_date = last_date + timedelta(days=1)
        start_date = next_date.strftime('%Y%m%d')
        print(f"📦 检测到现有数据，最后日期: {last_date.strftime('%Y-%m-%d')}")
        print(f"📦 增量下载: {start_date} 至今")
    
    end_date = datetime.now().strftime('%Y%m%d')
    
    if start_date > end_date:
        print(f"✅ 数据已是最新 (最后日期: {last_date.strftime('%Y-%m-%d')})")
        return True
    
    # 获取股票列表
    stock_list = get_csi300_stocks()
    
    # 分批下载
    batch_size = 50
    all_data = []
    failed_stocks = []
    
    print(f"\n🔄 开始下载 {len(stock_list)} 只股票数据...")
    
    for i, stock in enumerate(stock_list):
        batch_idx = i // batch_size
        if i % batch_size == 0:
            print(f"\n=== Batch {batch_idx+1} ({i+1}-{min(i+batch_size, len(stock_list))}) ===")
        
        print(f"[{i+1}/{len(stock_list)}] {stock} ...", end=" ")
        df = download_stock_daily(stock, start_date, end_date)
        
        if df is not None and len(df) > 0:
            all_data.append(df)
            print(f"✓ {len(df)} rows")
        else:
            print("✗")
            failed_stocks.append(stock)
        
        # 每批结束休息
        if (i + 1) % batch_size == 0 and i < len(stock_list) - 1:
            print(f"⏸️  Batch complete, sleeping 10s...")
            time.sleep(10)
    
    # 处理失败的股票（重试一次）
    if failed_stocks:
        print(f"\n🔄 重试 {len(failed_stocks)} 只失败股票...")
        for stock in failed_stocks:
            df = download_stock_daily(stock, start_date, end_date)
            if df is not None and len(df) > 0:
                all_data.append(df)
            time.sleep(0.5)
    
    # 合并并保存数据
    if not all_data:
        print("⚠️ 未下载到任何新数据")
        return True  # 这不是错误，可能是节假日无数据
    
    print(f"\n=== 合并数据 ===")
    new_df = pd.concat(all_data, ignore_index=True)
    print(f"新数据行数: {len(new_df)}")
    
    # 合并到现有数据
    if DATA_FILE.exists() and last_date is not None:
        existing_df = pd.read_csv(DATA_FILE)
        
        # 去重：合并新数据，删除重复项
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        
        # 去重：按 ts_code + trade_date
        before_dedup = len(combined_df)
        combined_df = combined_df.drop_duplicates(subset=['ts_code', 'trade_date'])
        after_dedup = len(combined_df)
        
        print(f"合并后去重: {before_dedup} → {after_dedup} (删除 {before_dedup - after_dedup} 重复)")
    else:
        combined_df = new_df
    
    # 保存
    combined_df.to_csv(DATA_FILE, index=False)
    print(f"✅ 数据已保存: {DATA_FILE}")
    print(f"   总行数: {len(combined_df)}")
    print(f"   日期范围: {combined_df['trade_date'].min()} ~ {combined_df['trade_date'].max()}")
    
    return True


if __name__ == '__main__':
    try:
        success = update_daily_data()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
