# fin/ — 金融投研垂类 Agent 调教工作区

> 本目录是 nous 项目的金融投研方向，与 `fin` 分支一一对应。
> **权威上下文在 [`product-context.md`](./product-context.md)** — 任何设计先读它。

## 立场（不重复造轮子）

我们不自研投研 agent、不训练金融 LLM、不重写回测引擎。
我们做的是**对已有 SOTA 组件的整合与调教**。Route A 已选定：
**Qlib + RD-Agent + ARIS + nous**，nous 的角色是**准入 gate + 证据链 + 合规审计**。

目标 = **at least useful**。不是 SOTA paper。

## 产品一句话

> **为孙总 9 人 A 股私募团队（7 亿规模）做一个"决策副脑"——减轻认知负担，不替代决策。**
> 对外叫"备忘录助手"、"风控提醒"。**绝不叫 AI 系统**。

## 文档

| 文件 | 作用 | 读的顺序 |
|------|------|---------|
| [`product-context.md`](./product-context.md) | **权威**：团队 / 定位 / 红线 / 四能力 / Route A / 代码资产 | 1️⃣ 必读 |
| [`landscape-2026-04.md`](./landscape-2026-04.md) | 2026-04 快照：上游 SOTA 矩阵 + Tier 划分 | 2️⃣ 外部映射 |
| [`integration-hooks.md`](./integration-hooks.md) | nous gate 与上游/invest 模块的具体对接点 | 3️⃣ 落地 |
| [`sota-tracker.yaml`](./sota-tracker.yaml) | 月度自检：项目、版本、上次 check、差距标签 | 4️⃣ 持续跟进 |

## 节奏

- **季度**：重刷 landscape，新增/退役条目
- **月度**：跑 sota-tracker 看 star/release 变化，补 diff 说明
- **周度**：如果有 POC 在跑，出一份 1 段话的 "useful or not" 结论

## 代码资产提醒

`invest/`（125 files / 449MB，factor / backtest / skills / institutional / signals / reports）
**仅存在于东丞本地 fin 分支**，按红线不推 origin。本目录只做 public 设计 + 对接层。
