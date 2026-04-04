# Team Bootstrap Plan

## 目标

在 30 天内，把 Nous 从“单 agent loop”升级成一个最小可运行的科研实验室系统。

目标不是 30 天内变成 fully autonomous lab，
而是先实现：

- 能控
- 能停
- 能审计
- 能写回
- 能稳定 kill 弱方向

---

## 0. 先回答：哪些旧机制先下线

### 立即降级的旧机制

1. **“Loop 数量 = 进展”**
2. **“长对话 = 研究推进”**
3. **“benchmark 抠细节 = 方法论升级”**
4. **“所有 learnings 都应该记下来”**
5. **“agent 可以自己随时改目标”**

### 先保留但纳入新框架的能力

1. Claude Code 执行能力
2. ARIS 启动与后台跑任务能力
3. benchmark / ablation 运行能力
4. paper drafting / revision 能力
5. git / branch / recovery 收口能力

---

## 1. 第 1 周：搭骨架，不追求聪明

## 本周目标

只做结构，不追求复杂自动化。

### 1.1 固定 5 个角色

- Sponsor / Decision Owner
- Lab Conductor
- Evidence Engine
- Research Worker
- Critic-Archivist

### 1.2 固定 6 个工件模板

必须先落模板：

1. `PROJECT_CHARTER.md`
2. `EVIDENCE_LEDGER.md`
3. `HYPOTHESIS_PACK.md`
4. `EXPERIMENT_PACK.md`
5. `REVIEW_MEMO.md`
6. `LEARNING_RECORD.md`

### 1.3 固定 5 个 Gate

- Problem Gate
- Evidence Gate
- Falsifiability Gate
- Critic Gate
- Stable Learning Gate

### 1.4 定好默认节奏

- 日启动会
- 证据轮
- 研究轮
- 日终评审
- 周五 kill review

## 本周交付

- 角色说明文档
- 模板文件
- 每个 gate 的 pass/fail 标准
- 一份演示用的空项目 skeleton

## 本周禁止事项

- 不上大 swarm
- 不做自动自改编排器
- 不做“自动论文工厂”
- 不同时启动多个大题

---

## 2. 第 2 周：拿 1 个小题跑通闭环

## 本周目标

选一个小而清晰的研究问题，跑完整闭环。

### 2.1 题目要求

必须满足：

- 范围小
- 有现成资料
- 有明确 success metric
- 有 falsifiable output

### 2.2 执行顺序

1. Sponsor 定题
2. Evidence Engine 生成 Evidence Ledger
3. Worker 生成 2–3 个 hypothesis
4. Debate / ranking 选 Top-1/2
5. 生成最小实验或最小分析包
6. Critic 审
7. 输出 Learning Record

### 2.3 成功标准

- 跑完完整闭环
- 不是只停在文献总结
- 至少产出一个 falsifiable artifact
- 至少 kill 一个方向

## 本周交付

- 第一份真实 Evidence Ledger
- 第一份 Hypothesis Pack
- 第一份 Review Memo
- 第一条通过 gate 的 Learning Record

---

## 3. 第 3 周：把 Evidence Engine 变默认入口

## 本周目标

把检索与证据系统从“辅助工具”升级成“默认入口”。

### 3.1 必做能力

Evidence Engine v1 必须支持：

1. query expansion
2. entity normalization
3. citation traversal
4. conflict spotting
5. insufficiency verdict
6. source-linked evidence cards

### 3.2 工程上至少要做到

- 每条核心 claim 带 source id
- 能输出 conflict / gap
- 能说“证据不足”
- 不允许直接替代 hypothesis ranking

### 3.3 成功标准

- 新项目默认先过 Evidence Gate
- worker 不再先自由 brainstorm
- 证据工件可复用、可审计

## 本周交付

- Evidence Ledger v1 模板定稿
- 检索协议 / 查询模板
- contradiction / insufficiency 输出格式

---

## 4. 第 4 周：引入 Critic 和 weekly kill review

## 本周目标

让实验室真正具备：

- 纠错能力
- 止损能力
- 干净写回能力

### 4.1 Critic 机制

Critic 默认检查：

- claim-data consistency
- citation validity
- cherry-picking risk
- overfitting risk
- venue mismatch risk

### 4.2 Weekly Kill Review

周五必须回答：

1. 哪个方向继续
2. 哪个方向 kill
3. 哪个方向需要 shrink
4. 哪些 learning 可以升稳定层

### 4.3 成功标准

- 有明确 kill list
- 有明确 continue list
- 有明确 stable learning list
- 低质量方向能被及时停掉

## 本周交付

- Weekly Research Packet 模板
- Kill Review 模板
- Stable Learning 提交格式

---

## 5. 30 天结束时，系统应具备什么能力

到 Day 30，Nous Lab v1 至少应该具备：

1. 一个固定的 5 角色最小编制
2. 一套稳定工件流
3. 一套 gate 流程
4. 一个默认的 Evidence Engine 入口
5. 一套 weekly kill review 节奏
6. 至少 3 条通过 gate 的 Stable Learnings
7. 至少 1 个完整闭环案例

---

## 6. 哪些 subagents 先建

## 必先建（P0）

### 6.1 Evidence Engine Agent

职责：

- query expansion
- citation traversal
- evidence extraction
- contradiction mining
- insufficiency verdict

为什么先建：

- 它是整个 lab 的默认入口
- 没有它，后面都是 freeform improvisation

### 6.2 Critic-Archivist Agent

职责：

- 审核结论
- 红队检查
- 判定是否写回稳定层

为什么先建：

- 没有它，系统会快速污染 memory

### 6.3 Conductor / AI PI Agent

职责：

- 拆题
- 排工
- 控节奏
- 组织周决策包

为什么先建：

- 没有统一 conductor，系统就会重新退化成“大家各跑各的”

## 第二批（P1）

### 6.4 Hypothesis Tournament Agent

职责：

- 做 pairwise debate
- 做 ranking
- 选 Top-k

### 6.5 Experiment Pack Builder

职责：

- 把 hypothesis 压成最小实验包
- 校验是否可执行

## 第三批（P2）

### 6.6 Bounded Self-Improvement Agent

职责：

- 只改 query policy / prompt policy / templates / reranker
- 禁止改主目标与主评分器

### 6.7 Venue Strategist

职责：

- venue mapping
- 主叙事维护
- 必补证据清单

---

## 7. 默认运行规则

### Rule 1：一次只押 1 个主问题

最多 2 个子问题，避免分散。

### Rule 2：没有 Evidence Ledger，不进入 hypothesis 阶段

### Rule 3：没有 falsifiable artifact，不算研究进展

### Rule 4：没有 Critic 通过，不算实验室结论

### Rule 5：没有 holdout 或外部验证，不写入 Stable Learning

### Rule 6：每周必须 kill 至少 1 个方向

### Rule 7：任何自改进都必须可回滚

---

## 8. 我建议优先拿什么项目试跑

不要一上来就拿大而全的 Nous 主论文全流程。

### 推荐试跑题型

1. **一个 literature intelligence 题**
   - 例如：对某个竞争方向做 evidence map + contradiction map

2. **一个 hypothesis ranking 题**
   - 例如：从 5 个下一步研究方向中选 Top-2

3. **一个最小实验设计题**
   - 例如：把 1 个 hypothesis 压成可运行实验包

### 不推荐作为第一个试跑题的

- 端到端自动写论文
- 多周大项目自动推进
- 没有明确 metric 的开放式探索

---

## 9. 风险清单

### 风险 1：重新退化为单 agent 长对话

对策：
- 强制工件流
- 强制 gate

### 风险 2：证据引擎做成“高级搜索摘要器”

对策：
- 必须输出 conflict 与 insufficiency
- 不允许直接下研究结论

### 风险 3：Critic 变成装饰品

对策：
- 没过 Critic 就不能写回稳定层
- 周五 kill review 必须由 Critic 提供输入

### 风险 4：bounded self-improvement 偷偷变成无边界自改进

对策：
- 白名单模块
- 冻结 holdout
- 人工审批关键改动

### 风险 5：lab 变成内容工厂

对策：
- 只认 artifact
- 只认 holdout / external validation
- 只认 kill / continue 决策

---

## 10. Day 30 后的升级条件

只有在满足以下条件后，才考虑 Nous Lab v2：

1. v1 至少跑通 3 个完整闭环
2. Stable Learning 至少累计 10 条且可复现
3. weekly kill review 连续执行 4 周
4. Evidence Engine 被证明确实减少了无效探索
5. Critic 被证明确实拦住了低质量结论

否则，不应该扩大 agent 数量或增加自动化深度。

---

## 11. 最后的执行原则

> 先做能控的实验室，再做更聪明的实验室。

30 天的目标不是炫技，而是建立一个：

- 不乱跑
- 能止损
- 会学习
- 可复盘
- 能持续升级

的 Nous Lab v1。
