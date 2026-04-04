# Experiment Pack — owner-harm-generalization-v1

## 1. 目标 hypothesis

- **Hypothesis IDs**：H1 vs H2
- **要验证的关键差异**：KG context 在 owner-harm v3 held-out 上是否带来可测的泛化增益，还是 semantic layer 本身已承担主要收益。

## 2. 最小实验设计

- **数据 / 任务**：
  - owner-harm v3 held-out（300 harmful + 150 benign）
  - 按既有 held-out protocol 跑完整三层 gate
- **baseline**：
  1. `with_kg`：当前完整配置（L1+L2+L3 + KG/Cozo context）
  2. `no_kg`：保持其他条件不变，仅禁用 KG / db context
- **ablation**：
  - 主对照：with_kg vs no_kg on held-out
  - 次级归因：按 held-out 8 个子类输出 per-category TPR / FP 变化
- **hidden holdout / 外部验证**：
  - 当前 v3 held-out 视为验证集，不允许为其结果新增规则
  - 若结果支持新叙事，只允许改 paper，不允许改 held-out 任务定义

## 3. 执行方式

- **脚本 / 命令**：
  - 优先复用现有 benchmark runner / `m12_component_ablation.py` 的安全修正版
  - 必须确保 provider 注入逻辑与已修复版本一致，避免 FAIL_OPEN 假阳性/假阴性
- **依赖**：
  - semantic gate provider 可用
  - held-out 数据可读
  - 若 `with_kg` 需要 Cozo / embedded KG，需先确认本机依赖状态
- **预估时间**：
  - no_kg held-out：中等
  - with_kg held-out：取决于 Cozo/KG 依赖恢复情况
- **预估成本**：
  - 属于本周已批准付费实验窗口内

## 4. 成功 / 失败判据

- **成功判据**：
  1. 得到 with_kg 与 no_kg 在 held-out 上的可复现对照结果
  2. 结果足以支持以下三种结论之一：
     - KG 明显帮助 held-out generalization
     - KG 无显著帮助
     - KG 仅对少数子类有帮助
  3. 可将结论写入 paper 的 contribution / limitation / discussion，而不是只停留在内部日志
- **失败判据**：
  1. 依赖/脚本问题导致无法得到可信 with_kg 结果
  2. 结果存在 provider 注入/FAIL_OPEN 一类实现污染，无法解释
  3. 为了追求结果，流程开始诱导修补 held-out 规则
- **提前停止条件**：
  1. 如果 `with_kg` 依赖无法在受控时间内恢复，则先产出“no_kg 已证 + with_kg blocked by dependency”的审计结论
  2. 如果结果解释需要修改 holdout 定义或补规则，则立即停止并记为 overfitting risk

## 5. 风险

- **实现风险**：
  - `with_kg` 路径可能受 Cozo / embedded KG 依赖限制
  - 历史上 ablation script 曾有 provider 注入 bug，必须显式复核
- **评估风险**：
  - training-set no_kg = 0 增益容易被误解成“KG 一直没用”
  - held-out 对照若不输出子类归因，容易得出过度简化结论
- **过拟合风险**：
  - 最大风险不是实验失败，而是看到 held-out 弱点后顺手补规则
  - 本项目禁止把 held-out 当优化目标；只允许测量和归因

## 6. 预期输出

- `with_kg vs no_kg` held-out 总表
- per-category held-out 对照表
- 是否需要修改 paper 中 KG 叙事的 reviewer-facing note
- 一份由 Critic 通过/否决的 Review Memo
