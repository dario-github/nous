# Review Memo — owner-harm-generalization-v1

## Verdict

- **总体结论**：revise
- **是否允许升格为实验室结论**：no（先改向，再补工件）

## Strongest Case For

- 当前项目最可贵的地方是真实存在的不过拟合纪律：明确禁止为了 held-out 指标去反向补规则。
- 现有 error taxonomy（structural vs addressable）本身就有研究价值，优于很多只报分数不解剖失败模式的安全论文。
- 双审计都认可：主问题应从“KG 是否帮助”转向“Hijacking 失败到底是不是当前架构边界”。这个改向能更直接提高 paper 的 reviewer readiness。

## Strongest Case Against

- 原版本把 KG 当主问题，优先级放错了。reviewer 更可能攻击 Hijacking 43.3% TPR，而不是追问 KG 小增益。
- 原版 experiment pack 对 KG 的机制定义不够清楚：如果 KG 真是 post-gate enrichment，则不该影响判决指标。
- 原版 H1/H2 更像二元结果占位，而不是带机制预测的 hypothesis pack。

## Evidence Problems

- **缺失证据**：
  - 34 个 Hijacking FN 的逐例样本级分析
  - 哪些失败是 gate 不可见、哪些其实已可见的证据表
  - reviewer-facing 的最小架构扩展草图
- **证据冲突**：
  - paper 当前对 KG 的表述，与把 KG 当主对照实验的做法存在张力
- **claim-data 不一致**：
  - 如果没有逐例证据，就不能把“Hijacking 是结构性失效”说得太满

## Overfitting / Self-deception Check

- **是否只是抠已有测试集**：当前改向后，目标是解释失败边界，不是继续抠分数；方向正确。
- **是否缺 hidden holdout**：当前分析依赖既有 held-out，不新增 hidden holdout；可接受，因为主任务是边界剖析而非继续优化。
- **是否存在“看起来很忙”但无 artifact**：存在过。双审计结论出来后没有立即落盘，就是一次 artifact discipline 失守；本 memo 与 learning record 用于纠正这一点。

## Recommendation

- **continue / shrink / kill**：continue after revise
- **如果继续，下一步只允许做什么**：
  1. 先完成 34 个 Hijacking FN 的样本级 taxonomy
  2. 再写 reviewer-facing limitation / architecture-boundary 文案
  3. KG 问题仅保留为 P2，不得抢占本周主精力