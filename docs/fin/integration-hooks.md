# nous × 上游 / invest：具体 hook 点

> 目的：把"nous 做守门员"落到 file:line 级别，避免写抽象设计文档。
> 本文件不写代码，只写**在哪里接**、**塞什么 context**、**期望 gate 判什么**。
>
> Revision 2026-04-21：按 `product-context.md` 的 Route A + 四大产品能力重排。
> Hook-1（TradingAgents）降级观望；Hook-5/6/7 新增，对齐产品能力 1/2/3。

---

## 优先级总表

| Hook | 对接产品能力 | 优先级 | 状态 |
|------|------------|-------|------|
| Hook-5 · 决策卡字段完整性 gate | 能力 1（结构化决策卡） | **P0** | 准备中 |
| Hook-2 · RD-Agent 因子准入 gate | 能力 4（AI4Science 流水线） | **P0** | 准备中 |
| Hook-6 · 魔鬼代言人 | 能力 2 | **P1** | 设计中 |
| Hook-7 · 多视角陪审团融合 | 能力 3 | **P1** | 设计中 |
| Hook-3 · FinRL env gate | — | P2 | 观望 |
| Hook-4 · FinGPT 作为 fact 源 | — | P2 | 观望 |
| Hook-1 · TradingAgents PM 前置 gate | —（Route B 已拒） | ❌ | watching only |

---

## Hook-5 · 决策卡字段完整性 gate（P0 · 能力 1）

### 位置
- 上游 / invest：`invest/reports/` 输出 12 维度 checklist JSON
- 对接点：PM 在前端（微信/简易表单）提交 checklist 前

### nous 侧
- 规则文件：`ontology/constraints/fin/T-CARD-001.yaml`
  ```text
  id: T-CARD-001
  trigger:
    action_type: {in: [submit_decision_card]}
  checks:
    - block_if: objective.filled_ratio < 1.0
    - block_if: subjective.thesis.len < 100
    - warn_if:  subjective.exit_condition == ""
    - warn_if:  subjective.risks.count < 2
  ```
- KG 上下文（检索型，非推荐型）：
  - 过去 6 个月**本团队** submit 过的相似 ticker / 行业的决策卡
  - 展示"去年 X PM 在类似情境下写了什么"（让 PM 自己看，**不总结、不打分**）

### 不做
- ❌ 不对决策卡质量打分
- ❌ 不跨 PM 比较
- ❌ 不自动填写 subjective 字段

### 成功判据
- 4 PM × 5 卡 = 20 样本，block/warn 人审一致率 ≥ 80%
- 孙总定性反馈"有用"

---

## Hook-2 · RD-Agent 因子准入 gate（P0 · 能力 4）

### 位置
- 上游：`rdagent fin_quant` self-loop 产出因子 → 入 invest/ 因子池前
- RD-Agent 暴露 execution trace，作为 proof_trace 输入

### 拦截方式
RD-Agent 作为 PyPI 库使用；在 factor commit callback 前塞 wrapper：
```text
for factor in rdagent_round_output.factors:
    verdict = nous.gate(
        tool_call={"tool_name": "accept_factor", "formula": factor.expr,
                   "ir": factor.ir, "turnover": factor.turnover},
        kg_context=build_factor_kg_context(factor, existing_factor_pool),
    )
    if verdict.action == "allow":
        persist_to_invest_factor_pool(factor)
    else:
        log_rejection(factor, verdict.reason)
```

### nous 侧
- `ontology/constraints/fin/T-FACTOR-001.yaml` —
  - `block: ir < 0.3`
  - `block: max_correlation_with_pool > 0.85`（KG 查 invest/features/ 现有因子）
  - `warn:  turnover > 2.0`（双边 200%）
  - `warn:  formula_depth > 8`（过拟合嫌疑）
- KG 种子：把 existing factor pool 作为 concept 实体，带 formula 向量 + 历史 IR 属性

### 成功判据
holdout 期 IR(gate-approved pool) ≥ IR(raw pool)，拒绝率 ≤ 50%。

---

## Hook-6 · 魔鬼代言人（P1 · 能力 2）

### 位置
- 对接点：PM 提交决策卡后的异步 spawn
- 骨架：**ARIS**（对抗/反思推理）做 skeleton + nous `semantic_gate` 做 executor + `proof_trace` 做留痕

### 流程
```text
1. PM 提交 decision_card
2. 系统 enqueue "devil's-advocate job"（异步，不阻塞 PM）
3. ARIS 骨架产生 N 条反驳候选（参考 invest/docs/ 的模板）
4. nous.semantic_gate 对每条反驳做 filter：
   - drop: 与 card 事实不符 / 重复
   - keep: 点出 card 中没覆盖的风险维度
5. 留存结果到 decision_log + KG（不弹窗，不打扰 PM）
6. 当 PM 下次看同一 ticker 时，反驳可见（拉力 > 推力）
```

### 不做
- ❌ 不弹窗打断 PM 工作流（违反红线 3）
- ❌ 不做"反驳评分"或"反驳命中率"（会变成排名 PM）
- ❌ 不让反驳 agent 做价格预测

### 成功判据
- 一个月内 5 个决策卡跑了反驳；PM 自发回看反驳记录 ≥ 1 次（定性）
- 至少 1 次反驳命中后来真实发生的风险（人工复盘）

---

## Hook-7 · 多视角陪审团融合（P1 · 能力 3）

### 位置
- 三个独立 agent（价值 / 动量 / 事件催化）**各自**跑在 invest/skills/ 的信号之上
- nous 做 verdict 融合，不做加权黑箱

### nous 侧
- 规则：`ontology/constraints/fin/T-JURY-001.yaml` —
  ```text
  - warn_if: disagreement_entropy > 0.8
  - block_if: all_three_agents_disagree AND position_delta > risk_budget
  - allow_otherwise: True
  ```
- 前端展示：**显式**列三个 agent 各自打分 + 分歧指标，**不**合成一个"综合分"
- PM 自己决策；系统只呈现分歧

### 不做
- ❌ 不隐藏加权系数
- ❌ 不"替 PM 投票"
- ❌ 不在 3 个 agent 之外再加"超级 agent"

### 成功判据
- 分歧 > 阈值的案例，人审 ≥ 70% 认为"确实值得再看一眼"

---

## Hook-2（重列细节见上）· Hook-3 / Hook-4（P2 观望）

### Hook-3 · FinRL env.step() action gate
- **不在本季度做**。Route A 不直接用 FinRL；若未来 ARIS 引入 RL，再评估
- 若做：在 `StockTradingEnv.step(action)` 里把 "action_size > risk_budget" 从 reward penalty 改成 hard block
- 风险：训练期 block 过频会让 RL 学不到东西 → 需 curriculum：前 20% 只 warn

### Hook-4 · FinGPT-Forecaster 作为 fact 源
- **不在本季度做**。Wind 采购可能覆盖 sentiment feed，先看 Wind 结果
- 若做：把 FinGPT sentiment 输出作为 `facts["sentiment_finbert"]` 喂给 gate，避免每次实时调 LLM

---

## Hook-1 · TradingAgents PM 前置 gate（❌ 降级 watching）

- **原计划**：在 `TradingAgentsGraph.propagate` 外层 wrapper 注入 `nous.gate()`
- **为什么降级**：
  1. Route B 已被辩论拒绝（见 `product-context.md §7`）
  2. TradingAgents 的 multi-persona debate 会"改变 PM 的研究风格"（违反红线 3）
  3. 投入 2 天做一个**不会上线**的 POC = 浪费
- **仍保留**在 sota-tracker.yaml 里：等他们出声明式 risk DSL 就重评

---

## 明确不做的 hook（反 scope creep）

- ❌ fork ai-hedge-fund / TradingAgents 任一仓库
- ❌ 在 OpenBB Platform 内部改代码（AGPL 风险）
- ❌ 自己训 finetune 金融 LLM
- ❌ 重新实现回测引擎（Qlib / invest/backtest 已够）
- ❌ 给 PM 打分 / 排名（红线 2/7）

---

## 每个 hook 的 DoD（Definition of Done）

1. nous 侧 YAML 规则 + KG 实体 schema 已 commit 到 `ontology/constraints/fin/`
2. wrapper adapter（< 100 行 Python）能跑通一次 end-to-end demo
3. `logs/gate_events.jsonl` 出现 fin domain event
4. dashboard（`dashboard/api.py`）能看到这些 event 的统计
5. 本文件更新 "status=done"，关联 PR/commit hash
6. **孙总或至少 2 个 PM 用过一次并反馈"有用 / 无用 / 碍事"**（定性，不数字化）

> 没走到 6 的 hook 不是 done，是"工程 done / 产品未验证"——不能并入主线叙事。
