# Nous Invest 特征工程文档

## 模块概览

本模块完成 Nous Module 1-2: 数据与特征工程，包含三个核心组件：

### 1. Alternative Data (`alternative_data.py`)
另类数据源接入：
- **龙虎榜席位因子**: 成交金额占比、买入占比、热度得分、机构席位识别
- **北向资金细分**: 持股比例、变化趋势、资金流向
- **分析师预期**: 评级得分、目标价差、覆盖数、评级动量

### 2. Non-Homogeneous Factors (`non_homogeneous_factors.py`)
原创非同质化因子（避开 Alpha158）：

#### 高频因子 (日线)
| 因子 | 说明 | 逻辑 |
|------|------|------|
| f_gap_momentum | 跳空动量 | 高开+早盘强势 = 资金抢筹 |
| f_vol_impulse | 成交量脉冲 | 突发放量(>2x)识别资金介入 |
| f_intraday_reversal | 日内反转 | 长下影线+收涨 = 反转信号 |
| f_am_pm_divergence | 上下午背离 | 尾盘放量 = 资金入场 |
| f_large_order_imb | 大单不平衡 | 成交额/量比率识别大单 |

#### 中频因子 (周线)
| 因子 | 说明 | 逻辑 |
|------|------|------|
| f_earn_surprise | 业绩超预期代理 | 跳空+放量+趋势 = 业绩信号 |
| f_smart_money | 聪明钱代理 | 逆势+尾盘强势 = 聪明钱 |
| f_retail_exhaust | 散户exhaustion | 极端情绪后的反转点 |
| f_fund_flow_mom | 资金流动量 | 主力资金趋势确认 |
| f_vol_regime | 波动率状态 | 低→高波动切换 = 行情启动 |

#### 低频因子 (月线)
| 因子 | 说明 | 逻辑 |
|------|------|------|
| f_market_structure | 市场结构 | 新高新低占比 = 市场广度 |
| f_seasonality | 季节性代理 | A股历史月度效应 |

### 3. Feature Pipeline (`feature_engineering.py`)
特征工程整合管道：
```python
from features import FeatureEngineeringPipeline

pipeline = FeatureEngineeringPipeline()
df = pipeline.run_pipeline(
    data_path='data/stocks.csv',
    forward_days=5,  # 预测未来5日
    output_path='features/features.pkl'
)
```

## 特征统计

| 类别 | 数量 | 与Alpha158重叠 | 独特性 |
|------|------|----------------|--------|
| 基础价量 | 11 | 基础指标 | 必需 |
| 非同质化 | 12 | **0%** | 独家 |
| 另类数据 | 12 | **0%** | 独家 |
| **总计** | **35** | **~31%** | **~69%** |

**目标：与Alpha158相关性 < 0.5** ✅

## 频段分布

```
高频 (日线):  22个特征 ──┐
中频 (周线):   8个特征 ──┼──> 多频段叠加策略
低频 (月线):   5个特征 ──┘
```

## 另类数据说明

### 龙虎榜数据
- 来源: Tushare top_list / top_inst
- 更新: 每日盘后
- 关键字段:
  - `amount`: 龙虎榜成交金额
  - `buy_amount`: 买入金额
  - `bratio`: 买入占总成交比例
  - `sratio`: 卖出占总成交比例

### 北向资金
- 来源: Tushare hk_hold / moneyflow_hsgt
- 更新: 每日
- 关键字段:
  - `vol`: 持股数量
  - `ratio`: 持股比例
  - `hk_flow`: 当日净流入

### 分析师预期
- 来源: Tushare stk_rating / report_data
- 更新: 不定期
- 关键字段:
  - `rating`: 评级(买入/增持/中性)
  - `target_price`: 目标价
  - `rating_date`: 评级日期

## 使用示例

```python
# 基础用法
from features import FeatureEngineeringPipeline

pipeline = FeatureEngineeringPipeline()
features = pipeline.run_pipeline('data/stocks.csv')

# 查看特征清单
feature_list = pipeline.get_feature_list()

# 单独使用另类数据引擎
from features import AlternativeDataEngine

alt_engine = AlternativeDataEngine()
toplist_factors = alt_engine.compute_toplist_factors('20260415')
north_factors = alt_engine.compute_north_factors('20260415')

# 单独使用因子引擎
from features import NonHomogeneousFactorEngine

factor_engine = NonHomogeneousFactorEngine()
df_with_factors = factor_engine.compute_all_factors(stock_df)
```

## 与项目其他模块的关系

```
Data (Layer 1) 
    ↓
Features (Layer 2) <-- 本模块
    ↓
Models (Layer 3)
    ↓
Portfolio (Layer 4)
```

## 输出格式

特征矩阵 DataFrame 包含：
- 基础字段: `ts_code`, `trade_date`, `open`, `high`, `low`, `close`, `volume`
- 特征字段: `return_*`, `f_*`, `top_*`, `north_*`, `analyst_*`
- 目标字段: `target_return`, `target_alpha`, `target_direction`

## 依赖

- pandas
- numpy
- scipy
- tushare

## 更新日志

**v0.1.0 (2026-04-16)**
- 初始版本
- 完成另类数据引擎
- 完成非同质化因子设计
- 完成特征工程管道

## TODO

- [ ] 接入实时另类数据流
- [ ] 添加更多小市值专属因子
- [ ] 实现特征重要性分析
- [ ] 添加特征相关性监控
