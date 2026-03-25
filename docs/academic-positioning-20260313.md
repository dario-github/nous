# Nous 学术定位报告 — 5 论文综合分析

> 2026-03-13 | 基于 CLAUSE / Lobster / VFLog / NeSy Survey / DeepLog 精读
> 子报告: `/tmp/subagent-out/{clause,lobster,vflog,nesy-survey,deeplog}-analysis.md`

---

## 一、核心结论

### CLAUSE 不是竞品，是互补层

这是最重要的发现。CLAUSE 解决的是 **KGQA 上下文工程**（"从 KG 找最好的证据回答问题"），Nous 解决的是 **Agent 行为治理**（"基于 KG 的规则拦截危险操作"）。

| | CLAUSE | Nous |
|---|--------|------|
| 目标 | 组装最优上下文回答问题 | 拦截/治理 Agent 行为 |
| KG 角色 | 被动搜索空间（只读） | 活跃世界模型（持续更新） |
| 推理类型 | 路径发现 + 相关性评估 | 约束满足 + 逻辑推导 |
| 安全语义 | 无 | FAIL_CLOSED 核心 |
| 策略变更 | 需重训 | 热加载 <1ms |
| 自演化 | 无 | Proposal → TTL → 闭环 |

**重新定位**: design.md §13.3 从"🔴 竞品"改为"🟡 互补参考"。

### Nous 的学术定位

NeSy 综述给出了三范式分类。Nous 是**范式二（LLM→Symbolic）向范式三（LLM+Symbolic）过渡的桥梁形态**：

- **范式二特征**: fact extraction → Datalog gate（LLM 调符号工具）
- **范式三特征**: 自治理闭环（LLM 与符号系统持续双向交互）
- **推荐定位术语**: **"Iterative LLM-Symbolic Co-Reasoning"**

综述将范式三称为"圣杯问题"。Nous 已经在路上——比大多数停在范式一/二的工作更接近。

---

## 二、从 5 篇论文提炼的设计建议

### 优先级 P0 — 当前里程碑可做

**1. CLAUSE: 资源预算形式化**
为 `nous.gate()` 引入可配置预算（query 深度、扫描实体数、delegate token 上限），替代硬编码 P99 目标。在 M3 引入 LLM delegate 时尤为关键。

**2. CLAUSE: DecisionLog 成本归因**
拆分 `latency_us` 为 `fact_extraction_us / constraint_match_us / delegate_us / entities_scanned / constraints_evaluated`。直接提升 gate 性能的可观测性。

**3. proof_trace 加 provenance 字段**
当前 ProofStep 只有 `(rule_id, matched_facts, verdict)`。加 `provenance: dict?` 可选字段，承载 semiring 语义（布尔/概率/来源追踪），为 Scallop 集成预留。

### 优先级 P1 — M5 前预留

**4. Lobster: 推理后端 trait 抽象**
定义 `ReasoningBackend` 接口（eval_stratum / load_edb / query），支持 Cozo / Scallop / GPU Datalog 可插拔切换。关键：声明哪些关系是 static（hash index 跨请求复用）。

**5. constraint YAML 加 dialect + semantics**
`dialect` 字段（已预留）+ `semantics` 块（logic_algebra / weight_algebra / labeling）。最小扩展方案，向后兼容，支持未来概率/模糊推理。

**6. Lobster: 列式关系表示预留**
gate pipeline 的中间结果支持列式存储转换接口。GPU 后端的必要条件，但 M4 期间只需接口层隔离。

### 优先级 P2 — 长期方向

**7. DeepLog: 代数语义层**
引入显式的代数结构定义（Boolean/Prob/Fuzzy）和标记函数概念。当 Nous 需要概率约束或模糊规则时的架构基础。

**8. NeSy Survey: RL 自改进**
借鉴 SyreLM 的"符号求解器作为 RL 奖励源"，让 Nous 的 gate 判定结果作为 Agent 行为训练的反馈信号。

---

## 三、技术发现速查

### GPU Datalog 现状
- **VFLog**: 200x 是 vs CPU 列存储（VLog/Nemo），vs Soufflé 实际 20-30x
- **Lobster**: 在 VFLog 基础上再快 2x+，且支持概率/可微分
- **两者独立**: VFLog 是低级库无前端，Lobster 有完整 Scallop 前端 + APM IR
- **Nous 不急**: P99 <1ms 的 CPU 场景 GPU 启动开销反而变慢。约束规模 200+ 或需概率推理时再考虑

### Lobster APM 关键洞察
- 无控制流 + SSA + 静态分配 = "合法程序自动高效"
- `static h ← build(...)` 跨迭代复用 hash index → 3-16x 加速核心
- 对 Nous: 约束库基本不变只有 context 变化 → 完美匹配 static index 优化

### DeepLog 核心创新
- 真值-标签分离：同一原子既有 true/false 又有代数标签（概率/模糊分数）
- 扩展代数电路 = NeSy 的 LLVM（统一编译目标）
- 当前 YAML 设计不够：缺代数结构抽象、标记函数概念、真值-标签分离
- 但这是 M6+ 的事，当前 Datalog 精确推理足够

### NeSy 综述关键引用
- **LogicGuide** (Poesia 2024) — 逐步可靠性验证，改进约束检查粒度
- **LLM-Modulo** (Kambhampati 2024) — 最接近 Nous 的规划任务符号反馈框架
- **Chain-of-Symbol** (Hu 2024a) — 中间符号表示压缩，降低 token 成本

### 空白地带（Nous 可填补）
1. 🔴 多模态 NeSy（视觉+语言联合约束推理）— 综述明确指出最大空白
2. 🟡 高级混合架构（范式二→三的工程实现）— Nous 正在做
3. 🟡 NeSy 理论基础（泛化性能、缩放定律）— Nous 可提供实证平台

---

## 四、design.md 具体修改项

| 编号 | 位置 | 修改 |
|------|------|------|
| D1 | §13.3 | CLAUSE 从"🔴 最近竞品"改为"🟡 互补参考" |
| D2 | §13.1 | 增加第四后端: Learned KG Reasoning (CLAUSE 风格 RL 路径发现) |
| D3 | §11 | 增加资源预算目标 (query_depth / entities_scanned / delegate_token_budget) |
| D4 | §12 | DecisionLog 增加 cost_breakdown 字段 |
| D5 | §3 | ProofStep 增加 provenance: dict? |
| D6 | 新增 §14 | "学术定位: Iterative LLM-Symbolic Co-Reasoning" 章节 |

---

*综合分析完成。核心判断：Nous 在学术图谱中的位置比预想的更独特——不是 CLAUSE 的翻版，而是从"Agent 行为治理"这个独特切入点实现 NeSy 范式二→三的过渡。*
