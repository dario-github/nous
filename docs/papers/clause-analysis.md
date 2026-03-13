# CLAUSE 论文精读 × Nous 竞品分析

> **论文**: CLAUSE: Agentic Neuro-Symbolic Knowledge Graph Reasoning via Dynamic Learnable Context Engineering  
> **来源**: ICLR 2026 (Published), OpenReview 97Qk741ih6  
> **作者**: Yang Zhao, Chengxiao Dai, Wei Zhuo, Yue Xiu, Dusit Niyato (NTU/Sydney)  
> **分析日期**: 2026-03-13

---

## 1. 论文核心架构

### 1.1 问题定义

CLAUSE 将**多跳知识图谱问答 (KGQA)** 重新定义为**受约束的上下文构建决策过程**：给定问题 q 和知识图谱 K=(V,R,E)，目标是组装一个最优上下文（子图 + 推理路径 + 文本证据）送给 reader LLM 回答问题，同时满足三类部署约束：

- **边预算 β_edge**：子图编辑次数（控制图膨胀）
- **延迟预算 β_lat**：交互步数（控制响应时间）
- **Token 预算 β_tok**：选取的文本证据 token 数（控制 prompt 成本）

核心洞察：**"上下文工程"不是静态的 k-hop 扩展或 top-k 检索，而是一个需要学习的序列决策问题。**

### 1.2 三 Agent 框架

| Agent | 职责 | 操作对象 | 动作空间 | 消耗资源 |
|-------|------|---------|---------|---------|
| **Subgraph Architect** | 子图构建 | 图边 E_cand_t | ADD / DELETE / STOP | C_edge |
| **Path Navigator** | 推理路径发现 | 路径前缀 p_t | CONTINUE / BACKTRACK / STOP | C_lat |
| **Context Curator** | 证据选取 | 文本池 P_t | SELECT / STOP（listwise） | C_tok |

**运行流程**：
1. 从问题 q 中提取实体提及 M(q)，匹配锚定实体 → 种子集 S_0 → 初始前沿 F_0
2. Architect 在前沿边上做 ADD/DELETE，用 neural scorer 评估候选边的效用：`s(e|q,G_t) = w⊤h{ϕ_ent, ϕ_rel, ϕ_nbr, ϕ_deg}` 减去资源价格 λ_edge·c_edge 后决定是否执行
3. Navigator 沿图路径游走，在每步决定 CONTINUE/BACKTRACK/STOP，收集推理路径 Π
4. Curator 从文本化的节点/边/路径中 listwise 选择最小必要证据集，带学习到的 STOP head
5. 所有 Agent 都 STOP 或任一预算耗尽 → 将组装好的上下文交给 reader LLM 回答

### 1.3 KG 表示

- 标准三元组图 K=(V,R,E)，E ⊆ V×R×V
- 实体有文本描述，可做 lexical matching
- 使用 **frozen encoder** 计算实体/关系的语义相似度（非训练时更新）
- 图本身是**只读**的——Agent 只在本地子图 G_t 上做增删，不修改全局 KG

### 1.4 推理方法

**核心是"符号图操作 + 神经评分"的混合**：

- **符号层**：KG 边遍历、路径追踪、子图编辑——所有操作都是离散的、可审计的
- **神经层**：轻量级 neural scorer 为候选边/节点/路径打分，用于优先级排序
- **没有 Datalog / 一阶逻辑推理**——"符号"仅指图结构上的离散操作，不涉及逻辑规则匹配
- 推理链的可解释性来自路径追踪 Π（人类可读的路径 provenance），而非逻辑推导

### 1.5 训练算法：LC-MAPPO

**Lagrangian-Constrained Multi-Agent Proximal Policy Optimization**：
- CTDE（集中训练、分散执行）
- 集中 critic 有 4 个 head：Q_task, Q_edge, Q_lat, Q_tok（任务价值 + 三类成本）
- 每步塑形奖励：`r'_t = r_acc_t − λ_edge·c_edge_t − λ_lat·c_lat_t − λ_tok·c_tok_t`
- 对偶变量 λ_k 通过投影梯度上升更新：`λ_k ← [λ_k + η(E[C_k] − β_k)]_+`
- **单个 checkpoint 支持两种推理模式**：cap 模式（硬预算上限）和 price 模式（固定价格软权衡）

### 1.6 Context Engineering 实现

CLAUSE 的 "context engineering" 具体指：
1. **非静态**：不是 k-hop 或 top-k 固定策略，而是学习何时停止
2. **预算感知**：每个决策都考虑边际效用 vs 资源价格
3. **可组合**：子图构建、路径发现、证据选取三个维度独立但联合优化
4. **可调节**：部署时通过调 β 或 λ 即可改变精度-延迟-成本权衡，无需重训

### 1.7 实验结果

在 MetaQA 2-hop 上，相对 GraphRAG：
- EM@1: +39.3（87.3 vs 48.0）
- 延迟：-18.6%（1.14× vs 1.40×）
- 边膨胀：-40.9%（0.78× vs 1.32×）

在 HotpotQA 上：EM@1 71.7，超过所有 baseline（最强 KG-Agent 68.7）

消融实验（Table 5, MetaQA）：
- 去掉 Architect → EM 降 12.5pt（87.3→74.8），延迟 +32%
- 去掉 Navigator → EM 降 5.2pt，延迟 +18%
- 去掉 Curator → EM 降 6.7pt
- MAPPO 无对偶 → EM 降 2.3pt，边膨胀 +28%

---

## 2. 与 Nous 的重合

| 维度 | CLAUSE | Nous | 重合程度 |
|------|--------|------|---------|
| **"Neuro-Symbolic"定位** | 符号图操作 + 神经评分 | 确定性 Datalog + LLM 概率推理 | 🟡 概念重合，实现迥异 |
| **知识图谱作为核心基础设施** | KG 是推理的搜索空间 | KG 是实体/关系/本体存储 | 🟢 高度重合 |
| **三层/三组件分解** | 子图/路径/证据 三 Agent | KG/决策图谱/自治理 三层 | 🟡 都是三分法，但分解维度不同 |
| **离散可审计动作** | ADD/DELETE/STOP 可追踪 | 约束匹配 + proof_trace | 🟢 高度重合——都强调可解释性 |
| **决策日志/Provenance** | 路径追踪 Π 作为 provenance | DecisionLog 记录完整推导链 | 🟢 高度重合 |
| **预算/约束意识** | β_edge/β_lat/β_tok 硬约束 | P99 <5ms 性能目标 | 🟡 CLAUSE 更形式化 |
| **约束从代码变成数据** | 预算作为输入参数而非硬编码 | 约束规则存 YAML/DB 而非代码 | 🟢 同一哲学 |
| **多 Agent 协作** | 三 Agent MARL 协调 | Gateway hook → engine（单体） | 🔴 CLAUSE 有，Nous 当前没有 |

### 核心重合点

1. **"符号推理 + 神经能力"的分层设计**：两者都认为纯 LLM 或纯符号不够，需要混合
2. **知识图谱作为可查询的结构化世界模型**：都依赖 KG 提供结构化推理基础
3. **可审计性/Provenance 作为一等公民**：CLAUSE 的路径追踪 ≈ Nous 的 proof_trace + decision_log
4. **"把约束变成数据而非代码"**：CLAUSE 的 β/λ 参数化 ≈ Nous 的规则存 YAML

---

## 3. 与 Nous 的差异

### 3.1 CLAUSE 有而 Nous 没有的

| 维度 | CLAUSE 的能力 | Nous 现状 |
|------|-------------|----------|
| **多 Agent RL 训练** | LC-MAPPO 联合优化三个 Agent | 无训练组件，纯规则匹配 |
| **资源预算形式化** | 三维 CMDP（边/步/token），Lagrangian 对偶 | 仅 P99 延迟目标，无形式化约束框架 |
| **上下文工程** | 学习何时停止、选什么证据、走哪条路径 | 无（上下文组装由 OpenClaw/LLM 处理） |
| **子图构建学习** | 学习前沿扩展策略（哪些边有用） | 静态导入（memory/*.md → KG） |
| **路径推理** | 多跳路径发现 + BACKTRACK | path() 查询（BFS/DFS，非学习式） |
| **Pareto 权衡调节** | 单 checkpoint 支持 cap/price 两种模式 | 无（规则是硬判定） |
| **QA 任务直接评估** | HotpotQA/MetaQA/FactKG EM@1 | 无 QA 能力（面向行为拦截） |

### 3.2 Nous 有而 CLAUSE 没有的

| 维度 | Nous 的能力 | CLAUSE 现状 |
|------|-----------|------------|
| **确定性逻辑推理** | Cozo Datalog 原生规则匹配（P99 <1ms） | 无 Datalog/一阶逻辑——"符号"仅指图操作 |
| **行为拦截/Gate** | before_tool_call hook → verdict（allow/block/confirm/transform） | 无——CLAUSE 不做行为控制 |
| **规则热加载** | watchfiles → atomic put → <1ms 生效 | 模型需重训才能改变策略 |
| **自治理 / 规则演化** | Proposal → TTL → 自动衰减/升级 | 无——策略固定在训练后 |
| **安全语义** | FAIL_CLOSED（异常→confirm，永不 allow） | 无安全框架 |
| **本体论建模** | OntologyClass 层级 + 继承 + 约束绑定 | 无本体论——KG 是扁平三元组 |
| **双源真理** | MD 文件为 source of truth，KG 为加速层 | KG 是唯一数据源 |
| **FP/FN 度量 + 回滚** | Shadow mode 双写 + 自动回滚门槛 | 无部署安全机制 |
| **人机协作** | confirm verdict → 人工审核 | 全自动（无人在环） |

---

## 4. CLAUSE 的优势（Nous 应该借鉴的）

### 4.1 🔴 资源预算的形式化建模

CLAUSE 将三类资源（边/步/token）建模为 CMDP 约束，用 Lagrangian 对偶变量自动平衡。这比 Nous 当前的"P99 <5ms 目标"高级很多。

**Nous 可借鉴**：将 gate 调用的成本（推理步数、查询节点数、LLM token 消耗）形式化为可配置预算，而非硬编码性能目标。特别是当 Nous 扩展到 M3+ 引入 LLM delegate 判断时，token 预算控制变得关键。

### 4.2 🟡 "学习何时停止"的思想

CLAUSE 最强的创新是**learned STOP**——每个 Agent 都有显式 STOP head，通过 RL 学习最优停止时机。对比 Nous 当前的确定性匹配（匹配到就返回，没匹配到就 allow），CLAUSE 能在"不确定但可能需要更多推理"的灰色地带做出成本感知的决策。

**Nous 可借鉴**：在 M3+ delegate 路径中，引入"推理深度控制"——LLM 审议某个约束冲突时，设置 step budget 限制推理轮次，避免无限思考。

### 4.3 🟡 多 Agent 分工与联合优化

CLAUSE 将复杂任务分解为三个专门化 Agent，每个都有清晰的职责边界和资源归因。这种架构比单体引擎更容易扩展和调试。

**Nous 可借鉴**：当 Nous 的决策变复杂时（如 M3 自治理），可以考虑将 "事实提取"、"约束匹配"、"verdict 决策" 三步解耦为独立组件，各自维护状态和性能指标。

### 4.4 🟢 Provenance 的体系化

CLAUSE 将 provenance 从"附加日志"提升为"系统架构的组成部分"——路径追踪和选取证据本身就是 Agent 的输出。Nous 的 proof_trace 是 P0 审计建议才加的，说明还可以更系统化。

---

## 5. Nous 的差异化定位

### 5.1 Nous 不能被 CLAUSE 替代的核心价值

**CLAUSE 和 Nous 解决的是根本不同的问题**：

| 维度 | CLAUSE | Nous |
|------|--------|------|
| **目标** | 从 KG 中组装最优上下文回答问题 | 基于规则拦截/治理 Agent 行为 |
| **KG 角色** | 被动搜索空间（只读） | 活跃的世界模型（持续更新） |
| **推理类型** | 路径发现 + 相关性评估 | 约束满足 + 逻辑推导 |
| **安全语义** | 无 | 核心（FAIL_CLOSED / 不可逆拦截） |
| **部署位置** | 独立 QA 系统 | Agent runtime 的中间件 hook |
| **人在环** | 不需要 | 关键路径（confirm verdict） |
| **规则可编辑性** | 需重训 | 热加载 <1ms |

### 5.2 Nous 的独特价值

1. **Agent 行为治理层**：CLAUSE 是"让 Agent 更好地利用知识"，Nous 是"让 Agent 的行为受到约束"。前者提升能力，后者保证安全。两者不是竞品，是互补层。

2. **确定性推理作为安全基石**：CLAUSE 的"符号"是图遍历操作，本质仍是概率性的（neural scorer 决定方向）。Nous 的 Datalog 是真正的确定性推理——给定事实和规则，结论唯一确定。在安全关键场景（如 T3 不可逆操作拦截），确定性 > 概率性。

3. **规则作为可编辑数据**：CLAUSE 的策略冻结在模型权重中，改行为需要重训。Nous 的约束存在 YAML/DB 中，可以热加载。在需要快速响应新安全威胁的场景下，这是根本性优势。

4. **自治理闭环**：Nous 的 Proposal → TTL → 衰减 → 升级机制是 CLAUSE 完全没有的。KG 和规则能自我演化，不需要人工重训模型。

5. **人机协作的 verdict 路由**：confirm/warn/transform/delegate 等多种 verdict 类型体现了对真实部署场景的深入理解。CLAUSE 是全自动 pipeline，没有"不确定时征求人类意见"的设计。

### 5.3 定位总结

> **CLAUSE = KG-enhanced QA 的最优上下文工程器**  
> **Nous = Agent runtime 的本体论驱动治理引擎**  
> 
> CLAUSE 可以作为 Nous Layer 3 知识查询的一个**下游消费者**（用 Nous 的 KG 来回答问题），  
> 但 CLAUSE 无法替代 Nous 的 Layer 2（决策图谱/行为拦截）和 Layer 1（自治理）。

---

## 6. 对 Nous design.md 的具体设计建议

### 建议 1：引入资源预算框架（借鉴 CLAUSE §4 CMDP）

**现状**：design.md §11 只有 "gate P99 <5ms" 的性能目标，没有形式化的资源约束。

**建议**：为 `nous.gate()` 调用引入可配置资源预算：

```yaml
# ontology/config/resource-budget.yaml
gate_budgets:
  max_query_depth: 5          # Datalog 递归深度上限（≈ CLAUSE 的 β_lat）
  max_entities_scanned: 50    # 单次 gate 扫描实体上限（≈ CLAUSE 的 β_edge）
  delegate_token_budget: 512  # M3+ LLM delegate 的 token 上限（≈ CLAUSE 的 β_tok）
  timeout_us: 5000            # 硬超时
```

这在 M3+ 引入 LLM delegate 时尤为关键——需要控制 LLM 审议的 token 消耗和轮次。

### 建议 2：§13.1 推理后端分层增加"学习式路径推理"选项

**现状**：§13.1 列出 Cozo Datalog / Scallop / GPU Datalog 三个后端，全是声明式推理。

**建议**：增加第四个后端位置——**学习式 KG 推理**（CLAUSE 风格的 RL 路径发现）：

```
约束定义 (YAML/JSON)
    │
    ▼
中间表示 (patterns + rule_body + dialect)
    │
    ├─→ Cozo Datalog（精确推理，当前默认）
    ├─→ Scallop（概率推理 + provenance semiring，M5+）
    ├─→ GPU Datalog（Lobster APM / VFLog，规模化场景）
    └─→ Learned KG Reasoning（RL 路径发现，M6+ 复杂查询）  ← NEW
```

适用场景：当 query 需要多跳路径发现（如"东丞的同事中谁也在做 Agent 开发？"）且声明式规则不好写时，用 CLAUSE 风格的学习式推理作为 fallback。

### 建议 3：为 DecisionLog 增加成本归因字段（借鉴 CLAUSE 的资源归因设计）

**现状**：DecisionLog 有 `latency_us` 但只是一个总数。

**建议**：拆分成本归因：

```python
# decision_log schema 增加
cost_breakdown: {
    fact_extraction_us: int,     # extract_facts 耗时
    constraint_match_us: int,    # Datalog 匹配耗时  
    delegate_us: int?,           # M3+ LLM 审议耗时（如有）
    delegate_tokens: int?,       # M3+ LLM 消耗 token
    entities_scanned: int,       # 本次扫描了多少实体
    constraints_evaluated: int,  # 评估了多少条约束
}
```

这直接来自 CLAUSE 的"成本归因到源"设计思想（edits→C_edge, steps→C_lat, curations→C_tok），能显著提升 gate 性能的可观测性和优化指针。

### 建议 4：§13.3 学术竞品表更新 CLAUSE 关系为"互补"而非"竞品"

**现状**：design.md §13.3 标记 CLAUSE 为 "🔴 最近竞品"。

**建议**：更新为 "🟡 互补参考"。原因：

- CLAUSE 解决的是 **KGQA 上下文工程**（"从 KG 找最好的证据回答问题"）
- Nous 解决的是 **Agent 行为治理**（"基于 KG 中的规则拦截危险操作"）
- 两者共享"neuro-symbolic + KG"技术栈，但问题域不重叠
- CLAUSE 可能成为 Nous KG 查询层的一个增强组件（特别是复杂多跳查询场景），而非替代品

更新后：

```
| **CLAUSE** | 🟡 互补参考 | agentic 上下文工程：资源预算形式化、learned STOP、多 Agent 协调 | ICLR 2026 |
```

### 建议 5：在 M3 自治理设计中引入"推理深度预算"概念

**现状**：§8 自治理层的 Proposal 审核无资源控制——LLM 审议一个 Proposal 可能消耗不可预测的 token。

**建议**：借鉴 CLAUSE 的 learned STOP 思想，为自治理审议引入分级预算：

```yaml
# 自治理审议预算
governance_budgets:
  proposal_review:
    fast_check_token_limit: 256    # 快速检查：简单规则直接判
    deep_review_token_limit: 2048  # 深度审议：复杂规则
    max_review_rounds: 3           # 最大审议轮次（防无限讨论）
    escalation_threshold: 0.6      # confidence < 0.6 → 升级到人工
```

这确保自治理层本身也是资源可控的，不会因为一个复杂 Proposal 导致整个系统延迟。

---

## 附录：CLAUSE 关键数字速查

| 基准 | CLAUSE EM@1 | 最强基线 (KG-Agent) | 提升 |
|------|------------|-------------------|------|
| HotpotQA | 71.7 | 68.7 | +3.0 |
| FactKG | 84.2 | 82.1 | +2.1 |
| MetaQA 1-hop | 91.0 | 87.3 | +3.7 |
| MetaQA 2-hop | 87.3 | 78.0 | +9.3 |
| MetaQA 3-hop | 85.5 | 75.4 | +10.1 |

效率（相对 Vanilla RAG = 1.0×）：
- 延迟：0.98×-1.48×（大多低于 Agent 类基线的 1.3×-2.6×）
- 边膨胀：0.74×-0.90×（唯一低于 1.0× 的 Agent 方法）

消融核心发现：
- 去掉任何一个 Agent 都导致 EM 下降 5-12 pt
- LC-MAPPO 对偶机制对约束满足率提升 191%（vs 无对偶 MAPPO）
- Learned STOP 是效率增益的主要来源

---

*分析完成。核心结论：CLAUSE 和 Nous 不是直接竞品——CLAUSE 做的是"KG 上下文工程优化 QA"，Nous 做的是"基于 KG 的 Agent 行为治理"。技术栈有交集（NeSy + KG），但问题域正交。CLAUSE 的资源预算形式化、成本归因、learned STOP 思想值得 Nous 借鉴；Nous 的确定性推理、规则热加载、自治理闭环、安全语义是 CLAUSE 完全没有的独特价值。*
