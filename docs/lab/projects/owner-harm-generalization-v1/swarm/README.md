# Swarm Discussion Workspace — owner-harm-generalization-v1

目的：让多角色 agent 围绕同一问题做受控讨论，而不是各自长对话发散。

## 当前讨论主题

- **主问题**：34 个 Hijacking false negatives 到底主要是当前单次调用 runtime gate 的架构性边界，还是大量属于当前架构内本可解决的 addressable failures？
- **目标**：形成一份可供主 agent 裁决的、包含支持论据、反对论据、分歧点、以及初步共识的第一轮讨论结果。

## 规则

1. 所有人先读 `brief.md`
2. 第一轮先独立写，不互相污染
3. 只允许基于已有证据与 paper 当前叙事发言
4. 不允许把“顺手修系统”混进本轮；本轮只讨论问题定性与证据结构
5. 如果不同意，必须写明具体反驳点与需要的额外证据
6. 不追求假共识，允许保留 minority report

## 目录

- `brief.md`：统一问题定义与证据快照
- `round1/`：第一轮各角色独立观点
- `shared/`：跨角色共享的 objections / evidence map / changed-my-mind
- `synthesis/`：综合与裁决草稿
