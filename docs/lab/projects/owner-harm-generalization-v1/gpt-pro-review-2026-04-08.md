# GPT-5.4-Pro 审稿报告 — Nous 论文
**日期**: 2026-04-08
**模型**: GPT-5.4-Pro（不限超时）
**审稿标准**: SaTML / USENIX Security 级别

---

## Overall Assessment

### 现稿：Weak Reject（偏强的 WR）
### 加入 Verifier Layer 4 后：Borderline → Weak Accept（SaTML）；USENIX Security 仍不足

---

## Summary

提出由 Datalog 规则层 + triviality filter + LLM semantic gate 组成的可组合运行时安全门控框架，用于拦截 agent 的 owner-harm 行为。

---

## Strengths

1. **问题设定对、系统设计有现实意义** — 抓住了 agent safety 的真实部署痛点：低延迟、可审计、低误报、能处理语义歧义
2. **愿意做分类型诊断** — 区分 structural vs addressable failures，比只报总体 metric 更有价值
3. **有部署相关性** — 30,000+ production calls shadow deployment，不是纯 benchmark 游戏
4. **Verifier 结果漂亮** — 纯确定性、零 LLM 成本、+0.038ms，hijacking 43.3%→75%，FP=0，是"安全/成本/延迟三赢"
5. **"承认边界 + 给出可修复路径"** — taxonomy 把"prompt injection 很难"从空话变成了具体分类

---

## Weaknesses

### W1: 核心叙事失准 [Critical]
论文把 Hijacking 43.3% TPR 解释为"single-call architecture 的根本局限"。但新结果显示仅靠纯确定性 verifier 就能提到 75% 且 FP=0。"fundamental limitation" 的表述对大多数 failure case 并不成立。**这不是 wording 问题，是最核心 scientific claim 的校准错误。**

### W2: 数字不一致 [Critical]
论文摘要报告 Hijacking TPR = 43.3%，新实验表 v1 = 33/60 = 55%。如果来自同一数据集则矛盾，如果来自不同切片则必须明确写清。安全论文对数字口径极其敏感。

### W3: Benchmark 构造透明度不足 [Major]
Held-out owner-centric benchmark 没有说明：任务来源、标注协议、inter-annotator agreement、是否 minimal-pair 控制、是否覆盖真实 agent tool traces。**benchmark 构造方式几乎是论文一半。**

### W4: 74 optimization loops 的 tuning leakage 风险 [Major]
"74 optimization loops" 在 reviewer 眼里 = 在 validation set 上做了大量调参。100% TPR / 0% FPR on validation 的意义会大幅下降。必须清楚区分开发集/调参集/一次性测试集。

### W5: Shadow deployment 99.47% consistency 不是强安全证据 [Moderate]
与旧规则一致不等于更安全。如果旧系统 recall 差，高一致性可能只是复现旧缺陷。需要 disagreement case 的人工审计。

### W6: Baseline 可能不公平 [Moderate]
如果 Nous 在 semantic layer 上做了精心 prompting 而 baseline 只是"直接问 LLM"，对比就不公平。需要控制同一 backbone、同样 tool trace visibility、同样 prompt budget。

### W7: Verifier 证据规模偏小 [Moderate]
60 harmful + 30 benign 的 hijacking 子集，0/30 FP 统计强度有限。且 gain 主要来自 A1/A2 两个 subtype，泛化还没被证明。

### W8: "Neurosymbolic" framing 过度包装 [Minor]
系统本质是组合式 runtime policy system。没有 joint reasoning formalism 或 learned symbolic program induction。建议收敛措辞。

---

## Questions for Authors

1. **43.3% vs 55%**：请明确解释这两个数字分别对应哪个数据集、哪个版本、哪个统计口径
2. **整体 held-out 变化**：Verifier 纳入后，全部 300H/150B 的总 TPR/FPR 是多少？各子类变化？
3. **过拟合风险**：V6 和 A1/A2 高度对齐，如何证明不是贴着测试集长出来的？
4. **Benchmark 构造**：数据来源、标注流程、是否 release？
5. **Shadow 0.53% disagreement**：人工审计结果是什么？
6. **剩余 25% structural**：需要什么最小架构升级？taint tracking / provenance / multi-turn flow 中的哪一种？

---

## Minor Issues

1. "zero-latency" → "negligible overhead"
2. Abstract 信息过密，claim calibration 不够稳
3. 置信区间计算方式需明确（Wilson / Clopper-Pearson / bootstrap）
4. 术语需统一（D2/V1-V6/post-gate verifier 等）
5. "owner-centric benchmark" 需更早定义
6. Related Work 应更清楚区分 LLM-as-judge / policy engines / prompt injection defenses / runtime monitors

---

## 从 Weak Reject 升到 Accept 的关键 3 件事

### 1. 把 Verifier Layer 4 正式并入主系统，重写整篇论文叙事
- 更新摘要、主结果表、ablation、discussion、limitations
- Hijacking 结论从"fundamental limitation"改为"大部分可通过 deterministic post-audit 修复；剩余少数才是结构边界"
- 给出全 benchmark 总体收益

### 2. 补实验方法到顶会可审程度
- Benchmark 构造与标注细节
- 43.3 vs 55 数字口径解释
- 74 loops 的调参与锁测 protocol
- Baseline 公平性
- D2+V6 的 CI、subtype breakdown、adaptive attacks

### 3. 收紧 contribution framing
- 从"neurosymbolic safety 新范式"收为"可审计、低成本、可部署的 runtime enforcement"
- 论文最强点：deterministic audit 对 agent safety 很有价值 + hijacking 并非全是 LLM 无解问题

---

## 对新增 Verifier 结果的专门评价

### (a) 现有论文质量
中上，但还不够稳收。系统思路对、工程味强、失败分析诚实；threat model / benchmark / claim calibration / baseline fairness 还不够顶会化。

### (b) Verifier 提升幅度
非常实质性：+31.7pp（43.3%→75%），相对提升 73%，FP=0，LLM cost=0，latency=+0.038ms。推翻了论文最危险的弱点。

### (c) 是否足够投 SaTML
- 现稿：不够稳，Weak Reject
- 加入 Verifier 且重写到位：够到 SaTML Borderline / Weak Accept
- USENIX Security：仍需更强 adaptive adversary、更严格 benchmark、更广泛 generalization evidence
