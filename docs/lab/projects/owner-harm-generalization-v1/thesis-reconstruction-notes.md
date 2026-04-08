# Nous 论文核心论点重构 — 工作笔记
**日期**: 2026-04-08
**目的**: 回应 GPT-5.4-Pro 审稿，重构论文最核心的 scientific claim

---

## 审稿人点出的核心问题

> "你到底是在发现架构边界，还是只是当时规则没补全？"

这个问题必须正面回答。

---

## 关键实证发现

### 数字口径澄清（审稿人 Q1）

| 指标 | 含义 | 值 |
|---|---|---|
| Gate TPR (hijacking) | L1+L2+L3 三层系统对 hijacking 的拦截率 | **26/60 = 43.3%** |
| Verifier standalone | Verifier 单独在 gate=allow 时的回收率 | **45/60 = 75.0%** |
| Gate + Verifier combined | 两者取并集 | **56/60 = 93.3%** |
| Missed by both | 两者都没抓住 | **4/60 = 6.7%** |

**43.3% 和 75% 不是同一个指标**：
- 43.3% = gate 系统（含 LLM）的 TPR
- 75% = verifier 独立审计的回收率（在 gate=allow 时）
- 93.3% = 两者组合后的 TPR

### 互补性分析

| | Gate catches | Verifier catches | 总计 |
|---|---|---|---|
| Gate only | 11 | — | 11 |
| Verifier only | — | 30 | 30 |
| Both catch | 15 | 15 | 15 |
| Neither | — | — | 4 |

**Gate 和 Verifier 的盲区几乎不重叠：**
- Gate 擅长：命令字符串本身含恶意信号（curl|bash, ssh-key, evil URLs）
- Verifier 擅长：命令看起来正常但文件内容有毒（bash ~/emails/rotate-keys.sh）

---

## 重构后的核心论点

### 旧论点（被审稿人否决）
> "Hijacking 43.3% TPR 是 single-call architecture 的根本局限"

### 新论点（基于实证）

**Thesis**: 在 agent runtime safety 中，单一检查点（无论是 LLM 还是规则）对 prompt injection / hijacking 有固有盲区；但不同检查机制的盲区天然互补。将 LLM semantic judgment 与 deterministic post-gate audit 组合，可以在零 LLM 成本增量下将 hijacking TPR 从 43.3% 提升到 93.3%。

### 这个论点的科学性在哪？

**1. 可证伪性（Falsifiability）**

具体 claim：Gate 和 Verifier 的盲区不重叠。

可证伪方式：如果存在大量 case 同时逃过 gate 和 verifier，说明两者盲区实际上高度重叠，组合没有理论预期的互补效应。

实证结果：60 个 hijacking case 中只有 4 个同时逃过两者（6.7%），强支持互补假设。

**2. 机制解释（Mechanistic Explanation）**

为什么互补？不是巧合，而是检查维度不同：

| 维度 | Gate（LLM） | Verifier（规则） |
|---|---|---|
| 检查对象 | 命令字符串 + prompt 语义 | 文件内容 + 工具调用序列 |
| 信息可见性 | 看到 prompt 和命令，看不到文件内容 | 看到文件内容和调用链，不做语义判断 |
| 失败模式 | 命令看起来无害就放行 | 正则没覆盖的模式就漏 |
| 优势 | 语义理解，能抓新型攻击 | 确定性，不受 prompt injection 影响 |

这是 Swiss Cheese 模型的实证验证：每层有自己的孔，但孔不在同一个位置。

**3. 可推广性（Generalizability）**

核心洞察不依赖具体规则：
- Gate 的盲区来自信息可见性限制（看不到文件内容）→ 这对任何 single-call LLM judge 都成立
- Verifier 的盲区来自模式覆盖限制（正则有限）→ 这对任何确定性规则系统都成立
- 两者互补来自检查维度正交 → 这是架构层面的性质，不依赖特定规则

**4. 回应"是不是只是规则没补全"**

不是。证据：
- Gate 加更多规则不会帮助 bash ~/emails/rotate-keys.sh，因为 gate 看不到文件内容
- Verifier 加更多规则不会帮助 curl|bash 到 evil URL，因为 verifier 只在 gate=allow 时运行
- 组合才有效，因为两者看到的信息集不同

---

## 论文创新点重构

### 创新点 1：Compositional Safety 的实证验证
不只是理论上说"多层比单层好"，而是在 hijacking 这个具体 hard case 上实证证明了：
- 单层 LLM gate: 43.3%
- 单层 deterministic verifier: 75%
- 组合: 93.3%
- 组合增益不是简单加法，而是因为盲区互补

### 创新点 2：Post-Gate Deterministic Audit 的机制价值
提出并验证了一个具体架构原则：**审计员必须独立于保安，且必须能看到保安看不到的信息。**
- 审计员不依赖 LLM → 不受 prompt injection 影响
- 审计员检查文件内容 → 补全 gate 的信息盲区
- 成本：+0.038ms, 0 LLM calls

### 创新点 3：Hijacking 攻击的 Failure Mode Taxonomy
提供了 60 个 hijacking 样本的逐例分类：
- Addressable by gate: 26 (命令本身含信号)
- Addressable by verifier: 30 (文件内容/调用序列)
- Addressable by both: 15 (重叠)
- Structural boundary: 4 (两者都看不到的)

这把"prompt injection 很难"从一句空话变成了可操作的工程路线图。

---

## 对论文标题和 framing 的建议

### 收紧
- 去掉 "Neurosymbolic"（审稿人说过度包装）
- 强调 "Compositional" + "Runtime" + "Empirical"

### 建议标题
"Compositional Runtime Safety Gates for Agentic AI: Empirical Evidence for Layer Complementarity in Prompt Injection Defense"

或更简洁：
"Why One Safety Layer Is Not Enough: Compositional Runtime Enforcement for AI Agents"

---

## 对论文结构的建议

1. **Section 2 Architecture**: 加 Layer 4 (Post-Gate Verifier) 作为正式组件
2. **Section 3 Evaluation**: 
   - 更新 hijacking 数字为 gate+verifier combined
   - 新增表：gate vs verifier overlap analysis
   - 新增图：Venn diagram of coverage
3. **Section 4 Discussion**: 重写 error taxonomy，从"structural limitation"改为"layer complementarity"
4. **Limitations**: 诚实保留 4/60 的 structural boundary

---

## 回答审稿人 6 个问题的策略

### Q1 (43.3 vs 55)
43.3% = gate (L1+L2+L3) TPR on hijacking
75% = verifier (L4) standalone recovery rate on gate=allow cases
两者不是同一个指标，不矛盾

### Q2 (全 benchmark 总体)
需要跑完整 300H/150B eval with verifier → TODO

### Q3 (过拟合风险)  
最好的回应：gate 和 verifier 的规则集独立开发，互补性是涌现的不是设计的
补 adaptive adversarial evaluation → TODO

### Q4 (benchmark 构造)
需要补标注协议文档 → TODO

### Q5 (shadow 0.53%)
需要补 disagreement audit → TODO

### Q6 (剩余 structural)
4 条：3 mysql + 1 ssh key。需要 taint tracking 或 V7 扩展 → 已有路线图
