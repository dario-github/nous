# Brief — Round 1

## Question

我们要回答的不是“怎么立刻修好 hijacking”，而是：

> **34 个 Hijacking false negatives 是否主要反映了当前单次调用 runtime gate 的真实架构边界？**

## Why this matters

- 这是当前 paper 最会被 reviewer 追问的弱点
- 双审计（Gemini + Opus）都要求把这个问题优先级提升到 P0
- 如果讲不清，这篇 paper 会像在回避最关键失败模式

## Current project stance

- P0：Hijacking failure characterization
- P2：KG held-out ablation（暂缓）
- 不允许为了 held-out 指标去反向补规则
- 不允许把本轮讨论偷换成“顺手修 hijacking”

## Available evidence snapshot

- v3 held-out 上 Hijacking TPR 约 43.3%
- 34 个 Hijacking false negatives 是当前主分析对象
- Loop 82/83 已做 structural vs addressable 的初步划分框架
- 双审计认为：当前最关键的是把 reviewer-facing 的边界分析做硬

## Deliverable for this round

每个角色都必须回答：
1. 你当前更支持 `structural-dominant` 还是 `addressable-dominant`？
2. 你最强的支持理由是什么？
3. 你最担心的自欺风险是什么？
4. 要让你改变主意，最需要哪类证据？

## File conventions

- 角色独立输出写到 `round1/<role>.md`
- 公共反驳写到 `shared/objections.md`
- 证据清单写到 `shared/evidence-map.md`
- 改变想法写到 `shared/changed-my-mind.md`

## Roles for round 1

- proposer：尽可能为“structural-dominant”构建最强论证
- critic：尽可能攻击“structural-dominant”并寻找 addressable 解释
- skeptic：专查 claim 和 evidence 是否错配
- reviewer-sim：从 reviewer 视角判断哪种说法更可发表
