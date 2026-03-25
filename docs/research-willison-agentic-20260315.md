# Simon Willison — Agentic Engineering (Pragmatic Summit 2026)

> 来源: https://simonwillison.net/2026/Mar/14/pragmatic-summit/
> 沉淀: 2026-03-15

## 与 Nous 相关的关键观点

### Lethal Trifecta（致命三合一）
模型能访问私密数据 + 暴露于恶意指令 + 有外泄渠道 = 灾难。
Prompt injection 至今无解（不像 SQL injection 有参数化查询）。
→ **Nous 的三层 gate 是工程化 mitigation，不是完美解但比 prompt 禁令强得多。**

### TDD for Agents
"测试现在免费了，不写测试是可怕的选择。"
→ 与 Nous 的 pytest 门禁一致。

### Sandboxing > 信任
Simon 自己都在 Mac 上 YOLO 跑 --dangerously-skip-permissions。
→ 说明即使专家也会在便利性面前放弃安全。Nous 的价值：**不靠自觉，靠机制。**

### 不读代码的时代
StrongDM: nobody writes code, nobody reads code — "clear insanity" 但值得关注。
→ 如果人不读代码了，谁来审查 agent 行为？Nous 的自动化审查变得更重要。
