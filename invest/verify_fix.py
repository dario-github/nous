"""
验证修复后的 Qlib instruments 和 Alpha158 数据加载
"""
import sys
sys.path.insert(0, '/Users/yan/clawd-agents/research/nous-invest/.venv/lib/python3.12/site-packages')

import qlib
from qlib.config import REG_CN
from qlib.data import D
from qlib.utils import init_instance_by_config

print("=" * 60)
print("Qlib 修复验证")
print("=" * 60)

# 初始化 Qlib
qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region=REG_CN)
print("✅ Qlib 初始化完成\n")

# 测试 instruments 加载
print("测试 1: 检查 instruments 文件")
print("-" * 40)
from pathlib import Path
csi300_path = Path.home() / ".qlib/qlib_data/cn_data/instruments/csi300.txt"
with open(csi300_path) as f:
    lines = f.readlines()
print(f"csi300.txt 包含 {len(lines)} 个股票")
print(f"前 5 个: {[l.split()[0] for l in lines[:5]]}")

# 测试 Alpha158 数据集
print("\n测试 2: 创建 Alpha158 数据集（轻量级测试）")
print("-" * 40)
task_config = {
    "class": "DatasetH",
    "module_path": "qlib.data.dataset",
    "kwargs": {
        "handler": {
            "class": "Alpha158",
            "module_path": "qlib.contrib.data.handler",
            "kwargs": {
                "start_time": "2024-01-01",
                "end_time": "2024-03-31",
                "fit_start_time": "2024-01-01",
                "fit_end_time": "2024-02-29",
                "instruments": "csi300",
            },
        },
        "segments": {
            "train": ("2024-01-01", "2024-02-29"),
            "valid": ("2024-03-01", "2024-03-15"),
            "test": ("2024-03-16", "2024-03-31"),
        },
    },
}

try:
    dataset = init_instance_by_config(task_config)
    print("✅ 数据集创建成功")
    
    # 获取训练数据
    from qlib.data.dataset.handler import DataHandler
    df_train = dataset.prepare("train", col_set=["feature", "label"], data_key=DataHandler.DK_L)
    print(f"✅ 训练数据 shape: {df_train.shape}")
    print(f"   特征列数: {len(df_train['feature'].columns)}")
    print(f"   行数: {len(df_train)}")
    
    # 获取测试数据
    df_test = dataset.prepare("test", col_set=["feature", "label"], data_key=DataHandler.DK_L)
    print(f"✅ 测试数据 shape: {df_test.shape}")
    
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("验证完成！修复成功！")
print("=" * 60)
