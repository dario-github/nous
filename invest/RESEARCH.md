# Nous Invest — Qlib 调研报告

> 调研日期：2026-04-16

## 1. Qlib 概况

| 项目 | 详情 |
|------|------|
| 仓库 | https://github.com/microsoft/qlib |
| 版本 | v0.9.7 (pip 最新), v0.9.0 是最后 tagged release (Dec 2022) |
| 许可证 | MIT |
| 支持Python | 3.8–3.12 (pip安装), 3.14 不支持 |
| 星标 | 16K+ |
| 最近活跃度 | main 分支持续活跃，2025 年有多次合并；RD-Agent 集成为最新重点 |

## 2. 内置因子库 — Alpha158

Alpha158 是 Qlib 内置的主力因子集（`qlib.contrib.data.handler.Alpha158`），覆盖：

**KBarch 特征 (15个)**: open/close/high/low/volume 的各种比率（如 close/open, high/close, low/close, amount 等）

**技术指标特征 (约 140 个)**:
- MA (移动平均): 5/10/20/30/60 日均线及比率
- MACD 类
- RSI
- ROC (变动率)
- Bollinger Band
- 标准差
- 动量因子
- 量价关系（如 volume*close_change 等）
- 各种时间窗口 (5/10/20/30/60 日)

**特征类型**:
- 原始价量比率
- 时序统计（均值/标准差/分位数）
- 技术指标衍生
- 截面排名

Alpha158 基本覆盖了 A 股量化常用的价量因子，可直接使用。

## 3. 内置模型

| 模型 | 类路径 | 说明 |
|------|--------|------|
| **LGBModel** | `qlib.contrib.model.gbdt` | LightGBM，主力基线模型 |
| **XGBModel** | `qlib.contrib.model.xgboost` | XGBoost |
| **DoubleEnsemble** | `qlib.contrib.model.double_ensemble` | 微软论文模型 |
| **Transformer** | `qlib.contrib.model.transformer` | Transformer 时序模型 |
| **Localformer** | `qlib.contrib.model.localformer` | Local Attention |
| **TCTS** | `qlib.contrib.model.tcts` | 时序聚类 |
| **TRA** | `qlib.contrib.model.tra` | Temporal Routing Adaptor |
| **HIST** | `qlib.contrib.model.hist` | 基于图的关系学习模型 |
| **IGMTF** | `qlib.contrib.model.igmtf` | 行业图模型 |
| **TabNet** | `qlib.contrib.model.tabnet` | Google TabNet |
| **ALSTM** | `qlib.contrib.model.alstm` | Attention LSTM |
| **GATs** | `qlib.contrib.model.gats` | 图注意力网络 |
| **MLP** | `qlib.contrib.model.mlp` | 基础 MLP |
| **TFT** | PyTorch forecasting | Temporal Fusion Transformer (需额外安装) |

**结论**: LightGBM 是最佳起点 — 训练快、效果好、不易过拟合。后续可尝试 Transformer/HIST。

## 4. A 股数据支持

| 数据源 | 方式 | 说明 |
|--------|------|------|
| 内置官方数据 | `python -m qlib.cli.data` | ⚠️ 目前因数据安全策略暂停 |
| **社区数据** | chenditc/investment_data | ✅ 推荐，每日更新，覆盖全 A 股 |
| Tushare → Qlib | 自写 dump 脚本 | 可行，但需手动处理 |
| AKShare → Qlib | 自写 dump 脚本 | 可行，免费但限速 |

社区数据包含：
- 日线 OHLCV（全市场）
- 复权因子
- 股票列表/指数成分
- 时间跨度：约 2007–至今

## 5. 回测引擎

Qlib 内置回测引擎，配置示例：

```yaml
backtest:
    start_time: 2017-01-01
    end_time: 2020-08-01
    account: 100000000
    benchmark: SH000300
    exchange_kwargs:
        limit_threshold: 0.095    # 涨跌停限制（A 股 10%）
        deal_price: close          # 成交价
        open_cost: 0.0005          # 买入成本（万5）
        close_cost: 0.0015         # 卖出成本（万15含印花税）
        min_cost: 5                # 最低手续费 5 元
```

**A 股支持评估**:
- ✅ 涨跌停限制 (`limit_threshold`)
- ✅ 交易成本（买卖分开设置）
- ✅ T+1 — 通过 `TopkDropoutStrategy` 实现，策略层面不当日买卖
- ✅ 基准对比
- ⚠️ 不内置停牌/ST 处理（需在数据层处理）
- ⚠️ 不内置最小交易单位 100 股（需自定义）

## 6. 评估指标

Qlib 内置评估覆盖：

| 指标 | 支持 | 说明 |
|------|------|------|
| **IC** | ✅ | 信息系数，自动计算 |
| **ICIR** | ✅ | IC 的信息比率 |
| **Sharpe** | ✅ | 年化夏普比率 |
| **MaxDD** | ✅ | 最大回撤 |
| **Alpha** | ✅ | 超额收益 |
| **Precision@k** | ✅ | 前k股票精确率 |
| **累计收益曲线** | ✅ | 自动绘图 |
| Turnover | ✅ | 换手率 |
| Volatility | ✅ | 波动率 |

**SPEC v0.2 覆盖度**: 全部覆盖 ✅

## 7. 备选方案对比

| 维度 | Qlib | Backtrader | vnpy | wondertrader |
|------|------|-----------|------|-------------|
| **定位** | AI 量化研究平台 | 事件驱动回测 | 实盘交易框架 | C++ 高性能回测 |
| **因子研究** | ✅ 强 | ❌ 需自写 | ⚠️ 基础 | ❌ 需自写 |
| **ML 集成** | ✅ 内置 | ❌ 需自写 | ❌ 需自写 | ❌ |
| **A 股 T+1** | ✅ | ✅ | ✅ | ✅ |
| **交易成本** | ✅ | ✅ | ✅ | ✅ |
| **实盘** | ⚠️ 在线 serving | ❌ | ✅ 强 | ✅ |
| **回测速度** | 中 | 慢 | 中 | 极快 |
| **学习曲线** | 中 | 低 | 高 | 高 |
| **社区** | 16K⭐ | 14K⭐ | 25K⭐ | 2K⭐ |
| **适合场景** | 因子挖掘+选股 | 策略验证 | 实盘交易 | 高频/大规模 |

**结论**:
- **选股择时**: Qlib 是最佳选择（因子+ML+回测一体化）
- **实盘**: 后续需要 vnpy 对接券商接口
- **高频**: wondertrader 备选，但不适合当前阶段

## 8. Tushare/AKShare 集成方案

### 方案一：社区数据（推荐）
直接使用 chenditc/investment_data，免费、每日更新、格式兼容。

### 方案二：Tushare → Qlib
```python
# 1. 用 tushare 下载日线数据
# 2. 转换为 Qlib 格式 (qlib dump)
python -m qlib.cli.data dump --csv_path data/ --qlib_dir ~/.qlib/qlib_data/cn_data
```
需要 Tushare token，有积分限制。

### 方案三：AKShare → Qlib
类似 Tushare，但免费。适合补充社区数据没有的字段（如财务数据）。

## 9. 架构决策

### 技术栈
```
数据层: Qlib 社区数据 (chenditc) + AKShare 补充
因子层: Alpha158 (内置) + 自定义因子
模型层: LightGBM → Transformer/HIST
回测层: Qlib 内置回测引擎
评估层: Qlib 内置 IC/ICIR/Sharpe/MaxDD
输出层: 每日选股信号 → CSV/JSON
```

### 环境要求
- Python 3.12 (brew python@3.12)
- pyqlib 0.9.7
- lightgbm 4.6.0
- 虚拟环境: nous-invest/.venv

### 目录结构
```
nous-invest/
├── .venv/              # Python 3.12 venv
├── RESEARCH.md         # 本调研报告
├── README.md           # 项目说明
├── requirements.txt    # 依赖
├── config/
│   └── base.yaml       # Qlib 基础配置 (LightGBM + Alpha158)
├── data/               # 数据目录 (symlink 或 cache)
├── models/             # 模型输出
├── signals/            # 选股信号输出
├── reports/            # 评估报告
└── run.py              # 主运行脚本
```
