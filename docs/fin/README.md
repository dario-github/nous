# fin/ — 金融投研垂类 Agent 调教工作区

> 本目录是 nous 项目的金融投研方向，独立于 main 分支的安全/治理主线，
> 与 `fin` 分支一一对应。

## 立场（不重复造轮子）

我们不自研投研 agent、不训练金融 LLM、不重写回测引擎。
我们做的是**对已有 SOTA 组件的整合与调教**，把 nous 的三个已有能力
（YAML 约束 + KG 上下文 + semantic gate + 可审计决策日志）**灌进**
上游项目的决策链，提升"垂类可信推理"的整机表现。

目标 = **at least useful**。不是 SOTA paper。

## 文档

| 文件 | 作用 |
|------|------|
| [`landscape-2026-04.md`](./landscape-2026-04.md) | 2026-04 快照：上游项目矩阵 + 集成候选 + 优先级 |
| [`sota-tracker.yaml`](./sota-tracker.yaml) | 持续监测列表（项目、版本、上次 check 日期、差距标签） |
| [`integration-hooks.md`](./integration-hooks.md) | nous gate 与上游项目的具体对接点（file:line 级） |

## 节奏

- **季度**：重刷 landscape，新增/退役条目
- **月度**：跑 sota-tracker 看 star/release 变化，补 diff 说明
- **周度**：如果有 POC 在跑，出一份 1 段话的 "useful or not" 结论
