"""
Nous Invest — Module 3-4 API 使用示例
展示如何调用模型集成和组合构建功能
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.portfolio_construction import (
    MultiModelEnsemble,
    IndustryNeutralizer,
    MarketCapLayering,
    RiskParityAllocator,
    PortfolioConstructor,
)


def example_1_basic_ensemble():
    """示例1: 基础多模型集成"""
    print("=" * 60)
    print("示例1: 基础多模型集成")
    print("=" * 60)
    
    # 假设已有训练好的模型,这里用随机数据演示
    np.random.seed(42)
    n_samples = 1000
    n_features = 50
    
    X_train = pd.DataFrame(np.random.randn(n_samples, n_features),
                          columns=[f'feature_{i}' for i in range(n_features)])
    y_train = pd.Series(np.random.randn(n_samples))
    X_valid = pd.DataFrame(np.random.randn(200, n_features),
                          columns=[f'feature_{i}' for i in range(n_features)])
    y_valid = pd.Series(np.random.randn(200))
    
    print("\n训练数据:")
    print(f"  X_train: {X_train.shape}")
    print(f"  y_train: {y_train.shape}")
    
    # 创建集成模型
    ensemble = MultiModelEnsemble()
    
    # 训练 (这里会尝试训练LightGBM和XGBoost)
    print("\n开始训练...")
    try:
        result = ensemble.fit(X_train, y_train, X_valid, y_valid, use_stacking=False)
        print(f"✅ 训练完成!")
        print(f"   权重: {result['weights']}")
    except Exception as e:
        print(f"⚠️ 训练失败 (可能是环境缺少依赖): {e}")
        print("   在生产环境中请确保安装: lightgbm, xgboost")


def example_2_industry_neutralization():
    """示例2: 行业中性化"""
    print("\n" + "=" * 60)
    print("示例2: 行业中性化")
    print("=" * 60)
    
    # 模拟股票分数
    codes = ['000001.SZ', '000002.SZ', '000063.SZ', '000100.SZ', '000333.SZ']
    scores = pd.Series([1.5, 0.8, 2.1, -0.5, 1.2], index=codes)
    
    print("\n原始分数:")
    print(scores)
    
    # 创建中性化器
    neutralizer = IndustryNeutralizer()
    
    # 手动设置行业映射
    neutralizer.industry_mapping = {
        '000001.SZ': '银行',
        '000002.SZ': '房地产',
        '000063.SZ': '通信',
        '000100.SZ': '电子',
        '000333.SZ': '家电',
    }
    
    # 中性化
    neutral_scores = neutralizer.neutralize(scores, date='20260415')
    
    print("\n中性化后分数:")
    print(neutral_scores)
    
    print("\n行业暴露:")
    exposure = neutralizer.get_industry_exposure(codes)
    print(exposure)


def example_3_risk_parity():
    """示例3: 风险平价权重"""
    print("\n" + "=" * 60)
    print("示例3: 风险平价权重")
    print("=" * 60)
    
    # 模拟收益率数据
    np.random.seed(42)
    dates = pd.date_range('20240101', '20260415', freq='D')
    stocks = ['A', 'B', 'C', 'D', 'E']
    
    returns = pd.DataFrame(
        np.random.randn(len(dates), 5) * 0.02,
        index=dates,
        columns=stocks
    )
    
    print(f"\n收益率数据: {returns.shape}")
    print(f"波动率:\n{returns.std() * np.sqrt(252)}")
    
    # 风险平价
    allocator = RiskParityAllocator(lookback_days=60)
    weights = allocator.calculate_weights(returns)
    
    print("\n风险平价权重:")
    print(weights)
    
    # 逆波动率权重
    iv_weights = allocator.inverse_volatility_weights(returns)
    print("\n逆波动率权重:")
    print(iv_weights)


def example_4_full_pipeline():
    """示例4: 完整流程"""
    print("\n" + "=" * 60)
    print("示例4: 完整流程演示")
    print("=" * 60)
    
    # 模拟预测分数
    np.random.seed(42)
    n_stocks = 300
    codes = [f'{i:06d}.SZ' if i % 2 == 0 else f'{i:06d}.SH' 
             for i in range(1, n_stocks + 1)]
    scores = pd.Series(np.random.randn(n_stocks), index=codes)
    
    # 模拟行业映射
    industries = ['银行', '房地产', '电子', '医药', '消费', '科技', '制造']
    industry_map = {code: np.random.choice(industries) for code in codes}
    
    print(f"\n预测股票数: {len(scores)}")
    print(f"预测分数分布: mean={scores.mean():.3f}, std={scores.std():.3f}")
    
    # 构建组合
    neutralizer = IndustryNeutralizer(industry_map)
    constructor = PortfolioConstructor(neutralizer=neutralizer)
    
    portfolio = constructor.construct(
        scores,
        date='20260415',
        n_stocks=20,
        neutralize=True,
        layering_filter=None,
        risk_parity=False
    )
    
    print("\n📊 最终组合:")
    print(portfolio.to_string())
    
    # 统计
    print(f"\n行业分布:")
    print(portfolio['industry'].value_counts())


def main():
    """运行所有示例"""
    print("=" * 70)
    print("Nous Invest — Module 3-4 API 使用示例")
    print("=" * 70)
    
    example_1_basic_ensemble()
    example_2_industry_neutralization()
    example_3_risk_parity()
    example_4_full_pipeline()
    
    print("\n" + "=" * 70)
    print("🎉 所有示例运行完成!")
    print("=" * 70)


if __name__ == '__main__':
    main()