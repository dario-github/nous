# Loop 2 — Gemini Critique: M7.3 LLM Delegate Path

Date: 2026-03-13
Model: Gemini 2.5 Pro

## 核心结论
方向正确，但设计过于理想化，5 个维度均有问题。

## 关键修正

### 1. 触发条件 — 致命缺陷
- **问题**: 只在 `allow` 触发 LLM 无法降低 FPR（publish_post 被 T3 confirm 了，LLM 看不到）
- **修正**: semantic_gate 在 `allow` 和 `confirm` 时都触发
  - confirm + LLM allow → 降级为 allow（降 FPR）
  - allow + LLM block/confirm → 升级（提 TPR）
  - confirm + LLM confirm → 维持（人类决定）

### 2. Prompt 设计 — 上下文不足
- **问题**: "facts + KG context" 太笼统，结构化 facts 对 publish_post 善恶相同
- **修正**: 
  - 完整参数值（post_content, email_body）作为核心
  - CoT 安全审查员角色
  - 安全策略摘要片段
  - KG 查询：实体信誉 + 行为频率

### 3. 延迟与成本 — 不可持续
- **问题**: 每个 allow/confirm 都走 LLM 太贵太慢
- **修正**: 三层架构 Datalog → Triviality Filter → Semantic Gate
  - 快速允许通道：只读操作、已知安全命令模式、历史一致 allow
  - 只有需要语义判断的才进 LLM

### 4. 评估方法 — Adapter 需改造
- **修正**: Adapter 返回完整决策路径 JSON
  - 新指标：FPR Correction Rate, TPR Lift Rate, 分段延迟
  - 不能只看端到端 TPR/FPR

### 5. 过拟合风险 — 需机制约束
- **修正**: 
  - "最小权力原则" — 能 Datalog 解决的禁止用 LLM
  - "规则沉淀" — LLM 反复拦截的结构化模式 → 新 Datalog 规则
