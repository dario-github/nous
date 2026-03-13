# Nous 自动迭代循环

> 东丞授权：全自动探索-研究-开发-评估-反思循环。不需要咨询。

## Swarm 阵容

| 角色 | 工具 | 调用方式 | 用途 |
|------|------|---------|------|
| **总控** | Opus | cron isolated session | 决策、编排、综合、反思 |
| **批判** | Gemini 3.1 Pro | `gemini -m gemini-3.1-pro "prompt"` | 审查设计/代码，找虚假/注水/过拟合 |
| **架构** | Codex (GPT-5.2) | `codex exec --skip-git-repo-check "prompt"` (pty:true) | 细化架构，写关键代码 |
| **开发** | Sonnet subagent | `sessions_spawn(model="anthropic/claude-sonnet-4-6")` | 批量编码+测试 |
| **开发2** | Mac Claude Code | `nodes.run` → `claude-bedrock.sh` | 仅 Mac 在线时。Bedrock，无成本 |

## 循环结构（每 2 小时）

### Step 1: Review（总控 Opus）
- 读 tasks.md + 上轮 loop-log
- 确定本轮最高优先级

### Step 2: Critique（Gemini 批判）
- `gemini "审查 nous 当前实现的 [具体模块]，找出虚假/注水/方法论问题"`
- 输出写入 /tmp

### Step 3: Design（Codex 架构）
- `codex exec "基于批判结果，细化 [具体功能] 的实现方案"`
- 关注代码架构质量

### Step 4: Implement（Sonnet 开发）
- spawn subagent 写代码 + 测试
- Mac 在线时用 Claude Code

### Step 5: Evaluate（总控 Opus）
- 跑 pytest，对比基线
- AgentHarm benchmark（建立后）

### Step 6: Reflect（总控 Opus）
- 写 loop-log
- 更新 tasks.md
- git push

## 当前方向（2026-03-13 东丞确认）

**路线 B：语义理解引擎**
- gate 要查 KG 理解"操作的是什么"
- 评估机制最重要——对标 AgentHarm benchmark
- 不是关键词匹配，是理解上下文语义

## 优先级队列

1. **评估基础设施** — 接入 AgentHarm benchmark，建立 baseline
2. **KG 语义增强** — 实体属性丰富化 + 关系类型化
3. **语义 gate** — gate 流程增加 KG enrichment
4. **学术对标** — 复现 QuadSentinel/VIRF 关键技术

## 约束

- 每个关键版本提交 GitHub + push
- spec 驱动，更新 tasks.md
- 不偏离主线（语义理解 > 关键词匹配）
- 评估机制最重要
- 结果写 `nous/docs/loop-log-YYYY-MM-DD-NN.md`

## 反作弊机制（2026-03-13 反思后新增）

| 隐患 | 对策 |
|------|------|
| 盲跑 | 第 1 轮**只做** AgentHarm 接入+baseline，后续才有度量 |
| 自评自 | Gemini 批判是**硬门禁**——说有问题就不能 push，先修 |
| 频繁无深度 | 4 小时一轮，每轮必须有可度量的指标变化 |
| 方向漂移 | 每轮开头重读 LOOP.md 方向声明，偏离就停 |
| 优化虚指标 | 每轮反思必须回答："这轮让 Nous 离'理解语义再判断'更近了吗？" |

## 反思模板

```markdown
# Loop N — YYYY-MM-DD

## 做了什么
## 指标变化（before → after）
## 这轮让 Nous 离语义理解更近了吗？
## Gemini 批判了什么？怎么处理的？
## 下次做什么
## 风险/问题
```
