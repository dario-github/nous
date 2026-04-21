"""
Nous Invest — Institutional Grade System
7亿规模私募机构级系统架构

目录结构:
├── __init__.py           # 包入口
├── config.py             # 全局配置 (基金/投资/风控/合规/交易/对冲)
├── pipeline.py           # 日常运行管道 (整合所有模块)
├── market_neutral/       # 市场中性框架
│   ├── __init__.py       # StockUniverse / AlphaModel / LongShortConstructor / BetaHedge / ExposureManager
├── risk/                 # 风控模块
│   ├── __init__.py       # VaRCalculator / DrawdownMonitor / ExposureLimiter / RiskBudget / StopLossManager / RiskManager
├── compliance/           # 合规披露
│   ├── __init__.py       # AMACReportGenerator / InvestorDisclosure / ComplianceChecker / AuditTrail
└── templates/            # 报告模板 (预留)

核心能力:
1. 容量约束选股: 日均成交额>5亿, 市值200-2000亿
2. Long-Short 市场中性: 多空1:1, beta中性, 行业/因子暴露控制
3. 多级风控: VaR(历史/参数/MC) + 回撤监控 + 暴露限制 + 止损
4. AMAC合规: 月报/季报/年报模板 + 投资者披露 + 合规自查 + 审计追踪

快速开始:
    from institutional import InstitutionalPipeline
    pipeline = InstitutionalPipeline()
    result = pipeline.daily_run(stock_data, ml_scores)

依赖:
    - pandas, numpy, scipy (科学计算)
    - features/ (特征工程, 可选)
    - skills/portfolio_construction.py (权重分配, 已内化)
