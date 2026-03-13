# Nous 自动迭代循环

> 东丞授权：全自动探索-研究-开发-评估-反思循环。不需要咨询。

## 循环结构

每次迭代包含 5 步：
1. **Review** — 读 spec/tasks/上次反思，确定本轮最高优先级
2. **Research** — 搜索学术 SOTA 中可复现的具体技术
3. **Implement** — 写代码 + 测试，小步提交
4. **Evaluate** — 跑测试 + 对比基线 + 记录指标变化
5. **Reflect** — 写反思：做了什么、学到什么、下次做什么

## 当前方向（2026-03-13 东丞确认）

**路线 B：语义理解引擎**（不是关键词匹配）
- gate 要查 KG 理解"操作的是什么"，不是只匹配 action_type
- KG 要有真实的、有意义的知识
- 评估机制最重要——对标 AgentHarm/QuadSentinel benchmark

## 优先级队列

1. **评估基础设施** — 接入 AgentHarm benchmark，建立 baseline
2. **KG 语义增强** — 实体属性丰富化 + 关系类型化 + 推理深度
3. **语义 gate** — gate 流程增加 KG enrichment 步骤
4. **学术对标** — 复现 QuadSentinel/VIRF 的关键技术

## 约束

- 每个关键版本提交 GitHub
- spec 驱动，更新 tasks.md
- 不偏离主线（语义理解 > 关键词匹配）
- 评估机制最重要
- 结果写 `nous/docs/loop-log-YYYY-MM-DD-NN.md`

## 反思模板

```markdown
# Loop N — YYYY-MM-DD

## 做了什么
## 指标变化（before → after）
## 学到什么
## 下次做什么
## 风险/问题
```
