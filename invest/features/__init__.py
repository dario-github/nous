"""
Nous Invest Features Module

数据与特征工程模块，整合另类数据和非同质化因子

Modules:
    alternative_data: 另类数据源 (龙虎榜、北向资金、分析师预期)
    non_homogeneous_factors: 非同质化因子设计 (避开Alpha158)
    feature_engineering: 特征工程管道

Usage:
    from features import FeatureEngineeringPipeline
    
    pipeline = FeatureEngineeringPipeline()
    df = pipeline.run_pipeline('data/stocks.csv')
"""

from .alternative_data import (
    AlternativeDataEngine,
    TOP_LIST_FACTORS,
    NORTH_FLOW_FACTORS,
    ANALYST_FACTORS
)

from .non_homogeneous_factors import (
    NonHomogeneousFactorEngine,
    NON_HOMOGENEOUS_FACTORS,
    get_factor_documentation
)

from .feature_engineering import (
    FeatureEngineeringPipeline,
    generate_feature_documentation
)

__version__ = '0.1.0'
__all__ = [
    'AlternativeDataEngine',
    'NonHomogeneousFactorEngine', 
    'FeatureEngineeringPipeline',
    'TOP_LIST_FACTORS',
    'NORTH_FLOW_FACTORS',
    'ANALYST_FACTORS',
    'NON_HOMOGENEOUS_FACTORS',
    'get_factor_documentation',
    'generate_feature_documentation',
]
