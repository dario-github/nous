# Project Charter — owner-harm-generalization-v1

## 1. 问题定义

- **项目名**：owner-harm-generalization-v1
- **一句话问题**：我们能否把 owner-harm v3 held-out 中 34 个 Hijacking false negatives 可靠地刻画为**当前单次调用 runtime gate 的架构性边界**，而不是一句模糊的 future work 借口？
- **为什么现在值得做**：双审计结论一致认为，当前最会被 reviewer 攻击的不是“KG 有没有帮助”，而是“为什么系统在 prompt injection / hijacking 上只有 43.3% TPR”。如果不能把这一点讲清，论文主叙事会显得像是在回避最关键失败模式。
- **和 Nous 主线的关系**：这是当前 owner-harm / runtime safety 主线的 **P0 问题**。KG held-out ablation 仍保留，但降级为 **P2**，只有在机制、baseline、阈值与统计设计补齐后才继续。

## 2. 成功标准

- **主要 success metric**：形成一份 reviewer-facing 的 Hijacking FN taxonomy，覆盖 34 个 held-out false negatives，并把它们区分为：
  1. **当前架构原则上看不到关键信号**的 structural failures
  2. **当前架构其实可见但实现/提示设计不足**的 addressable failures
- **次要 success metric**：将该结论写入 paper 主叙事 / limitations / future architecture section，使 reviewer 能接受“这是系统边界分析，不是找借口”。
- **什么结果也算有价值（证伪）**：如果对 34 个 Hijacking FN 的逐例分析表明，其中有相当一部分其实是当前架构可解决而我们没解决，那么这同样是高价值结果——说明当前 taxonomy 或系统边界叙事需要收缩。

## 3. 约束

- **时间预算**：优先在本周内产出第一版 reviewer-facing 分析
- **成本预算**：优先使用现有 held-out 样本和日志，不新开高成本实验线
- **不可做事项**：
  - 不允许为了 held-out 指标去反向补规则
  - 不允许修改 holdout 定义来迎合结论
  - 不允许把“问题讲清楚”偷换成“顺手把 hijacking 修掉”
- **过拟合防线**：held-out 只作边界分析，不作补丁优化目标；若发现 addressable gaps，只记录，不立即修补
- **P2 约束（KG）**：KG 项目暂不删除，但不得继续作为当前主问题推进；只有在补齐注入点定义、flat-context baseline、effect-size threshold、power analysis 后才允许重启

## 4. 目标产出

- [ ] Evidence Ledger（补足与 Hijacking 相关的证据链）
- [ ] Top-k Hypotheses（围绕 structural vs addressable 的可证伪假设）
- [x] Minimal Experiment Pack
- [ ] Review Memo
- [ ] Learning Record
- [ ] Reviewer-facing Hijacking taxonomy note

## 5. 决策门

- **Gate 1（问题是否足够具体）**：是。问题已收缩为“34 个 Hijacking FN 到底是不是当前单次调用 gate 的真实边界”。
- **Gate 2（是否已有可回链证据）**：是。已有 Loop 82/83、v3 held-out 类别统计、paper 当前 limitations、Gemini + Opus 双审计。
- **Gate 3（是否可证伪）**：是。如果逐例分析发现大量样本并非 structural，而是当前系统可解决但未解决，则当前边界叙事被证伪或至少被削弱。
- **Gate 4（Critic 是否通过）**：已通过，但结论为 **revise**，不是 continue-as-is。

## 6. 当前默认 target venue / narrative

- **主叙事**：runtime policy-enforcement layer for preventing owner-harm in tool-using LLM agents
- **目标 venue**：SaTML 主路；USENIX Security 为冲高备选
- **当前最缺的证据**：对 Hijacking / prompt injection 失败模式的可审计、可辩护、可写进 paper 的结构性边界分析
- **次级缺口**：KG 是否对 held-out generalization 有真实边际贡献；该问题保留，但不再是当前主问题

## 7. Sponsor 决策

- **continue / revise / stop**：revise
- **备注**：主项目转向 Hijacking characterization；KG 降级为 P2。