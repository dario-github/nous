"""
Nous Invest - 回测报告模板
Module 5-7: Backtest Report Template

完整的回测报告输出，包括:
- 收益分析
- 风险评估
- 周超额指标
- 容量分析
- 建议
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json


@dataclass
class BacktestReport:
    """回测报告数据结构"""
    
    # 基本信息
    report_date: str
    strategy_name: str
    backtest_period: str
    
    # 收益指标
    total_return: float = 0.0
    annual_return: float = 0.0
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    
    # 风险指标
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    annual_volatility: float = 0.0
    
    # 风险调整收益
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    information_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    # 周超额指标
    weekly_alpha_mean: float = 0.0
    weekly_alpha_std: float = 0.0
    weekly_alpha_sharpe: float = 0.0
    weekly_win_rate: float = 0.0
    weekly_profit_loss_ratio: float = 0.0
    
    # 交易统计
    total_trades: int = 0
    turnover_rate: float = 0.0
    avg_holding_days: float = 0.0
    
    # 容量分析
    safe_capacity: float = 0.0
    max_capacity: float = 0.0
    
    # 信号质量
    signal_correlation_alpha158: float = 0.0
    signal_uniqueness_score: float = 0.0
    
    # 年份表现
    yearly_performance: Dict[int, Dict] = None
    
    # 建议
    recommendations: List[str] = None


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, template_dir: Optional[str] = None):
        self.template_dir = template_dir
    
    def generate_report(
        self,
        backtest_results: Dict,
        weekly_metrics: Any,
        capacity_analysis: Any,
        strategy_name: str = "Nous Strategy"
    ) -> BacktestReport:
        """
        生成完整回测报告
        
        Parameters
        ----------
        backtest_results : Dict
            Qlib回测结果
        weekly_metrics : WeeklyMetrics
            周超额指标
        capacity_analysis : PortfolioCapacity
            容量分析
        strategy_name : str
            策略名称
            
        Returns
        -------
        BacktestReport
            完整报告
        """
        report = BacktestReport(
            report_date=datetime.now().strftime("%Y-%m-%d"),
            strategy_name=strategy_name,
            backtest_period="2022-2025"  # 默认
        )
        
        # 从回测结果提取
        if "indicator" in backtest_results:
            ind = backtest_results["indicator"]
            if isinstance(ind, dict):
                report.annual_return = ind.get("annualized_return", 0)
                report.annual_volatility = ind.get("annualized_volatility", 0)
                report.max_drawdown = ind.get("max_drawdown", 0)
                report.sharpe_ratio = ind.get("sharpe_ratio", 0)
                report.information_ratio = ind.get("information_ratio", 0)
        
        # 从周超额指标提取
        if hasattr(weekly_metrics, "weekly_alpha_mean"):
            report.weekly_alpha_mean = weekly_metrics.weekly_alpha_mean
            report.weekly_alpha_std = weekly_metrics.weekly_alpha_std
            report.weekly_alpha_sharpe = weekly_metrics.weekly_alpha_sharpe
            report.weekly_win_rate = weekly_metrics.win_rate
            report.weekly_profit_loss_ratio = weekly_metrics.profit_loss_ratio
            report.max_drawdown_duration = weekly_metrics.max_drawdown_duration
        
        # 从容量分析提取
        if hasattr(capacity_analysis, "total_safe_capacity"):
            report.safe_capacity = capacity_analysis.total_safe_capacity
            report.max_capacity = capacity_analysis.total_max_capacity
        
        # 生成建议
        report.recommendations = self._generate_recommendations(report)
        
        return report
    
    def _generate_recommendations(self, report: BacktestReport) -> List[str]:
        """生成策略建议"""
        recommendations = []
        
        # 周超额评估
        if report.weekly_alpha_sharpe < 1.0:
            recommendations.append("⚠️ 周超额夏普低于1.0，建议优化信号质量或降低换手")
        elif report.weekly_alpha_sharpe > 1.5:
            recommendations.append("✅ 周超额夏普表现优秀 (>1.5)，可维持当前策略")
        
        # 回撤评估
        if report.max_drawdown < -0.15:
            recommendations.append("🚨 最大回撤超过15%，建议加强风控或降低仓位")
        elif report.max_drawdown < -0.10:
            recommendations.append("⚠️ 最大回撤在10-15%区间，注意监控")
        
        # 容量评估
        if report.safe_capacity < 5_000_000:
            recommendations.append("⚠️ 组合安全容量低于500万，建议减少单票持仓或选择更流动性好的股票")
        
        # 胜率评估
        if report.weekly_win_rate < 0.50:
            recommendations.append("⚠️ 周胜率低于50%，建议检查信号方向是否正确")
        
        # 默认建议
        if not recommendations:
            recommendations.append("✅ 当前策略表现正常，建议维持现有参数")
        
        return recommendations
    
    def format_full_report(self, report: BacktestReport) -> str:
        """
        格式化完整报告为文本
        
        Returns
        -------
        str
            Markdown格式报告
        """
        lines = []
        
        # 标题
        lines.append("# Nous Invest 回测报告")
        lines.append(f"**策略名称**: {report.strategy_name}")
        lines.append(f"**报告日期**: {report.report_date}")
        lines.append(f"**回测区间**: {report.backtest_period}")
        lines.append("")
        
        # 核心指标摘要
        lines.append("## 📊 核心指标摘要")
        lines.append("")
        lines.append("| 指标 | 数值 | 目标 | 状态 |")
        lines.append("|------|------|------|------|")
        
        # 周超额
        status = "✅" if report.weekly_alpha_mean > 0.005 else "❌"
        lines.append(f"| 平均周超额 | {report.weekly_alpha_mean*100:+.4f}% | >0.5% | {status} |")
        
        # 夏普
        status = "✅" if report.weekly_alpha_sharpe > 1.5 else ("⚠️" if report.weekly_alpha_sharpe > 1.0 else "❌")
        lines.append(f"| 周超额夏普 | {report.weekly_alpha_sharpe:.2f} | >1.5 | {status} |")
        
        # 回撤
        status = "✅" if report.max_drawdown > -0.15 else "❌"
        lines.append(f"| 最大回撤 | {report.max_drawdown*100:.2f}% | <15% | {status} |")
        
        # 胜率
        status = "✅" if report.weekly_win_rate > 0.50 else "❌"
        lines.append(f"| 周胜率 | {report.weekly_win_rate*100:.1f}% | >50% | {status} |")
        
        lines.append("")
        
        # 收益分析
        lines.append("## 💰 收益分析")
        lines.append("")
        lines.append(f"- **年化收益率**: {report.annual_return*100:.2f}%")
        lines.append(f"- **基准收益**: {report.benchmark_return*100:.2f}%")
        lines.append(f"- **超额收益**: {report.excess_return*100:.2f}%")
        lines.append(f"- **夏普比率**: {report.sharpe_ratio:.2f}")
        lines.append(f"- **信息比率**: {report.information_ratio:.2f}")
        lines.append("")
        
        # 风险分析
        lines.append("## ⚠️ 风险分析")
        lines.append("")
        lines.append(f"- **最大回撤**: {report.max_drawdown*100:.2f}%")
        lines.append(f"- **回撤持续**: {report.max_drawdown_duration} 天")
        lines.append(f"- **年化波动**: {report.annual_volatility*100:.2f}%")
        lines.append(f"- **Calmar比率**: {report.calmar_ratio:.2f}")
        lines.append("")
        
        # 周超额详情
        lines.append("## 📈 周超额分析")
        lines.append("")
        lines.append(f"- **平均周超额**: {report.weekly_alpha_mean*100:+.4f}%")
        lines.append(f"- **周超额波动**: {report.weekly_alpha_std*100:.4f}%")
        lines.append(f"- **周超额夏普**: {report.weekly_alpha_sharpe:.4f}")
        lines.append(f"- **周胜率**: {report.weekly_win_rate*100:.1f}%")
        lines.append(f"- **盈亏比**: {report.weekly_profit_loss_ratio:.2f}")
        lines.append("")
        
        # 容量分析
        lines.append("## 💧 容量分析")
        lines.append("")
        lines.append(f"- **安全容量**: ¥{report.safe_capacity:,.0f}")
        lines.append(f"- **最大容量**: ¥{report.max_capacity:,.0f}")
        lines.append("")
        
        # 建议
        lines.append("## 💡 策略建议")
        lines.append("")
        for rec in (report.recommendations or []):
            lines.append(f"- {rec}")
        lines.append("")
        
        lines.append("---")
        lines.append("*Report generated by Nous Invest Backtest System*")
        
        return "\n".join(lines)
    
    def save_report(
        self,
        report: BacktestReport,
        filepath: str,
        format: str = "markdown"
    ) -> str:
        """
        保存报告到文件
        
        Parameters
        ----------
        report : BacktestReport
        filepath : str
        format : str
            'markdown', 'json', 'csv'
            
        Returns
        -------
        str
            保存的文件路径
        """
        if format == "markdown":
            content = self.format_full_report(report)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
        
        elif format == "json":
            data = asdict(report)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        elif format == "csv":
            # 简化为单行CSV
            data = asdict(report)
            df = pd.DataFrame([{
                k: v for k, v in data.items() 
                if not isinstance(v, (dict, list))
            }])
            df.to_csv(filepath, index=False)
        
        return filepath


def generate_full_backtest_report(
    backtest_results: Dict,
    weekly_metrics: Any,
    capacity_analysis: Any,
    output_path: str = "./reports",
    strategy_name: str = "Nous Strategy"
) -> str:
    """
    一站式生成并保存完整回测报告
    
    Returns
    -------
    str
        报告文件路径
    """
    import os
    os.makedirs(output_path, exist_ok=True)
    
    generator = ReportGenerator()
    
    # 生成报告
    report = generator.generate_report(
        backtest_results,
        weekly_metrics,
        capacity_analysis,
        strategy_name
    )
    
    # 保存为Markdown
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = os.path.join(output_path, f"backtest_report_{timestamp}.md")
    generator.save_report(report, md_path, "markdown")
    
    # 同时保存JSON
    json_path = os.path.join(output_path, f"backtest_report_{timestamp}.json")
    generator.save_report(report, json_path, "json")
    
    print(f"[Report] Markdown saved: {md_path}")
    print(f"[Report] JSON saved: {json_path}")
    
    return md_path


if __name__ == "__main__":
    print("[ReportGenerator] Module loaded successfully")
