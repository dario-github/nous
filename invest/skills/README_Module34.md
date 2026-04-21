# Nous Invest Module 3-4

## 模型与组合构建模块

### 文件结构

```
skills/
├── __init__.py                    # 模块导出
├── portfolio_construction.py      # 核心构建模块
└── fetch_auxiliary_data.py        # 辅助数据获取

run_module34.py                    # 主运行脚本
```

### 功能模块

#### 1. MultiModelEnsemble - 多模型集成
- LightGBM + XGBoost 双模型
- 基于验证集IC的动态权重优化
- Stacking元学习器(Linear/Ridge)
- 特征重要性融合

#### 2. IndustryNeutralizer - 行业中性化
- 行业内标准化 (z-score)
- Tushare行业数据自动加载
- 行业暴露分析

#### 3. MarketCapLayering - 市值分层
- 大盘/中盘/小盘三层划分
- 分层选股策略
- 市值过滤功能

#### 4. RiskParityAllocator - 风险平价
- 逆波动率权重
- 等风险贡献优化
- 目标波动率缩放

#### 5. PortfolioConstructor - 组合构建
- 整合所有模块
- 多种策略输出
- 权重归一化

### 使用方法

```bash
# 运行完整模块
cd /Users/yan/clawd-agents/research/nous-invest
python run_module34.py

# 仅使用组合构建模块
from skills import PortfolioConstructor, IndustryNeutralizer

neutralizer = IndustryNeutralizer()
constructor = PortfolioConstructor(neutralizer=neutralizer)
portfolio = constructor.construct(scores, date='20260415', n_stocks=20)
```

### 输出结果

- `models/module34/ensemble_model.pkl` - 训练好的集成模型
- `models/module34/feature_importance.csv` - 特征重要性
- `models/module34/predictions.csv` - 预测结果
- `models/module34/metrics.json` - 评估指标
- `models/module34/portfolio_*.csv` - 各类组合策略