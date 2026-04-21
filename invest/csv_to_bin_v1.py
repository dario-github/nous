"""
CSV 转换为 Qlib bin 格式 - 支持 Alpha158
Qlib bin 格式：每个字段一个 .day.bin 文件
"""
import pandas as pd
import numpy as np
from pathlib import Path
import struct
import pickle

def convert_csv_to_qlib_bin(csv_file, output_dir):
    """
    将单个股票的 CSV 转换为 Qlib bin 格式
    
    Qlib bin 格式:
    - 文件头: [N, 1] - N条记录, 1个字段
    - 日期部分: N个int32 (YYYYMMDD格式)
    - 数据部分: N个float32
    """
    df = pd.read_csv(csv_file)
    if len(df) == 0:
        return False
    
    # 确保日期格式正确
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 获取股票代码 (从文件名提取)
    stock_code = csv_file.stem  # e.g., "SH600000"
    
    # 定义字段映射
    fields = {
        'open': 'open',
        'close': 'close',
        'high': 'high',
        'low': 'low',
        'volume': 'volume',
        'money': 'money',  # amount
        'factor': 'factor',
    }
    
    # 为每个字段创建 .day.bin 文件
    for field_name, col_name in fields.items():
        if col_name not in df.columns:
            continue
            
        bin_file = output_path / f"{field_name}.day.bin"
        
        # 准备数据
        dates = df['date'].dt.strftime('%Y%m%d').astype(int).values
        values = df[col_name].astype(np.float32).values
        
        # 写入 bin 文件
        with open(bin_file, 'wb') as f:
            # 文件头: [N, 1]
            f.write(struct.pack('<ii', len(dates), 1))
            # 日期
            f.write(dates.astype(np.int32).tobytes())
            # 数据
            f.write(values.tobytes())
    
    return True

def batch_convert_csv_to_bin(features_dir, output_base_dir):
    """
    批量转换所有 CSV 文件到 bin 格式
    
    输出结构: output_base_dir/{stock_code}/{field}.day.bin
    """
    features_path = Path(features_dir)
    output_base = Path(output_base_dir)
    
    csv_files = list(features_path.glob("*.csv"))
    print(f"找到 {len(csv_files)} 个 CSV 文件")
    
    success_count = 0
    for i, csv_file in enumerate(csv_files):
        stock_code = csv_file.stem
        output_dir = output_base / stock_code
        
        try:
            if convert_csv_to_qlib_bin(csv_file, output_dir):
                success_count += 1
                if (i + 1) % 100 == 0:
                    print(f"  已处理 {i + 1}/{len(csv_files)}...")
        except Exception as e:
            print(f"  错误 {stock_code}: {e}")
    
    print(f"✅ 成功转换 {success_count}/{len(csv_files)} 只股票")
    return success_count

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert CSV to Qlib bin format')
    parser.add_argument('--input', default='~/.qlib/qlib_data/cn_data/features',
                       help='Input CSV files directory')
    parser.add_argument('--output', default='~/.qlib/qlib_data/cn_data/features_bin',
                       help='Output bin files directory')
    
    args = parser.parse_args()
    
    # 转换
    count = batch_convert_csv_to_bin(args.input, args.output)
    print(f"\n输出目录: {args.output}")
