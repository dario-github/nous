# Spec Gap Analysis: Loop 方向 vs OpenSpec User Story

> 2026-03-18 03:58 CST — required对齐

## 问题

Loop 33-36 做了三件事，没有一件在 spec 里程碑中有对应：

| Loop | 做了什么 | 对应 Spec 里程碑 |
|------|---------|----------------|
| 33 | Challenge benchmark + DeepSeek-V3.1 测试 | M8.6 Judge 模型选型（部分对应） |
| 34 | Semantic gate model swap qwen-turbo → V3.1 | M8.6（部分对应，但选了旧版本） |
| 35 | Triviality filter 52-2 FP 修复 | 无对应里程碑 |
| 36 | Intent Decomposition 全新架构 | **完全不在 spec 中** |

## 根因

1. **LOOP.md 循环结构取代了 spec 驱动**：每 2h 的 cron 循环按 loop-state.json 的 urgent 字段决定方向，而不是回 tasks.md 检查下一个未完成项
2. **urgent 字段由上一轮 Opus 自己设**：形成了自我参照的闭环——每轮的方向由上轮决定，spec 从未被检查
3. **没有 spec 守门人**：缺少一个机制在每轮开始时检查"这个方向在 spec 的哪个里程碑？"

## 应该在做什么？

按 tasks.md 未完成项，真正该推进的：

### 高优先级（spec 明确要求）
- **M8.6b** — Capability 指标完善（benign 任务多步完成率）← **这是 loss function 的盲区**
- **M7.2** — 关系类型化（56 实体的 RELATED_TO → 9 种类型化关系）
- **M7.3** — LLM delegate 路径（Datalog 未命中 → KG 上下文 → LLM 判断）
- **M9.1** — T 规则映射（AGENTS.md T1-T15 → Nous constraint YAML）

### 中优先级
- **M8.8-10** — Curriculum Phase 退出条件验证
- **M2.10** — GT v3 回归 + 双写一致率 >99% 持续 14 天

### Loop 做的事该归到哪里
- Intent Decomposition → 应该先写 OpenSpec proposal，经过 Swarm 审计再实施
- Model swap → M8.6 的子任务，但应该搜索最新模型（T1 违规）
- Triviality fix → 合理的 bugfix，不需要里程碑

## 纠正措施

1. **每轮 loop 开始必须检查 tasks.md**，而不是只看 loop-state.json urgent
2. **新方向必须先写 spec proposal**：Intent Decomposition 应该有自己的 OpenSpec 变更
3. **LOOP.md 增加 spec 检查步骤**：Step 0.5: Read tasks.md → 确认当前方向对齐
4. **urgent 字段不能只由 Opus 自设**：需要 Gemini 批判确认方向合理性

## 立即行动

- [ ] DeepSeek-V3.2 替换 V3.1，跑 val benchmark ← 进行中
- [ ] Intent Decomposition 提交 GPT-5.4 + Gemini 全局审计 ← 进行中
- [ ] Capability 指标补测方案（M8.6b）
- [ ] LOOP.md 增加 spec 对齐步骤
- [ ] Intent Decomposition 写 OpenSpec proposal（如果审计通过）
