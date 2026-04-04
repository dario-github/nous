# Nous Lab Runtime Kit

这套目录不是讨论稿，而是 **Nous Lab v1 的最小运行骨架**。

目标：

- 让研究推进围绕工件，而不是围绕长聊天记录
- 让每个方向都能被启动、评审、收缩或 kill
- 让 learnings 进入长期层前先经过 gate

---

## 目录结构

```text
docs/lab/
├── README.md
├── templates/
│   ├── PROJECT_CHARTER.template.md
│   ├── EVIDENCE_LEDGER.template.md
│   ├── HYPOTHESIS_PACK.template.md
│   ├── EXPERIMENT_PACK.template.md
│   ├── REVIEW_MEMO.template.md
│   ├── LEARNING_RECORD.template.md
│   └── WEEKLY_RESEARCH_PACKET.template.md
└── projects/
    └── owner-harm-generalization-v1/
```

---

## 最小运行流程

1. **Sponsor 定题**
   - 先写 `PROJECT_CHARTER.md`
   - 没有 charter，不进入自动推进

2. **Evidence Engine 建证据账本**
   - 填 `EVIDENCE_LEDGER.md`
   - 没有 source id 的观点默认无效

3. **Research Worker 产 hypothesis**
   - 填 `HYPOTHESIS_PACK.md`
   - 默认只保留 2 个最可证伪方向

4. **Conductor 压成最小实验包**
   - 填 `EXPERIMENT_PACK.md`

5. **Critic-Archivist 做 pass/fail 审核**
   - 填 `REVIEW_MEMO.md`

6. **只有通过 gate 的经验才能写入稳定层**
   - 填 `LEARNING_RECORD.md`

7. **每周五收口**
   - 汇总到 `WEEKLY_RESEARCH_PACKET.md`
   - 明确 continue / shrink / kill

---

## 初始化一个新项目

在 repo 根目录执行：

```bash
scripts/init_nous_lab_v1.sh <project-slug>
```

例如：

```bash
scripts/init_nous_lab_v1.sh owner-harm-generalization-v2
```

它会创建：

- `docs/lab/projects/<project-slug>/`
- 所有标准工件模板
- `STATE.yaml`

---

## 当前默认试运行项目

当前 repo 已放入一个首个试运行项目：

`docs/lab/projects/owner-harm-generalization-v1/`

它用于把 Nous 当前主线从“继续闷头 loop”切换为“实验室式推进”：

- 核心科学问题：KG 是否帮助 held-out generalization
- 核心约束：不能为了 benchmark overfitting 去修 held-out 细节
- 当前 target venue：SaTML 主路，USENIX Security 冲高

---

## 与现有 loop 的关系

从现在开始：

- loop 仍可作为执行日志存在
- 但 **project charter / evidence / hypothesis / review** 才是高优先级工件
- 没经过这些工件流的“进展”，不应视为实验室正式进展

---

## 关键流程规则

### 1. 关键计划双审计

以下内容默认需要 **Gemini 3.1 Pro + Opus** 双审计：

- 改主研究方向
- 改论文主叙事 / venue
- 改主评分器 / holdout
- 高成本实验线
- 改 Stable Learning 准入规则

### 2. 每周必须 kill 一个弱方向

没有 kill list，说明实验室在囤积方向而不是推进研究。

### 3. 没有 falsifiable artifact，不算进展

artifact 包括但不限于：

- 证据账本
- hypothesis pack
- 实验包
- 结果表
- 审核 memo

### 4. 没过 Critic，不算实验室结论

---

## 一句话原则

> 小团队、强证据、短循环、可停机、可写回。
