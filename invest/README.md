# Nous Invest — A 股 AI 选股择时系统

基于 LightGBM 的 A 股量化选股框架，支持全自动每日循环。

## 🚀 快速开始

```bash
# 激活环境
source .venv/bin/activate

# 查看最新选股信号
python view_signals.py

# 手动运行完整流程
python daily_loop.py --test

# 正式运行（含数据下载）
python daily_loop.py
```

## 🤖 全自动每日 Loop

系统支持全自动每日 Pipeline，详见 [INSTALL_CRON.md](./INSTALL_CRON.md)：

| 步骤 | 功能 | 状态 |
|------|------|------|
| 1️⃣ | 定时触发（工作日 18:00） | Cron |
| 2️⃣ | 增量下载 Tushare 数据 | ✅ |
| 3️⃣ | LightGBM 选股模型运行 | ✅ |
| 4️⃣ | 信号保存到 `signals/` | ✅ |
| 5️⃣ | Discord/飞书通知推送 | ✅ |

### 设置定时任务

```bash
# 编辑 crontab
crontab -e

# 添加（工作日 18:00 运行）
0 18 * * mon-fri /Users/yan/clawd-agents/research/nous-invest/run_daily.sh
```

## 📁 目录结构

```
nous-invest/
├── config/               # Qlib 配置文件
├── data/                 # 数据缓存
├── models/               # 模型输出
├── signals/              # 每日选股信号 📊
├── reports/              # 评估报告
├── logs/                 # 运行日志
├── daily_loop.py         # 主自动化脚本 🤖
├── run_round2_simple.py  # LightGBM 模型
├── update_tushare_daily.py  # 增量数据更新
├── view_signals.py       # 信号查看工具
└── run_daily.sh          # Cron 包装脚本
```

## 🎯 选股信号

**生成文件：**
- `signals/signal_YYYYMMDD_round2_simple.csv` - 每日选股信号
- `signals/metrics_YYYYMMDD_round2_simple.json` - 模型指标

**查看最新信号：**
```bash
python view_signals.py
```

输出示例：
```
🏆 Top 20 选股信号:
排名 股票代码      预测分数      收盘价     信号强度
 1   600183.SH  +0.004256   58.98      📊
 2   600482.SH  +0.004256   35.00      📊
...（依此类推）
```

## 📊 模型指标

当前模型表现（Round 2 - 简化版）：

| 指标 | 数值 |
|------|------|
| IC Mean | +0.0212 |
| ICIR | +0.1698 |
| 年化 IR | +2.6950 |
| IC > 0 比例 | 57.5% |
| 测试期 | 2025-04-01 ~ 2026-04-08 |

## 🔧 环境要求

- Python 3.12 (brew python@3.12)
- pyqlib 0.9.7+
- LightGBM
- requests (用于通知)

## 📖 文档

- [INSTALL_CRON.md](./INSTALL_CRON.md) - 自动化安装指南
- [RESEARCH.md](./RESEARCH.md) - 调研详情
