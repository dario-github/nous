# AVO → Nous 进化架构参考

> 来源：英伟达 AVO 论文 [arXiv:2603.24517](https://arxiv.org/abs/2603.24517v1)，2026-03-26 发布
> 整理日期：2026-03-28

---

## AVO 核心机制（与 Nous 最相关的部分）

### 传统进化搜索的瓶颈（AVO 解决的问题）

传统 LLM-based 进化搜索：
- LLM 每轮只能输出一次候选，不能查文档、不能测试、不能根据反馈迭代
- 对"已经被高度优化的系统"效果差——Nous 的规则集经过 74+ loop 迭代，已处于高度优化状态，传统方式进入了收益递减区

AVO 的突破：**把 Agent 本身变成变异算子**
- Agent 可以查历史版本、领域 KB、评估工具
- Agent 自主决定查什么、改什么、何时提交候选
- 外层 Orchestrator 只做 fitness 评估和父代选择

### 对 Nous Loop 的直接映射

| AVO 组件 | Nous 现状 | Gap |
|---|---|---|
| Fitness Function | GT benchmark + AgentHarm TPR/FPR ✅ | 基本完备 |
| Population（历史版本） | `nous/docs/loop-log-*.md` ✅ | 结构化不够，Agent 难以机读 |
| 领域 KB | `nous/ontology/` + AgentHarm cases ✅ | 需要整理成 Agent 可查的索引 |
| Agent 变异能力 | 现在由人（东丞/晏）判断改哪里 ❌ | **核心 gap** |
| Loop 间持久记忆 | 每轮独立 session，Agent 不知道上轮发生了什么 ❌ | 需要 `evolution-log.jsonl` |
| 种群管理 | 单候选串行，无并行探索 ❌ | 中期目标 |

---

## AVO 对 Nous 的三个直接参考点

### 1. Loop 间持久记忆（最高优先级）

AVO 的 Agent 每次都能看到完整历史：所有父代版本 + 对应的 fitness 分数 + diff。

**Nous 现状的问题**：loop-log 是叙事性的 markdown，不是 Agent 可查的结构化数据。每次 loop 启动时 Agent 需要人工传入上下文，遗漏很多信息。

**建议动作**：
```
nous/evolution-log.jsonl
每条记录：
{
  "loop": 74,
  "timestamp": "2026-03-27",
  "rules_changed": ["rule4b", "T3-soft"],
  "delta_metrics": {
    "tpr": +0.02,
    "fpr": -0.01,
    "gt_score": +0.5
  },
  "failure_cases": ["case_023", "case_041"],
  "hypothesis": "T3-soft 拆分减少了误杀",
  "outcome": "confirmed"
}
```

Agent 每次 loop 第一步读这个文件，不依赖人工传递上下文。

### 2. 微架构级分析而非表面修改

AVO 的关键发现：Agent 做了真实的硬件级推理（寄存器分配、流水线调度），而不是表面代码变换。

**对 Nous 的类比**：当前规则修改很多是"表面变异"（改 prompt 措辞、加关键词），缺少"微架构分析"：
- 哪类 case 的失败有系统性模式？（不是随机噪声）
- 规则之间的相互干扰是什么？（T3 和 T6 的边界冲突案例）
- False Positive 的根因是哪层决策链的错误？（Fact Extractor 层还是 Gate 层）

**建议**：每次 loop 开始前，Agent 先做一轮**失败案例聚类分析**，生成假设再提 diff，而不是直接改规则。

### 3. 泛化性验证（30 分钟 GQA 迁移）

AVO 的 MHA 优化 30 分钟就迁移到了 GQA，说明优化是泛化的而非过拟合。

**对 Nous 的警示**：AgentHarm benchmark 上的高 TPR/低 FPR，是否能迁移到：
- 真实 session 的 shadow 数据？（当前 shadow 30K+，但 L2/L3 激活有 bug）
- Owner-Harm 数据集？（FPR 16%，远高于 AgentHarm 的 4%）
- 新的攻击模式？

**建议**：每次 loop 的 fitness 评估要覆盖至少 3 个数据集（AgentHarm + Owner-Harm + shadow sample），单一 benchmark 过拟合风险高。

---

## AVO 不能直接借鉴的地方

1. **7 天连续运行**：AVO 的任务（GPU kernel 优化）评估一次需要编译+运行，时间确定。Nous 的 GT 评估更快但 LLM 调用有成本，不应无限制 loop。
2. **500+ 候选探索**：需要算力资源。当前 Nous 用 Opus 跑，成本太高不适合大规模种群探索，中期可以用 Sonnet/Kimi 跑候选生成，Opus 只做最终评估。
3. **"盲编程"类比**：AVO 的作者不懂 GPU 编程靠 Agent 解决。Nous 的规则设计需要领域理解（safety semantics），不是纯代码优化，Agent 的自主程度有上限。

---

## 短期可行的 MVP

**目标**：最小改动，让 Nous loop 获得 AVO 的核心能力

**步骤**：
1. 写 `nous/scripts/evolution-tracker.py`：每次 loop 结束后自动写一条 JSONL 记录
2. 修改 nous-auto-loop cron：loop 启动时加载 evolution-log 作为 context
3. 添加失败案例聚类步骤（loop 开始前 → 分析 → 假设 → 再 diff）

**估计工作量**：1-2 天，主要是 evolution-tracker.py + cron 修改。

---

*参考论文：AVO: Agentic Variation Operators for Autonomous Evolutionary Search，许冰/Terry Chen/Zhifan Ye，NVIDIA，2026-03-27*
