#!/usr/bin/env python3
"""
Nous Invest — 特征工程示例脚本
演示如何使用特征工程模块生成训练数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from features import FeatureEngineeringPipeline, AlternativeDataEngine, NonHomogeneousFactorEngine


def create_sample_data(n_stocks: int = 50, n_days: int = 60) -> pd.DataFrame:
    """创建示例数据用于测试"""
    np.random.seed(42)
    
    data = []
    base_date = datetime(2026, 2, 1)
    
    for i in range(n_stocks):
        ts_code = f"{600000 + i}.SH" if i < 30 else f"{300000 + i}.SZ"
        
        # 生成价格序列
        price = 10 + np.random.randn() * 5
        
        for d in range(n_days):
            date = base_date + timedelta(days=d)
            
            # 模拟价格变动
            ret = np.random.randn() * 0.02
            price = price * (1 + ret)
            
            # 日内数据
            high = price * (1 + abs(np.random.randn() * 0.01))
            low = price * (1 - abs(np.random.randn() * 0.01))
            open_price = price * (1 + np.random.randn() * 0.005)
            close = price
            
            # 成交量
            volume = int(np.random.lognormal(15, 0.5))
            amount = close * volume
            
            data.append({
                'ts_code': ts_code,
                'trade_date': date,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume,
                'amount': amount
            })
    
    return pd.DataFrame(data)


def demo_base_features():
    """演示基础特征计算"""
    print("="*60)
    print("示例1: 基础特征计算")
    print("="*60)
    
    # 创建示例数据
    df = create_sample_data(n_stocks=5, n_days=30)
    print(f"\n原始数据: {df.shape}")
    print(df.head())
    
    # 计算基础特征
    pipeline = FeatureEngineeringPipeline()
    df_features = pipeline.compute_base_features(df)
    
    # 显示新增的特征
    new_cols = [c for c in df_features.columns if c not in df.columns]
    print(f"\n新增特征列 ({len(new_cols)}个):")
    for col in new_cols:
        print(f"  - {col}")
    
    print(f"\n特征预览:")
    print(df_features[['ts_code', 'trade_date', 'close'] + new_cols[:5]].head(10))


def demo_non_homogeneous_factors():
    """演示非同质化因子"""
    print("\n" + "="*60)
    print("示例2: 非同质化因子")
    print("="*60)
    
    # 创建单只股票数据
    df = create_sample_data(n_stocks=1, n_days=60)
    stock_df = df[df['ts_code'] == df['ts_code'].iloc[0]].copy()
    
    print(f"\n股票数据: {stock_df['ts_code'].iloc[0]}")
    print(f"日期范围: {stock_df['trade_date'].min().date()} ~ {stock_df['trade_date'].max().date()}")
    
    # 计算非同质化因子
    engine = NonHomogeneousFactorEngine()
    df_factors = engine.compute_all_factors(stock_df)
    
    # 显示因子
    factor_cols = [c for c in df_factors.columns if c.startswith('f_')]
    print(f"\n非同质化因子 ({len(factor_cols)}个):")
    for col in factor_cols:
        print(f"  - {col}")
    
    print(f"\n因子统计:")
    print(df_factors[factor_cols].describe().round(4))


def demo_full_pipeline():
    """演示完整特征工程管道"""
    print("\n" + "="*60)
    print("示例3: 完整特征工程管道")
    print("="*60)
    
    # 创建示例数据
    df = create_sample_data(n_stocks=10, n_days=40)
    
    # 保存临时文件
    temp_path = '/tmp/nous_sample_data.csv'
    df.to_csv(temp_path, index=False)
    
    print(f"\n创建临时数据: {temp_path}")
    print(f"股票数: {df['ts_code'].nunique()}")
    print(f"日期数: {df['trade_date'].nunique()}")
    
    # 运行完整管道
    pipeline = FeatureEngineeringPipeline()
    
    try:
        result = pipeline.run_pipeline(
            data_path=temp_path,
            forward_days=5,
            output_path=None  # 不保存
        )
        
        # 显示结果
        print(f"\n特征矩阵形状: {result.shape}")
        
        feature_cols = [c for c in result.columns if c not in ['ts_code', 'trade_date']]
        base = [c for c in feature_cols if any(x in c for x in ['return', 'volatility', 'price', 'volume', 'ma_'])]
        nonhomo = [c for c in feature_cols if c.startswith('f_')]
        alt = [c for c in feature_cols if any(x in c for x in ['top_', 'north_', 'analyst_'])]
        target = [c for c in feature_cols if c.startswith('target_')]
        
        print(f"\n特征分类:")
        print(f"  基础特征: {len(base)}个")
        print(f"  非同质化: {len(nonhomo)}个")
        print(f"  另类数据: {len(alt)}个")
        print(f"  目标变量: {len(target)}个")
        
        print(f"\n目标变量分布:")
        print(result[target[:2]].describe().round(4))
        
    except Exception as e:
        print(f"运行出错: {e}")
        import traceback
        traceback.print_exc()


def demo_feature_list():
    """演示特征清单"""
    print("\n" + "="*60)
    print("示例4: 特征清单")
    print("="*60)
    
    pipeline = FeatureEngineeringPipeline()
    features = pipeline.get_feature_list()
    
    total = 0
    for category, feature_list in features.items():
        count = len(feature_list)
        total += count
        print(f"\n{category}: {count}个")
        for f in feature_list:
            print(f"  - {f}")
    
    print(f"\n总计: {total}个特征")


def main():
    """主函数"""
    print("\n" + "="*60)
    print("Nous Invest 特征工程示例")
    print("="*60)
    
    demo_base_features()
    demo_non_homogeneous_factors()
    demo_full_pipeline()
    demo_feature_list()
    
    print("\n" + "="*60)
    print("示例完成!")
    print("="*60)


if __name__ == '__main__':
    main()
