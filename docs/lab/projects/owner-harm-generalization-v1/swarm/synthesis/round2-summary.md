# Swarm Round 2 Summary — owner-harm-generalization-v1

## Round 2 outcome

第二轮没有收敛到“structural-dominant”或“addressable-dominant”的单边共识，但收敛出了一个**更硬、更可审计的最小共识**。

## Minimal consensus

> 当前证据足以说明 Hijacking failures 不是零散噪声，也不是单点 bug；但还不足以把全部 34 个 false negatives 直接定性为“已证实的结构性不可达”。下一步必须做逐样本归因，并辅以轻量干预对照，才有资格判断主导解释到底是 structural 还是 addressable。

## What the team now agrees on

1. **不能把“失败很多”直接升级为“结构性不可达”**
   - 总体 TPR、粗粒度 taxonomy、以及 reviewer 压力都不够构成结论。
2. **也不能把“可能可修”直接当成“主导解释已是 addressable”**
   - 如果没有样本级、可复核、可复现的轻量修补回收证据，addressable 也不能说太满。
3. **真正的分歧核心是证据门槛，不是价值判断**
   - 双方都要求：逐样本证据、可复核分类、以及至少一轮轻量干预对照。

## Most dangerous claim (do not overstate)

最危险、最容易被 reviewer 打穿的一句话是：

> “34 个 Hijacking false negatives 主要是当前 runtime gate 的结构性边界。”

当前版本说太满。可以保留为工作假说，但不能当结论。

## Safer current claim

当前更稳的说法是：

> Hijacking failures 已明确暴露出当前系统的重要盲点，并强烈怀疑其中包含结构性边界；但哪些样本属于结构性不可达、哪些属于当前实现可修，还需要逐样本归因和轻量干预证据来区分。

## Main-agent ruling

主裁决：

- **不接受** 现在就把 34 个 FN 全部写成 structural-dominant 结论
- **也不接受** 现在就把它们默认为 addressable-dominant
- **接受** 以下工作顺序：
  1. 做 34 个 Hijacking FN 的样本级判定表
  2. 设计一组严格受控的轻量干预（prompt / formatting / extraction / rule-composition）
  3. 再决定 paper 中主导叙事应写成“结构性边界主导”还是“可修失败主导”

## Immediate next artifact

下一份应产出的不是更多讨论，而是：

- `hijacking-sample-taxonomy.md`
- 含字段：sample id / visible signals / missing signals / tentative label / why not fix-now / evidence needed
