"""
将 Tushare CSV 数据转换为 Qlib bin 格式
"""
import pandas as pd
import numpy as np
from pathlib import Path
import json
import argparse

def convert_csv_to_bin(input_csv, output_dir):
    """将 Tushare CSV 转换为 Qlib bin 格式"""
    print(f"读取: {input_csv}")
    df = pd.read_csv(input_csv)
    
    print(f"数据: {len(df)} 行, {df['ts_code'].nunique()} 只股票")
    
    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 按股票分组处理
    grouped = df.groupby('ts_code')
    
    for ts_code, group in grouped:
        # 转换代码格式 (000001.SZ -> SZ000001)
        code, exchange = ts_code.split('.')
        if exchange == 'SZ':
            qlib_code = f'SZ{code}'
        else:
            qlib_code = f'SH{code}'
        
        # 排序
        group = group.sort_values('trade_date')
        
        # Qlib bin 格式: date, open, close, high, low, volume, money, factor
        # 保存为 CSV (Qlib 可以读取 CSV 格式，bin 是可选优化)
        output_file = output_path / f"{qlib_code}.csv"
        
        # 转换列名
        qlib_df = pd.DataFrame({
            'date': pd.to_datetime(group['trade_date'], format='%Y%m%d').dt.strftime('%Y-%m-%d'),
            'open': group['open'],
            'close': group['close'],
            'high': group['high'],
            'low': group['low'],
            'volume': group['vol'],
            'money': group['amount'],
            'factor': 1.0  # 前复权因子
        })
        
        # 合并已有数据（如果有）
        if output_file.exists():
            existing = pd.read_csv(output_file)
            combined = pd.concat([existing, qlib_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=['date'], keep='last')
            combined = combined.sort_values('date')
            combined.to_csv(output_file, index=False)
        else:
            qlib_df.to_csv(output_file, index=False)
        
    print(f"✅ 已保存到: {output_dir}")
    print(f"共 {len(list(output_path.glob('*.csv')))} 只股票")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='data/tushare_csi300_202310_202604.csv')
    parser.add_argument('--output', default='~/.qlib/qlib_data/cn_data/features')
    args = parser.parse_args()
    
    convert_csv_to_bin(args.input, args.output)
