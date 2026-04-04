# Nous Lab v1

## 一句话定义

Nous Lab v1 不是“大群 agent 自由讨论”，而是一个**小规模、可审计、可停机、可写回**的科研团队操作系统。

目标不是自动写完论文，而是持续提高：

- 研究问题质量
- 证据质量
- 实验有效率
- 投稿命中率

---

## 1. North Star

### 我们要优化什么

Nous Lab v1 的 North Star 不是：

- 生成更多 proposal
- 写更长的 paper draft
- 跑更多 loop
- 在现有 benchmark 上多抠一点细节

Nous Lab v1 要优化的是四个结果指标：

1. **更高的问题质量**
   - 研究问题更具体
   - 更可证伪
   - 更接近高价值贡献

2. **更高的证据质量**
   - 结论有来源
   - 冲突被显式发现
   - “信息不足”能被诚实输出

3. **更高的实验有效率**
   - 更少无效实验
   - 更快得到可复现结果
   - 更少“看起来很忙”但无实质推进

4. **更高的投稿匹配度**
   - 主叙事清晰
   - target venue 清楚
   - 必补证据明确

---

## 2. 最小角色编制

Nous Lab v1 只保留 5 个常驻席位。

### 2.1 Sponsor / Decision Owner

**默认对应：Dario**

职责：

- 定题
- 改题
- 停题
- 给预算和成功标准

输入：

- 高层目标
- 风险偏好
- 时间/成本边界

输出：

- Project Charter
- 优先级
- Go / No-Go 决策

约束：

- 必须是唯一最终决策源
- 不直接给 worker 下微观执行命令

### 2.2 Lab Conductor（AI PI）

职责：

- 拆题
- 排任务
- 决定是否拉 specialist
- 汇总结果
- 触发评审

输入：

- Charter
- 历史 memory
- backlog
- 已有证据

输出：

- Task Graph
- Subtask Briefs
- Daily Brief
- Weekly Decision Packet

约束：

- 不能把未经审查的结论写进长期层
- 必须遵守预算、轮次和停止条件

### 2.3 Evidence Engine

职责：

- query expansion
- citation traversal
- evidence extraction
- reranking
- contradiction mining
- insufficiency verdict

输入：

- 研究问题
- 检索预算
- 初始关键词 / 实体

输出：

- Evidence Ledger
- Gap List
- Conflict Map

约束：

- 只输出带来源的证据
- 不直接输出最终结论
- 每个 claim 必须能回链到 source id

### 2.4 Research Worker

职责：

- 基于证据提出 hypothesis
- 设计实验
- 形成分析解释
- 产出最小可执行方案

输入：

- Subtask Brief
- Evidence Ledger
- 评分 rubric

输出：

- Hypothesis Pack
- Experiment Pack
- Analysis Draft

约束：

- 不允许脱离证据自由发挥
- 关键判断必须标注：支持 / 假设 / 未知

### 2.5 Critic-Archivist

职责：

- 红队审查
- 找反例
- 查证据缺口
- 给 pass / fail
- 提炼稳定 learning

输入：

- Hypothesis Pack
- Evidence Ledger
- 历史教训
- 验收标准

输出：

- Review Memo
- Decision Recommendation
- Learning Record
- Playbook Delta

约束：

- 不能和当前轮 Research Worker 是同一实例
- 只有它能把内容提交到 Stable Learning 层

---

## 3. 工件系统

Nous Lab 不围绕聊天记录运转，围绕工件运转。

### 3.1 Charter

回答：

- 问题是什么
- 为什么重要
- 成功标准是什么
- 不允许做什么
- 预算和截止时间是什么

### 3.2 Task Graph

把项目拆成有限节点：

- evidence
- mapping
- hypotheses
- experiment
- review
- write-up

### 3.3 Evidence Ledger

最关键工件。每条证据至少包含：

- source id
- 摘要
- 关键引用段落
- relevance
- confidence
- conflicts
- open gaps

### 3.4 Hypothesis Pack

每个 hypothesis 必须包含：

- hypothesis statement
- mechanism chain
- supporting evidence ids
- falsification path
- expected information gain
- resource estimate
- expected failure modes

### 3.5 Review Memo

Critic-Archivist 给出：

- strongest claim
- weakest link
- counter-evidence
- pass / fail
- continue / shrink / kill recommendation

### 3.6 Learning Record

统一格式：

`Context → Action → Outcome → Evidence → Invalidation`

没有 invalidation boundary 的 learning 不能进稳定层。

---

## 4. 运行节奏

## 4.1 日节奏

### 日启动会

- Sponsor 定 1 个主问题
- 最多 2 个子问题
- Conductor 冻结当天 backlog

产出：

- Daily Brief
- 当日预算
- 停止条件

### 上午：证据轮

Evidence Engine 执行：

1. 窄搜
2. 查询扩展
3. 冲突识别
4. 证据不足判断

若两轮后仍无强证据：

- 标红为“证据不足”
- 不进入大规模推演

### 下午：研究轮

Research Worker：

- 只产 2–3 个候选方案
- 默认只保留前 2 个最可证伪方向

禁止：

- 同时跑 10 个方向
- 产生无限分支

### 日终：评审轮

Critic-Archivist：

- 对当日方案给 verdict
- 标出证据断点
- 决定是否可升格为实验室结论

Sponsor 只做：

- continue
- shrink
- stop

## 4.2 周节奏

- **周一**：定 bet
- **周二**：证据 + mapping
- **周三**：hypothesis + experiment plan
- **周四**：反驳 / 复算 / reviewer check
- **周五**：kill / continue 决策

硬规则：

> 每周必须 kill 至少一个弱方向。

没有 kill list 的 lab 会失控。

---

## 5. 决策门（Gates）

### Gate 1：问题是否足够具体

检查：

- 是否有清晰对象
- 是否可证伪
- 是否有时间和预算边界

失败处理：

- 不进入自动迭代
- 退回 Sponsor 重定义

### Gate 2：是否已有可回链证据

检查：

- 是否有至少一轮 Evidence Ledger
- 核心判断是否有 source id

失败处理：

- 不允许 Worker 自由推演

### Gate 3：假设是否可证伪

检查：

- 是否能设计最小实验/分析去验证
- 是否能给出失败条件

失败处理：

- 视为观点，不视为研究 hypothesis

### Gate 4：Critic 是否通过

检查：

- 是否存在关键反例未处理
- 是否有 cherry-picking 风险
- 是否存在证据空洞

失败处理：

- shrink / revise / kill

### Gate 5：是否值得写入 Stable Learning

检查：

- 是否至少复现一次或经外部验证一次
- 是否写清失效边界

失败处理：

- 保留在 Working Memory
- 不升格为稳定规则

---

## 6. 三层记忆

### 6.1 Raw Trace

内容：

- query
- 抓取结果
- 讨论转录
- 原始日志

特点：

- 只追加
- 不总结
- 用于审计，不用于直接决策

### 6.2 Working Memory

内容：

- 当前项目有效上下文
- open questions
- active hypotheses
- next checks

特点：

- 项目结束可 reset
- 防止脏状态继承

### 6.3 Stable Learning

内容：

- 通过 gate 的规则
- search patterns
- failure patterns
- evaluation rubrics
- protocol upgrades

特点：

- 必须经过 Critic-Archivist 审核
- 必须至少复现一次或外部验证一次

---

## 7. 反失控机制

### 单一 owner 机制

- 只有 Sponsor 能改目标
- 只有 Conductor 能派工
- worker 不直接接收新目标

### 证据先行机制

- 没有 evidence id 的观点默认无效
- 先证据，后 hypothesis

### 有限自治机制

- worker 可提分支
- 但必须回到 Conductor 批准
- specialist 并行数 ≤ 2

### 硬停止机制

建议默认：

- 检索 ≤ 8 次 / 题
- 评审 ≤ 2 轮
- 日内必须出 verdict
- 超预算自动停机并输出“当前最优结论 / 证据不足”

### 写回闸门机制

- agent 不得直接改 Stable Learning
- 所有长期写回都要过 Critic

### Reset 机制

以下情况强制 reset Working Memory：

- 项目切换
- 方向被 kill
- 证据链断裂
- 目标定义变化过大

---

## 8. 为什么这套适合 Nous

Nous 当前最需要的不是更大规模 swarm，而是：

- 防止自己乱跑
- 把“看起来有进展”和“真的有进展”区分开
- 把 benchmark polishing 和学术推进区分开
- 把 learnings 以干净、可回滚的方式写回系统

这套 5 角色结构满足：

- 小团队即可运行
- 可停机
- 可审计
- 可升级
- 与现有 Claude Code / ARIS / subagents 兼容

---

## 9. 成功标准

Nous Lab v1 成功，不是因为它“写了很多文档”，而是因为它在 30 天内做到：

1. 至少 1 个项目跑通完整闭环
2. 有可复用的 Evidence Ledger 模板
3. 有可执行的 Review Memo 模板
4. 有至少 3 条通过 gate 的 Stable Learnings
5. 每周能稳定 kill 弱方向，而不是无限累积方向

---

## 10. 失败标准

以下任一成立，视为 Nous Lab v1 失败：

- 3 天内拿不到像样证据
- 2 周内没有形成可证伪 hypothesis
- 连续 2 次评审被 Critic 否掉
- 项目目标反复漂移
- Stable Learning 被低质量经验污染
- 角色边界失效，重新退化为“单 agent 长对话 + 临场 improvisation”

---

## 11. 最后的原则

> 小团队、强证据、短循环、可停机、可写回。

如果 Nous Lab v1 做不到这五件事，就不要谈更大规模的自动科研。 
