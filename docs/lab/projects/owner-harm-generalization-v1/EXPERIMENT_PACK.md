# Experiment Pack — owner-harm-generalization-v1

## 1. 目标 hypothesis

- **Hypothesis IDs**：H1 vs H2（H3 为资源分配约束）
- **要验证的关键差异**：34 个 Hijacking false negatives 到底主要是 **当前单次调用 gate 的架构性边界**，还是大量属于 **当前架构内本可解决的 addressable failures**。

## 2. 最小研究设计

- **研究对象**：
  - owner-harm v3 held-out 中全部 Hijacking false negatives（当前基数：34）
- **核心任务**：
  1. 逐例复盘每个 FN 的输入形态、信息流路径、恶意指令嵌入方式、gate 当时可见内容
  2. 为每例标注：
     - `structural`: 关键危险信号不在当前单次 gate 的可见范围内
     - `addressable`: 关键危险信号已可见，但当前实现未充分利用
     - `uncertain`: 需要更多实现细节才能下判断
  3. 把 34 例归纳为 reviewer-facing taxonomy：
     - file-embedded injection
     - cross-step / deferred malicious intent
     - tool-mediated hidden context
     - instruction laundering / role indirection
     - other
- **对照 / 证伪方式**：
  - 若大多数样本被标为 `structural`，则支持 H1
  - 若大量样本被标为 `addressable`，则支持 H2，并削弱当前 paper 的边界叙事

## 3. 执行方式

- **输入材料**：
  - held-out Hijacking FN 样本
  - Loop 82/83 日志
  - 当前 paper 的方法与 limitations 表述
- **分析协议**：
  - 先按“gate 实际看到了什么”做可见性分析，再做失败机制归因
  - 禁止先假设“这一定是 structural”，必须逐例给出证据
  - 对每例至少写出：
    - gate 可见信号
    - gate 不可见但决定性信号
    - 为什么当前架构能/不能解决
- **实现依赖**：
  - 不要求新跑高成本 benchmark
  - 优先复用现有日志、样本、结果表

## 4. 成功 / 失败判据

- **成功判据**：
  1. 形成覆盖 34 例的可审计 taxonomy
  2. 能支持 paper 中一条明确、诚实、可防 reviewer 攻击的句子：
     - 要么“这确实是当前架构边界”
     - 要么“并非纯架构边界，我们之前说得太满了”
  3. 给出一个最小架构扩展方向草图（例如 taint tracking / content-aware gating），而不是空泛 future work
- **失败判据**：
  1. 只能给模糊印象，无法逐例回链
  2. taxonomy 依赖主观描述，没有样本级证据
  3. 为了让叙事好看，偷偷把 addressable failures 归进 structural
- **提前停止条件**：
  1. 如果拿不到逐例样本或关键日志，先产出“证据链不足”的审计结论
  2. 如果分析很快发现大部分案例是当前架构可见且可解，则立即停止“强边界”叙事，转为实现不足分析

## 5. 风险

- **方法风险**：
  - “structural” 与 “addressable” 容易被主观划分，必须强制样本级证据
- **叙事风险**：
  - 容易把 limitation 包装成贡献；必须让 falsification 条件足够真实
- **过拟合风险**：
  - 分析过程中可能自然冒出修补想法；本项目禁止顺手修补 held-out

## 6. 次级问题（降级保留，不在本轮主执行）

- KG held-out ablation 仍保留为 P2，但只有满足以下前提才允许重启：
  1. 说清 KG 注入点与 paper 表述是否一致
  2. 加入 `with_flat_context` baseline
  3. 预注册 effect-size threshold
  4. 做最小 power analysis

## 7. 预期输出

- 34 个 Hijacking FN 的样本级判定表
- reviewer-facing failure taxonomy
- 一段可写入 paper 的 architecture-boundary / limitation 文案
- 一份由 Critic 审过的 Review Memo