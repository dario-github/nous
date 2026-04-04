# Hypothesis Pack — owner-harm-generalization-v1

## Top Hypotheses

### H1

- **假设**：34 个 Hijacking false negatives 中，大多数属于 **structural failures**；单次调用 runtime gate 在看到的上下文里原则上缺失了做出可靠判决所需的关键信号，因此当前架构无法稳定拦截这类 prompt injection / hijacking。
- **机制链**：恶意指令被分散、嵌入、跨步传递或藏在 gate 当前不可见的位置 → gate 缺少必要 bits → 不是简单规则或 prompt 微调能补上的 → 需要更强架构（如 taint tracking / content-aware gating / multi-step provenance）。
- **支持证据 ID**：E1, E4, E6
- **反例 / 风险**：如果逐例复盘发现不少样本其实已经把关键危险信号暴露给 gate，只是我们没有利用好，那么这是假边界，不是结构性限制。
- **预期信息增益**：极高——直接决定 paper 的 limitations 和 architecture claim 是否站得住。
- **资源需求**：逐例读取 34 个 Hijacking FN；建立模式 taxonomy；与 paper 当前架构声明对齐。
- **失败条件**：超过少数例外的样本被判定为 addressable by current architecture。

### H2

- **假设**：34 个 Hijacking false negatives 中，有相当一部分并非 structural，而是 **addressable failures**；当前系统其实看到了足够信号，但 rule composition / semantic prompt / context formatting / extraction 方式没有用好。
- **机制链**：危险信号已在 gate 可见范围内 → 当前 heuristic / semantic layer 没有正确利用 → 这些失败不能被诚实地全归因为架构边界。
- **支持证据 ID**：E2, E5, E7
- **反例 / 风险**：如果大多数失败都涉及 gate 当前不可见的信息流，则 H2 不成立。
- **预期信息增益**：高——若成立，当前 paper 的“结构性边界”说法必须收缩，且未来工作优先级要改。
- **资源需求**：与 H1 相同，但更强调每例的“可见信号清单”。
- **失败条件**：逐例分析显示大多数样本在当前单次 gate 视角下缺乏必要信息。

### H3

- **假设**：KG 问题仍然重要，但在当前阶段只是 **次级科学问题**；在没有先讲清 Hijacking 架构边界前，KG 实验即使跑出来，也不会显著提高 paper 的 reviewer 通过率。
- **机制链**：reviewer 首先会追问 prompt injection 失败模式 → KG 只是次级子系统 → 若主失败模式不清楚，KG ablation 的说服力和优先级都偏低。
- **支持证据 ID**：E3, E6, E8
- **反例 / 风险**：如果 reviewer-facing 叙事实际更依赖 KG novelty 而不是 failure analysis，这一排序可能偏差。
- **预期信息增益**：中高——决定本周资源分配是否合理。
- **资源需求**：来自双审计、paper 结构、Loop 82/83 的证据整合。
- **失败条件**：后续 reviewer 预演显示 KG 贡献比 Hijacking 边界更核心。

## Ranking

| Hypothesis | Novelty | Feasibility | Grounding | Info Gain | Verdict |
|---|---|---|---|---|---|
| H1 | 高 | 中高 | 高 | 极高 | continue |
| H2 | 中高 | 中高 | 高 | 高 | continue |
| H3 | 中 | 高 | 高 | 中高 | continue |

## Top-k Decision

- **主保留方向**：H1、H2（形成对 current-architecture-boundary 的可证伪对照）
- **次级方向**：H3（用于约束资源分配与 paper 叙事）
- **kill 方向**：任何“先跑 KG 再说”“先顺手修 hijacking 再分析”的方向；这会重新退化成 benchmark polishing。