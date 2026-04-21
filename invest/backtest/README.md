# Nous Invest - 回测与评估体系

## 模块概述

本模块实现了完整的量化策略回测与评估能力 (Module 5-7)，包括:

| 模块 | 文件 | 功能描述 |
|------|------|----------|
| Module 5 | `qlib_backtest.py` | Qlib回测框架封装，支持周频调仓、成本模拟、滑点估计 |
| Module 6a | `weekly_metrics.py` | 周超额评估指标 (Weekly Alpha/Sharpe/Drawdown) |
| Module 6b | `capacity_analyzer.py` | 容量与冲击成本分析 |
| Module 7a | `daily_monitor.py` | 每日信号输出与风险监控 |
| Module 7b | `report_template.py` | 回测报告模板 |
| 主入口 | `__init__.py` | 一站式回测流程 `run_full_backtest_pipeline()` |
| CLI | `run_backtest.py` | 命令行运行脚本 |

## 快速开始

### 1. 使用一站式回测流程

```python
from backtest import run_full_backtest_pipeline

results = run_full_backtest_pipeline(
    predictions=signal_df,          # 预测信号 DataFrame
    capital=5_000_000,               # 初始资金
    start_date="2022-01-01",
    end_date="2025-12-31",
    output_dir="./reports",
    strategy_name="Nous Strategy"
)
```

### 2. 单独使用各模块

#### 周超额指标计算
```python
from backtest import WeeklyAlphaCalculator, calculate_weekly_alpha_metrics

# 计算周超额指标
metrics, weekly_alpha = calculate_weekly_alpha_metrics(
    strategy_returns,
    benchmark_returns
)

# 生成报告
calculator = WeeklyAlphaCalculator()
print(calculator.generate_report(metrics))
```

#### 容量分析
```python
from backtest import CapacityAnalyzer, estimate_portfolio_capacity

# 分析组合容量
portfolio, estimates = estimate_portfolio_capacity(
    stock_data_df,
    capital=5_000_000,
    target_positions=20
)

# 生成报告
analyzer = CapacityAnalyzer()
print(analyzer.generate_capacity_report(portfolio, estimates))
```

#### 每日监控
```python
from backtest import DailyMonitor, run_daily_monitor

# 生成每日监控
result = run_daily_monitor(
    predictions=predictions_df,
    current_drawdown=0.08,
    output_dir="./signals"
)

print(result["output_text"])
```

### 3. 命令行使用

```bash
# 完整回测
python backtest/run_backtest.py \
    --signal-file ./signals/predictions.csv \
    --output ./reports \
    --capital 5000000 \
    --start-date 2022-01-01

# 仅每日监控
python backtest/run_backtest.py --daily \
    --signal-file ./signals/latest.csv \
    --output ./signals
```

## 核心指标说明

### 周超额指标 (对齐私募标准)

| 指标 | 说明 | 目标值 |
|------|------|--------|
| 平均周超额 | 策略周收益 - 基准周收益 | > 0.5% |
| 周超额夏普 | 周超额收益 / 周超额波动 × √52 | > 1.5 |
| 最大回撤 | 从高点到低点的最大跌幅 | < 15% |
| 周胜率 | 周超额 > 0 的周数占比 | > 50% |
| 盈亏比 | 盈利周平均 / 亏损周平均 | > 1.0 |

### 容量评估指标

| 指标 | 说明 |
|------|------|
| 安全容量 | 基于日均成交额的可交易金额 (不造成明显冲击成本) |
| 最大容量 | 理论上限 (2倍安全容量) |
| 冲击成本 | 买入特定比例日均成交额的估计成本 (bps) |
| 流动性评分 | 0-100分，综合成交额、波动率、换手率 |

### 风险监控阈值

| 指标 | 警告 | 严重 | 紧急 |
|------|------|------|------|
| Top5集中度 | 40% | 50% | - |
| 最大回撤 | 10% | 15% | 20% |
| 流动性评分 | 50 | 30 | - |

## 文件结构

```
backtest/
├── __init__.py              # 包入口，一站式流程
├── qlib_backtest.py        # Qlib回测框架
├── weekly_metrics.py       # 周超额指标
├── capacity_analyzer.py    # 容量分析
├── daily_monitor.py        # 每日监控
├── report_template.py      # 报告模板
├── run_backtest.py         # CLI脚本
└── README.md               # 本文件
```

## 与其他模块的关系

```
┌─────────────────────────────────────────────────────────────┐
│                   Nous Invest v0.3                          │
├─────────────────────────────────────────────────────────────┤
│  Data Ingestion ──> Feature Engineering ──> Model Layer     │
│      (Tushare)        (自研特征)            (LightGBM)       │
│                              │                              │
│                              ▼                              │
│                    ┌─────────────────┐                     │
│                    │   Predictions   │                     │
│                    └────────┬────────┘                     │
│                             │                              │
│                             ▼                              │
│  ┌────────────────────────────────────────────────────────┐│
│  │              Backtest & Evaluation                      ││
│  │  ┌──────────────┬──────────────┬──────────────┐        ││
│  │  │ Qlib回测     │ 周超额指标   │ 容量分析     │        ││
│  │  │ 成本模拟     │ Sharpe/回撤  │ 冲击成本     │        ││
│  │  └──────────────┴──────────────┴──────────────┘        ││
│  │                              │                           ││
│  │                              ▼                           ││
│  │  ┌──────────────┬──────────────┬──────────────┐          ││
│  │  │ 每日监控     │ 风险预警     │ 报告输出     │          ││
│  │  │ 信号输出     │ 健康检查     │ Markdown/JSON│          ││
│  │  └──────────────┴──────────────┴──────────────┘          ││
│  └────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## 更新日志

- **v0.1.0** (2026-04-16): 初始版本，完成Module 5-7
  - Qlib回测框架封装
  - 周超额评估指标实现
  - 容量与冲击成本模型
  - 每日信号输出与风险监控
  - Markdown/JSON报告模板

## 注意事项

1. **Qlib依赖**: `qlib_backtest.py` 依赖qlib库，如果plotly等可视化库缺失，会自动降级使用
2. **数据格式**: 预测信号DataFrame需要包含 `date`, `instrument`, `score` 三列
3. **交易日历**: 周超额计算默认使用周五为周结束日 (`W-FRI`)，可根据需要调整
4. **容量估计**: 容量分析需要股票的日均成交额数据，实际使用时应从Tushare等数据源获取
