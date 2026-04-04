# Hypothesis Pack — owner-harm-generalization-v1

## Top Hypotheses

### H1

- **假设**：KG context 在 owner-harm v3 held-out 上提供了训练集看不到的补充语义/关系信息，因此在 with_kg vs no_kg 对照中会出现可测的 held-out generalization 增益。
- **机制链**：held-out 中存在更多跨实体、跨步骤、隐含关系型伤害模式 → rules-only 无法覆盖 → semantic layer 需要上下文增强 → KG 提供实体/关系补充，提升判断质量。
- **支持证据 ID**：E1, E2, E4
- **反例 / 风险**：training set 上 no_kg = 0 损失增量（E3）说明 KG 很可能只是“架构舞台布景”；如果 held-out 也无收益，则该假设失败。
- **预期信息增益**：高——直接决定是否继续押注 KG 作为论文有效组件。
- **资源需求**：一次受控 held-out with_kg / no_kg 对照实验；可能需要 Cozo / KG 依赖环境恢复。
- **失败条件**：with_kg 与 no_kg 在 held-out 上无显著差异，或 KG 反而拖累结果。

### H2

- **假设**：KG 在当前 Nous 中并未构成有效检测能力，held-out 的主要收益几乎全部来自 semantic layer 本身，KG 应从“当前贡献”降级为“未来探索方向”。
- **机制链**：semantic gate 本身提供大部分泛化能力 → KG 没有额外提供可用信息，或信息注入方式不足以影响决策 → training set 和 held-out 都不会看到 KG 带来的可测收益。
- **支持证据 ID**：E2, E3, E5
- **反例 / 风险**：若 held-out 某些 structural failure 依赖实体敏感度/关系信息，则 KG 可能在局部子类有真实帮助。
- **预期信息增益**：高——若成立，论文叙事和方法论押注都要及时收缩。
- **资源需求**：与 H1 相同；关键是 held-out 直接对照与子类归因。
- **失败条件**：held-out 上 with_kg 对关键子类出现稳定增益，且可复现。

## Ranking

| Hypothesis | Novelty | Feasibility | Grounding | Info Gain | Verdict |
|---|---|---|---|---|---|
| H1 | 中 | 中 | 中高 | 高 | continue |
| H2 | 中 | 高 | 高 | 高 | continue |

## Top-k Decision

- 保留方向：H1、H2（它们形成一个可证伪的核心对照，而不是两个互不相干方向）
- kill 方向：任何“先去修 held-out addressable gaps 再看 KG”的方向；这会把验证项目退化成 benchmark overfitting。
