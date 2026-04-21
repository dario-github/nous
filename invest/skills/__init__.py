"""
Nous Invest — 模型与组合构建模块

模块3-4核心组件:
- MultiModelEnsemble: LightGBM + XGBoost + Stacking
- IndustryNeutralizer: 行业中性化
- MarketCapLayering: 市值分层
- RiskParityAllocator: 风险平价权重
- PortfolioConstructor: 组合构建主类
"""

from .portfolio_construction import (
    MultiModelEnsemble,
    IndustryNeutralizer,
    MarketCapLayering,
    RiskParityAllocator,
    PortfolioConstructor,
    evaluate_portfolio,
)

__all__ = [
    'MultiModelEnsemble',
    'IndustryNeutralizer',
    'MarketCapLayering',
    'RiskParityAllocator',
    'PortfolioConstructor',
    'evaluate_portfolio',
]