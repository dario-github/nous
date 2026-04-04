# Auto Research v2

## 一句话定义

Auto Research v2 不是“自动写论文流水线”，而是一个**有外部真值约束的研究迭代引擎**。

它的核心目标是：

- 更高质量的研究问题
- 更可信的证据链
- 更少无效实验
- 更清晰的投稿叙事

---

## 1. v1 的主要问题

Auto Research v1 的典型问题：

1. **单 agent 长对话推进**
   - 看起来在推进
   - 实际很难审计、很难停机、很难比较方案优劣

2. **benchmark polishing 容易伪装成研究进展**
   - 在现有测试集上抠细节
   - 但没有更强的方法论升级

3. **没有分层评分器**
   - idea、evidence、experiment、write-up 混在一起
   - 导致“会说”常被错当“会研究”

4. **没有 bounded self-improvement**
   - 改进没有边界
   - 很容易过拟合 scorer / benchmark

5. **长期学习层污染风险高**
   - 一次偶然成功容易被写成稳定规律

---

## 2. v2 的设计原则

### 原则 1：想法层与执行层分离

想法层回答：

- 研究什么
- 为什么值得做
- 哪个 hypothesis 更值得下注

执行层回答：

- 能不能跑通
- 是否优于 baseline
- 是否在 holdout 上有效

### 原则 2：先证据，后假设

没有带来源的 evidence，不进入 hypothesis ranking。

### 原则 3：只在可机判模块上做自改进

允许自改进的模块：

- query policy
- reranker
- prompt policy
- experiment template
- reviewer rubric
- execution scripts

不允许直接无约束修改：

- 总目标
- 主评分器
- 最终验收标准
- 长期记忆准入机制

### 原则 4：分阶段、可评分、可淘汰

每轮都必须有：

- artifact
- rubric
- stop condition
- kill condition

### 原则 5：冻结 holdout

所有真正的“升级”都必须过冻结 holdout。

---

## 3. v2 的 7 步闭环

## Step 1：Problem Framing

### 输入

- 研究主题
- 预算
- 时间上限
- baseline
- 不可做事项

### 输出

- Task Card

### 核心问题

- 这个问题是否可证伪？
- 是否有 success metric？
- 是否存在 holdout 或外部验证路径？

### 评分器

- clarity
- falsifiability
- measurable success
- scope fit

### 停止条件

如果没有明确 success metric，不进入自动迭代，只能转为人工研究辅助。

---

## Step 2：Parallel Candidate Generation

### 输入

- Task Card
- 初始文献 / 数据 / 代码

### 输出

- 候选 hypothesis 列表
- 候选实验路线
- 每条路线的 evidence ids

### 推荐机制

- Orchestrator–Workers

### 评分器

- coverage
- deduplication quality
- grounding quality
- relevance

### 停止条件

- 新候选的边际增益明显下降
- 或达到查询/成本预算

---

## Step 3：Debate + Tournament Ranking

### 输入

- 候选 hypothesis 集合

### 输出

- Top-k hypotheses
- 每个 hypothesis 的主要反驳点
- 关键不确定性

### 推荐机制

- Generate–Debate–Evolve
- pairwise tournament

### 评分器

- novelty
- feasibility
- grounding
- expected information gain
- pairwise win rate

### 停止条件

- 排名前列稳定
- 新增 debate 不再改变前列顺序

---

## Step 4：Minimal Executable Experiment Design

### 输入

- Top-k hypotheses

### 输出

- Experiment Pack
  - 数据
  - baseline
  - ablation
  - 运行脚本
  - 风险说明

### 推荐机制

- Evaluator–Optimizer

### 评分器

- completeness
- executability
- variable control
- reproducibility readiness

### 停止条件

- 方案通过 rubric
- 具备一键运行或最小人工介入运行条件

---

## Step 5：Execution + External Validation

### 输入

- Experiment Pack

### 输出

- 结果表
- 运行日志
- 失败案例
- 成本记录

### 评分器

- did it run
- baseline delta
- holdout delta
- variance
- compute-to-gain ratio

### 停止条件

- 连续两轮无实质提升
- 达到预算上限
- holdout 无增益

---

## Step 6：Review + Attribution

### 输入

- 结果表
- 中间轨迹
- 证据链

### 输出

- Review Memo
- 结论可信度
- 继续 / 收缩 / 停止建议

### 评分器

- claim-data consistency
- hallucination rate
- cherry-picking risk
- spot-audit consistency

### 停止条件

- 结论可信度达标
- 或被判定“不值得继续”

---

## Step 7：Bounded Self-Improvement + Archive

### 输入

- 整轮轨迹
- 失败模式
- 成功策略

### 输出

- 更新后的 query / prompt / rubric / template / tool policy
- 策略谱系归档

### 评分器

- frozen holdout gain
- transfer to adjacent tasks
- reduction in wasted experiments
- rollback safety

### 停止条件

- 只提升公开 benchmark、未提升真实任务
- 修改触及主评分器 / 主目标时，必须人工审批
- 未过 holdout 的改动不得晋级

---

## 4. 分层评分器体系

## 4.1 想法层评分器

用于 hypothesis / direction ranking。

### 必选维度

- novelty
- feasibility
- grounding
- expected information gain

### 推荐形式

- pairwise ranking 优于单标量分数
- rubric + 对抗辩论 优于直接打总分

### 不应单独依赖

- “语言上是否听起来合理”
- “是否像一个好摘要”

---

## 4.2 执行层评分器

用于实验与实现层。

### 必选维度

- 可运行性
- 可复现性
- baseline 改善
- holdout 改善
- 成本效率

### 推荐形式

- executable checks
- hidden holdout
- delayed feedback

---

## 4.3 写作层评分器

用于 proposal / paper / response refinement。

### 必选维度

- evidence completeness
- citation validity
- internal consistency
- claim calibration
- venue fit

### 注意

写作层评分器只能做局部优化，不能替代科研层评分器。

---

## 5. 关键计划双审计机制

关键计划默认必须经过 **Gemini 3.1 Pro + Opus** 双模型批判审计，不能只过单模型。

### 5.1 什么算“关键计划”

以下任一命中，即视为关键计划：

- 改变研究主方向
- 改变论文主叙事 / target venue
- 启动新的高成本实验线
- 修改主评分器 / 主验收口径 / holdout 设计
- 改写长期 playbook / Stable Learning 准入规则
- 引入新的实验室角色、gate、核心 protocol

### 5.2 双审计分工

#### Gemini 3.1 Pro

负责：

- 外部资料对照
- 大上下文一致性检查
- 漏掉的重要相关工作 / 反例 / alternative framing
- 研究路线是否脱离 SOTA

#### Opus

负责：

- 关键论证链是否站得住
- 方案内部矛盾
- reviewer 视角的攻击面
- 计划是否其实在自嗨 / 过拟合 / 假创新

### 5.3 双审计输出要求

每次双审计至少输出：

- strongest case for the plan
- strongest case against the plan
- missing evidence
- kill / continue / revise recommendation

### 5.4 通过条件

关键计划只有在以下条件满足时才能晋级执行：

1. Gemini 3.1 Pro 完成外部一致性与 SOTA 对照审计
2. Opus 完成批判性 / reviewer 视角审计
3. 两者的关键反对意见都被显式记录
4. Sponsor 明确选择：continue / revise / stop

若只完成单边审计，则只能视为“草案”，不能视为正式计划。

---

## 6. 反过拟合机制

Auto Research v2 必须默认内置以下反过拟合设计。

### 5.1 Hidden Holdout

- holdout 不能频繁改
- agent 不能完全看见 scorer
- 真正升级只看 holdout 表现

### 5.2 Freeze the Evaluator

- scorer 冻结一段时间
- 不允许一边优化一边改评测标准

### 5.3 Artifact Requirement

每轮必须至少产出一种 falsifiable artifact：

- 新 hypothesis
- 可运行脚本
- 结果表
- ablation
- venue comparison note

### 5.4 External Audit

- 人类 spot audit
- 引用核验
- 复现实验
- 成本核算

### 5.5 Kill Weak Directions

- 每周必须 kill 至少一个方向
- 不允许 backlog 无上限膨胀

---

## 6. Nous 中适合采用的机制

### 适合直接采用

1. **Orchestrator–Workers**
   - 用于 literature scan、baseline mapping、实验分工

2. **Debate + Tournament**
   - 用于 hypothesis ranking 与研究方向选择

3. **Evaluator–Optimizer**
   - 用于实验计划、proposal、写作局部精修

4. **Bounded evolutionary loop**
   - 仅用于 query policy、reranker、experiment templates、scripts

### 不适合直接照搬

1. **端到端 AI Scientist 式论文工厂**
2. **无边界 self-rewrite**
3. **纯 benchmark 驱动自进化**
4. **把 reviewer LLM 当唯一真理**

---

## 7. v2 成功标准

Auto Research v2 成功，不是因为生成了更多内容，而是因为它做到：

1. 研究方向选择更稳
2. 每周都有可验证 artifact
3. 无效实验率下降
4. holdout 命中率提升
5. venue fit 更清晰
6. 学习写回更干净、可回滚

---

## 8. v2 失败信号

若出现以下情况，说明 v2 设计失败：

- token 量上升，但 artifact 质量无提升
- benchmark 分数提高，但 holdout/真实任务无提升
- worker 越来越忙，但 kill list 越来越少
- memory 快速膨胀，但 stable learning 很少能复现
- 写作越来越像样，研究结论却越来越空

---

## 9. 对 Nous 的直接含义

对 Nous 而言，v2 的首要任务不是继续优化“Loop 84 怎么跑”，而是：

1. 建立 Evidence Engine
2. 建立分层评分器
3. 建立 Debate/Tournament 机制
4. 建立 bounded self-improvement 边界
5. 建立 weekly kill review

---

## 10. 最后的定义

> Auto Research v2 = 分层评分 + 对抗筛选 + 可执行验证 + 冻结 holdout + 局部自改进 + 全程可回滚。

如果没有这六件事，就不要把系统叫作“可持续升级的自动科研”。
