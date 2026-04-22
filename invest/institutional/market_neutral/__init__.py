"""
Nous Invest — Market Neutral Framework (Long-Short)
市场中性基础框架: 7亿规模私募级

核心组件:
1. StockUniverse — 容量约束选股池 (日均成交额>5亿, 市值200-2000亿)
2. AlphaModel — 信号整合与打分
3. BetaHedge — 对冲配比优化 (股指期货/融券)
4. LongShortConstructor — 多空组合构建
5. ExposureManager — 因子暴露管理
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import warnings
warnings.filterwarnings('ignore')


# ──────────────────────────────────────────────
# Constants — 7亿规模私募约束
# ──────────────────────────────────────────────

class InstitutionalConstraints:
    """机构级约束常量"""
    AUM = 700_000_000  # 7亿
    MAX_SINGLE_WEIGHT = 0.05  # 单票最大权重 5%
    MIN_LIQUIDITY = 500_000_000  # 日均成交额 > 5亿
    MIN_MARKET_CAP = 20_000_000_000  # 市值 > 200亿
    MAX_MARKET_CAP = 200_000_000_000  # 市值 < 2000亿
    TARGET_BETA = 0.0  # 市场中性目标 beta=0
    BETA_TOLERANCE = 0.10  # beta 偏差容忍 ±0.10
    MAX_SECTOR_EXPOSURE = 0.15  # 单行业最大暴露 15%
    MAX_FACTOR_EXPOSURE = 0.20  # 单风格因子最大暴露 20%
    LONG_SHORT_RATIO = 1.0  # 多空比 1:1
    MIN_STOCKS_LONG = 40  # 多头最少 40 只
    MIN_STOCKS_SHORT = 20  # 空头最少 20 只
    TARGET_GROSS_LEVERAGE = 2.0  # 目标总杠杆 (多+空)
    TARGET_NET_LEVERAGE = 0.0  # 目标净杠杆 (中性)


@dataclass
class StockLiquidity:
    """个股流动性指标"""
    ts_code: str
    name: str = ""
    avg_amount_20d: float = 0.0  # 20日日均成交额
    avg_amount_60d: float = 0.0  # 60日日均成交额
    market_cap: float = 0.0  # 总市值
    circulating_cap: float = 0.0  # 流通市值
    free_float_ratio: float = 0.0  # 自由流通比例
    turnover_rate_20d: float = 0.0  # 20日平均换手率
    amihud_illiquidity: float = 0.0  # Amihud 非流动性
    eligible: bool = False  # 是否进入选股池
    reject_reason: str = ""  # 剔除原因


@dataclass
class LongShortPortfolio:
    """多空组合"""
    date: str

    # 多头
    long_codes: List[str] = field(default_factory=list)
    long_weights: np.ndarray = field(default_factory=lambda: np.array([]))
    long_scores: np.ndarray = field(default_factory=lambda: np.array([]))

    # 空头
    short_codes: List[str] = field(default_factory=list)
    short_weights: np.ndarray = field(default_factory=lambda: np.array([]))
    short_scores: np.ndarray = field(default_factory=lambda: np.array([]))

    # 对冲
    hedge_instruments: List[str] = field(default_factory=list)  # 期货/融券标的
    hedge_ratios: Dict[str, float] = field(default_factory=dict)

    # 组合指标
    gross_leverage: float = 0.0
    net_leverage: float = 0.0
    estimated_beta: float = 0.0
    sector_exposures: Dict[str, float] = field(default_factory=dict)
    factor_exposures: Dict[str, float] = field(default_factory=dict)

    # 容量
    long_capacity: float = 0.0
    short_capacity: float = 0.0


# ──────────────────────────────────────────────
# 1. Stock Universe — 容量约束选股池
# ──────────────────────────────────────────────

class StockUniverse:
    """
    容量约束选股池
    
    筛选条件 (7亿规模):
    - 日均成交额 > 5亿元
    - 总市值 200亿 - 2000亿
    - 非ST / 非退市 / 上市满1年
    - 自由流通比例 > 15%
    """

    def __init__(self,
                 min_amount: float = InstitutionalConstraints.MIN_LIQUIDITY,
                 min_mcap: float = InstitutionalConstraints.MIN_MARKET_CAP,
                 max_mcap: float = InstitutionalConstraints.MAX_MARKET_CAP,
                 min_free_float: float = 0.15):
        self.min_amount = min_amount
        self.min_mcap = min_mcap
        self.max_mcap = max_mcap
        self.min_free_float = min_free_float
        self._universe_cache: Dict[str, List[StockLiquidity]] = {}

    def screen(self,
               stock_data: pd.DataFrame,
               date: Optional[str] = None,
               lookback: int = 20) -> List[StockLiquidity]:
        """
        运行选股池筛选

        Parameters
        ----------
        stock_data : DataFrame
            必须包含: ts_code, trade_date, amount, close, total_mv, circ_mv, turnover_rate
            amount 单位: 千元 (Tushare 标准)
            total_mv / circ_mv 单位: 万元 (Tushare 标准)
        date : str
            截止日期 YYYYMMDD
        lookback : int
            回望天数

        Returns
        -------
        List[StockLiquidity]
        """
        if date is None:
            date = stock_data['trade_date'].max()

        recent = stock_data[stock_data['trade_date'] <= date].copy()
        recent = recent.sort_values(['ts_code', 'trade_date'])

        results = []
        for code, grp in recent.groupby('ts_code'):
            sl = self._screen_single(grp.tail(lookback))
            results.append(sl)

        eligible = [s for s in results if s.eligible]
        print(f"[StockUniverse] {date}: {len(eligible)}/{len(results)} eligible "
              f"(amount>{self.min_amount/1e8:.0f}亿, "
              f"mcap {self.min_mcap/1e8:.0f}-{self.max_mcap/1e8:.0f}亿)")

        return results

    def _screen_single(self, recent: pd.DataFrame) -> StockLiquidity:
        """筛选单只股票"""
        code = recent['ts_code'].iloc[-1]
        sl = StockLiquidity(ts_code=code)

        if len(recent) < 5:
            sl.reject_reason = "数据不足"
            return sl

        # 日均成交额 (Tushare amount 单位千元 → 元)
        avg_amount_20d = recent['amount'].mean() * 1000 if 'amount' in recent.columns else 0
        avg_amount_60d = avg_amount_20d  # 简化
        sl.avg_amount_20d = avg_amount_20d
        sl.avg_amount_60d = avg_amount_60d

        # 市值 (Tushare total_mv 单位万元 → 元)
        latest = recent.iloc[-1]
        market_cap = latest.get('total_mv', 0) * 10000 if 'total_mv' in latest.index else 0
        circulating_cap = latest.get('circ_mv', 0) * 10000 if 'circ_mv' in latest.index else 0
        sl.market_cap = market_cap
        sl.circulating_cap = circulating_cap

        # 换手率
        sl.turnover_rate_20d = recent.get('turnover_rate', pd.Series([0])).mean()

        # 自由流通比例
        if market_cap > 0:
            sl.free_float_ratio = circulating_cap / market_cap
        else:
            sl.free_float_ratio = 0

        # ── 筛选条件 ──
        if avg_amount_20d < self.min_amount:
            sl.reject_reason = f"成交额不足({avg_amount_20d/1e8:.1f}亿<{self.min_amount/1e8:.0f}亿)"
            return sl

        if market_cap < self.min_mcap:
            sl.reject_reason = f"市值偏小({market_cap/1e8:.0f}亿<{self.min_mcap/1e8:.0f}亿)"
            return sl

        if market_cap > self.max_mcap:
            sl.reject_reason = f"市值偏大({market_cap/1e8:.0f}亿>{self.max_mcap/1e8:.0f}亿)"
            return sl

        if sl.free_float_ratio < self.min_free_float:
            sl.reject_reason = f"自由流通不足({sl.free_float_ratio:.0%}<{self.min_free_float:.0%})"
            return sl

        # Amihud illiquidity
        if 'close' in recent.columns and 'amount' in recent.columns:
            ret = recent['close'].pct_change().dropna()
            amt = recent['amount'].iloc[1:] * 1000  # → 元
            valid = (ret != 0) & (amt > 0)
            if valid.sum() > 5:
                sl.amihud_illiquidity = (ret[valid].abs() / amt[valid]).mean()

        sl.eligible = True
        return sl

    def get_eligible_codes(self,
                           stock_data: pd.DataFrame,
                           date: Optional[str] = None) -> List[str]:
        """获取符合条件的股票代码列表"""
        results = self.screen(stock_data, date)
        return [s.ts_code for s in results if s.eligible]


# ──────────────────────────────────────────────
# 2. Alpha Model — 信号整合
# ──────────────────────────────────────────────

class AlphaModel:
    """
    信号整合与打分

    整合多源信号:
    - ML 模型预测 (LightGBM/XGBoost ensemble)
    - 另类数据因子 (龙虎榜/北向/分析师)
    - 非同质化因子
    """

    def __init__(self,
                 signal_weights: Optional[Dict[str, float]] = None):
        self.signal_weights = signal_weights or {
            'ml_score': 0.40,
            'alt_score': 0.25,
            'non_homo_score': 0.20,
            'technical_score': 0.15,
        }

    def compute_composite_score(self,
                                ml_scores: pd.Series,
                                alt_scores: Optional[pd.Series] = None,
                                non_homo_scores: Optional[pd.Series] = None,
                                technical_scores: Optional[pd.Series] = None) -> pd.Series:
        """
        计算综合打分

        Parameters
        ----------
        ml_scores : pd.Series
            ML模型预测分 (index: ts_code)
        alt_scores, non_homo_scores, technical_scores : Optional[Series]

        Returns
        -------
        pd.Series  综合打分 (index: ts_code)
        """
        # 归一化每个信号到 Z-Score
        scores = pd.DataFrame(index=ml_scores.index)
        scores['ml'] = self._zscore(ml_scores)

        if alt_scores is not None:
            common = scores.index.intersection(alt_scores.index)
            scores.loc[common, 'alt'] = self._zscore(alt_scores.loc[common])

        if non_homo_scores is not None:
            common = scores.index.intersection(non_homo_scores.index)
            scores.loc[common, 'non_homo'] = self._zscore(non_homo_scores.loc[common])

        if technical_scores is not None:
            common = scores.index.intersection(technical_scores.index)
            scores.loc[common, 'technical'] = self._zscore(technical_scores.loc[common])

        # 加权合成
        composite = pd.Series(0.0, index=scores.index)
        for col, w_key in [('ml', 'ml_score'), ('alt', 'alt_score'),
                           ('non_homo', 'non_homo_score'), ('technical', 'technical_score')]:
            if col in scores.columns:
                w = self.signal_weights.get(w_key, 0)
                composite += scores[col].fillna(0) * w

        return composite

    @staticmethod
    def _zscore(s: pd.Series) -> pd.Series:
        return (s - s.mean()) / (s.std() + 1e-8)


# ──────────────────────────────────────────────
# 3. Beta Hedge — 对冲配比
# ──────────────────────────────────────────────

class BetaHedge:
    """
    对冲配比优化

    支持对冲工具:
    - 股指期货: IF/IH/IC/IM
    - 融券 (如有券源)
    """

    # 期货合约乘数
    FUTURES_MULTIPLIER = {
        'IF': 300,  # 沪深300
        'IH': 300,  # 上证50
        'IC': 200,  # 中证500
        'IM': 200,  # 中证1000
    }

    def __init__(self,
                 aum: float = InstitutionalConstraints.AUM,
                 target_beta: float = InstitutionalConstraints.TARGET_BETA,
                 beta_tolerance: float = InstitutionalConstraints.BETA_TOLERANCE):
        self.aum = aum
        self.target_beta = target_beta
        self.beta_tolerance = beta_tolerance

    def compute_hedge_ratio(self,
                            long_beta: float,
                            short_beta: float,
                            long_weight: float,
                            short_weight: float,
                            benchmark: str = 'IF') -> Dict[str, float]:
        """
        计算期货对冲比例

        Parameters
        ----------
        long_beta : float  多头组合 beta
        short_beta : float  空头组合 beta
        long_weight : float  多头权重合计
        short_weight : float  空头权重合计
        benchmark : str  对冲标的

        Returns
        -------
        Dict with keys: hedge_ratio, contracts_needed, residual_beta
        """
        net_beta = long_beta * long_weight - short_beta * short_weight
        hedge_ratio = net_beta / 1.0 if True else net_beta  # 期货 beta≈1
        residual_beta = net_beta - hedge_ratio

        # 合约数量
        multiplier = self.FUTURES_MULTIPLIER.get(benchmark, 300)
        notional_per_contract = 4000 * multiplier  # 估算: 指数点位 * 乘数
        contracts = abs(hedge_ratio) * self.aum / notional_per_contract
        contracts = round(contracts)

        direction = 'short' if hedge_ratio > 0 else 'long'

        return {
            'net_beta': round(net_beta, 4),
            'hedge_ratio': round(hedge_ratio, 4),
            'contracts_needed': contracts,
            'direction': direction,
            'residual_beta': round(residual_beta, 4),
            'benchmark': benchmark,
            'notional_hedged': round(abs(hedge_ratio) * self.aum, 0),
        }

    def select_optimal_hedge(self,
                             portfolio_exposure: Dict[str, float]) -> Dict[str, float]:
        """
        选择最优对冲组合

        Parameters
        ----------
        portfolio_exposure : dict
            指数暴露 {index_name: beta_exposure}

        Returns
        -------
        Dict {futures_code: weight}
        """
        # 简化: 按暴露大小选择主力合约
        total_exposure = sum(abs(v) for v in portfolio_exposure.values())
        if total_exposure == 0:
            return {}

        hedge_weights = {}
        for idx, exp in portfolio_exposure.items():
            weight = exp / total_exposure
            hedge_weights[idx] = round(weight, 4)

        return hedge_weights


# ──────────────────────────────────────────────
# 4. Long-Short Constructor — 多空组合构建
# ──────────────────────────────────────────────

class LongShortConstructor:
    """
    多空组合构建器

    流程:
    1. 从 StockUniverse 获取选股池
    2. AlphaModel 打分
    3. 按 score 分配多/空头
    4. 行业中性 + 因子暴露控制
    5. 对冲配比
    """

    def __init__(self,
                 constraints: Optional[InstitutionalConstraints] = None,
                 universe: Optional[StockUniverse] = None,
                 alpha_model: Optional[AlphaModel] = None,
                 beta_hedge: Optional[BetaHedge] = None):
        self.constraints = constraints or InstitutionalConstraints()
        self.universe = universe or StockUniverse()
        self.alpha_model = alpha_model or AlphaModel()
        self.beta_hedge = beta_hedge or BetaHedge()
        self.industry_mapping: Dict[str, str] = {}

    def set_industry_mapping(self, mapping: Dict[str, str]):
        self.industry_mapping = mapping

    def construct(self,
                  scores: pd.Series,
                  liquidity_data: Dict[str, StockLiquidity],
                  stock_betas: Optional[pd.Series] = None,
                  date: Optional[str] = None) -> LongShortPortfolio:
        """
        构建多空组合

        Parameters
        ----------
        scores : pd.Series
            综合打分 (index: ts_code, values: composite score)
        liquidity_data : dict
            {ts_code: StockLiquidity}
        stock_betas : Optional[Series]
            个股 beta (index: ts_code)
        date : str

        Returns
        -------
        LongShortPortfolio
        """
        c = self.constraints

        # ── 1. 过滤: 只保留合格股票 ──
        eligible_codes = [code for code in scores.index
                         if code in liquidity_data and liquidity_data[code].eligible]
        eligible_scores = scores.loc[scores.index.isin(eligible_codes)]

        if len(eligible_scores) < c.MIN_STOCKS_LONG + c.MIN_STOCKS_SHORT:
            raise ValueError(
                f"合格股票不足: {len(eligible_scores)} < {c.MIN_STOCKS_LONG + c.MIN_STOCKS_SHORT}")

        # ── 2. 排序分多空 ──
        sorted_scores = eligible_scores.sort_values(ascending=False)

        n_long = min(max(c.MIN_STOCKS_LONG, len(sorted_scores) // 3), 80)
        n_short = min(max(c.MIN_STOCKS_SHORT, len(sorted_scores) // 5), 40)

        long_candidates = sorted_scores.head(n_long)
        short_candidates = sorted_scores.tail(n_short)

        # ── 3. 权重分配 ──
        long_weights = self._assign_weights(
            long_candidates, max_weight=c.MAX_SINGLE_WEIGHT)
        short_weights = self._assign_weights(
            short_candidates, max_weight=c.MAX_SINGLE_WEIGHT)

        # ── 4. 行业暴露约束 ──
        long_weights = self._constrain_sector(
            long_weights, c.MAX_SECTOR_EXPOSURE)
        short_weights = self._constrain_sector(
            short_weights, c.MAX_SECTOR_EXPOSURE)

        # ── 5. 对冲 ──
        long_beta = self._estimate_portfolio_beta(
            long_weights, stock_betas)
        short_beta = self._estimate_portfolio_beta(
            short_weights, stock_betas)

        hedge_info = self.beta_hedge.compute_hedge_ratio(
            long_beta=long_beta,
            short_beta=short_beta,
            long_weight=long_weights.sum(),
            short_weight=short_weights.sum(),
        )

        # ── 6. 组装结果 ──
        portfolio = LongShortPortfolio(
            date=date or pd.Timestamp.now().strftime('%Y%m%d'),
            long_codes=long_weights.index.tolist(),
            long_weights=long_weights.values,
            long_scores=long_candidates.loc[long_weights.index].values,
            short_codes=short_weights.index.tolist(),
            short_weights=short_weights.values,
            short_scores=short_candidates.loc[short_weights.index].values,
            hedge_instruments=[hedge_info['benchmark']],
            hedge_ratios={hedge_info['benchmark']: hedge_info['hedge_ratio']},
            gross_leverage=long_weights.sum() + short_weights.sum(),
            net_leverage=long_weights.sum() - short_weights.sum(),
            estimated_beta=hedge_info.get('residual_beta', 0),
        )

        # 行业暴露
        portfolio.sector_exposures = self._compute_sector_exposure(
            long_weights, short_weights)

        # 容量
        portfolio.long_capacity = sum(
            liquidity_data.get(c, StockLiquidity(ts_code=c)).avg_amount_20d * 0.05
            for c in long_weights.index)
        portfolio.short_capacity = sum(
            liquidity_data.get(c, StockLiquidity(ts_code=c)).avg_amount_20d * 0.03
            for c in short_weights.index)

        return portfolio

    def _assign_weights(self,
                        scores: pd.Series,
                        max_weight: float) -> pd.Series:
        """
        按 score 加权分配权重 (受 max_weight 约束)
        """
        # Score → 正权重
        w = scores.abs()
        w = w / w.sum()

        # 截断超限
        capped = w.clip(upper=max_weight)
        excess = (w - capped).sum()
        below = w[w < max_weight]
        if excess > 0 and len(below) > 0:
            redistribution = excess * below / below.sum()
            capped.loc[below.index] += redistribution

        # 二次截断
        capped = capped.clip(upper=max_weight)
        capped = capped / capped.sum()

        return capped

    def _constrain_sector(self,
                          weights: pd.Series,
                          max_exposure: float) -> pd.Series:
        """约束单一行业权重"""
        if not self.industry_mapping:
            return weights

        sectors = weights.index.map(lambda c: self.industry_mapping.get(c, 'UNKNOWN'))
        sector_weights = pd.DataFrame({'weight': weights, 'sector': sectors})
        sector_totals = sector_weights.groupby('sector')['weight'].sum()

        over_sectors = sector_totals[sector_totals > max_exposure].index

        if len(over_sectors) == 0:
            return weights

        result = weights.copy()
        for sector in over_sectors:
            mask = sectors == sector
            sector_stocks = result[mask]
            scale = max_exposure / sector_stocks.sum()
            result[mask] *= scale

        # 重新归一化
        result = result / result.sum()
        return result

    def _estimate_portfolio_beta(self,
                                 weights: pd.Series,
                                 betas: Optional[pd.Series]) -> float:
        if betas is None:
            return 1.0
        common = weights.index.intersection(betas.index)
        if len(common) == 0:
            return 1.0
        return float((weights.loc[common] * betas.loc[common]).sum())

    def _compute_sector_exposure(self,
                                 long_w: pd.Series,
                                 short_w: pd.Series) -> Dict[str, float]:
        if not self.industry_mapping:
            return {}

        exposures = {}
        for label, ws in [('long', long_w), ('short', short_w)]:
            for code, w in ws.items():
                sector = self.industry_mapping.get(code, 'UNKNOWN')
                sign = 1 if label == 'long' else -1
                exposures[sector] = exposures.get(sector, 0) + sign * w

        return {k: round(v, 4) for k, v in sorted(exposures.items(),
                                                    key=lambda x: abs(x[1]),
                                                    reverse=True)}


# ──────────────────────────────────────────────
# 5. Exposure Manager — 因子暴露管理
# ──────────────────────────────────────────────

class ExposureManager:
    """
    因子暴露管理

    控制:
    - 行业暴露 (GICS 二级行业)
    - 风格因子暴露 (市值/价值/动量/波动率)
    - Beta 暴露
    """

    # 标准风格因子
    STYLE_FACTORS = ['size', 'value', 'momentum', 'volatility', 'liquidity', 'quality']

    def __init__(self,
                 max_sector: float = InstitutionalConstraints.MAX_SECTOR_EXPOSURE,
                 max_style: float = InstitutionalConstraints.MAX_FACTOR_EXPOSURE):
        self.max_sector = max_sector
        self.max_style = max_style

    def compute_factor_exposure(self,
                                portfolio_weights: pd.Series,
                                factor_loadings: pd.DataFrame) -> Dict[str, float]:
        """
        计算组合因子暴露

        Parameters
        ----------
        portfolio_weights : Series (index: ts_code)
        factor_loadings : DataFrame (index: ts_code, columns: factor names)

        Returns
        -------
        Dict {factor_name: exposure}
        """
        common = portfolio_weights.index.intersection(factor_loadings.index)
        if len(common) == 0:
            return {}

        w = portfolio_weights.loc[common]
        loadings = factor_loadings.loc[common]

        exposures = {}
        for factor in loadings.columns:
            exp = float((w * loadings[factor]).sum())
            exposures[factor] = round(exp, 4)

        return exposures

    def check_breach(self,
                     exposures: Dict[str, float]) -> Dict[str, dict]:
        """
        检查暴露是否超限

        Returns
        -------
        Dict {factor: {'value': float, 'limit': float, 'breach': bool}}
        """
        results = {}
        for factor, exp in exposures.items():
            is_sector = factor not in self.STYLE_FACTORS
            limit = self.max_sector if is_sector else self.max_style
            results[factor] = {
                'value': exp,
                'limit': limit,
                'breach': abs(exp) > limit,
            }
        return results

    def generate_exposure_report(self,
                                 portfolio: LongShortPortfolio) -> str:
        """生成暴露报告"""
        lines = [
            f"{'='*60}",
            f"因子暴露报告 — {portfolio.date}",
            f"{'='*60}",
            "",
            f"📊 组合杠杆: Gross={portfolio.gross_leverage:.2f}, Net={portfolio.net_leverage:.2f}",
            f"📈 估计 Beta: {portfolio.estimated_beta:.4f}",
            "",
            "🏗️ 行业暴露:",
        ]

        for sector, exp in portfolio.sector_exposures.items():
            flag = "⚠️" if abs(exp) > self.max_sector else "  "
            lines.append(f"  {flag} {sector:10s}: {exp:+.2%}")

        lines.append("")
        lines.append("📐 风格因子暴露:")
        for factor, exp in portfolio.factor_exposures.items():
            flag = "⚠️" if abs(exp) > self.max_style else "  "
            lines.append(f"  {flag} {factor:12s}: {exp:+.4f}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)
