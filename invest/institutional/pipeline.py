"""
Nous Invest — Institutional Pipeline
7亿规模私募机构级日常运行管道

整合:
1. StockUniverse (选股池)
2. AlphaModel (信号)
3. LongShortConstructor (多空组合)
4. RiskManager (风控)
5. ComplianceChecker (合规)
6. AMACReportGenerator (报告)
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional

from .market_neutral import (
    StockUniverse, AlphaModel, LongShortConstructor,
    InstitutionalConstraints, StockLiquidity, LongShortPortfolio
)
from .risk import (
    RiskManager, RiskMetrics, VaRCalculator,
    DrawdownMonitor, ExposureLimiter, StopLossManager
)
from .compliance import (
    AMACReportGenerator, ComplianceChecker, AuditTrail,
    FundInfo, MonthlyReportData, QuarterlyReportData, InvestorDisclosure
)
from .config import (
    FUND_CONFIG, INVESTMENT_CONSTRAINTS, RISK_CONFIG,
    COMPLIANCE_CONFIG, TRADING_CONFIG, HEDGE_CONFIG
)


class InstitutionalPipeline:
    """
    机构级日常运行管道

    日流程:
    1. 更新数据
    2. 选股池筛选
    3. 信号生成 & 打分
    4. 多空组合构建
    5. 风控检查
    6. 合规自查
    7. 审计日志
    """

    def __init__(self, fund_info: Optional[FundInfo] = None):
        self.fund_info = fund_info or FundInfo(
            fund_name=FUND_CONFIG["name"],
            fund_code=FUND_CONFIG["code"],
            aum=FUND_CONFIG["aum"],
            strategy_type=FUND_CONFIG["strategy"],
            benchmark=FUND_CONFIG["benchmark"],
        )

        # 核心组件
        self.constraints = InstitutionalConstraints()
        self.universe = StockUniverse(
            min_amount=INVESTMENT_CONSTRAINTS["min_daily_amount"],
            min_mcap=INVESTMENT_CONSTRAINTS["min_market_cap"],
            max_mcap=INVESTMENT_CONSTRAINTS["max_market_cap"],
        )
        self.alpha_model = AlphaModel()
        self.constructor = LongShortConstructor(constraints=self.constraints)
        self.risk_manager = RiskManager(
            aum=self.fund_info.aum,
            max_drawdown=RISK_CONFIG["max_drawdown_limit"],
        )
        self.compliance = ComplianceChecker()
        self.report_generator = AMACReportGenerator(fund_info=self.fund_info)
        self.disclosure = InvestorDisclosure(fund_info=self.fund_info)
        self.audit = AuditTrail(log_dir=COMPLIANCE_CONFIG["audit_log_dir"])

    def daily_run(self,
                  stock_data: pd.DataFrame,
                  ml_scores: pd.Series,
                  alt_scores: Optional[pd.Series] = None,
                  fund_nav: Optional[pd.Series] = None,
                  sector_map: Optional[Dict[str, str]] = None,
                  stock_betas: Optional[pd.Series] = None,
                  date: Optional[str] = None) -> Dict:
        """
        每日运行管道

        Returns
        -------
        Dict with keys:
            'universe', 'portfolio', 'risk_metrics',
            'compliance_checks', 'status'
        """
        date = date or datetime.now().strftime('%Y%m%d')
        self.audit.log("daily_run_start", category="pipeline", details=f"date={date}")

        # 1. 选股池
        universe_results = self.universe.screen(stock_data, date)
        liquidity_map = {s.ts_code: s for s in universe_results}
        eligible_codes = [s.ts_code for s in universe_results if s.eligible]

        self.audit.log("universe_screen", category="pipeline",
                       details=f"eligible={len(eligible_codes)}")

        # 2. 信号打分
        composite_scores = self.alpha_model.compute_composite_score(
            ml_scores=ml_scores,
            alt_scores=alt_scores,
        )
        # 只保留合格股票
        eligible_scores = composite_scores[
            composite_scores.index.isin(eligible_codes)]

        # 3. 多空组合
        if sector_map:
            self.constructor.set_industry_mapping(sector_map)

        try:
            portfolio = self.constructor.construct(
                scores=eligible_scores,
                liquidity_data=liquidity_map,
                stock_betas=stock_betas,
                date=date,
            )
        except ValueError as e:
            self.audit.log("portfolio_error", category="risk",
                           details=str(e))
            return {'status': 'ERROR', 'message': str(e)}

        # 4. 风控
        risk_metrics = None
        if fund_nav is not None and len(fund_nav) > 30:
            fund_returns = fund_nav.pct_change().dropna()
            risk_metrics = self.risk_manager.daily_risk_check(
                fund_returns=fund_returns,
                fund_nav=fund_nav,
                weights_long=pd.Series(
                    portfolio.long_weights, index=portfolio.long_codes),
                weights_short=pd.Series(
                    portfolio.short_weights, index=portfolio.short_codes),
                sector_map=sector_map or {},
                betas=stock_betas,
                date=date,
            )

            # 风控日志
            self.audit.log("risk_check", category="risk",
                           details=f"level={risk_metrics.overall_risk_level.value}")

        # 5. 合规
        long_w = pd.Series(portfolio.long_weights, index=portfolio.long_codes)
        short_w = pd.Series(portfolio.short_weights, index=portfolio.short_codes)
        compliance_checks = self.compliance.run_full_check(
            portfolio_weights=pd.concat([long_w, -short_w]),
            gross_leverage=portfolio.gross_leverage,
            net_exposure=portfolio.net_leverage,
            disclosure_status={'monthly_nav': 'SUBMITTED'},
        )

        self.audit.log("compliance_check", category="compliance",
                       details=f"checks={len(compliance_checks)}")

        self.audit.log("daily_run_end", category="pipeline",
                       details=f"date={date}, status=OK")

        return {
            'status': 'OK',
            'date': date,
            'universe': {
                'total': len(universe_results),
                'eligible': len(eligible_codes),
            },
            'portfolio': portfolio,
            'risk_metrics': risk_metrics,
            'compliance_checks': compliance_checks,
        }

    def generate_reports(self,
                         monthly_data: Optional[MonthlyReportData] = None,
                         quarterly_data: Optional[QuarterlyReportData] = None,
                         report_type: str = 'monthly') -> str:
        """生成报告"""
        if report_type == 'monthly' and monthly_data:
            return self.report_generator.generate_monthly_report(monthly_data)
        elif report_type == 'quarterly' and quarterly_data:
            return self.report_generator.generate_quarterly_report(quarterly_data)
        return ""
