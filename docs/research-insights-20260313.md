# Nous 学术启示笔记 — 2026-03-13

> 来源：东丞调研 Datalog/KG/NeSy 前沿文献后的 6 条启示
> 落盘：对应到 Nous 当前设计的具体影响

---

## 1. Rust + Datalog 路线验证

**信号**：Nemo (Rust)、CozoDB (Rust)、VFLog (Datalog GPU)、Lobster (Datalog GPU) 全部指向 Datalog 是正确的推理基座。

**对 Nous 的影响**：
- 当前选型 Cozo（Rust 引擎 + Python binding）方向正确
- 纯 Python 策略是正确的务实选择（cozo-embedded wheel 已经是 Rust 内核）
- 如果未来需要 Rust 扩展（自定义算子/性能关键路径），基座已经在那里

**行动**：无需立即改动。设计验证 ✅

---

## 2. Scallop Provenance Semiring

**论文**：Scallop — 可微分 Datalog 框架，核心创新是 provenance semiring（来源半环）

**为什么重要**：
- 决策图谱不只需要"决策是什么"，还需要"为什么是这个决策"
- 当前 proof_trace 只记录匹配的规则链 + 事实绑定（M1.9）
- Semiring 抽象可以统一多种"为什么"：布尔（是否匹配）、概率（多大可能性）、来源（哪些事实贡献了）、可微分（梯度传播）

**对 Nous 的影响**：
- design.md §12 已预留 Scallop 插槽（开放决策 #5）
- **具体建议**：在 proof_trace 接口设计中预留 provenance 字段
  - 当前：`ProofStep(rule_id, matched_facts, verdict)`
  - 扩展：`ProofStep(rule_id, matched_facts, verdict, provenance: dict?)`
  - provenance 字典可以承载 boolean/probabilistic/differentiable 标签
- M5+ 引入 Scallop 时，只需填充 provenance 字段，不改接口

**行动**：M2.10 双写期间，给 proof_trace 加 `provenance` 可选字段。低成本，高预留价值。

---

## 3. 增量推理是必须的

**信号**：RDFox 证明实时场景下全量重算不可行。

**当前状态**：
- M1.3 增量同步 ✅（文件 mtime vs DB updated_at，无变更 <200ms）
- 但这是**数据层增量**，不是**推理层增量**
- 当前 gate 每次调用都是：extract_facts → load_constraints → match → verdict
- 约束集小（5-20 条）时没问题，但约束集增长到 100+ 或 KG 节点 1000+ 时，全量 match 会成瓶颈

**对 Nous 的影响**：
- Cozo 本身支持 materialized view（`?[...] := ...` stored relations），但没有自动增量物化
- **短期（M2-M4）**：约束集 <50，全量 match P99 <5ms，不是瓶颈
- **中期（M5+）**：需要增量物化策略
  - 选项 A：Cozo 手动维护 stored relations + trigger 更新
  - 选项 B：引入 RDFox 增量推理层作为 Cozo 上层
  - 选项 C：Scallop 增量 Datalog 编译

**行动**：在 design.md 增加"增量推理路线图"章节。M4 期间开始 benchmark 约束集规模。

---

## 4. GPU 路线预留

**论文**：Lobster (2503.21937) — Abstract Plan Machine (APM)，把声明式 Datalog 编译到 GPU 并行执行

**为什么重要**：
- 当 KG 规模达到万级实体 + 百条推理规则，CPU Datalog 可能不够
- Lobster 的 APM 是一个好参考：如何把 Datalog 规则分解为可并行的执行计划
- VFLog (2501.13051) 提供了 GPU Datalog 的底层基础设施

**对 Nous 的影响**：
- M0-M4 不需要 GPU（P99 <1ms，CPU 足够）
- 但 M5 政府决策 POC 如果要处理大规模政策网络，可能需要
- **架构预留**：gate pipeline 的 `match_constraint` 步骤应该是可插拔的
  - 当前：Python 遍历约束列表
  - 未来：可替换为 GPU Datalog 引擎

**行动**：确认 gate pipeline 的 matcher 是可插拔接口（目前 `match_constraint` 函数签名即可）。无需立即改动。

---

## 5. CLAUSE — 最接近 Nous 的学术工作

**特征**：agentic reasoning + KG + context engineering

**为什么重要**：
- 如果 CLAUSE 已经做了类似的事，Nous 需要明确差异化
- 可能有设计决策可以直接借鉴，避免重复踩坑

**行动**：🔴 **需要细读 CLAUSE 论文**。优先级高于 Lobster/VFLog（那两个是工程参考，CLAUSE 是架构竞品）。建议安排一个 research session 专门精读。

---

## 6. DeepLog 统一中间表示

**问题**：如果 Nous 未来支持多种推理后端（精确 Datalog / 概率 Scallop / 可微分 NeSy），需要统一的中间表示层。

**对 Nous 的影响**：
- 当前：约束定义 = YAML → Cozo Datalog 查询字符串
- 未来：同一条约束可能需要编译到不同后端
  - 精确推理：Cozo Datalog
  - 概率推理：Scallop semiring
  - GPU 加速：Lobster APM

**具体建议**：
- 约束 YAML 已经是一种中间表示（verdict + patterns + priority）
- 关键是 **`rule_body` 字段不能硬绑 Cozo 语法**
- 建议：rule_body 改为结构化 JSON（patterns 已经是了），后端编译器负责翻译
  - 当前大部分约束用 `patterns`（结构化），只有高级规则用 `rule_body`（原始 Datalog）
  - 对 `rule_body` 引入 `dialect` 字段：`dialect: cozo` / `dialect: scallop` / `dialect: lobster`

**行动**：在 constraint YAML 格式中加 `dialect` 可选字段（默认 `cozo`）。低成本预留。

---

## 必读论文优先级

| 优先级 | 论文 | 原因 | ID |
|--------|------|------|------|
| 🔴 P0 | CLAUSE | 最接近 Nous 的架构竞品（Agentic NeSy KG） | OpenReview 97Qk741ih6 |
| 🟡 P1 | Lobster | GPU+Datalog+NeSy 工程参考 | 2503.21937 |
| 🟡 P1 | VFLog | GPU Datalog 基础设施 | 2501.13051 |
| 🟡 P1 | NeSy for LLM Reasoning | 三范式综述，定位 Nous 在学术图谱中的位置 | 2508.13678 |
| 🟢 P2 | DeepLog | 统一 NeSy 表示层 + 代数电路 | 2508.13697 |
| 🟢 P2 | Scallop | 可微分 Datalog + provenance semiring | 已知 |
| 🟢 P2 | RDFox | 增量推理工程实践 | 商业系统 |

---

*2026-03-13 东丞调研启示 → 晏落盘*
