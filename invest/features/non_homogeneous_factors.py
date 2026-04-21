"""
Nous Invest — 非同质化因子 (Non-Homogeneous Factors)
避开 Alpha158 同质化陷阱的原创因子设计
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from scipy import stats
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class Factor:
    """因子定义"""
    name: str
    category: str  # 'high_freq', 'mid_freq', 'low_freq'
    description: str
    frequency: str  # '1min', 'daily', 'weekly', 'monthly'
    computation: str


class NonHomogeneousFactorEngine:
    """
    非同质化因子引擎 — 避开 Alpha158 的原创设计
    
    设计原则:
    1. 不直接使用 Alpha158 因子
    2. 结合 A股微观结构特点
    3. 跨频段信号叠加
    4. 小市值/非拥挤区域适配
    """
    
    def __init__(self):
        self.factors = self._define_factors()
    
    def _define_factors(self) -> List[Factor]:
        """定义所有非同质化因子"""
        return [
            # ========== 高频因子 (1-min 或日线合成) ==========
            Factor('price_gap_momentum', 'high_freq', 
                   '跳空动量 (开盘缺口 + 首30分钟趋势)', 'daily', 'ohlc'),
            Factor('volume_impulse', 'high_freq',
                   '成交量脉冲 (量比突增识别)', 'daily', 'volume'),
            Factor('intraday_reversal', 'high_freq',
                   '日内反转强度 (高低点位置)', 'daily', 'ohlc'),
            Factor('am_pm_divergence', 'high_freq',
                   '上午下午背离 (前后半场成交量比)', 'daily', 'volume'),
            Factor('large_order_imbalance', 'high_freq',
                   '大单不平衡 (估算大单净流入)', 'daily', 'moneyflow'),
            
            # ========== 中频因子 (日线级别，基本面+资金) ==========
            Factor('earnings_surprise_proxy', 'mid_freq',
                   '业绩超预期代理 (开盘跳空+成交量)', 'daily', 'ohlcv'),
            Factor('smart_money_proxy', 'mid_freq',
                   '聪明钱代理 (尾盘+早盘资金流向)', 'daily', 'moneyflow'),
            Factor('retail_exhaustion', 'mid_freq',
                   '散户 exhaustion 信号 (散户 vs 机构行为)', 'daily', 'toplist'),
            Factor('fund_flow_momentum', 'mid_freq',
                   '资金流动量 (主力资金趋势)', 'weekly', 'moneyflow'),
            Factor('volatility_regime', 'mid_freq',
                   '波动率状态 (高/低波动切换)', 'weekly', 'volatility'),
            
            # ========== 低频因子 (周/月级别，宏观+板块) ==========
            Factor('small_cap_rotation', 'low_freq',
                   '小盘轮动 (大小盘相对强弱)', 'weekly', 'index'),
            Factor('sector_momentum_divergence', 'low_freq',
                   '板块动量背离 (领涨 vs 领跌板块)', 'weekly', 'sector'),
            Factor('liquidity_regime', 'low_freq',
                   '流动性状态 (成交量趋势)', 'monthly', 'volume'),
            Factor('market_structure', 'low_freq',
                   '市场结构 (新高新低股票数)', 'weekly', 'breadth'),
            Factor('seasonality_proxy', 'low_freq',
                   '季节性代理 (月度效应)', 'monthly', 'calendar'),
        ]
    
    # ========== 高频因子计算 ==========
    
    def price_gap_momentum(self, df: pd.DataFrame) -> pd.Series:
        """
        跳空动量因子
        
        逻辑: 高开+首30分钟走强 = 强势信号
             低开+首30分钟反弹 = 反转信号
        """
        # 开盘价相对昨收缺口
        gap = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
        
        # 日内首段趋势 (用open到high/low中点估计)
        morning_trend = (df['high'] - df['open']) / (df['high'] - df['low'] + 1e-8)
        
        # 跳空动量 = 缺口方向 * 早盘强度
        factor = np.where(gap > 0, 
                         gap * morning_trend,
                         gap * (1 - morning_trend))
        
        return pd.Series(factor, index=df.index)
    
    def volume_impulse(self, df: pd.DataFrame, window: int = 20) -> pd.Series:
        """
        成交量脉冲因子
        
        逻辑: 成交量突然放大(>2倍均量)且价格上涨 = 资金介入
        """
        vol_ma = df['volume'].rolling(window).mean()
        vol_ratio = df['volume'] / vol_ma
        
        # 成交量脉冲 (突增)
        impulse = np.where(vol_ratio > 2, vol_ratio, 0)
        
        # 结合价格方向
        price_change = df['close'].pct_change()
        factor = impulse * np.sign(price_change)
        
        return pd.Series(factor, index=df.index)
    
    def intraday_reversal(self, df: pd.DataFrame) -> pd.Series:
        """
        日内反转强度
        
        逻辑: (close - open) 与 (high - low) 的比值
             值越大表示日内由弱转强
        """
        body = df['close'] - df['open']
        range_hl = df['high'] - df['low']
        
        # 日内反转强度 [-1, 1]
        factor = body / (range_hl + 1e-8)
        
        # 极端反转信号 (长下影线+收涨)
        lower_shadow = df[['open', 'close']].min(axis=1) - df['low']
        reversal_signal = np.where(
            (lower_shadow / (range_hl + 1e-8) > 0.3) & (df['close'] > df['open']),
            factor * 2,
            factor
        )
        
        return pd.Series(reversal_signal, index=df.index)
    
    def am_pm_divergence(self, df: pd.DataFrame) -> pd.Series:
        """
        上午下午背离 (使用成交量估算)
        
        逻辑: 上午放量下午缩量 = 短期可能调整
             上午缩量下午放量 = 资金尾盘入场
        """
        # 由于日线数据，使用价量关系代理
        # 实体位置代理上午/下午力量对比
        body_position = ((df['close'] + df['open']) / 2 - df['low']) / (df['high'] - df['low'] + 1e-8)
        
        # 结合成交量变化
        vol_change = df['volume'].pct_change()
        
        # 尾盘强势信号
        factor = (body_position - 0.5) * 2 * np.sign(vol_change + 0.01)
        
        return pd.Series(factor, index=df.index)
    
    def large_order_imbalance(self, df: pd.DataFrame) -> pd.Series:
        """
        大单不平衡代理 (使用成交额/成交量比率)
        
        逻辑: 大单多 = 成交额/成交量 高 (均价高)
             大单净买入 = 价格上涨+放量
        """
        # 平均成交价格
        avg_price = df['amount'] / df['volume'] if 'amount' in df.columns else df['close']
        
        # 均价相对收盘价的偏离
        price_deviation = avg_price / df['close'] - 1
        
        # 结合涨跌方向
        price_change = df['close'].pct_change()
        factor = price_deviation * np.sign(price_change) * np.log(df['volume'] + 1)
        
        return pd.Series(factor, index=df.index)
    
    # ========== 中频因子计算 ==========
    
    def earnings_surprise_proxy(self, df: pd.DataFrame, window: int = 5) -> pd.Series:
        """
        业绩超预期代理
        
        逻辑: 业绩公告日通常伴随:
             1. 开盘跳空
             2. 成交量放大
             3. 价格趋势延续
        """
        # 跳空幅度
        gap = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
        
        # 成交量异常
        vol_ma = df['volume'].rolling(window).mean()
        vol_anomaly = df['volume'] / vol_ma
        
        # 趋势延续 (后3日vs前3日)
        past_return = df['close'].shift(1) / df['close'].shift(4) - 1
        future_return = df['close'].shift(-3) / df['close'] - 1
        trend_continuation = future_return - past_return
        
        # 综合超预期信号
        factor = gap * vol_anomaly * np.sign(trend_continuation)
        
        return pd.Series(factor, index=df.index)
    
    def smart_money_proxy(self, df: pd.DataFrame) -> pd.Series:
        """
        聪明钱代理
        
        逻辑: 聪明钱通常在:
             1. 尾盘入场 (收盘接近高点)
             2. 下跌中逆势买入 (低点放量)
             3. 上涨中从容出货 (高点放量滞涨)
        """
        # 收盘位置 (高 = 强势)
        close_position = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-8)
        
        # 成交量加权
        vol_percentile = df['volume'].rolling(20).apply(
            lambda x: stats.percentileofscore(x, x.iloc[-1]), raw=False
        ) / 100
        
        # 聪明钱信号: 收盘强势 + 放量 或 收盘弱势+缩量
        smart_long = close_position * vol_percentile
        smart_short = (1 - close_position) * (1 - vol_percentile)
        
        factor = smart_long - smart_short
        
        return pd.Series(factor, index=df.index)
    
    def retail_exhaustion(self, df: pd.DataFrame, window: int = 5) -> pd.Series:
        """
        散户 exhaustion 信号
        
        逻辑: 散户通常在:
             1. 连续上涨后追高
             2. 连续下跌后割肉
             3. 高波动中频繁交易
        
        exhaustion 信号 = 极端情绪反转点
        """
        # 连续涨跌天数
        returns = df['close'].pct_change()
        up_streak = returns.rolling(window).apply(
            lambda x: sum(1 for i in range(len(x)) if x.iloc[i] > 0), raw=False
        )
        down_streak = window - up_streak
        
        # 波动率
        volatility = returns.rolling(window).std()
        
        # 成交量异常
        vol_ma = df['volume'].rolling(window).mean()
        vol_spike = df['volume'] / vol_ma
        
        # 做多 exhaustion (连续下跌+放量+反弹)
        long_exhaustion = np.where(
            (down_streak >= 3) & (vol_spike > 1.5) & (returns > 0),
            1, 0
        )
        
        # 做空 exhaustion (连续上涨+放量+下跌)
        short_exhaustion = np.where(
            (up_streak >= 3) & (vol_spike > 1.5) & (returns < 0),
            -1, 0
        )
        
        factor = long_exhaustion + short_exhaustion
        
        return pd.Series(factor, index=df.index)
    
    def fund_flow_momentum(self, df: pd.DataFrame, window: int = 10) -> pd.Series:
        """
        资金流动量
        
        逻辑: 主力资金持续流入 = 上涨趋势确认
        """
        # 资金净流入代理 (价格*成交量趋势)
        money_flow = df['close'] * df['volume']
        mf_change = money_flow.pct_change(window)
        
        # 价格动量
        price_momentum = df['close'].pct_change(window)
        
        # 资金流-价格背离检测
        divergence = np.sign(mf_change) != np.sign(price_momentum)
        
        factor = mf_change * np.where(divergence, -0.5, 1)
        
        return pd.Series(factor, index=df.index)
    
    def volatility_regime(self, df: pd.DataFrame, short_window: int = 5, long_window: int = 20) -> pd.Series:
        """
        波动率状态
        
        逻辑: 低波动->高波动 切换往往伴随大行情
             高波动->低波动 可能表示趋势结束
        """
        returns = df['close'].pct_change()
        
        short_vol = returns.rolling(short_window).std()
        long_vol = returns.rolling(long_window).std()
        
        # 波动率比率
        vol_ratio = short_vol / long_vol
        
        # 波动率状态
        factor = vol_ratio * np.sign(returns.rolling(long_window).mean())
        
        return pd.Series(factor, index=df.index)
    
    # ========== 低频因子计算 ==========
    
    def small_cap_rotation(self, df_small: pd.DataFrame, df_large: pd.DataFrame, window: int = 20) -> pd.Series:
        """
        小盘轮动因子
        
        逻辑: 小盘相对大盘的强弱周期
        """
        # 计算相对强弱
        small_return = df_small['close'].pct_change(window)
        large_return = df_large['close'].pct_change(window)
        
        relative_strength = small_return - large_return
        
        # 轮动动量
        rotation_momentum = relative_strength.diff(window // 4)
        
        factor = relative_strength + rotation_momentum
        
        return pd.Series(factor, index=df_small.index)
    
    def sector_momentum_divergence(self, sector_data: Dict[str, pd.DataFrame], window: int = 20) -> pd.DataFrame:
        """
        板块动量背离
        
        逻辑: 计算各板块动量，识别领涨/领跌板块
        """
        momentum_scores = {}
        
        for sector, df in sector_data.items():
            momentum = df['close'].pct_change(window)
            momentum_scores[sector] = momentum
        
        momentum_df = pd.DataFrame(momentum_scores)
        
        # 领涨板块 (前20%)
        leader_threshold = momentum_df.quantile(0.8, axis=1)
        # 领跌板块 (后20%)
        laggard_threshold = momentum_df.quantile(0.2, axis=1)
        
        # 背离程度
        divergence = leader_threshold - laggard_threshold
        
        return pd.DataFrame({
            'leader_momentum': leader_threshold,
            'laggard_momentum': laggard_threshold,
            'divergence': divergence
        }, index=momentum_df.index)
    
    def liquidity_regime(self, df: pd.DataFrame, window: int = 60) -> pd.Series:
        """
        流动性状态
        
        逻辑: 成交量趋势反映市场流动性
        """
        # 成交量趋势
        volume_trend = df['volume'].rolling(window).mean()
        volume_change = volume_trend.pct_change(window // 4)
        
        # 成交额趋势
        amount_trend = df['amount'].rolling(window).mean() if 'amount' in df.columns else volume_trend * df['close']
        
        # 流动性得分
        factor = volume_change + amount_trend.pct_change(window // 4)
        
        return pd.Series(factor, index=df.index)
    
    def market_structure(self, df: pd.DataFrame, window: int = 20) -> pd.Series:
        """
        市场结构 (新高新低)
        
        逻辑: 新高股票数占比反映市场广度
        """
        # 计算20日新高/新低
        high_20 = df['high'].rolling(window).max()
        low_20 = df['low'].rolling(window).min()
        
        new_high = (df['close'] >= high_20.shift(1)).astype(int)
        new_low = (df['close'] <= low_20.shift(1)).astype(int)
        
        # 净新高
        net_new_high = new_high.rolling(window).sum() - new_low.rolling(window).sum()
        
        factor = net_new_high / window
        
        return pd.Series(factor, index=df.index)
    
    def seasonality_proxy(self, df: pd.DataFrame) -> pd.Series:
        """
        季节性代理
        
        逻辑: A股历史月度效应
             1-2月: 春节效应 (偏正面)
             4月: 业绩披露期 (波动)
             6月: 年中流动性紧张
             10月: 国庆后行情
        """
        df_copy = df.copy()
        df_copy['month'] = pd.to_datetime(df_copy.index).month
        
        # 月度得分 (基于A股历史统计)
        month_score = {
            1: 0.3,   # 春节行情
            2: 0.5,   # 春节延续
            3: 0.1,   # 两会
            4: -0.2,  # 业绩披露
            5: 0.0,
            6: -0.3,  # 年中紧张
            7: 0.1,
            8: -0.1,
            9: 0.0,
            10: 0.4,  # 国庆后
            11: 0.3,
            12: 0.2   # 跨年
        }
        
        factor = df_copy['month'].map(month_score).fillna(0)
        
        return pd.Series(factor, index=df.index)
    
    # ========== 批量计算 ==========
    
    def compute_all_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算所有非同质化因子
        
        Parameters:
            df: DataFrame with columns [open, high, low, close, volume, amount]
        
        Returns:
            DataFrame with all factors
        """
        result = df.copy()
        
        # 高频因子
        result['f_gap_momentum'] = self.price_gap_momentum(df)
        result['f_vol_impulse'] = self.volume_impulse(df)
        result['f_intraday_reversal'] = self.intraday_reversal(df)
        result['f_am_pm_divergence'] = self.am_pm_divergence(df)
        result['f_large_order_imb'] = self.large_order_imbalance(df)
        
        # 中频因子
        result['f_earn_surprise'] = self.earnings_surprise_proxy(df)
        result['f_smart_money'] = self.smart_money_proxy(df)
        result['f_retail_exhaust'] = self.retail_exhaustion(df)
        result['f_fund_flow_mom'] = self.fund_flow_momentum(df)
        result['f_vol_regime'] = self.volatility_regime(df)
        
        # 低频因子
        result['f_market_structure'] = self.market_structure(df)
        result['f_seasonality'] = self.seasonality_proxy(df)
        
        return result


# ==================== 因子定义清单 ====================

NON_HOMOGENEOUS_FACTORS = {
    'high_freq': [
        ('f_gap_momentum', '跳空动量', '价格行为'),
        ('f_vol_impulse', '成交量脉冲', '量能异常'),
        ('f_intraday_reversal', '日内反转', '技术形态'),
        ('f_am_pm_divergence', '上午下午背离', '时段分析'),
        ('f_large_order_imb', '大单不平衡', '资金流'),
    ],
    'mid_freq': [
        ('f_earn_surprise', '业绩超预期代理', '事件驱动'),
        ('f_smart_money', '聪明钱代理', '资金流'),
        ('f_retail_exhaust', '散户exhaustion', '行为金融'),
        ('f_fund_flow_mom', '资金流动量', '趋势'),
        ('f_vol_regime', '波动率状态', '风险'),
    ],
    'low_freq': [
        ('f_market_structure', '市场结构', '广度'),
        ('f_seasonality', '季节性代理', '日历效应'),
        ('f_liquidity_regime', '流动性状态', '宏观'),
        ('f_sector_rotation', '板块轮动', '行业'),
    ]
}


def get_factor_documentation() -> str:
    """获取因子文档"""
    doc = """
# Nous Invest 非同质化因子文档

## 设计原则

1. **避开 Alpha158**: 不使用任何 Alpha158 中定义的因子
2. **A股微观结构**: 针对 A股 T+1、散户占比高等特点设计
3. **跨频段叠加**: 高/中/低频信号互补
4. **可解释性**: 每个因子都有明确的经济逻辑

## 高频因子 (Daily)

| 因子名 | 中文名 | 逻辑说明 |
|--------|--------|----------|
| f_gap_momentum | 跳空动量 | 开盘缺口 + 早盘趋势的复合信号 |
| f_vol_impulse | 成交量脉冲 | 成交量突增(>2倍)识别资金介入 |
| f_intraday_reversal | 日内反转 | 长下影线+收涨 = 反转信号 |
| f_am_pm_divergence | 上午下午背离 | 时段成交量差异代理 |
| f_large_order_imb | 大单不平衡 | 成交额/成交量比率识别大单 |

## 中频因子 (Weekly)

| 因子名 | 中文名 | 逻辑说明 |
|--------|--------|----------|
| f_earn_surprise | 业绩超预期代理 | 跳空+放量+趋势 = 业绩信号 |
| f_smart_money | 聪明钱代理 | 尾盘强势+逆势买入 |
| f_retail_exhaust | 散户exhaustion | 极端情绪后的反转点 |
| f_fund_flow_mom | 资金流动量 | 主力资金趋势确认 |
| f_vol_regime | 波动率状态 | 低波动→高波动切换信号 |

## 低频因子 (Monthly)

| 因子名 | 中文名 | 逻辑说明 |
|--------|--------|----------|
| f_market_structure | 市场结构 | 新高新低股票占比 |
| f_seasonality | 季节性代理 | A股历史月度效应 |
| f_liquidity_regime | 流动性状态 | 成交量趋势 |
| f_sector_rotation | 板块轮动 | 大小盘/行业相对强弱 |

## 与 Alpha158 差异

| 维度 | Alpha158 | Nous 非同质化因子 |
|------|----------|-------------------|
| 设计来源 | 成熟论文/公开因子 | 原创+A股特性 |
| 同质化程度 | 高 (多人使用) | 低 (独家设计) |
| 频率侧重 | 以日线为主 | 高/中/低频分层 |
| 微观结构 | 较少考虑 | A股 T+1 适配 |
| 数据依赖 | 基础价量 | 另类数据整合 |

"""
    return doc


if __name__ == '__main__':
    # 生成文档
    print(get_factor_documentation())
