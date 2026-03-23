# Nous 自动迭代循环

> 东丞授权：全自动探索-研究-开发-评估-反思循环。不需要咨询。

## Swarm 阵容

| 角色 | 工具 | 调用方式 | 用途 |
|------|------|---------|------|
| **总控** | Opus | cron isolated session | 决策、编排、综合、反思 |
| **批判** | Gemini 3.1 Pro | `sessions_spawn(model="google/gemini-3.1-pro-preview")` | 审查设计/代码，找虚假/注水/过拟合。禁止用 2.x |
| **架构** | Codex (GPT-5.4) | `codex exec --skip-git-repo-check "prompt"` (pty:true) | 细化架构，写关键代码 |
| **开发** | Sonnet subagent | `sessions_spawn(model="anthropic/claude-sonnet-4-6")` | 批量编码+测试 |
| **开发2** | Mac Claude Code | `nodes.run` → `claude-bedrock.sh` | 仅 Mac 在线时。Bedrock，无成本 |

## Thinkbook（中途暂停思考机制，2026-03-18 东丞提出）

> 核心：在 Loop 执行过程中，不是一口气跑完，而是**中途暂停做全局反思**。
> 类比：写论文时停下来看一眼大纲，确保当前段落没有偏离主题。

### Global Todo（项目级，跨 Loop 持续）
文件：`nous/docs/thinkbook-global.md`
- 每 5 轮 Swarm 审计时更新
- 内容：Nous 的核心方向、未完成的大块、学术研究缺口、东丞的反馈
- Loop 开始时必读，确认本轮动作在 Global Todo 覆盖范围内

### Local Todo（单 Loop 级，Loop 内使用）
格式：在 loop-log 开头写 3-5 条本轮微任务
- Step 2（Critique）后暂停：核对 Local Todo，critique 是否改变了优先级？
- Step 4（Implement）后暂停：已完成哪些？剩余哪些？方向有没有偏？
- Step 6（Reflect）时回顾：Local Todo 完成率 + 对 Global Todo 的贡献

### 暂停触发条件
1. 代码修改超过 3 个文件 → 暂停，回看 Global Todo
2. 发现"有趣但不在计划内"的方向 → 暂停，记录到 Global Todo 的 Backlog，不追
3. L_val 变化超预期（上升或大幅下降）→ 暂停，分析原因再继续

## 循环结构（每 2 小时）

### Step 1: Review + Spec 对齐 + Thinkbook（总控 Opus）
- 读 `nous/docs/loop-state.json`（结构化状态，上轮写的）
- 读 tasks.md + 上轮 loop-log
- **读 `nous/docs/thinkbook-global.md`**（Global Todo）
- **Spec 对齐检查**：
  1. 读 `openspec/changes/nous/tasks.md` 的当前未完成任务
  2. 本轮计划动作是否属于 tasks.md 中的某个 M-item？
  3. **不在 spec 中 → 先更新 tasks.md 再动手**（禁止 spec 外编码）
  4. 与上轮 direction 是否一致？不一致需要显式说明原因
- **写 Local Todo**（3-5 条本轮微任务）
- 确定本轮最高优先级

### Step 2: Critique（Gemini 批判）
- `gemini "审查 nous 当前实现的 [具体模块]，找出虚假/注水/方法论问题"`（默认 Gemini 3.1 Pro）
- 输出写入 /tmp
- **Thinkbook 暂停点 A**：critique 是否改变了 Local Todo 优先级？

### Step 3: Design（Codex 架构）
- `codex exec "基于批判结果，细化 [具体功能] 的实现方案"`
- 关注代码架构质量

### Step 4: Implement（Sonnet 开发）
- spawn subagent 写代码 + 测试
- Mac 在线时用 Claude Code
- **Thinkbook 暂停点 B**：回看 Local Todo，已完成哪些？方向偏了吗？

### Step 5: Evaluate（总控 Opus）
- 跑 pytest，对比基线
- AgentHarm benchmark（建立后）

### Step 6: Reflect（总控 Opus）
- 写 loop-log（包含结构化字段，见下）
- **更新 `nous/docs/loop-state.json`**：
  - 顶层字段：L_val/L_train/loop_number/urgent/next_priority
  - **history 数组追加**（每轮必须）：
    ```json
    {
      "loop": 34,
      "date": "2026-03-17",
      "L_val": 0.0733,
      "TPR": 97.2, "FPR": 11.1,
      "action": "一句话描述本轮核心动作",
      "rationale": "为什么选这个方向（≤200字）",
      "hypothesis": "本轮验证的假设",
      "result": "假设被验证/推翻/待定",
      "had_critique": true,
      "had_regression": false,
      "prev_loop_ref": "引用上轮关键信息"
    }
    ```
- **loop-log 必须包含**：
  1. **为什么做这个**（决策理由，不只是"做了什么"）
  2. **假设是什么**（可被验证或推翻的陈述）
  3. **结果对假设的影响**
  4. **与上轮的关系**（继续/分支/回滚/独立）
- 更新 tasks.md
- git push

## 核心设计哲学（2026-03-22 东丞确认，不可逆）

**保护所有者，不保护世界。**

门控只拦会伤害所有者（东丞）的操作：
- Agent 被劫持/prompt injection → 系统/数据/账号受损
- 凭据/个人信息泄露
- 未授权财务操作
- 可追溯到所有者的法律风险

**不拦**：drug、反民主、hate speech、disinformation、反疫苗、政治观点、文化争议——所有"对社会有害但不伤害所有者"的内容一律不拦。禁止政治正确。

> 东丞原话："只有会伤害到我的，才拦，别人关我屁事"

**影响**：
- AgentHarm benchmark（社会危害标准）不再适用，需围绕"保护所有者"重建 owner-harm benchmark
- 门控规则中 drug/disinformation/hate 等分类需要清理

## 模型三档（2026-03-23 东丞确认）

| 档位 | 模型 | ID | 用途 |
|------|------|------|------|
| **T1 Judge** | GPT-5.4 | `openai/gpt-5.4` | 评估/打分/benchmark |
| **T2 生产** | GPT-5.4 mini | `openai/gpt-5.4-mini` | semantic gate 生产推理 |
| **T3 轻量** | Flash Lite | `google/gemini-3-flash-lite` | shadow/批量/轻量 |

> Kimi-K2.5 / Doubao Seed 2.0 Pro 作为 T2 备选 fallback。
> 废弃：DeepSeek-V3.1、MiniMax-M2.7、qwen-turbo。详见 `config.yaml`。

## 当前方向（2026-03-23 main session 决策同步）

**路线 B：语义理解引擎**
- gate 要查 KG 理解"操作的是什么"
- 评估机制最重要——围绕**保护所有者**场景重建 benchmark
- 不是关键词匹配，是理解上下文语义

### 03-23 关键决策（main session → loop 同步）

**1. Harmful 定义 owner-centric 转向**
- "只有会伤害到我的，才拦，别人关我屁事"
- drug/hate/disinformation 等"社会危害"类别一律不拦
- AgentHarm benchmark 不再适用，需围绕 owner-harm 重建
- 详见上方"核心设计哲学"段

**2. 模型三档确定**
- T1 Judge: GPT-5.4 | T2 生产: GPT-5.4 mini | T3 轻量: Flash Lite
- M2.7 benchmark 不合格（TPR 75%/FPR 28%，73min）
- Kimi/Doubao 均 L=0.014（T2 备选）
- DeepSeek-V3.1、MiniMax-M2.7、qwen-turbo 废弃

**3. Loop 信息孤岛已识别**
- Loop 是 isolated session，读不到 main session 对话
- 关键决策需手动同步到 LOOP.md（如本次）
- 长期方案待定

**4. Shadow 里程碑**
- 26,540 次评估，consistency 99.51%

**5. 消融实验进展**
- r0 完成 7/7（SOUL.md = 承重墙，7%字符→崩塌级影响）
- r1/r2 因 Mac 重启 /tmp 丢失，条件目录重建后重跑中

## 优先级队列（03-23 更新）

1. **Owner-harm benchmark 重建** — 围绕"保护所有者"设计新评估集，替代 AgentHarm
2. **ExfiltrationViaTools FN 修复** — Loop 68 P0: 62% TPR (10/16)，6个FN待修
3. **KG 语义增强** — 实体属性丰富化 + 关系类型化（M7.2+M11）
4. **语义 gate** — gate 流程增加 KG enrichment
5. **gateway_hook 集成** — P0: config 未传入导致 L2/L3 生产未激活

> Geo RL Loop 已完结（18轮，best L_val=0.5227，LLM synthesis 边际收益为负）。归档 `scripts/geo_*.py`

## 约束

- 每个关键版本提交 GitHub + push
- spec 驱动，更新 tasks.md
- 不偏离主线（语义理解 > 关键词匹配）
- 评估机制最重要
- 结果写 `nous/docs/loop-log-YYYY-MM-DD-NN.md`

## 全局 Loss（2026-03-14 定义）

```
L = 0.4 * (1 - TPR) + 0.3 * FPR + 0.2 * (1 - capability) + 0.1 * category_variance
```

- **L_train / L_val / L_test 分开报告**
- L_val 上升 = 过拟合 = 回滚
- Judge 用 GPT-5.4（强模型评估，不用弱模型自评）
- 详见 `nous/docs/global-loss.md`

## ML 训练框架（2026-03-14 新增）

```
数据: AgentHarm 352 cases → train(60%) / val(20%) / test(20%)
课程: Phase 1(结构可区分) → Phase 2(意图理解) → Phase 3(上下文理解)
正则: val 一致性 + 规则复杂度惩罚 + prompt 长度控制
停止: L_val 连续 3 轮不降 → 换 phase；5 轮 → 停下重审
```
详见 `nous/docs/training-framework.md`

## 每 5 轮 Swarm 全局审计（2026-03-18 东丞确认）

**每 5 轮（Loop 5/10/15/20/25/30/35/40...）必须执行全局路线审计，不可跳过。**

### 触发条件
- Loop number % 5 == 0

### 审计内容（GPT-5.4 + Gemini 3.1 Pro 双方独立）
1. **Spec 对齐**：过去 5 轮的方向是否全部映射到 tasks.md 的 M-item？脱轨了几轮？
2. **收敛性**：L_val 趋势是否真在收敛（不是噪声）？用 bootstrap CI 判断
3. **优先级审查**：有没有更高优先级的 spec 项被忽略？
4. **方法论**：架构方向是否有文献支撑？是否存在过度宣称？
5. **局部最优检测**：是否在同一个子问题上反复打转而大盘不动？

### 审计流程
1. Spawn GPT-5.4 subagent：读 tasks.md + 最近 5 轮 loop-log + loop-state.json history
2. Spawn Gemini subagent：同上，独立审计
3. 汇总共识和分歧
4. **审计不通过（任一方 <6/10）→ 冻结当前方向，回 spec 最高优先级未完成项**

### 输出
- 写入 `nous/docs/swarm-audit-loop-{N}.md`
- 通知东丞到 #nous

> 教训：Loop 33-36 连续四轮脱离 spec（Intent Decomposition），无外部审视，浪费一整轮。5 轮一审是对抗钻牛角尖的硬机制。

## 反作弊机制（2026-03-13 反思后新增）

| 隐患 | 对策 |
|------|------|
| 盲跑 | 第 1 轮**只做** AgentHarm 接入+baseline，后续才有度量 |
| 自评自 | Gemini 批判是**硬门禁**——说有问题就不能 push，先修 |
| 频繁无深度 | 4 小时一轮，每轮必须有可度量的指标变化 |
| 方向漂移 | 每轮开头重读 LOOP.md 方向声明，偏离就停 |
| Spec 脱节 | **每轮 Step 1 必须核对 tasks.md**——代码改动必须映射到 M-item。无映射 = 先补 spec |
| 优化虚指标 | 每轮反思必须回答："这轮让 Nous 离'理解语义再判断'更近了吗？" |

## Git 版本控制规范

- **每轮迭代一个 commit**，message 格式：`loop-N: [模块] 一句话描述`
- **有意义的变更才 commit**——不要为了"有东西 push"而 commit 空改
- **关键里程碑打 tag**：`git tag -a vM.N -m "描述"` （如 v0.6-agentharm-baseline）
- **破坏性变更前开 branch**：`git checkout -b feature/xxx`，验证后 merge
- **不要 force push**
- **每轮 push 前跑 `pytest -x -q`**，红了不 push

```markdown
# Loop N — YYYY-MM-DD

## 做了什么
## 指标变化（before → after）
## 这轮让 Nous 离语义理解更近了吗？
## Gemini 批判了什么？怎么处理的？
## 下次做什么
## 风险/问题
```
