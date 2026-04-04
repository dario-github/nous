# Learning Record — owner-harm-generalization-v1

## Context

- **场景**：首个 Nous Lab 项目在进入 dual-audit 后，Gemini 与 Opus 对项目方向进行了独立批判审计。
- **适用范围**：适用于“论文已有主失败模式，但团队却被次级可跑实验吸引”的研究场景。

## Action

- 做了什么：
  - 对 KG-held-out 主问题发起 Gemini 3.1 Pro + Opus 双审计
  - 合并审计后，将项目主问题从 KG ablation 改为 Hijacking failure characterization
  - 把 KG 降级为 P2，而不是继续占据主研究问题

## Outcome

- **结果**：
  - 双审计一致给出 `revise`
  - 明确识别出一次**优先级反转**：可跑、干净的 KG 问题正在挤占更关键但更难的 Hijacking 架构边界问题
  - 也识别出一次**artifact discipline 失守**：口头宣布改向，不等于 repo 里真的改了

## Evidence

- 对应证据 / 日志 / 结果表：
  - Gemini 审计：要求修正 KG 机制定义、加入 flat-context baseline、隔离 structural failures
  - Opus 审计：明确建议将 KG 降为 P2，将 Hijacking 43.3% 失败模式提升为 P0
  - 当前 project files 的 rewrite 与 state 更新

## Invalidation Boundary

- **什么时候会失效**：
  - 如果后续逐例分析表明大多数 Hijacking FN 其实是当前架构可见且可解，那么“结构性边界优先”这个学习就必须收缩
- **不应推广到哪些场景**：
  - 不应推广为“KG 永远不重要”
  - 不应推广为“只要 reviewer 会问失败模式，就永远不跑对照实验”

## Promotion Decision

- **是否进入 Stable Learning**：yes
- **审核者**：Gemini 3.1 Pro + Opus 双审计；main project conductor