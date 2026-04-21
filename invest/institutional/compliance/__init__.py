"""
Nous Invest — Compliance & Disclosure Module
合规披露模块: AMAC 月报/季报/年报模板

7亿私募合规要求:
1. AMAC Reporting — 基金业协会报告模板
2. InvestorDisclosure — 投资者披露文件
3. ComplianceChecker — 合规自查
4. AuditTrail — 审计追踪
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import os


class ReportFrequency(Enum):
    DAILY = "日报"
    WEEKLY = "周报"
    MONTHLY = "月报"
    QUARTERLY = "季报"
    ANNUAL = "年报"


class ReportStatus(Enum):
    DRAFT = "草稿"
    REVIEW = "审核中"
    APPROVED = "已审核"
    SUBMITTED = "已提交"


# ──────────────────────────────────────────────
# 1. AMAC Report Templates
# ──────────────────────────────────────────────

@dataclass
class FundInfo:
    """基金基本信息"""
    fund_name: str = ""
    fund_code: str = ""
    fund_type: str = "私募证券投资基金"
    manager_name: str = ""
    manager_code: str = ""
    custodian_name: str = ""
    inception_date: str = ""
    aum: float = 700_000_000  # 7亿
    benchmark: str = "中证500指数"
    risk_level: str = "R4"
    strategy_type: str = "市场中性"


@dataclass
class MonthlyReportData:
    """月报数据"""
    report_month: str  # YYYYMM
    nav_start: float  # 月初净值
    nav_end: float  # 月末净值
    monthly_return: float  # 月收益率
    benchmark_return: float  # 基准收益
    excess_return: float  # 超额收益

    # 风险指标
    monthly_volatility: float = 0.0
    monthly_max_drawdown: float = 0.0
    monthly_sharpe: float = 0.0
    monthly_sortino: float = 0.0
    monthly_calmar: float = 0.0

    # 持仓统计
    position_count: int = 0
    avg_holding_days: float = 0.0
    monthly_turnover: float = 0.0
    long_short_ratio: float = 1.0
    gross_leverage: float = 2.0
    net_exposure: float = 0.0

    # VaR
    var_95: float = 0.0
    cvar_95: float = 0.0

    # 行业分布
    top5_industries: Dict[str, float] = field(default_factory=dict)
    top10_holdings: Dict[str, float] = field(default_factory=dict)


@dataclass
class QuarterlyReportData:
    """季报数据"""
    report_quarter: str  # 2026Q1
    nav_start: float
    nav_end: float
    quarterly_return: float
    benchmark_return: float
    excess_return: float

    # 累计指标
    annualized_return: float = 0.0
    annualized_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    profit_loss_ratio: float = 0.0

    # 季度汇总
    avg_position_count: int = 0
    avg_monthly_turnover: float = 0.0
    total_transactions: int = 0
    avg_daily_var: float = 0.0

    # 月度明细
    monthly_data: List[MonthlyReportData] = field(default_factory=list)

    # 策略归因
    alpha_attribution: Dict[str, float] = field(default_factory=dict)
    risk_attribution: Dict[str, float] = field(default_factory=dict)


@dataclass
class AnnualReportData:
    """年报数据"""
    report_year: str  # 2026

    # 全年收益
    annual_return: float = 0.0
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    annual_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    sortino_ratio: float = 0.0
    information_ratio: float = 0.0

    # 分季度
    quarterly_data: List[QuarterlyReportData] = field(default_factory=list)

    # 合规统计
    compliance_events: int = 0
    risk_breach_count: int = 0
    investor_complaints: int = 0
    regulatory_actions: int = 0

    # 运营统计
    total_aum_start: float = 0.0
    total_aum_end: float = 0.0
    subscriptions: float = 0.0
    redemptions: float = 0.0
    management_fees: float = 0.0
    performance_fees: float = 0.0
    trading_costs: float = 0.0


class AMACReportGenerator:
    """
    AMAC 报告生成器

    生成基金业协会要求的:
    - 月度报告
    - 季度报告
    - 年度报告
    """

    def __init__(self, fund_info: Optional[FundInfo] = None):
        self.fund_info = fund_info or FundInfo()

    # ── 月报 ──

    def generate_monthly_report(self,
                                data: MonthlyReportData,
                                output_format: str = 'markdown') -> str:
        """
        生成 AMAC 月度报告

        Parameters
        ----------
        data : MonthlyReportData
        output_format : 'markdown' | 'json'

        Returns
        -------
        str  报告内容
        """
        fi = self.fund_info

        if output_format == 'json':
            return self._monthly_to_json(data)

        # Markdown 格式
        report = f"""# {fi.fund_name} 月度报告

## 基本信息

| 项目 | 内容 |
|------|------|
| 基金名称 | {fi.fund_name} |
| 基金编码 | {fi.fund_code} |
| 管理人 | {fi.manager_name} |
| 托管人 | {fi.custodian_name} |
| 报告期间 | {self._format_month(data.report_month)} |
| 基金策略 | {fi.strategy_type} |
| 基准指数 | {fi.benchmark} |

## 净值表现

| 指标 | 数值 |
|------|------|
| 期初净值 | {data.nav_start:.4f} |
| 期末净值 | {data.nav_end:.4f} |
| 本月收益率 | {data.monthly_return:.2%} |
| 基准收益率 | {data.benchmark_return:.2%} |
| 超额收益 | {data.excess_return:.2%} |

## 风险指标

| 指标 | 数值 |
|------|------|
| 月波动率 | {data.monthly_volatility:.4f} |
| 月最大回撤 | {data.monthly_max_drawdown:.2%} |
| Sharpe | {data.monthly_sharpe:.2f} |
| Sortino | {data.monthly_sortino:.2f} |
| 95% VaR | ¥{data.var_95/1e4:,.0f}万 |
| 95% CVaR | ¥{data.cvar_95/1e4:,.0f}万 |

## 持仓情况

| 指标 | 数值 |
|------|------|
| 持仓数量 | {data.position_count} |
| 平均持有天数 | {data.avg_holding_days:.1f} |
| 月换手率 | {data.monthly_turnover:.2%} |
| 多空比 | {data.long_short_ratio:.2f} |
| 总杠杆 | {data.gross_leverage:.2f} |
| 净敞口 | {data.net_exposure:.2%} |

## 行业分布

| 行业 | 权重 |
|------|------|
"""
        for ind, w in sorted(data.top5_industries.items(),
                             key=lambda x: x[1], reverse=True):
            report += f"| {ind} | {w:.2%} |\n"

        report += f"""
## 前十大持仓

| 股票 | 权重 |
|------|------|
"""
        for stock, w in sorted(data.top10_holdings.items(),
                               key=lambda x: x[1], reverse=True):
            report += f"| {stock} | {w:.2%} |\n"

        report += f"""
---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
*本报告仅供基金业协会备案及投资者披露使用*
"""
        return report

    # ── 季报 ──

    def generate_quarterly_report(self,
                                  data: QuarterlyReportData,
                                  output_format: str = 'markdown') -> str:
        fi = self.fund_info

        if output_format == 'json':
            return self._quarterly_to_json(data)

        report = f"""# {fi.fund_name} 季度报告

## 基本信息

| 项目 | 内容 |
|------|------|
| 基金名称 | {fi.fund_name} |
| 基金编码 | {fi.fund_code} |
| 管理人 | {fi.manager_name} |
| 报告期间 | {data.report_quarter} |
| 策略类型 | {fi.strategy_type} |

## 季度业绩

| 指标 | 数值 |
|------|------|
| 期初净值 | {data.nav_start:.4f} |
| 期末净值 | {data.nav_end:.4f} |
| 季度收益率 | {data.quarterly_return:.2%} |
| 基准收益率 | {data.benchmark_return:.2%} |
| 超额收益 | {data.excess_return:.2%} |
| 年化收益率 | {data.annualized_return:.2%} |
| 年化波动率 | {data.annualized_volatility:.2%} |
| Sharpe比率 | {data.sharpe_ratio:.2f} |
| 最大回撤 | {data.max_drawdown:.2%} |
| Calmar比率 | {data.calmar_ratio:.2f} |
| 胜率 | {data.win_rate:.2%} |
| 盈亏比 | {data.profit_loss_ratio:.2f} |

## 运营概况

| 指标 | 数值 |
|------|------|
| 平均持仓数 | {data.avg_position_count} |
| 平均月换手率 | {data.avg_monthly_turnover:.2%} |
| 总交易笔数 | {data.total_transactions} |
| 日均VaR(95%) | ¥{data.avg_daily_var/1e4:,.0f}万 |

## 月度明细

| 月份 | 收益率 | 超额 | 波动率 | 回撤 |
|------|--------|------|--------|------|
"""
        for m in data.monthly_data:
            report += (f"| {self._format_month(m.report_month)} "
                       f"| {m.monthly_return:.2%} "
                       f"| {m.excess_return:.2%} "
                       f"| {m.monthly_volatility:.4f} "
                       f"| {m.monthly_max_drawdown:.2%} |\n")

        if data.alpha_attribution:
            report += "\n## 策略归因\n\n| 因子 | 贡献 |\n|------|------|\n"
            for factor, contrib in sorted(data.alpha_attribution.items(),
                                          key=lambda x: abs(x[1]), reverse=True):
                report += f"| {factor} | {contrib:.2%} |\n"

        report += f"""
---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
        return report

    # ── 年报 ──

    def generate_annual_report(self,
                               data: AnnualReportData,
                               output_format: str = 'markdown') -> str:
        fi = self.fund_info

        if output_format == 'json':
            return self._annual_to_json(data)

        report = f"""# {fi.fund_name} 年度报告

## 基本信息

| 项目 | 内容 |
|------|------|
| 基金名称 | {fi.fund_name} |
| 基金编码 | {fi.fund_code} |
| 管理人 | {fi.manager_name} |
| 报告年度 | {data.report_year} |
| 成立日期 | {fi.inception_date} |
| 策略类型 | {fi.strategy_type} |

## 年度业绩

| 指标 | 数值 |
|------|------|
| 年度收益率 | {data.annual_return:.2%} |
| 基准收益率 | {data.benchmark_return:.2%} |
| 超额收益 | {data.excess_return:.2%} |
| 年化波动率 | {data.annual_volatility:.2%} |
| Sharpe比率 | {data.sharpe_ratio:.2f} |
| Sortino比率 | {data.sortino_ratio:.2f} |
| 最大回撤 | {data.max_drawdown:.2%} |
| Calmar比率 | {data.calmar_ratio:.2f} |
| 信息比率 | {data.information_ratio:.2f} |

## 规模变动

| 项目 | 金额 |
|------|------|
| 期初规模 | ¥{data.total_aum_start/1e8:.2f}亿 |
| 期末规模 | ¥{data.total_aum_end/1e8:.2f}亿 |
| 期间申购 | ¥{data.subscriptions/1e8:.2f}亿 |
| 期间赎回 | ¥{data.redemptions/1e8:.2f}亿 |

## 费用

| 项目 | 金额 |
|------|------|
| 管理费 | ¥{data.management_fees/1e4:,.0f}万 |
| 业绩报酬 | ¥{data.performance_fees/1e4:,.0f}万 |
| 交易成本 | ¥{data.trading_costs/1e4:,.0f}万 |

## 合规情况

| 项目 | 数值 |
|------|------|
| 合规事件 | {data.compliance_events} |
| 风险超限次数 | {data.risk_breach_count} |
| 投资者投诉 | {data.investor_complaints} |
| 监管处罚 | {data.regulatory_actions} |

## 季度明细

| 季度 | 收益率 | 超额 | 最大回撤 |
|------|--------|------|----------|
"""
        for q in data.quarterly_data:
            report += (f"| {q.report_quarter} "
                       f"| {q.quarterly_return:.2%} "
                       f"| {q.excess_return:.2%} "
                       f"| {q.max_drawdown:.2%} |\n")

        report += f"""
---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
*本报告依据《私募投资基金信息披露管理办法》编制*
"""
        return report

    # ── JSON 序列化 ──

    def _monthly_to_json(self, data: MonthlyReportData) -> str:
        d = {
            'report_type': 'monthly',
            'fund_code': self.fund_info.fund_code,
            'report_month': data.report_month,
            'nav_start': data.nav_start,
            'nav_end': data.nav_end,
            'monthly_return': data.monthly_return,
            'benchmark_return': data.benchmark_return,
            'excess_return': data.excess_return,
            'monthly_volatility': data.monthly_volatility,
            'monthly_max_drawdown': data.monthly_max_drawdown,
            'monthly_sharpe': data.monthly_sharpe,
            'position_count': data.position_count,
            'monthly_turnover': data.monthly_turnover,
            'long_short_ratio': data.long_short_ratio,
            'gross_leverage': data.gross_leverage,
            'net_exposure': data.net_exposure,
            'var_95': data.var_95,
            'top5_industries': data.top5_industries,
            'top10_holdings': data.top10_holdings,
        }
        return json.dumps(d, ensure_ascii=False, indent=2)

    def _quarterly_to_json(self, data: QuarterlyReportData) -> str:
        d = {
            'report_type': 'quarterly',
            'fund_code': self.fund_info.fund_code,
            'report_quarter': data.report_quarter,
            'quarterly_return': data.quarterly_return,
            'benchmark_return': data.benchmark_return,
            'excess_return': data.excess_return,
            'annualized_return': data.annualized_return,
            'annualized_volatility': data.annualized_volatility,
            'sharpe_ratio': data.sharpe_ratio,
            'max_drawdown': data.max_drawdown,
            'calmar_ratio': data.calmar_ratio,
            'win_rate': data.win_rate,
            'avg_position_count': data.avg_position_count,
            'total_transactions': data.total_transactions,
        }
        return json.dumps(d, ensure_ascii=False, indent=2)

    def _annual_to_json(self, data: AnnualReportData) -> str:
        d = {
            'report_type': 'annual',
            'fund_code': self.fund_info.fund_code,
            'report_year': data.report_year,
            'annual_return': data.annual_return,
            'benchmark_return': data.benchmark_return,
            'excess_return': data.excess_return,
            'annual_volatility': data.annual_volatility,
            'sharpe_ratio': data.sharpe_ratio,
            'max_drawdown': data.max_drawdown,
            'total_aum_start': data.total_aum_start,
            'total_aum_end': data.total_aum_end,
            'compliance_events': data.compliance_events,
            'risk_breach_count': data.risk_breach_count,
        }
        return json.dumps(d, ensure_ascii=False, indent=2)

    @staticmethod
    def _format_month(ym: str) -> str:
        if len(ym) == 6:
            return f"{ym[:4]}年{ym[4:]}月"
        return ym


# ──────────────────────────────────────────────
# 2. Investor Disclosure
# ──────────────────────────────────────────────

class InvestorDisclosure:
    """
    投资者披露文件生成

    合规要求:
    - 净值披露 (月度)
    - 季度报告
    - 重大事项临时披露
    - 年度审计报告摘要
    """

    def __init__(self, fund_info: Optional[FundInfo] = None):
        self.fund_info = fund_info or FundInfo()

    def generate_nav_disclosure(self,
                                nav_history: pd.Series,
                                as_of_date: Optional[str] = None) -> str:
        """生成净值披露"""
        fi = self.fund_info
        if as_of_date is None:
            as_of_date = str(nav_history.index[-1])

        latest_nav = nav_history.iloc[-1]
        mtd_start = nav_history.loc[
            nav_history.index >= pd.Timestamp(as_of_date).replace(day=1)]
        mtd_return = (latest_nav / mtd_start.iloc[0] - 1) if len(mtd_start) > 0 else 0

        return f"""# {fi.fund_name} 净值公告

**公布日期**: {as_of_date}

| 项目 | 数值 |
|------|------|
| 单位净值 | {latest_nav:.4f} |
| 日期 | {as_of_date} |
| 月初以来收益 | {mtd_return:.2%} |

*净值已经托管人复核确认*
"""

    def generate_material_event_disclosure(self,
                                           event_type: str,
                                           event_date: str,
                                           description: str,
                                           impact: str) -> str:
        """生成重大事项临时披露"""
        return f"""# 重大事项临时公告

## {event_type}

**公告日期**: {event_date}
**基金名称**: {self.fund_info.fund_name}

### 事项描述
{description}

### 影响分析
{impact}

### 应对措施
（管理人将根据基金合同约定采取相应措施）

---

*本公告依据《私募投资基金监督管理暂行办法》及基金合同编制*
"""


# ──────────────────────────────────────────────
# 3. Compliance Checker
# ──────────────────────────────────────────────

@dataclass
class ComplianceCheckItem:
    """合规检查项"""
    category: str
    item: str
    requirement: str
    status: str  # PASS / FAIL / N/A
    detail: str = ""
    severity: str = "INFO"  # INFO / WARNING / CRITICAL


class ComplianceChecker:
    """
    合规自查工具

    检查维度:
    1. 投资限制
    2. 信息披露时效
    3. 风控指标
    4. 运营合规
    """

    # 私募法规核心限制
    INVESTMENT_LIMITS = {
        'single_stock_max': 0.10,  # 单票 ≤ 10% (一般私募)
        'single_stock_neutral': 0.05,  # 市场中性策略单票 ≤ 5%
        'total_derivatives': 1.0,  # 衍生品 ≤ 净资产
        'illiquid_assets': 0.20,  # 非流动性资产 ≤ 20%
        'leverage_max': 2.0,  # 杠杆 ≤ 200% (一般私募)
    }

    DISCLOSURE_DEADLINES = {
        'monthly_nav': 5,  # 月末后5个工作日
        'quarterly_report': 30,  # 季末后30个工作日
        'annual_report': 90,  # 年末后90个工作日
        'material_event': 2,  # 重大事项2个工作日
    }

    def run_full_check(self,
                       portfolio_weights: pd.Series,
                       gross_leverage: float,
                       net_exposure: float,
                       disclosure_status: Dict[str, str],
                       nav_last_update: Optional[str] = None) -> List[ComplianceCheckItem]:
        """
        全量合规检查

        Returns
        -------
        List[ComplianceCheckItem]
        """
        checks = []

        # ── 投资限制 ──
        max_weight = portfolio_weights.abs().max() if len(portfolio_weights) > 0 else 0
        checks.append(ComplianceCheckItem(
            category='投资限制',
            item='单票集中度',
            requirement=f'≤{self.INVESTMENT_LIMITS["single_stock_neutral"]:.0%}(市场中性)',
            status='PASS' if max_weight <= self.INVESTMENT_LIMITS['single_stock_neutral'] else 'FAIL',
            detail=f'最大权重: {max_weight:.2%}',
            severity='CRITICAL' if max_weight > self.INVESTMENT_LIMITS['single_stock_neutral'] else 'INFO'
        ))

        checks.append(ComplianceCheckItem(
            category='投资限制',
            item='总杠杆',
            requirement=f'≤{self.INVESTMENT_LIMITS["leverage_max"]:.0%}',
            status='PASS' if gross_leverage <= self.INVESTMENT_LIMITS['leverage_max'] else 'FAIL',
            detail=f'当前杠杆: {gross_leverage:.2f}',
            severity='CRITICAL' if gross_leverage > self.INVESTMENT_LIMITS['leverage_max'] else 'INFO'
        ))

        checks.append(ComplianceCheckItem(
            category='投资限制',
            item='净敞口',
            requirement='市场中性 ≤ 10%',
            status='PASS' if abs(net_exposure) <= 0.10 else 'FAIL',
            detail=f'当前净敞口: {net_exposure:.2%}',
            severity='WARNING' if abs(net_exposure) > 0.05 else 'INFO'
        ))

        # ── 信息披露 ──
        for disc_type, deadline in self.DISCLOSURE_DEADLINES.items():
            status = disclosure_status.get(disc_type, 'UNKNOWN')
            is_ok = status in ['SUBMITTED', 'APPROVED', 'N/A']
            checks.append(ComplianceCheckItem(
                category='信息披露',
                item=disc_type,
                requirement=f'≤{deadline}个工作日',
                status='PASS' if is_ok else 'FAIL',
                detail=f'状态: {status}',
                severity='WARNING' if not is_ok else 'INFO'
            ))

        # ── 运营合规 ──
        if nav_last_update:
            days_since = (datetime.now() - pd.Timestamp(nav_last_update)).days
            checks.append(ComplianceCheckItem(
                category='运营合规',
                item='净值更新',
                requirement='≤1个工作日',
                status='PASS' if days_since <= 1 else 'FAIL',
                detail=f'距上次更新: {days_since}天',
                severity='WARNING' if days_since > 1 else 'INFO'
            ))

        return checks

    def generate_compliance_report(self,
                                   checks: List[ComplianceCheckItem]) -> str:
        """生成合规自查报告"""
        lines = [
            f"{'='*60}",
            f"📋 合规自查报告 — {datetime.now().strftime('%Y-%m-%d')}",
            f"{'='*60}",
        ]

        # 按类别分组
        categories = {}
        for c in checks:
            categories.setdefault(c.category, []).append(c)

        for cat, items in categories.items():
            lines.append(f"\n## {cat}")
            for item in items:
                icon = '✅' if item.status == 'PASS' else '❌'
                lines.append(
                    f"  {icon} {item.item}: {item.status} "
                    f"({item.detail}) [要求: {item.requirement}]")

        # 统计
        total = len(checks)
        passed = sum(1 for c in checks if c.status == 'PASS')
        failed = sum(1 for c in checks if c.status == 'FAIL')
        critical = sum(1 for c in checks if c.severity == 'CRITICAL')

        lines.append(f"\n{'='*60}")
        lines.append(f"汇总: {passed}/{total} 通过, {failed} 不通过, {critical} 严重")
        lines.append("=" * 60)

        return "\n".join(lines)


# ──────────────────────────────────────────────
# 4. Audit Trail
# ──────────────────────────────────────────────

@dataclass
class AuditEntry:
    """审计日志条目"""
    timestamp: str
    action: str
    actor: str  # 操作人/系统
    category: str  # trade / risk / compliance / config
    details: str = ""
    before_state: str = ""
    after_state: str = ""


class AuditTrail:
    """
    审计追踪

    记录所有关键操作:
    - 交易决策
    - 风控事件
    - 合规操作
    - 系统配置变更
    """

    def __init__(self, log_dir: str = "logs/audit"):
        self.log_dir = log_dir
        self.entries: List[AuditEntry] = []
        os.makedirs(log_dir, exist_ok=True)

    def log(self,
            action: str,
            actor: str = "system",
            category: str = "trade",
            details: str = "",
            before_state: str = "",
            after_state: str = ""):
        """记录审计条目"""
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            action=action,
            actor=actor,
            category=category,
            details=details,
            before_state=before_state,
            after_state=after_state,
        )
        self.entries.append(entry)

        # 持久化
        log_file = os.path.join(
            self.log_dir,
            f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl")
        with open(log_file, 'a') as f:
            f.write(json.dumps({
                'timestamp': entry.timestamp,
                'action': entry.action,
                'actor': entry.actor,
                'category': entry.category,
                'details': entry.details,
            }, ensure_ascii=False) + '\n')

    def query(self,
              category: Optional[str] = None,
              since: Optional[str] = None,
              action: Optional[str] = None) -> List[AuditEntry]:
        """查询审计日志"""
        results = self.entries
        if category:
            results = [e for e in results if e.category == category]
        if since:
            results = [e for e in results if e.timestamp >= since]
        if action:
            results = [e for e in results if action in e.action]
        return results

    def export_audit_log(self,
                         output_path: str,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> str:
        """导出审计日志"""
        entries = self.entries
        if start_date:
            entries = [e for e in entries if e.timestamp >= start_date]
        if end_date:
            entries = [e for e in entries if e.timestamp <= end_date + 'T23:59:59']

        data = [{
            'timestamp': e.timestamp,
            'action': e.action,
            'actor': e.actor,
            'category': e.category,
            'details': e.details,
        } for e in entries]

        with open(output_path, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return output_path
