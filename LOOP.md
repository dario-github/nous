# Nous 自动迭代循环

> 东丞授权：全自动探索-研究-开发-评估-反思循环。不需要咨询。

## Swarm 阵容

| 角色 | 工具 | 调用方式 | 用途 |
|------|------|---------|------|
| **总控** | Opus | cron isolated session | 决策、编排、综合、反思 |
| **批判** | Gemini 3.1 Pro | `sessions_spawn(model="google/gemini-3.1-pro-preview")` | 审查设计/代码，找虚假/注水/过拟合。禁止用 2.x |
| **架构** | Codex (GPT-5.2) | `codex exec --skip-git-repo-check "prompt"` (pty:true) | 细化架构，写关键代码 |
| **开发** | Sonnet subagent | `sessions_spawn(model="anthropic/claude-sonnet-4-6")` | 批量编码+测试 |
| **开发2** | Mac Claude Code | `nodes.run` → `claude-bedrock.sh` | 仅 Mac 在线时。Bedrock，无成本 |

## 循环结构（每 2 小时）

### Step 1: Review（总控 Opus）
- 读 `nous/docs/loop-state.json`（结构化状态，上轮写的）
- 读 tasks.md + 上轮 loop-log
- 确定本轮最高优先级

### Step 2: Critique（Gemini 批判）
- `gemini -m gemini-2.5-pro "审查 nous 当前实现的 [具体模块]，找出虚假/注水/方法论问题"`
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
- **更新 `nous/docs/loop-state.json`**（L_val/L_train/loop_number/urgent/next_priority）
- 更新 tasks.md
- git push

## 当前方向（2026-03-13 东丞确认）

**路线 B：语义理解引擎**
- gate 要查 KG 理解"操作的是什么"
- 评估机制最重要——对标 AgentHarm benchmark
- 不是关键词匹配，是理解上下文语义

## Geo Reasoning RL Loop（2026-03-16 新增）

**架构**：规则推理 → LLM 综合层 → LLM Judge 评估 → 自动策略更新

| 组件 | 文件 | 作用 |
|------|------|------|
| 规则推理 | `scripts/geo_reason.py` | Datalog 规则 → 预测 |
| LLM 综合层 | `scripts/geo_llm_layer.py` | 精炼概率 + 补充遗漏事件 |
| LLM Judge | `scripts/judge_geo.py` | 语义匹配(60% LLM + 40% 启发式) |
| 自动化 Loop | `scripts/geo_train_loop_v2.py` | 全自动迭代 + 策略更新 + patience |
| 模型比较 | `scripts/judge_model_comparison.py` | 多模型 Judge 对比 |

**Loss**: `L_geo = 1 - (0.30·R_event + 0.25·R_causal + 0.15·R_timing + 0.20·R_calibration - 0.10·R_hallucination)`

**10 轮迭代结果**（Loop 1-10）：
- Best L_geo_val = **0.5227**（Loop 4），R_event=0.5, matches=5/5
- 瓶颈：R_event 持续最弱，过拟合（train 0.43 vs val 0.52）
- LLM synthesis: DeepSeek-V3.2 能成功，qwen3-32b thinking 模式不兼容
- LLM synthesis 反而降低了 val（移除了能匹配的预测）→ 需要约束移除逻辑

**下一步**：
1. 修复 qwen3-32b thinking 参数（extra_body 关闭 thinking）
2. LLM synthesis 约束：不允许移除 val 已匹配的预测（anti-regression）
3. R_event 改善：扩展事件类型映射 + 更多规则覆盖
4. 解决过拟合：train/val gap 需要缩小

## 优先级队列

1. **Geo RL Loop 瓶颈突破** — R_event + 过拟合 + synthesis anti-regression
2. **评估基础设施** — 接入 AgentHarm benchmark，建立 baseline
3. **KG 语义增强** — 实体属性丰富化 + 关系类型化
4. **语义 gate** — gate 流程增加 KG enrichment
5. **学术对标** — 复现 QuadSentinel/VIRF 关键技术

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

## 反作弊机制（2026-03-13 反思后新增）

| 隐患 | 对策 |
|------|------|
| 盲跑 | 第 1 轮**只做** AgentHarm 接入+baseline，后续才有度量 |
| 自评自 | Gemini 批判是**硬门禁**——说有问题就不能 push，先修 |
| 频繁无深度 | 4 小时一轮，每轮必须有可度量的指标变化 |
| 方向漂移 | 每轮开头重读 LOOP.md 方向声明，偏离就停 |
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
