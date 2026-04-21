# invest/ 真实状态报告 · 2026-04-21

> 通读时间：约 1 小时 · 作者：Claude (fin 接管方)
> 授权：东丞 "全权接管 invest/" · 读不改原则
> 源头：`invest/docs/nous-investment-module.md` v7 是权威设计文档（本报告不与其冲突）
>
> **范围**：只描述现状、不排优先级、不改方案。让 5/15 前的决策有准确底图。

---

## 1. 硬事实

| 项 | 值 |
|----|----|
| 公司 | 中诚志远投资有限公司（北京） · AMAC P1067541 |
| AUM | 7 亿+ |
| 东丞 | AI 负责人，**5/15 正式入职** |
| 当前阶段 | 4 周入职准备（4/15-5/12）— Week 1 行业认知已完成 |
| 5/15-5/22 | 出 demo（你说"出框架"） |
| ~6/15 | 出"完整产品" |
| 代码所在 | `invest/` （449MB，已随 nous private 受保护） |
| 沟通渠道 | 微信（团队日常工具） |

---

## 2. v7 设计文档（`invest/docs/nous-investment-module.md`）核心锚点

**产品一句话**："决策操作系统" / 决策副脑 / 备忘录助手。对外**绝不**叫 AI 系统。

**四大能力**：
1. 结构化决策卡（12 维度 checklist）
2. 魔鬼代言人（可选的反驳 Agent，记录不打扰）
3. 多视角陪审团（价值/动量/事件催化三独立打分）
4. AI4Science 因子流水线（RD-Agent → Qlib → review-gate）

**5 条 Swarm 辩论纪律**：PM 先独立判断 AI 后出手；魔鬼代言人可选非门槛；指标后台静默不排名；绝不叫 AI 系统；拉力 > 推力。

**董事长 OKR（v7 §9.1）**：
- O1 让 LP 看到前沿科技（3 月内演示一次）
- O2 降低决策随机性（回撤 24h 给出逻辑）
- O3 1 人支撑 5→10 亿 AUM
- O4 合规可审计（1h 内给任意时间点档案）

---

## 3. 代码模块实况

### 3.1 能跑的（✅）

| 模块 | 文件 | 状态 |
|------|------|------|
| 数据层 | `update_tushare*.py`、`download_*.py`、`convert_to_qlib*.py` | ✅ 1800 股全量数据 |
| Daily Loop | `daily_loop.py` + `run_daily.sh` + Discord/飞书 webhook | ✅ Cron ready |
| 简化模型 | `run_round2_simple.py`（CSI300 + 8 因子 LightGBM） | ✅ **IC 0.0212 / ICIR 0.17 / 年化 IR 2.70**（2025-04 ~ 2026-04） |
| Alpha158 模型 | Qlib Alpha158 + LightGBM on 1800 股 | ✅ **IC 0.0151 / ICIR 0.11 / 年化 IR 1.69**（2025-07 ~ 2026-04，341k 预测） |
| 全量 Pipeline | `run_full_pipeline.py` | ✅ 跑过一次（2026-04-16 日期），生成 HTML 周报 |
| 因子 crowding 研报 | `scripts/factor_crowding_analysis.py` + `reports/factor_crowding_report_20260416.md` | ✅ 数字明确（EP/BP/Mom/Quality 等 IC，Alpha158 相关性矩阵） |
| 市场环境研报 | `reports/A股市场环境分析_2026年4月.md` + `scripts/market_env_analysis.py` | ✅ 研报产出齐 |

### 3.2 代码完整但**没串进 daily loop**（⚠️）

| 模块 | 文件 | 实况 |
|------|------|------|
| 多模型集成 | `skills/portfolio_construction.py` | 完整类 `MultiModelEnsemble` LGB+XGB+Stacking + `IndustryNeutralizer` + `MarketCapLayering` + `RiskParityAllocator` + `PortfolioConstructor` | **daily_loop 未调用，走的是 round2_simple 旧路径** |
| 非同质化因子 | `features/non_homogeneous_factors.py` | 15 因子设计（5 高频 + 5 中频 + 5 低频），但未进因子池跑 IC | **与 v7 能力 4 对口，代码 ~50% 的骨架** |
| 机构级 Pipeline | `institutional/pipeline.py` + market_neutral / risk / compliance 子模块 | 完整 StockUniverse → AlphaModel → LongShortConstructor → RiskManager → ComplianceChecker → AMACReportGenerator → AuditTrail | **无 daily driver 调用入口，组件 ready** |
| Qlib 回测 | `backtest/qlib_backtest.py`（TopkDropoutStrategy 周调仓）+ `backtest/daily_monitor.py` (604 行) + capacity/weekly_metrics/report_template | **独立组件，未 wired 成一键 end-to-end** |

### 3.3 v7 设计里有、代码里**零覆盖**（❌）

| v7 能力 | 现状 |
|---------|------|
| 结构化决策卡（能力 1） | ❌ 0%，连 12 维度 schema JSON 都没有 |
| 魔鬼代言人（能力 2） | ❌ 0%，ARIS 骨架存在于 nous 主线但未拉入 fin |
| 多视角陪审团（能力 3） | ❌ 0%（但多模型 ensemble 的代码骨架在 `portfolio_construction.py`，可作为引子） |
| AI4Science 因子流水线（能力 4） | ⚠️ 20%，有非同质化因子设计 + crowding 研报，但 RD-Agent self-loop 未接入 |
| 微信推送（v7 §3.2） | ⚠️ 50%，Discord/飞书 webhook 就位，企微机器人未接 |

---

## 4. 当前指标（实测）

### 模型表现

| 配置 | 训练期 | 测试期 | IC | ICIR | 年化 IR | IC>0 比例 | 样本量 |
|------|-------|-------|-----|------|---------|-----------|---------|
| CSI300 + 8 因子 LGB（round2_simple） | ~2024-06 | 2025-04 ~ 2026-04 (247 日) | **0.0212** | **0.170** | **2.70** | 57.5% | 73,855 |
| 1800 股 + Alpha158 + LGB | ~2025-03 | 2025-07 ~ 2026-04 (190 日) | 0.0151 | 0.107 | 1.69 | 53.7% | 341,487 |

**读法**（不下结论，只给口径）：
- 小而精（CSI300 8 因子）IC 更高，信号集中
- 大而全（1800 Alpha158）IC 低但样本大，年化 IR 也能到 1.69
- v7 SPEC 目标：周超额 > 0.5% / 周夏普 > 1.5 / MaxDD < 15%  — **未实测，当前 loop 只算 IC/ICIR 不算组合回报**

### 因子 crowding 研报（2026-04-16）的量化结论摘录

- 主流因子（EP/BP/Mom6M/Quality/Rev5D/Rev20D/Vol20D）绝对 IC 均值 0.0334（正常）
- Alpha158 内部 14 因子平均 |相关| = 0.35；>0.6 的因子对 16 组 → **Alpha158 同质化严重已量化证实**
- 机构方向一致性 0.63（中等同质化）
- CSI500 HHI 0.00284（分散）

---

## 5. 明显 gap（事实层面）

1. **daily_loop 跑的模型 vs 实际能跑的最好模型不一致** — round2_simple 是 2025-04 的旧路径，portfolio_construction 的 LGB+XGB ensemble 已经写完但没串上
2. **institutional/pipeline.py 没有 daily driver** — 里面的 StockUniverse/RiskManager/AuditTrail/AMACReport 都在"待调用"状态
3. **回测组件齐全但未 end-to-end wired** — `run_backtest.py` 存在，具体耦合深度要再读
4. **v7 四能力代码覆盖率极低** — 决策卡/魔鬼代言人/陪审团是 0；因子流水线 20%
5. **signals/ 快照稀疏** — 只有 2 个 metrics 文件（4/8 和 4/13），说明生产 cron 启动不久 / 本地未持续运行
6. **nous 主线的 gate / semantic_gate / KG / proof_trace 未对接** — v7 设计里提到 review-gate + ARIS 但 fin 代码层无 import
7. **没有 weekly 超额计算的落盘文件** — SPEC v0.3 目标是周超额 0.5%，但 signals/reports 里没看到对 benchmark 的超额时序

---

## 6. nous 主线里**可复用**的组件（供决策参考，不代表要用）

| nous 主线 | 可能对接 v7 能力 |
|-----------|---------------|
| `src/nous/gate.py` (gate()) | 决策卡字段完整性 gate、因子准入 gate |
| `src/nous/semantic_gate.py` | 魔鬼代言人的 LLM 推理（已有 LLMProvider Protocol 可换 qwen-turbo） |
| `src/nous/db.py` (NousDB/Cozo) | KG 存决策历史、标的 Markov blanket、因子池 |
| `src/nous/decision_log.py` + `proof_trace.py` | 合规可审计（董事长 O4） |
| `ontology/constraints/T*.yaml` + `hot_reload.py` | 合规规则热加载 |
| `dashboard/api.py` (FastAPI + SSE) | 给 PM 看决策流、给 CIO 看团队聚合 |

---

## 7. 入职准备节奏（来自 `invest/docs/private-equity-onboarding.md`）

- **Week 1 (4/15-4/21)** 行业全景 + 监管 ✅ 行业认知笔记已完成
- **Week 2 (4/22-4/28)** 投研流程 + AI 切入点 — 待做
- **Week 3 (4/29-5/5)** 技术栈 + 实施路径 — 待做
- **Week 4 (5/6-5/12)** 入职准备 + 30/60/90 天计划 — 待做
- **5/15 入职**

---

## 8. 我没读全的（诚实）

- `backtest/` 6 个文件里只看了 qlib_backtest.py 头 80 行 + daily_monitor.py 头 60 行
- `institutional/` 的 market_neutral.py / risk.py / compliance.py 底层实现（只看了 pipeline.py 聚合）
- `features/alternative_data.py` + `features/feature_engineering.py` 未读
- `scripts/industry_rotation.py` + `scripts/market_env_analysis.py` 未读
- `invest/docs/nous-user-stories.md`、`invest/docs/nous-landing-prep.md`、`invest/a-share-policy-tracker-2026Q1.md` 未读
- `reports/` 的中文 MD 只扫了 factor_crowding

按需要可再深入。

---

## 9. 本报告**不做**的事（避免越界）

- ❌ 不给出"第一个该做什么"
- ❌ 不给 5/15 demo 方案建议
- ❌ 不给 6/15 产品范围建议
- ❌ 不评价代码质量 / 不重构
- ❌ 不下"IC 0.0212 好不好"之类的判断

这些由你看完这份底图后再决定方向。
