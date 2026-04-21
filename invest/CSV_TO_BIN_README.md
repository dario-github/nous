"""
CSV 转 Qlib Bin 格式工具
=======================

此脚本将 Qlib features 目录中的 CSV 文件转换为 Qlib 原生的 bin 格式，
使 Alpha158 等处理器能够正确读取数据。

使用方法:
    .venv/bin/python csv_to_bin.py

Qlib Bin 格式说明:
- 每个股票一个子目录 (如 SH600000/)
- 每个字段一个 .day.bin 文件 (如 close.day.bin, open.day.bin)
- 文件结构: [start_index (float32)] + [values (float32 array)]
- start_index 是数据在交易日历中的起始位置

转换后结构:
    ~/.qlib/qlib_data/cn_data/features/
    ├── SH600000/
    │   ├── open.day.bin
    │   ├── close.day.bin
    │   ├── high.day.bin
    │   ├── low.day.bin
    │   ├── volume.day.bin
    │   ├── money.day.bin
    │   └── factor.day.bin
    ├── SH600009/
    │   └── ...
    └── ...

已转换数据:
- 沪深300 (300只股票) ✅
- 数据范围: 2023-10-09 至 2026-04-15
- 交易日历: 2005-01-04 至 2026-04-16 (5168天)

验证结果:
- Alpha158 成功加载 159 个特征
- Qlib D.features() 正确读取数据
- 数据格式完全兼容 Qlib 标准

后续步骤:
如需转换中证500/中证1000数据，将CSV文件放入features目录后重新运行此脚本。
"""
