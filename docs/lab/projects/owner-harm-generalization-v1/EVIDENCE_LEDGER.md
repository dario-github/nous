# Evidence Ledger — owner-harm-generalization-v1

> 规则：没有 source id 的关键判断默认无效。

## Evidence Cards

| ID | Claim / Fact | Source | Evidence Snippet | Relevance | Confidence | Conflicts | Gaps |
|---|---|---|---|---|---|---|---|
| E1 | 在 v3 held-out 上，L1+L2-only 仅达到 12.7% TPR / 6.7% FPR，说明 rules-only 在 harder unseen set 上明显不足。 | `docs/loop-log-2026-04-04-82.md` | “L1+L2 only: TPR 12.7% / FPR 6.7% … L3 contribution +62.6pp” | 高 | 高 | 与 training-set 100%/0% 形成张力 | 还缺 with_kg vs no_kg on held-out 的直接对照 |
| E2 | 在 v3 held-out 上，完整 L1+L2+L3 达到 75.3% TPR / 3.3% FPR，且 L3 的增益高于 v2。 | `docs/loop-log-2026-04-04-82.md`, `paper/main.tex` | “L3 的贡献在更难的数据集上更大（62.6pp vs v2 的 45.4pp）” | 高 | 高 | 暂无直接冲突 | 需要区分 L3 中 semantic reasoning 与 KG context 的相对贡献 |
| E3 | 在 owner-harm training set 上，`no_kg` 结果为 100% / 0% / L=0，说明 KG 在 training set 上没有边际检测价值。 | `docs/loop-log-2026-04-04-83.md` | “no_kg (db=None) … 100.0% / 0.0% / L=0.0 … KG adds zero marginal detection value on the training set.” | 高 | 高 | 容易被误读为“KG 完全没用” | 训练集结果不能直接外推到 held-out generalization |
| E4 | Loop 82 的 error taxonomy 将 held-out failures 拆成 structural 与 addressable，两类问题提示“继续修规则”不是正确主线。 | `docs/loop-log-2026-04-04-82.md`, `paper/main.tex` | “46.8% structural vs 53.2% addressable … deliberately NOT fixed to avoid held-out overfitting.” | 高 | 高 | 与“继续刷 held-out 规则”相冲突 | 需要明确 KG 是否帮助 structural 类失败 |
| E5 | 论文当前主叙事更像 runtime policy-enforcement layer for preventing owner-harm，而不是 benchmark paper。 | `docs/NOUS_LAB_V1.md`, `docs/AUTO_RESEARCH_V2.md`, `paper/main.tex` | target venue / narrative 已收束到 SaTML / USENIX 路线 | 中 | 中高 | 若 KG 没帮助，需改写一部分叙事 | 需要更强证据支撑“为什么三层结构仍然必要” |
| E6 | 当前最大科学问题不是再修 benchmark，而是回答 KG 在 held-out generalization 中是否有真实价值。 | `docs/lab/projects/owner-harm-generalization-v1/PROJECT_CHARTER.md` | 项目问题已固定为 “Does KG context improve held-out generalization on owner-harm v3?” | 高 | 高 | 暂无 | 需要形成最小实验包并通过 Critic |

## Conflict Map

- **C1**：training set 上 KG = 0 边际价值（E3），但 held-out 上 semantic layer 整体增益很大（E1/E2）。冲突点不在于“L3 有没有用”，而在于“KG 是否是 L3 有效性的必要组成部分”。
- **C2**：runtime enforcement 主叙事（E5）依赖 compositional story；若 KG 在 held-out 仍无帮助，则需将 KG 从“当前有效组件”降级为“未来 generalization direction”。

## Gaps / Insufficiency

- **G1**：缺少 with_kg vs no_kg on v3 held-out 的直接对照结果。
- **G2**：缺少“KG 主要帮助哪一类 held-out failure”的子类分析。
- **G3**：缺少 Critic 视角结论：若 KG held-out 无效，paper 应如何诚实改写贡献边界。

## Working Summary

- 当前最强证据：rules-only 在 held-out 上明显不足（E1），完整系统在 held-out 上显著更强（E2），但 training set 上 KG 无边际价值（E3）。
- 当前最弱证据：KG 是否对 held-out generalization 有帮助，目前没有直接数据。
- 当前不能下结论的点：不能说 KG 有用，也不能说 KG 无用；真正缺的是 held-out 对照。 
