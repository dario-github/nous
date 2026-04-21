"""
诊断 Qlib instruments 解析问题的调试脚本
"""
import sys
sys.path.insert(0, '/Users/yan/clawd-agents/research/nous-invest/.venv/lib/python3.12/site-packages')

import qlib
from qlib.config import REG_CN
from qlib.data import D

print("=" * 60)
print("Qlib Instruments 诊断")
print("=" * 60)

# 初始化 Qlib
qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region=REG_CN)
print("✅ Qlib 初始化完成\n")

# 检查 instruments 解析
print("测试 1: 直接读取 csi300 股票池")
print("-" * 40)
try:
    # 使用 D.list_instruments 获取 instruments
    instruments = D.list_instruments(instruments="csi300")
    print(f"返回类型: {type(instruments)}")
    if isinstance(instruments, dict):
        print(f"返回 keys 数量: {len(instruments)}")
        print(f"前 10 个 keys: {list(instruments.keys())[:10]}")
    elif isinstance(instruments, list):
        print(f"返回列表长度: {len(instruments)}")
        print(f"前 10 个: {instruments[:10]}")
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()

# 检查 instrument 文件
print("\n测试 2: 检查 instruments 文件格式")
print("-" * 40)
import pandas as pd
from pathlib import Path

csi300_path = Path.home() / ".qlib/qlib_data/cn_data/instruments/csi300.txt"
if csi300_path.exists():
    print(f"文件存在: {csi300_path}")
    print(f"文件大小: {csi300_path.stat().st_size} bytes")
    print(f"文件行数: {sum(1 for _ in open(csi300_path))}")
    print("\n前 20 行内容:")
    with open(csi300_path) as f:
        for i, line in enumerate(f):
            if i >= 20:
                break
            print(f"  [{i+1}] {line.strip()!r}")
else:
    print(f"❌ 文件不存在: {csi300_path}")

# 检查 features 目录
print("\n测试 3: 检查 features 目录")
print("-" * 40)
features_dir = Path.home() / ".qlib/qlib_data/cn_data/features"
if features_dir.exists():
    files = list(features_dir.glob("*.csv"))
    print(f"features 目录存在，包含 {len(files)} 个 CSV 文件")
    print(f"示例文件: {files[0].name if files else '无'}")
    # 检查一个文件内容
    if files:
        sample_df = pd.read_csv(files[0])
        print(f"\n示例文件 {files[0].name} 的内容:")
        print(sample_df.head())
else:
    print(f"❌ features 目录不存在: {features_dir}")

# 检查 instruments 解析配置
print("\n测试 4: 检查 Qlib 配置")
print("-" * 40)
from qlib.config import C
print(f"provider_uri: {C.get('provider_uri')}")
print(f"region: {C.get('region')}")
print(f"inst_processor: {C.get('inst_processor')}")

# 检查 list_instruments 的底层实现
print("\n测试 5: 直接使用 InstrumentStore")
print("-" * 40)
try:
    from qlib.data.data import InstrumentStore
    inst_store = InstrumentStore(Market="csi300", freq="day")
    # 获取所有 instruments
    all_inst = inst_store.get_all_instruments()
    print(f"InstrumentStore 返回类型: {type(all_inst)}")
    print(f"InstrumentStore 返回数量: {len(all_inst)}")
    if isinstance(all_inst, dict):
        print(f"前 5 个: {dict(list(all_inst.items())[:5])}")
    elif isinstance(all_inst, pd.DataFrame):
        print(f"列名: {all_inst.columns.tolist()}")
        print(f"前 5 行:\n{all_inst.head()}")
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
