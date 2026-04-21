"""
Tushare CSV → Qlib 格式转换 (扩展版 - 支持 CSI300 + CSI500 + CSI1000)
合并所有数据并转换为 Qlib 标准格式
"""
import pandas as pd
import numpy as np
from pathlib import Path
import shutil
import json

DATA_DIR = Path("data")
QLIB_FEATURES_DIR = Path.home() / ".qlib/qlib_data/cn_data/features"

def convert_code(ts_code):
    """Tushare: 000001.SZ → Qlib: SZ000001"""
    code, exchange = ts_code.split('.')
    if exchange == 'SZ':
        return f'SZ{code}'
    else:
        return f'SH{code}'


def process_csv_to_qlib(csv_path, label):
    """处理单个 CSV 文件转换为 Qlib 格式"""
    print(f"\n处理 {label}: {csv_path}")
    
    if not csv_path.exists():
        print(f"  ⚠️ 文件不存在: {csv_path}")
        return None
    
    df = pd.read_csv(csv_path)
    print(f"  原始数据: {len(df)} 行")
    
    if len(df) == 0:
        print(f"  ⚠️ 空数据")
        return None
    
    # Qlib 格式要求
    df['date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
    df['date'] = df['date'].dt.strftime('%Y-%m-%d')
    df['factor'] = 1.0  # 前复权
    
    # 转换列名和类型
    df['open'] = df['open'].astype(float)
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['volume'] = df['vol'].astype(float)
    df['money'] = df['amount'].astype(float)
    df['instrument'] = df['ts_code'].apply(convert_code)
    
    # 选择需要的列
    qlib_df = df[['instrument', 'date', 'open', 'close', 'high', 'low', 'volume', 'money', 'factor']]
    
    return qlib_df


def save_to_qlib(qlib_df, label):
    """保存到 Qlib features 目录"""
    QLIB_FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    
    saved_count = 0
    updated_count = 0
    instruments = qlib_df['instrument'].unique()
    
    print(f"\n保存 {label} 到 Qlib ({len(instruments)} 只股票)...")
    
    for instrument in instruments:
        stock_data = qlib_df[qlib_df['instrument'] == instrument].copy()
        stock_data = stock_data.drop(columns=['instrument'])
        stock_data = stock_data.sort_values('date')
        
        output_file = QLIB_FEATURES_DIR / f"{instrument}.csv"
        
        if output_file.exists():
            # 合并现有数据
            existing = pd.read_csv(output_file)
            combined = pd.concat([existing, stock_data], ignore_index=True)
            combined = combined.drop_duplicates(subset=['date'], keep='last')
            combined = combined.sort_values('date')
            combined.to_csv(output_file, index=False)
            updated_count += 1
        else:
            stock_data.to_csv(output_file, index=False)
            saved_count += 1
        
        total = saved_count + updated_count
        if total % 100 == 0:
            print(f"  已处理 {total} 只股票...")
    
    print(f"  ✓ 新增 {saved_count} 只, 更新 {updated_count} 只")
    return saved_count + updated_count


def main():
    print("="*60)
    print("Tushare → Qlib 格式转换 (扩展版)")
    print("="*60)
    
    # 检查数据文件
    csi300_path = DATA_DIR / "tushare_csi300_202310_202604.csv"
    csi500_path = DATA_DIR / "tushare_csi500_202310_202604.csv"
    csi1000_path = DATA_DIR / "tushare_csi1000_202310_202604.csv"
    
    all_data = []
    
    # 处理 CSI300
    csi300_df = process_csv_to_qlib(csi300_path, "CSI300")
    if csi300_df is not None:
        csi300_df['source_index'] = 'csi300'
        all_data.append(csi300_df)
    
    # 处理 CSI500
    csi500_df = process_csv_to_qlib(csi500_path, "CSI500")
    if csi500_df is not None:
        csi500_df['source_index'] = 'csi500'
        all_data.append(csi500_df)
    
    # 处理 CSI1000
    csi1000_df = process_csv_to_qlib(csi1000_path, "CSI1000")
    if csi1000_df is not None:
        csi1000_df['source_index'] = 'csi1000'
        all_data.append(csi1000_df)
    
    if not all_data:
        print("\n⚠️ 没有数据可以处理!")
        return
    
    # 合并所有数据
    print("\n" + "="*60)
    print("合并所有数据...")
    print("="*60)
    full_df = pd.concat(all_data, ignore_index=True)
    print(f"合并后总行数: {len(full_df)}")
    
    # 去重 (同一股票可能在多个指数中)
    # 保留所有数据点，但确保 (instrument, date) 唯一
    full_df = full_df.drop_duplicates(subset=['instrument', 'date'], keep='first')
    print(f"去重后总行数: {len(full_df)}")
    
    # 统计
    unique_instruments = full_df['instrument'].nunique()
    print(f"去重后股票数: {unique_instruments}")
    
    # 保存到 Qlib
    total_saved = save_to_qlib(full_df, "全部数据")
    
    # 保存合并后的原始数据（用于备份）
    merged_path = DATA_DIR / "tushare_all_indices_202310_202604.csv"
    full_df.to_csv(merged_path, index=False)
    print(f"\n💾 合并数据已保存: {merged_path}")
    
    # 验证
    print("\n" + "="*60)
    print("验证")
    print("="*60)
    
    # 检查几只股票
    check_stocks = ["SZ300750", "SH600519", "SH000905"]
    for stock in check_stocks:
        check_file = QLIB_FEATURES_DIR / f"{stock}.csv"
        if check_file.exists():
            check_df = pd.read_csv(check_file)
            print(f"  {stock}: {len(check_df)} rows, {check_df['date'].min()} ~ {check_df['date'].max()}")
    
    # 统计 Qlib features 目录中的股票数量
    feature_files = list(QLIB_FEATURES_DIR.glob("*.csv"))
    print(f"\nQlib features 目录共有 {len(feature_files)} 只股票")
    
    print("\n✅ 数据转换完成!")
    print("\n下一步: 运行 run_multi_index.py 进行多指数模型训练")


if __name__ == "__main__":
    main()
