# nous × 上游：具体 hook 点

> 目的：把"nous 做守门员"落到 file:line 级别，避免写抽象设计文档。
> 不写代码，只写**在哪里接**、**塞什么 context**、**期望 gate 判什么**。

---

## Hook 1 — TradingAgents Portfolio Manager 前置 gate

### 位置
- 上游：`tradingagents/graph/trading_graph.py` → `TradingAgentsGraph.propagate(ticker, date)`
- PM 节点是 LangGraph 最后一个 decision node；按官方描述 "approves/rejects the transaction proposal"

### 拦截方式（不 fork）
在调用 `propagate` 的外层 wrapper 里：
```text
decision = ta.propagate(ticker, date)    # 现有上游调用
verdict  = nous.gate(                    # 新增：守门
    tool_call={"tool_name": "execute_trade", **decision.to_dict()},
    kg_context=build_finance_kg_context(ticker),  # 调 nous KG 查 ticker Markov blanket
)
final = apply_verdict(decision, verdict)  # 映射 allow→原样 / warn→标注 / block→否决
```
`build_finance_kg_context` 是 nous 侧小函数（<30 行），不碰上游源代码。

### nous 侧需准备
- `ontology/constraints/fin/T-PM-001.yaml` — Portfolio Manager 审计规则
  - e.g. `if facts.sentiment_score < -0.3 and facts.news_has_regulatory_keyword: verdict = warn`
- `memory/entities/fin/<ticker>.md` — ticker 作为 resource 实体，持仓/行业/关联
- 无需改 `gate.py`；接口现成（见 `src/nous/gate.py:253`）

### 成功判据
10 ticker × 30 天样本，**gate warn/block 命中率**（人工判定）≥ 60%，
且 **原 PM 的合理 approve 被误杀率** ≤ 10%。

---

## Hook 2 — RD-Agent 因子接受前 gate

### 位置
- 上游：`rdagent fin_quant` self-loop 在 propose 新因子后入库；入库动作是拦截点
- RD-Agent 有 execution trace，可作为 gate 的 proof_trace 输入

### 拦截方式
RD-Agent 作为 PyPI 库使用；在它的 factor commit callback 位置（如果没暴露就包 subprocess + 读 trace）前塞：
```text
for factor in rdagent_round_output.factors:
    verdict = nous.gate(
        tool_call={"tool_name": "accept_factor", "formula": factor.expr,
                   "ir": factor.ir, "turnover": factor.turnover},
        kg_context=build_factor_kg_context(factor, existing_factor_pool),
    )
    if verdict.action == "allow":
        persist(factor)
    else:
        log_rejection(factor, verdict.reason)
```

### nous 侧需准备
- `ontology/constraints/fin/T-FACTOR-001.yaml`
  - block: `ir < 0.3`
  - block: `max_correlation_with_pool > 0.85` （KG 查）
  - warn: `turnover > 2.0`（双边 200%）
  - warn: `formula depth > 8`（过拟合嫌疑）
- KG 种子：把 existing factor pool 作为 concept 实体，带 formula 向量 + 历史 IR 属性

### 成功判据
holdout 期 IR(gate-approved pool) ≥ IR(raw pool)，拒绝率不超过 50%（不能太苛刻）。

---

## Hook 3（T2，暂不做）— FinRL env.step() action gate

### 位置
- 上游：`finrl.meta.env_stock_trading.env_stocktrading.StockTradingEnv.step(action)`
- RL 的 action 是连续仓位向量；传统做法是 reward penalty，我们改 hard block

### 思路
```text
def step(self, action):
    proposal = action_to_trades(action, self.state)
    verdict = nous.gate({"tool_name": "portfolio_rebalance", "trades": proposal}, ...)
    if verdict.action == "block":
        action = self.last_safe_action   # 或全 0
    return super().step(action)
```

### 风险
- 训练期 block 过频会让 RL 学不到东西 → 需要 curriculum：前 20% 只 warn，后面才 block
- 需要 FinRL-X 发稳定 release；当前还在迁移中 → **等**

---

## Hook 4（T2，暂不做）— FinGPT-Forecaster 作为 fact 源

### 思路
把 FinGPT 的 HF 推理结果写到 gate 的 `context.facts`：
```text
facts["sentiment_finbert"] = fingpt_sentiment(news_snippet)
facts["forecaster_direction"] = fingpt_forecaster(ticker)
```
然后让 YAML 规则引用这些 fact，而不是每次实时调 LLM（贵）。

### 前置条件
先跑一次 FinGPT-Forecaster HF Space，看 latency & 成本；如果 > 5s/call，上 batch + 离线缓存。

---

## 不做的 hook（明确拒绝 scope creep）

- ❌ fork ai-hedge-fund 重写 19 个 persona prompt — 其价值在 persona 本身，守门员角色用 TradingAgents 足够
- ❌ 在 OpenBB Platform 内部改代码 — 作为数据源接入即可，AGPL 边界清晰
- ❌ 自己训练 finetune 的金融 LLM — 任何时候都优先 off-the-shelf
- ❌ 重新实现回测引擎 — qlib / pybroker 任一足矣

---

## 集成完成的 DoD（Definition of Done）

对每个 hook：
1. nous 侧 YAML 规则 + KG 实体 schema 已 commit
2. wrapper adapter（<100 行 Python）能跑通一次 end-to-end demo
3. `logs/gate_events.jsonl` 里出现金融 domain 的 event 条目
4. dashboard（已有 `dashboard/api.py`）能看到这些 event 的统计
5. 本文件更新 "status=done"，关联 PR/commit hash

> 没做到 DoD 的 hook 就是 **未完成**，不要并入主线。
