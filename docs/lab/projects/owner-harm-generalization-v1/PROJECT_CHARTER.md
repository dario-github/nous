# Project Charter — owner-harm-generalization-v1

## 1. 问题定义

- **项目名**：owner-harm-generalization-v1
- **一句话问题**：KG context 是否能在 owner-harm v3 held-out 上提升真正的泛化，而不是只在训练集上制造“看起来有架构”的效果？
- **为什么现在值得做**：Nous 当前已经知道训练集上 `no_kg = ΔL 0.0`，但真正关键的科学问题是 KG 对 harder held-out 的语义层是否有帮助；这直接关系到论文的真实性、叙事完整性、以及是否还要继续押注 KG。
- **和 Nous 主线的关系**：这是当前 owner-harm / runtime safety 主线中最重要的科学问题之一，优先于继续在已有训练集上修规则。

## 2. 成功标准

- **主要 success metric**：在 v3 held-out 上得到 with_kg vs no_kg 的可信对照结果，并能支持或否定“KG 帮助 held-out generalization”这一命题。
- **次要 success metric**：将结果写入 paper 主叙事与 limitations，而不是只停留在内部日志。
- **什么结果也算有价值**（负结果/证伪）：证实 KG 无帮助，或只在极少子类帮助；这同样是高价值负结果。

## 3. 约束

- **时间预算**：优先在本周内完成首轮结论
- **成本预算**：一周内付费实验已获批准，但仍需受控
- **不可做事项**：不允许为了 held-out 指标去反向补规则；不允许修改 holdout 定义来迎合结果
- **过拟合防线**：held-out 只作验证，不作规则打补丁目标；若发现 addressable gaps，只记录，不立即修补

## 4. 目标产出

- [ ] Evidence Ledger
- [ ] Top-k Hypotheses
- [ ] Minimal Experiment Pack
- [ ] Review Memo
- [ ] Learning Record

## 5. 决策门

- **Gate 1（问题是否足够具体）**：是。问题已收缩为“KG 对 held-out generalization 是否有真实边际贡献”。
- **Gate 2（是否已有可回链证据）**：是。已有 Loop 82/83 结果、v3 held-out baseline、training-set no_kg 结果、paper 当前叙事。
- **Gate 3（是否可证伪）**：是。通过 with_kg vs no_kg on v3 held-out 对照可直接证伪。
- **Gate 4（Critic 是否通过）**：待执行。

## 6. 当前默认 target venue / narrative

- **主叙事**：runtime policy-enforcement layer for preventing owner-harm in tool-using LLM agents
- **目标 venue**：SaTML 主路；USENIX Security 为冲高备选
- **当前最缺的证据**：KG 是否对 held-out generalization 有真实帮助；如果没有，必须诚实改写语义层/KG叙事

## 7. Sponsor 决策

- **continue / revise / stop**：continue
- **备注**：执行时必须遵守“不能在已有测试集上扣细节、不能过拟合”的总约束。
