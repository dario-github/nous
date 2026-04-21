# AI 投研开源项目景观扫描 · 2026-04

> 快照日期：2026-04-21 · 下次复盘：2026-07（季度）
> 目的：识别上游 SOTA 组件，决定集成/观望/忽略；**不是要全部集成**。

---

## 0. TL;DR（给自己看的）

**主观（fundamental / LLM 多 agent）赛道**
- 决定性胜者：`virattt/ai-hedge-fund`（56.7k★）与 `TauricResearch/TradingAgents`（52.1k★）
- 二者都用 LLM 多 agent + 辩论/投票，架构高度相似；前者胜在投资家角色数（19 个原型），
  后者胜在 orchestration（LangGraph）清晰、Python API 规整。
- **nous 的增量空间**：二者都有 Risk Manager / Portfolio Manager 作为"把关层"，
  但都是 LLM prompt 兜底，没有声明式规则 + KG 可审计证据链。→ 高价值集成点。

**CTA / 量化（RL + 因子挖掘）赛道**
- 基础设施：`microsoft/qlib`（41.1k★，含 `RD-Agent` 12.6k★ 做因子自动挖掘）
- RL：`AI4Finance-Foundation/FinRL`（14.8k★，5 个 DRL 算法，下一代 FinRL-X 模块化）
- **nous 的增量空间**：RD-Agent 自迭代提出新因子时**缺验证门**，正是 gate() + constraint
  YAML 的主场 → 因子接受前的自动审计 hook。

**时序基础模型赛道**（零样本预测组件）
- Chronos (Amazon) / TimesFM (Google) / Moirai (Salesforce) / Lag-Llama / TimeGPT (Nixtla)
- **nous 不做模型**，但在 ensemble 时可以把"模型间分歧 > 阈值"作为 gate warn 触发。

**数据层**
- `OpenBB` (66.2k★, AGPLv3) — 基础设施级数据平台，已有 MCP server & agent 生态
- `FinGPT` (19.7k★) — sentiment / NER / RAG 的微调 LoRA 模型

---

## 1. 项目矩阵（Tier 1：必须知道）

| 项目 | Stars | License | 类型 | Orchestration | 入口 API | 备注 |
|------|-------|---------|------|---------------|----------|------|
| [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) | 56.7k | MIT | 多 agent LLM | LangChain-ish | `src/main.py` CLI + `src/backtester.py` | 19 个 agent（13 投资家 + 6 分析类）；Portfolio Manager 做最终决策；回测就位 |
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | 52.1k | Apache-2.0 | 多 agent LLM | **LangGraph** | `TradingAgentsGraph.propagate(ticker, date)` | 6+ agent + 多轮辩论；多 LLM provider；Risk Team + PM 做 approve/reject |
| [microsoft/qlib](https://github.com/microsoft/qlib) | 41.1k | MIT | 量化平台 | workflow yaml | `qrun` + `examples/workflow_by_code.ipynb` | 监督/RL/市场动态三范式；内置回测 IC/累计收益/DD |
| [microsoft/RD-Agent](https://github.com/microsoft/RD-Agent) | 12.6k | MIT | 自动化 R&D | self-loop | `rdagent fin_quant` CLI + PyPI | 自动因子挖掘 + 模型演化；有 execution trace，**无声明式约束门** |
| [AI4Finance/FinRL](https://github.com/AI4Finance-Foundation/FinRL) | 14.8k | MIT | DRL 交易 | SB3 | `train.py / test.py / trade.py` | A2C/DDPG/PPO/SAC/TD3；FinRL-X 下一代模块化 |
| [AI4Finance/FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | 19.7k | MIT | 金融 LLM 微调 | HF | LoRA adapters | sentiment/NER/forecaster；Forecaster 模块可作为独立信号源 |
| [AI4Finance/FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | 6.7k | Apache-2.0 | 金融 agent 平台 | **AutoGen** | `finrobot.agents.workflow` | Perception/Brain/Action 四层；valuation/DCF/research report |
| [OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB) | 66.2k | AGPLv3 | 数据平台 | — | `from openbb import obb` | 数据底座；**AGPL 要注意**；有 MCP server |

## 2. Tier 2：值得纳入 watchlist（暂不集成）

| 项目 | Stars(估) | 意义 |
|------|-----------|------|
| [pipiku915/FinMem-LLM-StockTrading](https://github.com/pipiku915/FinMem-LLM-StockTrading) | 中 | Layered memory + character，ICLR LLM Agents workshop 原型；思路借鉴 |
| [Open-Finance-Lab/AgenticTrading](https://github.com/Open-Finance-Lab/AgenticTrading) | 小 | FinAI Contest 2025 的 baseline stack |
| [amazon-science/chronos-forecasting](https://github.com/amazon-science/chronos-forecasting) | 高 | 零样本价格/波动率预测；作为 ensemble 成员 |
| [google-research/timesfm](https://github.com/google-research/timesfm) | 高 | Decoder-only 基础模型，100B 数据点 |
| [SalesforceAIResearch/uni2ts (Moirai)](https://github.com/SalesforceAIResearch/uni2ts) | 中 | Masked encoder，任意频率多变量 |
| [time-series-foundation-models/lag-llama](https://github.com/time-series-foundation-models/lag-llama) | 中 | 首个开源概率预测 decoder-only |
| [Nixtla/nixtla (TimeGPT)](https://github.com/Nixtla/nixtla) | 高 | 生产级零样本 + 异常检测 |
| [edtechre/pybroker](https://github.com/edtechre/pybroker) | 中 | ML 驱动策略回测，纯 Python |
| [LeonardoBerti00/DeepMarket](https://github.com/LeonardoBerti00/DeepMarket) | 小 | Diffusion LOB 模拟；压测/对抗数据用 |
| [NoFxAiOS/nofx](https://github.com/NoFxAiOS/nofx) | 11.2k | "3 次错就停"的安全模式 — 自动止损哲学可借 |

## 3. 基准 & 评测（给自省用）

- **AgenticAI-Finance benchmark** (aimultiple, 2025)：FinGPT 79% > FinRobot 74% > FinRL 53%
- **FinAI Contest 2025** (Open-Finance-Lab)：Task 3 单股交易的正式 leaderboard
- **FINCON** (NeurIPS 2024)：多 agent 合成决策对比组
- **ACM AI-in-Finance 2024**：LLM Agents for Investment Management 的系统综述

---

## 4. nous 对上游的增量价值（为什么不做 fork）

nous 已有（见 `src/nous/gate.py:253` 的 `gate()` 接口）：

1. **声明式 YAML 约束**（`ontology/constraints/T*.yaml`）可热加载
2. **KG 上下文**（Cozo embedded，`_build_kg_context` at `gate.py:343`）
3. **Semantic gate**（LLM 兜底，可换 provider，`semantic_gate.py:78`）
4. **Verifier 层**（post-gate 审计，`gate.py:421`）
5. **Proof trace + decision log**（JSONL at `logs/gate_events.jsonl`）

上游的**共同缺口**：

| 缺口 | 上游现状 | nous 补什么 |
|------|---------|------------|
| Risk / PM 层是 LLM prompt | ai-hedge-fund / TradingAgents | 声明式规则 + KG 事实 + 可审计证据链 |
| 因子/策略演化无验证门 | RD-Agent / AlphaGen | 提议→gate→接受 的 propose-confirm 回路 |
| 决策日志非结构化 | 全部 | 统一 DecisionLog schema，跨 agent 可审计 |
| 无 constraint 热更新 | 全部 | watchfiles 热加载（`hot_reload.py`） |

**结论**：nous 是"**上游 agent 管道里的 policy 守门员 + 审计员**"。
不重复投研推理，只做**"这一步能不能做、证据足不足、是否越界"**的裁判。

---

## 5. 集成优先级（T1 / T2 / 观望）

### T1（本季度做，高 ROI）

**T1-A：TradingAgents × nous 守门员（主观赛道）**
- 理由：LangGraph orchestration 最清晰，Apache-2.0 友好，Portfolio Manager 节点是天然 hook
- 做法：把 PM 的 approve/reject 前置一次 `gate(trade_proposal)` 调用
- 证据：`tradingagents/graph/trading_graph.py` 的 propagate 链末端注入
- 成本：一个 YAML rules 文件 + 一个 adapter 函数，<1 天

**T1-B：RD-Agent × nous propose-confirm（CTA 赛道）**
- 理由：RD-Agent 自迭代产生因子 + 模型；当前无准入 gate
- 做法：rdagent 的 factor proposal → 拦截 → `gate(factor_accept_action, context={factor_formula, backtest_stats})` → 通过才入库
- 成本：YAML（过拟合阈值、IR 下限、换手率上限）+ adapter，<2 天
- 关键收益：**把 propose-confirm 从 prompt-level 提升到规则+KG level**，GPT-5.4 批评"KG 是舞台布景"在这里直接反驳——因为因子之间的相关性、和已持仓因子的冲突，KG 是最自然的存储

### T2（下季度再评）

- **FinRL × nous env 层合规**：在 RL env step() 里插 gate，把 "action_size > risk_budget" 变成 hard block（而非 reward 惩罚）
- **OpenBB MCP × nous KG seed**：OpenBB 查到的基本面 → 喂 KG 做初始化；AGPL 许可需讨论
- **FinGPT-Forecaster 作为 sentiment feed**：把其输出作为 fact 注入 gate context

### 观望（暂不动）

- `virattt/ai-hedge-fund`：star 最多但 19 个投资家 prompt 过强人设，要么全 fork 要么整块包住；先看 TradingAgents POC 结果
- 时序基础模型 Chronos / TimesFM / TimeGPT：上游已成熟，纳入仅在需要 ensemble 分歧检测时
- FinRobot：AutoGen 路线与我们 LangGraph 偏好略冲突，功能与 TradingAgents 重合

---

## 6. "at least useful" 两个最小 POC

### POC-1：TradingAgents 前置 nous 守门员
- **输入**：TradingAgents 对 NVDA 2026-01-15 的 propagate 结果（含 PM 输出）
- **nous 守门**：一条 YAML 规则——"如果 sentiment_score < -0.3 且 news_analyst 最近 7 天出现'regulatory' keyword，downgrade approve → confirm"
- **成功判据**：10 个 ticker × 30 天窗口回测，看 downgrade 触发次数是否命中真实负面事件（人工 sanity check 5 个样本即可）
- **不做的事**：不追求超额收益，只看"把关有没有意义"

### POC-2：RD-Agent 因子准入 gate
- **输入**：rdagent fin_quant 跑 1 轮产出的 10 个新因子
- **nous 守门**：YAML——
  - IR < 0.3 → block
  - 与已有因子相关性 > 0.85 → block（KG 查）
  - 换手率 > 200% → warn
- **成功判据**：在一个 holdout 期，gate 通过的因子组合 IR ≥ gate 拒绝的因子组合 IR（排除过拟合因子）
- **不做的事**：不训练模型，不做 alpha mining 本身，只做"准入"

---

## 7. 差距与风险（诚实）

- **LLM 成本**：qwen-turbo 已在 nous 主线用于 semantic gate；金融 POC 建议复用
- **数据**：AGPLv3 的 OpenBB 若集成需明确许可边界；Tier 1 POC 可先用 yfinance / Alpha Vantage 免费层
- **评测**：AgenticAI-Finance benchmark 需要 reproduction；暂以"TradingAgents baseline + nous 守门"vs"TradingAgents 原版"做 A/B
- **人设塞进 system prompt vs. 声明式规则**：ai-hedge-fund 的 19 个投资家 prompt 注入 LLM 的知识太"软"；
  我们不赢这个，我们只赢"最终这笔能不能下"的**硬审计**

---

## 8. 自省 checklist（每月）

- [ ] sota-tracker.yaml 里是否有 major version bump？
- [ ] 有没有新项目 >5k★ 且与我们方向重叠但我们没列入？
- [ ] 上一轮 POC 结论是不是还成立，还是新版本已经覆盖？
- [ ] 我们是不是开始**自研**了？如果是，停下来找上游
- [ ] AgenticAI-Finance 榜单有没有更新，我们的相对位置？

---

## 附录 A：主要引用

- TradingAgents v0.2.3（2026-Q1）: multi-provider、GPT-5.4 家族、backtesting date fidelity
- FinRL-X paper arXiv:2603.21330（"AI-Native Modular Infrastructure for Quantitative Trading"）
- FinMem arXiv:2311.13743（ICLR LLM Agents Workshop 2024）
- aimultiple AgenticAI-Finance benchmark 2025
