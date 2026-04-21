"""
Nous Invest — 另类数据因子模块
Alternative Data Factors (龙虎榜、北向资金、分析师预期)
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import tushare as ts
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


@dataclass
class TopListFactor:
    """龙虎榜席位因子"""
    name: str
    description: str
    frequency: str  # 'daily', 'weekly'
    category: str   # 'momentum', 'smart_money', 'sentiment'


@dataclass
class NorthFlowFactor:
    """北向资金因子"""
    name: str
    description: str
    frequency: str
    category: str


@dataclass
class AnalystFactor:
    """分析师预期因子"""
    name: str
    description: str
    frequency: str
    category: str


class AlternativeDataEngine:
    """
    另类数据引擎 — 龙虎榜、北向细分、分析师预期
    """
    
    def __init__(self, tushare_token: Optional[str] = None):
        """初始化Tushare连接"""
        if tushare_token:
            ts.set_token(tushare_token)
        else:
            # 尝试从配置文件读取
            import os
            token_path = os.path.expanduser('~/.config/tushare/token')
            if os.path.exists(token_path):
                with open(token_path, 'r') as f:
                    ts.set_token(f.read().strip())
        
        self.pro = ts.pro_api()
        self._cache = {}
        
    # ==================== 龙虎榜数据 ====================
    
    def fetch_toplist(self, trade_date: str) -> pd.DataFrame:
        """
        获取龙虎榜数据
        
        Parameters:
            trade_date: 交易日期 (YYYYMMDD)
            
        Returns:
            DataFrame with toplist data
        """
        cache_key = f'toplist_{trade_date}'
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        try:
            df = self.pro.top_list(trade_date=trade_date)
            self._cache[cache_key] = df
            return df
        except Exception as e:
            print(f"Error fetching toplist for {trade_date}: {e}")
            return pd.DataFrame()
    
    def fetch_toplist_detail(self, trade_date: str) -> pd.DataFrame:
        """
        获取龙虎榜详细数据（营业部）
        
        Parameters:
            trade_date: 交易日期 (YYYYMMDD)
        """
        cache_key = f'toplist_detail_{trade_date}'
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        try:
            df = self.pro.top_inst(trade_date=trade_date)
            self._cache[cache_key] = df
            return df
        except Exception as e:
            print(f"Error fetching toplist detail for {trade_date}: {e}")
            return pd.DataFrame()
    
    def compute_toplist_factors(self, trade_date: str) -> pd.DataFrame:
        """
        计算龙虎榜相关因子
        
        Factors:
        - top_amount_ratio: 龙虎榜成交金额/总成交金额
        - top_buy_ratio: 龙虎榜买入/龙虎榜总成交额
        - top_inst_ratio: 机构席位买入占比
        - top_hot_score: 上榜热度 (近5日上榜次数)
        - top_momentum_3d: 上榜后3日动量
        """
        # 获取当前及历史数据
        dates = []
        current = datetime.strptime(trade_date, '%Y%m%d')
        for i in range(10):  # 近10个交易日
            date_str = (current - timedelta(days=i)).strftime('%Y%m%d')
            dates.append(date_str)
        
        # 收集数据
        all_data = []
        for d in dates:
            df = self.fetch_toplist(d)
            if not df.empty:
                df['trade_date'] = d
                all_data.append(df)
        
        if not all_data:
            return pd.DataFrame()
            
        df_all = pd.concat(all_data, ignore_index=True)
        
        # 计算因子
        factors = []
        for ts_code in df_all['ts_code'].unique():
            stock_data = df_all[df_all['ts_code'] == ts_code]
            
            factor = {
                'ts_code': ts_code,
                'trade_date': trade_date,
            }
            
            # 当日数据
            today_data = stock_data[stock_data['trade_date'] == trade_date]
            if not today_data.empty:
                factor['top_amount_ratio'] = today_data['amount'].values[0] / (today_data['turnover'].values[0] * 10000) if today_data['turnover'].values[0] > 0 else 0
                factor['top_buy_ratio'] = today_data['buy_amount'].values[0] / today_data['amount'].values[0] if today_data['amount'].values[0] > 0 else 0.5
            else:
                factor['top_amount_ratio'] = 0
                factor['top_buy_ratio'] = 0.5
            
            # 热度因子 (近5日上榜次数)
            factor['top_hot_score'] = len(stock_data[stock_data['trade_date'] >= (current - timedelta(days=5)).strftime('%Y%m%d')])
            
            # 累计净买入
            factor['top_net_buy_5d'] = stock_data['net_buy'].sum() if 'net_buy' in stock_data.columns else 0
            
            factors.append(factor)
        
        return pd.DataFrame(factors)
    
    # ==================== 北向资金数据 ====================
    
    def fetch_north_flow(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取北向资金数据 (沪港通+深港通)
        """
        cache_key = f'north_{start_date}_{end_date}'
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        try:
            # 沪深港通持股
            df = self.pro.hk_hold(start_date=start_date, end_date=end_date)
            self._cache[cache_key] = df
            return df
        except Exception as e:
            print(f"Error fetching north flow: {e}")
            return pd.DataFrame()
    
    def fetch_north_daily(self, trade_date: str) -> pd.DataFrame:
        """获取北向资金每日汇总"""
        try:
            df = self.pro.moneyflow_hsgt(trade_date=trade_date)
            return df
        except Exception as e:
            print(f"Error fetching north daily: {e}")
            return pd.DataFrame()
    
    def compute_north_factors(self, trade_date: str, lookback: int = 20) -> pd.DataFrame:
        """
        计算北向资金因子
        
        Factors:
        - north_ratio: 北向持股比例
        - north_change_1d: 1日持股变化
        - north_change_5d: 5日持股变化
        - north_flow_ratio: 北向资金流入/成交额
        - north_concentration: 北向持股集中度 (前10%股票占比)
        """
        # 获取历史数据
        end = datetime.strptime(trade_date, '%Y%m%d')
        start = (end - timedelta(days=lookback*2)).strftime('%Y%m%d')
        
        df = self.fetch_north_flow(start, trade_date)
        if df.empty:
            return pd.DataFrame()
        
        factors = []
        for ts_code in df['ts_code'].unique():
            stock_df = df[df['ts_code'] == ts_code].sort_values('trade_date')
            
            if len(stock_df) < 5:
                continue
                
            factor = {
                'ts_code': ts_code,
                'trade_date': trade_date,
                'north_ratio': stock_df['ratio'].values[-1] if 'ratio' in stock_df.columns else 0,
                'north_change_1d': stock_df['vol'].values[-1] - stock_df['vol'].values[-2] if len(stock_df) >= 2 else 0,
                'north_change_5d': stock_df['vol'].values[-1] - stock_df['vol'].values[-5] if len(stock_df) >= 5 else 0,
            }
            
            # 计算趋势 (10日回归斜率)
            if len(stock_df) >= 10:
                y = stock_df['vol'].values[-10:]
                x = np.arange(10)
                factor['north_trend'] = np.polyfit(x, y, 1)[0]
            else:
                factor['north_trend'] = 0
                
            factors.append(factor)
        
        return pd.DataFrame(factors)
    
    # ==================== 分析师预期数据 ====================
    
    def fetch_analyst_report(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取券商研报数据
        """
        try:
            df = self.pro.report_data(ts_code=ts_code, start_date=start_date, end_date=end_date)
            return df
        except Exception as e:
            print(f"Error fetching analyst report: {e}")
            return pd.DataFrame()
    
    def fetch_analyst_rating(self, ts_code: str) -> pd.DataFrame:
        """
        获取分析师评级数据
        """
        try:
            df = self.pro.stk_rating(ts_code=ts_code)
            return df
        except Exception as e:
            print(f"Error fetching analyst rating: {e}")
            return pd.DataFrame()
    
    def compute_analyst_factors(self, trade_date: str) -> pd.DataFrame:
        """
        计算分析师预期因子
        
        Factors:
        - analyst_rating_score: 综合评级得分 (1-5)
        - analyst_target_gap: (目标价-现价)/现价
        - analyst_coverage: 覆盖分析师数量
        - analyst_momentum: 评级上调数量 - 下调数量
        - expect_surprise_1m: 近1月研报超预期比例
        """
        # 获取日期范围
        end = datetime.strptime(trade_date, '%Y%m%d')
        start_1m = (end - timedelta(days=30)).strftime('%Y%m%d')
        start_3m = (end - timedelta(days=90)).strftime('%Y%m%d')
        
        try:
            # 获取评级数据
            df_rating = self.pro.stk_rating(start_date=start_3m, end_date=trade_date)
            if df_rating.empty:
                return pd.DataFrame()
            
            factors = []
            for ts_code in df_rating['ts_code'].unique():
                stock_df = df_rating[df_rating['ts_code'] == ts_code]
                
                # 评级映射
                rating_map = {'买入': 5, '增持': 4, '中性': 3, '减持': 2, '卖出': 1}
                stock_df['rating_score'] = stock_df['rating'].map(rating_map).fillna(3)
                
                factor = {
                    'ts_code': ts_code,
                    'trade_date': trade_date,
                    'analyst_rating_score': stock_df['rating_score'].mean(),
                    'analyst_coverage': len(stock_df),
                }
                
                # 评级动量 (近1月 vs 近3月)
                recent = stock_df[stock_df['rating_date'] >= start_1m]
                older = stock_df[stock_df['rating_date'] < start_1m]
                
                if not recent.empty and not older.empty:
                    factor['analyst_momentum'] = recent['rating_score'].mean() - older['rating_score'].mean()
                else:
                    factor['analyst_momentum'] = 0
                
                # 目标价空间
                if 'target_price' in stock_df.columns and not stock_df['target_price'].empty:
                    latest_target = stock_df['target_price'].values[-1]
                    # 需要当前价格，这里简化处理
                    factor['analyst_target_gap'] = 0.1  # 占位
                else:
                    factor['analyst_target_gap'] = 0
                    
                factors.append(factor)
            
            return pd.DataFrame(factors)
            
        except Exception as e:
            print(f"Error computing analyst factors: {e}")
            return pd.DataFrame()


# ==================== 因子定义 ====================

TOP_LIST_FACTORS = [
    TopListFactor('top_amount_ratio', '龙虎榜成交金额占比', 'daily', 'momentum'),
    TopListFactor('top_buy_ratio', '龙虎榜买入占比', 'daily', 'smart_money'),
    TopListFactor('top_hot_score', '龙虎榜热度(近5日次数)', 'daily', 'sentiment'),
    TopListFactor('top_net_buy_5d', '龙虎榜5日净买入', 'daily', 'smart_money'),
    TopListFactor('top_inst_ratio', '机构席位占比', 'daily', 'smart_money'),
]

NORTH_FLOW_FACTORS = [
    NorthFlowFactor('north_ratio', '北向持股比例', 'daily', 'smart_money'),
    NorthFlowFactor('north_change_1d', '北向持股1日变化', 'daily', 'flow'),
    NorthFlowFactor('north_change_5d', '北向持股5日变化', 'weekly', 'flow'),
    NorthFlowFactor('north_trend', '北向持股趋势(10日)', 'daily', 'momentum'),
]

ANALYST_FACTORS = [
    AnalystFactor('analyst_rating_score', '分析师综合评级', 'weekly', 'fundamental'),
    AnalystFactor('analyst_target_gap', '目标价上涨空间', 'weekly', 'expectation'),
    AnalystFactor('analyst_coverage', '分析师覆盖数', 'weekly', 'attention'),
    AnalystFactor('analyst_momentum', '评级动量(上调-下调)', 'weekly', 'sentiment'),
]


if __name__ == '__main__':
    # 测试
    engine = AlternativeDataEngine()
    
    # 测试日期
    test_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    
    print("="*50)
    print("龙虎榜因子测试")
    print("="*50)
    toplist_factors = engine.compute_toplist_factors(test_date)
    print(toplist_factors.head())
    
    print("\n" + "="*50)
    print("北向资金因子测试")
    print("="*50)
    north_factors = engine.compute_north_factors(test_date)
    print(north_factors.head())
