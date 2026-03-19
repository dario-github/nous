# Loop 47 — 本体论推理与 Agent 推理结合：文献搜索

> 日期: 2026-03-19
> 目标: 找到 KG/本体论如何有效与 agent 推理结合的 SOTA 方法
> 触发: 东丞 03-19 #nous 明确要求

## 核心问题

Nous 当前状态：Datalog pattern matching + LLM prompt 兜底。KG 125 实体/143 关系存在但无推理能力。
Loop 43 实验：KG 直注入 semantic gate → FPR 从 5.6% 翻倍到 11.1%。粗暴注入不行。

东丞提出的三个方向：
1. 选择性注入（马尔科夫毯）
2. KG/DO 的推理机选择（TrOWL 太重后的替代）
3. 基于程序公理的自动推理

## 文献搜索结果

### 最相关论文

**P1. SCL: Structured Cognitive Loop with Governance Layer** (2511.17673, Feb 2026)
- R-CCAM 五阶段架构：Retrieval → Cognition → Control → Action → Memory
- "Soft Symbolic Control" = 符号约束应用于概率推理，同时保留神经推理的灵活性
- 实验：零策略违规 + 消除冗余工具调用 + 完整决策追溯
- **与 Nous 的关系**：SCL 的 Governance Layer ≈ Nous 的 gate()。区别在于 SCL 在 Cognition 阶段就介入，不是在 Action 后拦截
- **启示**：前置推理（think before act）比后置拦截（act then check）更有效？

**P2. OWL 2 RL + Datalog 混合推理** (Herron et al. 2025, SAGE)
- OWL 2 RL profile 可以无缝混合 OWL 推理 + 补充 Datalog 规则
- **关键发现**：不需要完整 OWL 推理机（TrOWL/HermiT），OWL 2 RL 子集可以用 Datalog 引擎执行
- **对 Nous 的意义**：Cozo 已经是 Datalog 引擎 → 可以直接表达 OWL 2 RL 的推理规则，无需额外推理机

**P3. SymAgent: Neural-Symbolic Self-Learning** (ACM Web 2025)
- KG 上的自学习 agent，将 KG 推理和 LLM 推理结合
- 不是简单的 RAG + KG，而是让 agent 在 KG 上做 multi-hop reasoning

**P4. Scallop: 可微分 Datalog** (PLDI 2023, UPenn)
- Datalog 扩展，支持概率推理和可微分推理
- provenance semirings 理论基础
- 可以从数据中学习 Datalog 规则的权重
- **对 Nous**：如果把 Nous 的 Datalog 规则替换为 Scallop，可以实现"软规则"——规则有置信度而非二值

**P5. ReKnoS: Super-Relations for KG Reasoning** (OpenReview 2024)
- 多关系路径聚合成 super-relations
- 增强 forward/backward reasoning
- 更高效的 LLM 查询

**P6. KG Embedding 注入 LLM** (2505.07554, May 2025)
- 把 KG embedding 作为 token 直接注入 LLM 输入
- model-agnostic，resource-efficient
- **与 Loop 43 失败的关系**：我们塞的是自然语言描述（noisy），他们用的是 embedding（dense/structured）

**P7. ATA: Autonomous Trustworthy Agents** (已在 research-ontology 中)
- 离线 LLM → formal KB，运行时纯符号推理
- 对 prompt injection 天然免疫

### 撤稿/低质量

- 2504.07640 (Neuro-Symbolic + OWL) — 已撤稿，参考文献和架构描述有误

## 方向分析

### 东丞提出的三个方向 vs 搜索发现

**1. 马尔科夫毯选择性注入**
- 搜索没有找到直接把 Markov Blanket 用于 KG→LLM 注入的论文
- 但有两个近似思路：
  - ReKnoS 的 super-relation 路径压缩（减少噪声路径）
  - KG Embedding 注入（把结构信息压缩成 dense vector，避免自然语言噪声）
- **实验想法**：在 Nous 的 `_build_kg_context()` 中，用 Markov Blanket 原理只取当前 tool_call 的条件独立边界内实体（parents + children + co-parents in causal graph），丢弃无关上下文

**2. 推理机选择（替代 TrOWL）**
- **最大发现**：OWL 2 RL 可以用 Datalog 执行！不需要专门的 OWL 推理机
- Cozo 本身就是 Datalog → 只需要把 OWL 2 RL 的推理规则编码成 Cozo 规则
- 这意味着我们可以在不增加任何新依赖的情况下获得本体推理能力
- **Scallop 路径**：更激进——可微分 Datalog，规则有概率权重。但需要 Rust 编译

**3. 程序公理自动推理**
- ATA 的方向最接近：LLM 离线生成 formal KB → 运行时符号推理
- 可以让 LLM 从现有的 T 规则 + 决策历史 → 自动生成新的 Datalog 约束
- **实验想法**：用 GPT-5.4 审查 shadow log 中的 FP/FN → 提出新 Datalog 规则 → 自动验证

## 实验优先级

| # | 实验 | 预期 | 难度 | 价值 |
|---|------|------|------|------|
| E1 | OWL 2 RL 规则编码到 Cozo | 获得 subclass/property chain 推理 | 低 | 高 |
| E2 | Markov Blanket 选择性注入 | 降低 Loop 43 的 FPR 翻倍问题 | 中 | 高 |
| E3 | LLM→Datalog 规则自动生成 | 从 FP/FN 自动修复 | 中 | 高 |
| E4 | Scallop 可微分 Datalog | 软规则+置信度 | 高(Rust) | 中 |
| E5 | KG Embedding 替代自然语言注入 | 更结构化的上下文 | 中 | 中 |

建议顺序：E1 → E2 → E3（低风险到高风险，每个一个 loop）
