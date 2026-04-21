"""
详细调试 Qlib 数据加载问题
"""
import multiprocessing
multiprocessing.set_start_method('fork', force=True)

import pandas as pd
import numpy as np
from pathlib import Path

import qlib
from qlib.config import REG_CN
from qlib.data import D

print("=" * 60)
print("Qlib 详细数据加载调试")
print("=" * 60)

# 初始化 Qlib
qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region=REG_CN)
print("✅ Qlib 初始化完成\n")

# 1. 检查 instruments
print("1. 检查 instruments 加载")
print("-" * 40)
from qlib.data.data import Inst
instruments = Inst.list_instruments(instruments="csi300", as_list=True)
print(f"Instruments 数量: {len(instruments)}")
print(f"前 10 个: {instruments[:10]}")

# 2. 检查 calendar
print("\n2. 检查交易日历")
print("-" * 40)
from qlib.data.data import Cal
calendar = Cal.calendar(freq='day')
print(f"总交易日数: {len(calendar)}")
print(f"日历范围: {calendar[0]} ~ {calendar[-1]}")

# 3. 直接检查特征数据
print("\n3. 直接检查特征数据加载")
print("-" * 40)
try:
    # 尝试加载单个股票的特征数据
    test_inst = instruments[0] if instruments else "SH600000"
    print(f"测试股票: {test_inst}")
    
    # 使用 D.features 加载数据
    fields = ['$close', '$open', '$high', '$low', '$volume']
    df = D.features([test_inst], fields, start_time='2023-10-09', end_time='2024-03-31', freq='day')
    print(f"D.features 返回:")
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {df.columns.tolist()}")
    if len(df) > 0:
        print(f"  前 5 行:\n{df.head()}")
    else:
        print("  ⚠️ 数据为空!")
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()

# 4. 测试 Alpha158 数据准备
print("\n4. 测试 Alpha158 数据准备")
print("-" * 40)
from qlib.contrib.data.handler import Alpha158
from qlib.data.dataset.handler import DataHandler

try:
    handler = Alpha158(
        instruments="csi300",
        start_time="2024-01-01",
        end_time="2024-03-31",
        fit_start_time="2024-01-01",
        fit_end_time="2024-02-29",
    )
    print(f"✅ Alpha158 handler 创建成功")
    
    # 获取数据
    df = handler.fetch(data_key=DataHandler.DK_L)
    print(f"Handler fetch 返回:")
    print(f"  Shape: {df.shape}")
    if len(df) > 0:
        print(f"  列数: {len(df.columns)}")
        print(f"  列名 (前 10): {df.columns[:10].tolist()}")
        print(f"  前 3 行:\n{df.head(3)}")
    else:
        print("  ⚠️ 数据为空!")
        
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("调试完成")
print("=" * 60)
