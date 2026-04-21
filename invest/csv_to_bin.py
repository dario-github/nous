"""
CSV 转换为 Qlib bin 格式 - 正确的 Qlib 格式

Qlib bin 格式说明:
- 文件头 (4 bytes): start_index (float32) - 对应 calendar 中的位置
- 数据部分: 连续的 float32 值

注意: Qlib 使用 calendar 索引，而不是实际日期!
"""
import pandas as pd
import numpy as np
from pathlib import Path
import struct
import qlib
from qlib.config import REG_CN

def load_calendar(provider_uri='~/.qlib/qlib_data/cn_data'):
    """加载 Qlib 的交易日历"""
    provider_uri = Path(provider_uri).expanduser()
    qlib.init(provider_uri=str(provider_uri), region=REG_CN)
    from qlib.data.storage.file_storage import FileCalendarStorage
    calendar_storage = FileCalendarStorage(freq='day', future=False)
    return calendar_storage.data

def convert_csv_to_qlib_bin_correct(csv_file, output_dir, calendars):
    """
    将单个股票的 CSV 转换为 Qlib bin 格式（正确版本）
    
    参数:
        csv_file: 输入 CSV 文件路径
        output_dir: 输出目录
        calendars: 交易日历列表
    """
    df = pd.read_csv(csv_file)
    if len(df) == 0:
        return False
    
    # 确保日期格式正确并排序
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 定义字段映射: Qlib字段名 -> CSV列名
    fields = {
        'open': 'open',
        'close': 'close',
        'high': 'high',
        'low': 'low',
        'volume': 'volume',
        'money': 'money',
        'factor': 'factor',
    }
    
    # 获取该股票的起止日期
    start_date = df['date'].min()
    end_date = df['date'].max()
    
    # 创建日期到值的映射
    date_to_values = {}
    for _, row in df.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d')
        date_to_values[date_str] = row
    
    # 为每个字段创建 .day.bin 文件
    for field_name, col_name in fields.items():
        if col_name not in df.columns:
            continue
            
        bin_file = output_path / f"{field_name}.day.bin"
        
        # 找到该股票数据在 calendar 中的起始索引
        start_idx = None
        for i, cal_date in enumerate(calendars):
            cal_date_str = pd.Timestamp(cal_date).strftime('%Y-%m-%d')
            if cal_date_str in date_to_values:
                start_idx = i
                break
        
        if start_idx is None:
            print(f"  警告: {csv_file.stem} 没有找到匹配的 calendar 日期")
            continue
        
        # 构建数据数组
        # 从 start_idx 开始，对每个 calendar 日期，如果有数据就填充，没有就用 nan
        values = []
        for i in range(start_idx, len(calendars)):
            cal_date_str = pd.Timestamp(calendars[i]).strftime('%Y-%m-%d')
            if cal_date_str in date_to_values:
                val = float(date_to_values[cal_date_str][col_name])
                values.append(val)
            else:
                # 如果数据结束，停止
                if pd.Timestamp(calendars[i]) > end_date:
                    break
                values.append(np.nan)
        
        if not values:
            continue
            
        # 写入 bin 文件: [start_index] + [values...]
        with open(bin_file, 'wb') as f:
            # 第一个值是 start_index
            f.write(struct.pack('<f', float(start_idx)))
            # 后续是数据值
            for val in values:
                f.write(struct.pack('<f', float(val) if not np.isnan(val) else np.nan))
        
    return True

def batch_convert_csv_to_bin(features_dir, output_base_dir, provider_uri='~/.qlib/qlib_data/cn_data'):
    """
    批量转换所有 CSV 文件到 bin 格式
    
    输出结构: output_base_dir/{stock_code}/{field}.day.bin
    """
    features_path = Path(features_dir).expanduser()
    output_base = Path(output_base_dir).expanduser()
    
    # 加载 calendar
    print("加载 Qlib 交易日历...")
    calendars = load_calendar(provider_uri)
    print(f"  共 {len(calendars)} 个交易日")
    print(f"  范围: {calendars[0]} ~ {calendars[-1]}")
    
    csv_files = list(features_path.glob("*.csv"))
    print(f"\n找到 {len(csv_files)} 个 CSV 文件")
    
    success_count = 0
    for i, csv_file in enumerate(csv_files):
        stock_code = csv_file.stem
        output_dir = output_base / stock_code
        
        try:
            if convert_csv_to_qlib_bin_correct(csv_file, output_dir, calendars):
                success_count += 1
                if (i + 1) % 100 == 0:
                    print(f"  已处理 {i + 1}/{len(csv_files)}...")
        except Exception as e:
            print(f"  错误 {stock_code}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n✅ 成功转换 {success_count}/{len(csv_files)} 只股票")
    return success_count

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert CSV to Qlib bin format')
    parser.add_argument('--input', default='~/.qlib/qlib_data/cn_data/features',
                       help='Input CSV files directory')
    parser.add_argument('--output', default='~/.qlib/qlib_data/cn_data/features',
                       help='Output bin files directory')
    parser.add_argument('--provider-uri', default='~/.qlib/qlib_data/cn_data',
                       help='Qlib data directory for calendar')
    
    args = parser.parse_args()
    
    # 转换
    count = batch_convert_csv_to_bin(args.input, args.output, args.provider_uri)
    print(f"\n输出目录: {args.output}")
