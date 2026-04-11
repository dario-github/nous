# 双审稿人审查 Round 2 — 2026-04-11

## Reviewer A (GPT-5.4-Pro): Reject (4/10, Confidence 4/5)

### Strengths
- S1: 问题选得好，现实相关性强
- S2: 清晰主线：威胁模型 → 系统设计 → 跨benchmark对比 → 因果解释
- S3: 诚实的自我限制声明
- S4: Hijacking layer complementarity 分析有启发性
- S5: 生产部署至少说明不只是benchmark

### Weaknesses (致命)
- W1 🔴: 核心实验数字不一致（AgentHarm 176/176 vs 300/150混用、P2 pilot百分比与主实验相同但样本数不相容、Banking 9 vs 10 tasks矛盾）
- W2 🔴: SSDG 理论不够"定理级"（axiom把结论装进前提、无proof、theorem里塞经验数值）
- W3 🔴: P1否定与P2肯定在理论上不自洽（形式化未区分 raw context vs usable context）
- W4 🟡: 因果归因过强（baseline输入不等价、评测粒度不同、混杂因素多）
- W5 🟡: 最强结果都来自自建benchmark
- W6 🟡: C1-C8"互斥"不可信
- W7 🟡: 生产部署证据过于anecdotal

### Key Questions
- Q1: 统一核对所有样本量/分母/指标
- Q2: L3在不同实验里到底能看到哪些上下文？
- Q5: 如何证明gap主要来自L1而不是多因素混合？

### Missing References
- Formal causality (Pearl)
- Access control / information flow 文献

---

## Reviewer B (Opus): Weak Reject (4/10, Confidence 4/5)

### Strengths
- S1: 问题定义有价值且时机恰当
- S2: 受控实验设计思路正确
- S3: 诚实的自我限制声明
- S4: Hijacking 分层互补性结果有启发性
- S5: 分类学覆盖分析有用

### Weaknesses (致命)
- W1 🔴: 27样本统计效力严重不足（4/27 的95% CI=[5.9%, 32.5%]）
- W2 🔴: Owner-Harm Benchmark方法论薄弱（单人标注、无IAA、post-hoc、分布不透明）
- W3 🔴: SSDG过度包装（P2是平凡结果、P1被reject）
- W4 🟡: 缺乏与现有系统实验对比（Llama Guard、NeMo等）
- W5 🟡: 生产部署证据不可验证
- W6 🟡: 形式化定义与实验之间有断层
- W7 🟡: 叙事存在循环性

### Key Questions
- Q2: 零样本LLM 59.3% > Nous 14.8%——简单LLM是否就是更好的owner-harm防御？
- Q4: P1被reject后"structured goal-action alignment"有实验支持还是纯推测？
- Q6: Table 1覆盖判断标准是什么？

### Missing References
- R2Guard, AgentMonitor, Invariant Analyzer
- PromptGuard, BIPIA
- Anthropic tool use safety

---

## 共识问题（两位审稿人都提到）
1. SSDG理论过度包装，应降级为framework/hypothesis
2. 自建benchmark方法论不够严谨
3. 核心数字统计效力不足
4. 生产部署证据不够rigorous
5. 缺乏与现有系统的横向实验对比
