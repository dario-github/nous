# AI 投研开源项目景观扫描 · 2026-04

> 快照日期：2026-04-21 · 下次复盘：2026-07（季度）
> 目的：识别上游 SOTA 组件，决定集成/观望/忽略；**不是要全部集成**。
>
> ## 📌 Revision 2026-04-21（下午，东丞补上下文后）
>
> 本文件**初版**写在不知道以下事实的前提下：
> 1. 已有 9 人 A 股私募团队的真实需求（见 `product-context.md`）
> 2. Route A（Qlib + RD-Agent + ARIS）已选定
> 3. `invest/` 125 files / 449MB 已在东丞本地 fin 分支就位
> 4. 四大产品能力已定义（决策卡/魔鬼代言人/陪审团/因子流水线）
>
> 受影响的结论：
> - **POC-1（TradingAgents × nous 守门员）降级为 watching** — 与 Route A 冲突
> - **POC-2（RD-Agent × nous propose-confirm）保留并升级为 P0** — 对应能力 4
> - **新增 POC-3/4/5**：对接能力 1/2/3（见 `integration-hooks.md` Hook-5/6/7）
> - ai-hedge-fund persona prompt 路线与红线"不改变 PM 研究风格"冲突 → 保持 watching
>
> 下面矩阵内容仍然有效，解读时须套 Route A + 四能力 + 红线这三层滤镜。

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

> Revision 2026-04-21：T1-A 已降级至观望（与 Route A + 红线冲突）。
> 原 T1-B 升级为 P0，**并新增三个与四大产品能力对齐的 POC**。

**T1-A：TradingAgents × nous 守门员** — ~~原计划~~ **→ 降级 watching**
- 冲突点：1) Route B 已被拒；2) persona 驱动的多 agent 模式，会"改变 PM 的研究风格"（违反红线 3）
- 还在 `sota-tracker.yaml` 里盯着，等他们出声明式 DSL 就重评

**T1-B → P0：RD-Agent × nous review-gate**（= 产品能力 4 · AI4Science 因子流水线）
- 理由：RD-Agent 自迭代产生因子 + 模型；当前无准入 gate
- 做法：rdagent 的 factor proposal → 拦截 → `gate(factor_accept_action, context={factor_formula, backtest_stats})` → 通过才入库
- 成本：YAML（过拟合阈值、IR 下限、换手率上限）+ adapter，<2 天
- 关键收益：**把 propose-confirm 从 prompt-level 提升到规则+KG level**；因子间相关性、与已持仓因子冲突，KG 是最自然存储
- Hook：见 `integration-hooks.md` Hook-2

**T1-C → P0：结构化决策卡 gate**（= 产品能力 1）
- 对接 `invest/` 的 reports/ + features/ 输出，把 12 维度 checklist 用 YAML 表达
- gate 校验字段完整性（客观数据已填 / 主观判断已填），阻止"空壳卡片"提交
- KG 把历史相似 case 作为上下文喂给 PM（不是 LLM，是检索）
- Hook：见 `integration-hooks.md` Hook-5

**T1-D → P1：魔鬼代言人**（= 产品能力 2）
- PM 提交决策卡后 spawn 一个反驳 agent；反驳意见**记录不弹窗**
- 技术骨架：ARIS 风格的反思推理 + nous semantic_gate 作为执行器 + proof_trace 留痕
- **可选工具**：PM 不理会也能通过，但痕迹永久入库
- Hook：见 `integration-hooks.md` Hook-6

**T1-E → P1：多视角陪审团**（= 产品能力 3）
- 价值 / 动量 / 事件催化 三个独立 agent 打分投票
- gate 做 multi-verdict 融合；分歧 > 阈值触发 warn（而不是隐藏加权）
- Hook：见 `integration-hooks.md` Hook-7

### T2（下季度再评）

- **FinRL × nous env 层合规**：在 RL env step() 里插 gate，把 "action_size > risk_budget" 变成 hard block（而非 reward 惩罚）
- **OpenBB MCP × nous KG seed**：OpenBB 查到的基本面 → 喂 KG 做初始化；AGPL 许可需讨论
- **FinGPT-Forecaster 作为 sentiment feed**：把其输出作为 fact 注入 gate context

### 观望（暂不动）

- `virattt/ai-hedge-fund`：star 最多但 19 个投资家 prompt 会**改变 PM 研究风格**（违反红线 3）
- `TauricResearch/TradingAgents`：Route B 已拒；persona debate 同样违反红线 3
- 时序基础模型 Chronos / TimesFM / TimeGPT：上游已成熟，纳入仅在需要 ensemble 分歧检测时
- FinRobot：AutoGen 路线与 Route A 的 ARIS 骨架重合但更重；暂不引入

---

## 6. "at least useful" 最小 POC（Revision 2026-04-21）

按深度智耀教训"**先单点验证价值 → 再扩展 → 人类始终审阅签字**"，第一批只做一个：

### POC-α（第一战）：结构化决策卡 + 字段完整性 gate
- **为什么先做这个**：它是 PM 每天都接触的产品面，而不是后台组件；孙总能直接看到价值
- **输入**：PM 填写的 12 维度决策卡（对接 invest/reports/ 已有的字段）
- **nous 守门**：`ontology/constraints/fin/T-CARD-001.yaml` —
  - `block if objective_fields.filled_ratio < 1.0`（客观数据必须全填，系统自动）
  - `block if subjective.thesis.length < 100`（论点少于 100 字直接拒）
  - `warn if subjective.exit_condition is empty`（退出条件空就警告）
- **KG**：检索过去 6 个月相似 ticker / 相似行业的决策卡（**只检索、不推荐**）
- **成功判据**：
  1. 4 个 PM 各提交 5 张卡，gate 的 block/warn 人审一致率 ≥ 80%
  2. 孙总看到"完整证据链"后评价"有用"（定性，不数字化）
- **不做的事**：不评分卡片质量、不比较 PM 之间、不推价格预测

### POC-β（第二战，POC-α 过了再做）：RD-Agent 因子准入 gate
- **输入**：rdagent fin_quant 跑 1 轮产出的 10 个新因子
- **nous 守门**：YAML —
  - `block if IR < 0.3`
  - `block if max_correlation_with_pool > 0.85`（KG 查 invest/ 已有因子池）
  - `warn if turnover > 2.0`
  - `warn if formula_depth > 8`
- **成功判据**：holdout 期 IR(gate-approved pool) ≥ IR(raw pool)，拒绝率 ≤ 50%
- **不做的事**：不训练模型、不做 alpha mining 本身、只做"准入"

### POC-γ（后置，依赖 α + β 都过了）：魔鬼代言人
- 详见 `integration-hooks.md` Hook-6

---

## 7. 差距与风险（诚实）

- **LLM 成本**：qwen-turbo 已在 nous 主线用于 semantic gate；金融 POC 复用
- **数据**：按红线 5 **本地处理**，tushare + Wind（采购中）覆盖 A 股；OpenBB AGPL 暂不直接集成
- **评测**：不做 benchmark 竞赛，基准是孙总 + 4 PM 的**定性反馈** + `internal_poc_*` 硬指标
- **孙总信任曲线**：按深度智耀路径，**先单点 POC-α 价值验证 → 再扩展 → 始终人审签字**

---

## 8. 自省 checklist（每月）

- [ ] sota-tracker.yaml 里是否有 major version bump？
- [ ] 有没有新项目 >5k★ 且与我们方向重叠但我们没列入？
- [ ] 上一轮 POC 结论是不是还成立，还是新版本已经覆盖？
- [ ] 我们是不是开始**自研**了？如果是，停下来找上游
- [ ] 红线有没有被悄悄越过？（特别是"AI 系统"措辞、PM 排名、LLM 预测价格）
- [ ] `invest/` 数据有没有被意外推到 origin？（红线 5）
- [ ] 孙总最近一次反馈是什么，跟我们 roadmap 对得上吗？

---

## 附录 A：主要引用

- TradingAgents v0.2.3（2026-Q1）: multi-provider、GPT-5.4 家族、backtesting date fidelity
- FinRL-X paper arXiv:2603.21330（"AI-Native Modular Infrastructure for Quantitative Trading"）
- FinMem arXiv:2311.13743（ICLR LLM Agents Workshop 2024）
- aimultiple AgenticAI-Finance benchmark 2025
