"""
Nous Invest — Module 3-4: Model Ensemble & Portfolio Construction
多模型集成 + 行业中性化/市值分层 + 风险平价权重分配

Features:
1. LightGBM + XGBoost ensemble with stacking
2. Industry neutralization module
3. Market cap layering
4. Risk parity weight allocation
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Union
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings('ignore')


class MultiModelEnsemble:
    """多模型集成: LightGBM + XGBoost with Stacking"""
    
    def __init__(self, 
                 lgb_params: Optional[Dict] = None,
                 xgb_params: Optional[Dict] = None,
                 meta_model_type: str = 'linear'):
        """
        Args:
            lgb_params: LightGBM参数
            xgb_params: XGBoost参数
            meta_model_type: 元学习器类型 ('linear', 'ridge', 'lgb')
        """
        self.lgb_params = lgb_params or self._default_lgb_params()
        self.xgb_params = xgb_params or self._default_xgb_params()
        self.meta_model_type = meta_model_type
        
        self.lgb_model = None
        self.xgb_model = None
        self.meta_model = None
        self.weights = {'lgb': 0.5, 'xgb': 0.5}
        
    def _default_lgb_params(self) -> Dict:
        """默认LightGBM参数。L1/L2 历史上被设成 205/580（几乎把信号压平），
        改为业界常见量级；有需求的调用方请显式传 lgb_params 覆盖。"""
        return {
            "objective": "mse",
            "colsample_bytree": 0.8879,
            "learning_rate": 0.0421,
            "subsample": 0.8789,
            "lambda_l1": 0.1,
            "lambda_l2": 0.1,
            "max_depth": 8,
            "num_leaves": 210,
            "num_threads": 4,
            "verbose": -1,
            "metric": "mse",
        }

    def _default_xgb_params(self) -> Dict:
        """默认XGBoost参数。同 LGB，reg_alpha/reg_lambda 从 205/580 调到 0.1。"""
        return {
            "objective": "reg:squarederror",
            "colsample_bytree": 0.8879,
            "learning_rate": 0.0421,
            "subsample": 0.8789,
            "reg_alpha": 0.1,
            "reg_lambda": 0.1,
            "max_depth": 8,
            "n_estimators": 500,
            "early_stopping_rounds": 50,
            "verbosity": 0,
        }
    
    def fit(self, X_train: pd.DataFrame, y_train: pd.Series,
            X_valid: pd.DataFrame, y_valid: pd.Series,
            use_stacking: bool = True) -> Dict:
        """
        训练多模型集成
        
        Returns:
            训练结果字典
        """
        print("=" * 60)
        print("🧠 多模型集成训练")
        print("=" * 60)
        
        # 训练 LightGBM
        print("\n[1/3] 训练 LightGBM...")
        try:
            import lightgbm as lgb
            dtrain = lgb.Dataset(X_train.values, label=y_train.values.squeeze())
            dvalid = lgb.Dataset(X_valid.values, label=y_valid.values.squeeze(), reference=dtrain)
            
            self.lgb_model = lgb.train(
                self.lgb_params,
                dtrain,
                num_boost_round=500,
                valid_sets=[dvalid],
                callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
            )
            print(f"   ✅ LightGBM best iteration: {self.lgb_model.best_iteration}")
        except Exception as e:
            print(f"   ⚠️ LightGBM训练失败: {e}")
            self.lgb_model = None
        
        # 训练 XGBoost
        print("\n[2/3] 训练 XGBoost...")
        try:
            import xgboost as xgb
            self.xgb_model = xgb.XGBRegressor(**self.xgb_params)
            self.xgb_model.fit(
                X_train.values, y_train.values.squeeze(),
                eval_set=[(X_valid.values, y_valid.values.squeeze())],
                verbose=False
            )
            print(f"   ✅ XGBoost best iteration: {self.xgb_model.best_iteration}")
        except Exception as e:
            print(f"   ⚠️ XGBoost训练失败: {e}")
            self.xgb_model = None
        
        # 计算最优权重 (基于验证集IC)
        self._optimize_weights(X_valid, y_valid)
        
        # Stacking (可选)
        if use_stacking and self.lgb_model is not None and self.xgb_model is not None:
            print("\n[3/3] 训练 Stacking Meta-Learner...")
            self._fit_meta_learner(X_valid, y_valid)
        
        return {
            'lgb_iteration': getattr(self.lgb_model, 'best_iteration', None),
            'xgb_iteration': getattr(self.xgb_model, 'best_iteration', None),
            'weights': self.weights,
        }
    
    def _optimize_weights(self, X_valid: pd.DataFrame, y_valid: pd.Series):
        """基于验证集IC优化模型权重"""
        if self.lgb_model is None and self.xgb_model is None:
            return
        
        ics = {}
        
        if self.lgb_model is not None:
            pred_lgb = self.lgb_model.predict(X_valid.values)
            ic_lgb = stats.spearmanr(pred_lgb, y_valid.values.squeeze())[0]
            ics['lgb'] = max(0, ic_lgb)  # 负IC设为0
            
        if self.xgb_model is not None:
            pred_xgb = self.xgb_model.predict(X_valid.values)
            ic_xgb = stats.spearmanr(pred_xgb, y_valid.values.squeeze())[0]
            ics['xgb'] = max(0, ic_xgb)
        
        # Softmax权重归一化
        if len(ics) > 0:
            exp_ics = {k: np.exp(v * 10) for k, v in ics.items()}  # 放大差异
            total = sum(exp_ics.values())
            self.weights = {k: v / total for k, v in exp_ics.items()}
        
        print(f"   📊 模型IC: {ics}")
        print(f"   ⚖️ 优化权重: {self.weights}")
    
    def _fit_meta_learner(self, X_valid: pd.DataFrame, y_valid: pd.Series):
        """训练Stacking元学习器"""
        # 获取基模型预测
        preds = []
        if self.lgb_model is not None:
            preds.append(self.lgb_model.predict(X_valid.values))
        if self.xgb_model is not None:
            preds.append(self.xgb_model.predict(X_valid.values))
        
        if len(preds) < 2:
            return
        
        X_meta = np.column_stack(preds)
        y_meta = y_valid.values.squeeze()
        
        if self.meta_model_type == 'linear':
            from sklearn.linear_model import LinearRegression
            self.meta_model = LinearRegression()
            self.meta_model.fit(X_meta, y_meta)
            print(f"   ✅ Meta-Learner 系数: {self.meta_model.coef_}")
        elif self.meta_model_type == 'ridge':
            from sklearn.linear_model import Ridge
            self.meta_model = Ridge(alpha=1.0)
            self.meta_model.fit(X_meta, y_meta)
            print(f"   ✅ Ridge Meta-Learner 系数: {self.meta_model.coef_}")
        else:
            # 默认使用加权平均
            pass
    
    def predict(self, X: pd.DataFrame, method: str = 'weighted') -> np.ndarray:
        """
        预测
        
        Args:
            X: 特征数据
            method: 集成方法 ('weighted', 'stacking', 'average')
        
        Returns:
            预测值数组
        """
        preds = []
        weights = []
        
        if self.lgb_model is not None:
            preds.append(self.lgb_model.predict(X.values))
            weights.append(self.weights.get('lgb', 0.5))
            
        if self.xgb_model is not None:
            preds.append(self.xgb_model.predict(X.values))
            weights.append(self.weights.get('xgb', 0.5))
        
        if len(preds) == 0:
            raise ValueError("没有可用的模型进行预测")
        
        if method == 'stacking' and self.meta_model is not None:
            X_meta = np.column_stack(preds)
            return self.meta_model.predict(X_meta)
        
        # 加权平均
        weights = np.array(weights) / sum(weights)
        result = np.zeros(len(preds[0]))
        for pred, w in zip(preds, weights):
            result += pred * w
        
        return result
    
    def get_feature_importance(self, feature_names: List[str]) -> pd.DataFrame:
        """获取特征重要性"""
        importance_df = pd.DataFrame({'feature': feature_names})
        
        if self.lgb_model is not None:
            importance_df['lgb_importance'] = self.lgb_model.feature_importance(importance_type='gain')
        
        if self.xgb_model is not None:
            importance_df['xgb_importance'] = self.xgb_model.feature_importances_
        
        # 平均重要性
        importance_cols = [c for c in importance_df.columns if 'importance' in c]
        if len(importance_cols) > 0:
            importance_df['avg_importance'] = importance_df[importance_cols].mean(axis=1)
            importance_df = importance_df.sort_values('avg_importance', ascending=False)
        
        return importance_df


class IndustryNeutralizer:
    """行业中性化模块"""
    
    def __init__(self, industry_mapping: Optional[Dict[str, str]] = None):
        """
        Args:
            industry_mapping: 股票代码到行业的映射 {code: industry_code}
        """
        self.industry_mapping = industry_mapping or {}
        self.industry_means = {}
        
    def load_from_tushare(self, trade_date: str, api_token: Optional[str] = None):
        """从Tushare加载行业数据"""
        try:
            import tushare as ts
            if api_token:
                ts.set_token(api_token)
            pro = ts.pro_api()
            
            # 获取股票基础信息(包含行业)
            df = pro.stock_basic(exchange='', list_status='L', 
                                 fields='ts_code,industry,name,area')
            self.industry_mapping = dict(zip(df['ts_code'], df['industry']))
            print(f"✅ 加载行业数据: {len(self.industry_mapping)} 只股票")
            return df
        except Exception as e:
            print(f"⚠️ 加载行业数据失败: {e}")
            return None
    
    def neutralize(self, scores: pd.Series, date: Optional[str] = None) -> pd.Series:
        """
        行业中性化: 每个行业内标准化
        
        Args:
            scores: MultiIndex Series (date, code) 或单日期 Series (code)
            date: 日期 (如果scores是单日期)
        
        Returns:
            中性化后的分数
        """
        if len(self.industry_mapping) == 0:
            print("⚠️ 没有行业映射,跳过中性化")
            return scores
        
        df = scores.reset_index()
        
        # 处理MultiIndex或单日期
        if 'datetime' in df.columns and 'instrument' in df.columns:
            df.columns = ['datetime', 'instrument', 'score']
        elif 'date' in df.columns and 'code' in df.columns:
            df.columns = ['datetime', 'instrument', 'score']
        else:
            # 单日期格式
            df.columns = ['instrument', 'score']
            df['datetime'] = date or pd.Timestamp.now()
        
        # 添加行业信息
        df['industry'] = df['instrument'].map(self.industry_mapping)
        df['industry'] = df['industry'].fillna('UNKNOWN')
        
        # 行业内标准化
        def _neutralize_group(g):
            if len(g) < 2:
                return g['score'] - g['score'].mean()
            return (g['score'] - g['score'].mean()) / (g['score'].std() + 1e-8)
        
        df['score_neutral'] = df.groupby(['datetime', 'industry'], group_keys=False).apply(_neutralize_group)
        
        # 恢复原始索引
        if 'level_0' in df.columns or len(df['datetime'].unique()) > 1:
            result = df.set_index(['datetime', 'instrument'])['score_neutral']
        else:
            result = df.set_index('instrument')['score_neutral']
        
        return result
    
    def get_industry_exposure(self, portfolio: List[str]) -> pd.Series:
        """计算组合的行业暴露"""
        industries = [self.industry_mapping.get(code, 'UNKNOWN') for code in portfolio]
        return pd.Series(industries).value_counts(normalize=True)


class MarketCapLayering:
    """市值分层模块"""
    
    def __init__(self, n_layers: int = 3, market_cap_data: Optional[pd.DataFrame] = None):
        """
        Args:
            n_layers: 分层数量 (默认3层: 大盘/中盘/小盘)
            market_cap_data: 市值数据 DataFrame (index: date, columns: stocks)
        """
        self.n_layers = n_layers
        self.market_cap_data = market_cap_data
        self.layer_boundaries = {}
        
    def load_market_cap(self, df: pd.DataFrame):
        """加载市值数据"""
        self.market_cap_data = df
        
    def get_layer(self, date: str, codes: List[str]) -> pd.Series:
        """
        获取指定日期的市值分层
        
        Returns:
            Series: code -> layer (0=大盘, n-1=小盘)
        """
        if self.market_cap_data is None:
            # 使用close * vol作为代理
            return pd.Series(1, index=codes)  # 默认全部中盘
        
        if date not in self.market_cap_data.index:
            return pd.Series(1, index=codes)
        
        mcaps = self.market_cap_data.loc[date, codes].dropna()
        
        # 按市值分层
        labels = list(range(self.n_layers))
        layers = pd.qcut(mcaps, q=self.n_layers, labels=labels, duplicates='drop')
        
        return layers
    
    def filter_by_layer(self, 
                        scores: pd.Series, 
                        date: str,
                        target_layers: List[int] = [2]) -> pd.Series:
        """
        按市值层过滤股票
        
        Args:
            scores: 预测分数
            date: 日期
            target_layers: 目标层 (默认[2]只选小盘)
        
        Returns:
            过滤后的分数
        """
        codes = scores.index.get_level_values(1).unique() if isinstance(scores.index, pd.MultiIndex) else scores.index
        layers = self.get_layer(date, list(codes))
        
        mask = layers.isin(target_layers)
        filtered_codes = layers[mask].index
        
        if isinstance(scores.index, pd.MultiIndex):
            return scores[scores.index.get_level_values(1).isin(filtered_codes)]
        return scores[scores.index.isin(filtered_codes)]
    
    def stratified_select(self,
                         scores: pd.Series,
                         date: str,
                         n_per_layer: int = 10) -> pd.DataFrame:
        """
        分层选股: 每层选前n只
        
        Returns:
            DataFrame with columns: [code, score, layer, rank_in_layer]
        """
        codes = scores.index.get_level_values(1).unique() if isinstance(scores.index, pd.MultiIndex) else scores.index
        layers = self.get_layer(date, list(codes))
        
        result = []
        for layer in range(self.n_layers):
            layer_codes = layers[layers == layer].index.tolist()
            if isinstance(scores.index, pd.MultiIndex):
                layer_scores = scores[scores.index.get_level_values(1).isin(layer_codes)]
            else:
                layer_scores = scores[scores.index.isin(layer_codes)]
            
            top_n = layer_scores.nlargest(n_per_layer).reset_index()
            top_n.columns = ['instrument', 'score'] if 'instrument' in top_n.columns else ['code', 'score']
            top_n['layer'] = layer
            top_n['rank_in_layer'] = range(1, len(top_n) + 1)
            result.append(top_n)
        
        return pd.concat(result, ignore_index=True)


class RiskParityAllocator:
    """风险平价权重分配"""
    
    def __init__(self, lookback_days: int = 60, target_volatility: float = 0.15):
        """
        Args:
            lookback_days: 波动率回望天数
            target_volatility: 目标年化波动率
        """
        self.lookback_days = lookback_days
        self.target_volatility = target_volatility
        
    def calculate_weights(self, 
                         returns_df: pd.DataFrame,
                         prediction_scores: Optional[pd.Series] = None) -> pd.Series:
        """
        计算风险平价权重
        
        Args:
            returns_df: 收益率数据 (index: date, columns: stocks)
            prediction_scores: 预测分数 (用于调整权重)
        
        Returns:
            权重 Series
        """
        # 计算波动率
        recent_returns = returns_df.iloc[-self.lookback_days:]
        vols = recent_returns.std() * np.sqrt(252)  # 年化波动率
        vols = vols.replace(0, np.nan).fillna(vols.median())
        
        # 风险平价: 权重与波动率倒数成正比
        inv_vols = 1.0 / vols
        weights = inv_vols / inv_vols.sum()
        
        # 如果有预测分数,进行调整
        if prediction_scores is not None:
            weights = self._adjust_by_prediction(weights, prediction_scores)
        
        # 目标波动率缩放
        portfolio_vol = np.sqrt(weights @ recent_returns.cov() @ weights) * np.sqrt(252)
        if portfolio_vol > 0:
            scale = min(1.0, self.target_volatility / portfolio_vol)
            weights = weights * scale
        
        return weights
    
    def _adjust_by_prediction(self, 
                              base_weights: pd.Series, 
                              scores: pd.Series,
                              alpha: float = 0.3) -> pd.Series:
        """根据预测分数调整权重"""
        # 将分数归一化为[0.5, 1.5]范围
        score_norm = 1 + alpha * (scores - scores.mean()) / (scores.std() + 1e-8)
        
        # 对齐索引
        common_idx = base_weights.index.intersection(score_norm.index)
        adjusted = base_weights.copy()
        adjusted.loc[common_idx] *= score_norm.loc[common_idx]
        
        return adjusted / adjusted.sum()
    
    def equal_risk_contribution(self, 
                                returns_df: pd.DataFrame,
                                max_iter: int = 100) -> pd.Series:
        """
        等风险贡献权重 (迭代求解)
        
        优化目标: 各资产对组合风险贡献相等
        """
        n = len(returns_returns.columns)
        cov = returns_df.iloc[-self.lookback_days:].cov().values
        
        # 初始化
        w = np.ones(n) / n
        
        for _ in range(max_iter):
            # 计算边际风险贡献
            portfolio_var = w @ cov @ w
            marginal_rc = cov @ w
            rc = w * marginal_rc
            
            # 调整权重
            target_rc = portfolio_var / n
            w_new = target_rc / (marginal_rc + 1e-8)
            w_new = w_new / w_new.sum()
            
            if np.max(np.abs(w_new - w)) < 1e-6:
                break
            w = w_new
        
        return pd.Series(w, index=returns_df.columns)
    
    def inverse_volatility_weights(self, returns_df: pd.DataFrame) -> pd.Series:
        """简单逆波动率权重"""
        vols = returns_df.iloc[-self.lookback_days:].std()
        inv_vols = 1.0 / vols.replace(0, np.nan).fillna(vols.median())
        return inv_vols / inv_vols.sum()


class PortfolioConstructor:
    """组合构建主类: 整合中性化、分层、权重分配"""
    
    def __init__(self,
                 neutralizer: Optional[IndustryNeutralizer] = None,
                 layering: Optional[MarketCapLayering] = None,
                 allocator: Optional[RiskParityAllocator] = None):
        """
        Args:
            neutralizer: 行业中性化器
            layering: 市值分层器
            allocator: 权重分配器
        """
        self.neutralizer = neutralizer or IndustryNeutralizer()
        self.layering = layering or MarketCapLayering()
        self.allocator = allocator or RiskParityAllocator()
        
    def construct(self,
                  scores: pd.Series,
                  date: str,
                  n_stocks: int = 20,
                  neutralize: bool = True,
                  layering_filter: Optional[List[int]] = None,
                  risk_parity: bool = True) -> pd.DataFrame:
        """
        构建投资组合
        
        Args:
            scores: 模型预测分数 (MultiIndex: date, code)
            date: 构建日期
            n_stocks: 选股数量
            neutralize: 是否行业中性化
            layering_filter: 市值层过滤 (None=不过滤)
            risk_parity: 是否使用风险平价权重
        
        Returns:
            DataFrame: columns=[code, raw_score, neutral_score, weight, industry]
        """
        print("\n" + "=" * 60)
        print("📊 组合构建")
        print("=" * 60)
        
        # 提取当日数据
        if isinstance(scores.index, pd.MultiIndex):
            daily_scores = scores.loc[date] if date in scores.index.get_level_values(0) else scores.xs(date, level=0)
        else:
            daily_scores = scores
        
        print(f"   原始股票数: {len(daily_scores)}")
        
        # 1. 市值分层过滤
        if layering_filter is not None:
            daily_scores = self.layering.filter_by_layer(daily_scores, date, layering_filter)
            print(f"   市值分层过滤后: {len(daily_scores)} (层: {layering_filter})")
        
        # 2. 行业中性化
        if neutralize:
            neutral_scores = self.neutralizer.neutralize(daily_scores, date)
            print(f"   ✅ 行业中性化完成")
        else:
            neutral_scores = daily_scores
        
        # 3. 选Top N
        top_n = neutral_scores.nlargest(n_stocks * 2)  # 多选一些用于权重优化
        selected_codes = top_n.index.tolist()
        
        # 4. 权重分配
        if risk_parity:
            # 这里需要历史收益率数据,简化处理为等权
            weights = pd.Series(1.0 / len(selected_codes), index=selected_codes)
            print(f"   ⚖️ 使用风险平价权重 (简化版)")
        else:
            # 按分数加权
            weights = top_n / top_n.sum()
        
        # 构建结果
        result = pd.DataFrame({
            'code': selected_codes[:n_stocks],
            'raw_score': daily_scores.loc[selected_codes[:n_stocks]].values,
            'neutral_score': neutral_scores.loc[selected_codes[:n_stocks]].values,
            'weight': weights.iloc[:n_stocks].values,
        })
        
        # 添加行业信息
        result['industry'] = result['code'].map(self.neutralizer.industry_mapping)
        
        # 归一化权重
        result['weight'] = result['weight'] / result['weight'].sum()
        
        print(f"\n📈 最终组合: {len(result)} 只股票")
        print(f"   行业分布:\n{result['industry'].value_counts()}")
        
        return result


def evaluate_portfolio(portfolio_df: pd.DataFrame,
                       returns_df: pd.DataFrame,
                       benchmark_returns: Optional[pd.Series] = None) -> Dict:
    """
    评估组合表现
    
    Returns:
        评估指标字典
    """
    codes = portfolio_df['code'].tolist()
    weights = portfolio_df['weight'].values
    
    # 组合收益率
    portfolio_returns = (returns_df[codes] * weights).sum(axis=1)
    
    # 计算指标
    total_return = (1 + portfolio_returns).prod() - 1
    annual_return = portfolio_returns.mean() * 252
    annual_vol = portfolio_returns.std() * np.sqrt(252)
    sharpe = annual_return / annual_vol if annual_vol > 0 else 0
    
    # 最大回撤
    cum_returns = (1 + portfolio_returns).cumprod()
    running_max = cum_returns.expanding().max()
    drawdown = (cum_returns - running_max) / running_max
    max_drawdown = drawdown.min()
    
    # 超额收益
    excess_return = None
    if benchmark_returns is not None:
        excess_returns = portfolio_returns - benchmark_returns
        excess_return = excess_returns.mean() * 252
        information_ratio = excess_return / (excess_returns.std() * np.sqrt(252))
    else:
        information_ratio = None
    
    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'annual_volatility': annual_vol,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_drawdown,
        'excess_return': excess_return,
        'information_ratio': information_ratio,
        'num_stocks': len(codes),
    }