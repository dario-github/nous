"""
Nous Invest — 轻量级模型集成与组合构建 (简化版)
不依赖完整Qlib数据,可用于已有预测结果
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
import json


class SimpleEnsemble:
    """轻量级多模型集成"""
    
    def __init__(self):
        self.models = {}
        self.weights = {}
    
    def add_model(self, name: str, predictions: pd.Series, weight: float = 1.0):
        """添加模型预测结果"""
        self.models[name] = predictions
        self.weights[name] = weight
    
    def ensemble_predict(self, method: str = 'weighted') -> pd.Series:
        """集成预测"""
        if method == 'weighted':
            total_weight = sum(self.weights.values())
            result = None
            for name, pred in self.models.items():
                w = self.weights[name] / total_weight
                if result is None:
                    result = pred * w
                else:
                    result = result.add(pred * w, fill_value=0)
            return result
        elif method == 'average':
            df = pd.concat(self.models.values(), axis=1)
            return df.mean(axis=1)
        elif method == 'rank':
            # Rank averaging
            ranks = pd.concat([p.rank() for p in self.models.values()], axis=1)
            return ranks.mean(axis=1)
        else:
            raise ValueError(f"Unknown method: {method}")


class SimplePortfolioBuilder:
    """轻量级组合构建器"""
    
    def __init__(self):
        self.industry_map = {}
        self.market_cap = {}
    
    def load_industry_data(self, file_path: Path):
        """加载行业数据"""
        df = pd.read_csv(file_path)
        if 'ts_code' in df.columns and 'industry' in df.columns:
            self.industry_map = dict(zip(df['ts_code'], df['industry']))
        print(f"✅ 加载行业数据: {len(self.industry_map)} 只股票")
    
    def neutralize(self, scores: pd.Series) -> pd.Series:
        """行业中性化 (简化版)"""
        df = scores.reset_index()
        df.columns = ['code', 'score']
        df['industry'] = df['code'].map(self.industry_map).fillna('UNKNOWN')
        
        # 行业内标准化
        def zscore(g):
            if len(g) < 2:
                return g * 0
            return (g - g.mean()) / (g.std() + 1e-8)
        
        df['neutral_score'] = df.groupby('industry')['score'].transform(zscore)
        return df.set_index('code')['neutral_score']
    
    def build_portfolio(self,
                       scores: pd.Series,
                       n_stocks: int = 20,
                       neutralize: bool = False,
                       risk_parity: bool = False) -> pd.DataFrame:
        """构建组合"""
        if neutralize and self.industry_map:
            scores = self.neutralize(scores)
        
        top_n = scores.nlargest(n_stocks)
        
        portfolio = pd.DataFrame({
            'code': top_n.index,
            'score': top_n.values,
        })
        
        if risk_parity:
            # 简化: 逆分数加权 (分数越高权重越大)
            weights = top_n / top_n.sum()
            portfolio['weight'] = weights.values
        else:
            portfolio['weight'] = 1.0 / len(portfolio)
        
        # 添加行业
        portfolio['industry'] = portfolio['code'].map(self.industry_map)
        
        # 归一化
        portfolio['weight'] = portfolio['weight'] / portfolio['weight'].sum()
        
        return portfolio


def main():
    """示例用法"""
    print("=" * 60)
    print("Nous Invest — 轻量级组合构建示例")
    print("=" * 60)
    
    # 假设已有预测数据
    np.random.seed(42)
    codes = [f'SH600{i:03d}' for i in range(1, 301)]
    
    # 模拟多模型预测
    lgb_pred = pd.Series(np.random.randn(300), index=codes)
    xgb_pred = pd.Series(np.random.randn(300), index=codes)
    
    # 集成
    ensemble = SimpleEnsemble()
    ensemble.add_model('lgb', lgb_pred, weight=0.6)
    ensemble.add_model('xgb', xgb_pred, weight=0.4)
    
    final_pred = ensemble.ensemble_predict(method='weighted')
    
    print(f"\n📈 集成预测完成: {len(final_pred)} 只股票")
    print(f"Top 10 预测:")
    print(final_pred.nlargest(10))
    
    # 构建组合
    builder = SimplePortfolioBuilder()
    portfolio = builder.build_portfolio(final_pred, n_stocks=20)
    
    print(f"\n📊 组合构建完成:")
    print(portfolio.head(10).to_string())
    
    # 保存
    output = Path('signals') / 'portfolio_simple.csv'
    output.parent.mkdir(exist_ok=True)
    portfolio.to_csv(output, index=False)
    print(f"\n💾 已保存: {output}")


if __name__ == '__main__':
    main()