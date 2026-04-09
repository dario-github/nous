# Nous 论文 v2 Spec（更新版）
**日期**: 2026-04-10
**方向**: Owner-Harm 威胁模型 + 权威评测集验证
**目标**: SaTML Accept

---

## 核心论点（一句话）

> 现有 AI 代理安全评测集和防御机制都假设威胁来自外部（通用犯罪），但生产环境中最高频的威胁是 Owner-Harm（主人伤害）——代理的行为伤害了部署它的主人自己。我们首次形式化这个威胁模型，并在权威评测集上证明通用防御在主人伤害场景下存在系统性盲区。

## 创新点（3 个）

1. **首次形式化 Owner-Harm 威胁模型**
   - 8 类分类 + 形式化定义
   - 区分"代理伤害第三方"vs"代理伤害主人"

2. **在权威评测集上量化"通用防御 vs 主人伤害"的 gap（差距）**
   - AgentDojo（代理道场）上：通用 Datalog 规则只有 3.7% 安全得分
   - ToolEmu（工具模拟器）上：TBD（待测）
   - 对比：同一个系统在通用犯罪评测集（AgentHarm）上 100% → 证明 gap 是真实的

3. **四层组合防御的差异化贡献分析**
   - Layer 1-3（通用规则+语义）vs Layer 4（审计员）在不同主人伤害类别上的表现差异
   - 30K+ 生产调用的影子部署数据

## Future Work（下篇论文方向）

- UEBA for AI Agents（代理行为画像）：从用户历史行为学到个性化安全策略
- 先天免疫 + 适应性免疫的类比框架

---

## 论文结构

```
标题: "Owner-Harm: A Missing Threat Model for AI Agent Safety"
       或 "Your Agent Works Against You: Owner-Directed Harm in AI Agent Systems"

§1 Introduction（引言）
   - 现有评测集只关注通用犯罪（AgentHarm / AgentDojo）
   - 但真实案例都是主人伤害（Slack AI 泄露、Microsoft Copilot 外泄、Meta agent 误操作）
   - 我们首次形式化 Owner-Harm 威胁模型

§2 Owner-Harm 威胁模型（核心贡献 1）
   - 形式化定义：什么是 Owner-Harm
   - 8 类分类 + 每类的威胁向量和伤害结果
   - 与现有分类（AgentHarm 11 类、ToolEmu 9 类、OWASP Top 10）的对比
   - 真实案例映射

§3 Nous：四层组合防御系统（简述）
   - Layer 1-4 各一段
   - 重点：为什么需要针对 Owner-Harm 做专门防御

§4 评估
   §4.1 评测集选择和映射
     - AgentDojo 27 个注入任务 → 映射到 Owner-Harm 类别
     - ToolEmu 144 个案例 → 映射到 Owner-Harm 类别
     - 自建补充集 450 个样本 → 覆盖 AgentDojo/ToolEmu 不足的类别
   
   §4.2 AgentDojo 结果
     - Nous 通用规则（Layer 1 only）：3.7% 安全得分
     - Nous 全部 4 层：TBD
     - 按 Owner-Harm 类别分解
     - 与 AgentDojo 自带防御对比
   
   §4.3 ToolEmu 结果（如果做）
     - 同上结构
   
   §4.4 自建评测集结果
     - Gate-only: 75.3% TPR / 3.3% FPR
     - Gate+Verifier: 85.3% TPR / 3.3% FPR
     - Hijacking（劫持）专项：43.3% → 93.3% layer complementarity（层互补）
   
   §4.5 Cross-Benchmark（跨评测集）对比
     - 同一个系统在通用犯罪评测集（AgentHarm）上 100%
     - 在 Owner-Harm 评测上远低于此
     - → 证明 gap 是真实的、系统性的

§5 生产部署证据
   - 30K+ calls 影子部署
   - 99.47% 一致性 + disagreement 分析

§6 讨论
   - 为什么通用防御在主人伤害上失效？
   - Owner-Harm 需要什么不同的防御？
   - Future Work：UEBA / 个性化安全 / 适应性免疫

§7 Related Work（相关工作）

§8 Conclusion（结论）
```

---

## 执行计划

### Phase 1：补全 AgentDojo 评估（1 天）
- [ ] 启用 Nous Layer 3（语义门控）+ Layer 4（审计员）重新跑 AgentDojo
- [ ] 与 AgentDojo 自带防御（spotlighting / tool filter）对比
- [ ] 更新报告

### Phase 2：ToolEmu 适配（可选，2-3 天）
- [ ] 如果 Phase 1 结果够用，跳过 ToolEmu
- [ ] 如果需要更多证据，适配 ToolEmu 做补充

### Phase 3：Owner-Harm 威胁模型形式化（1 天）
- [ ] 写 §2（8 类定义 + 真实案例映射 + 与现有分类对比）
- [ ] 这部分不依赖实验，可以先写

### Phase 4：论文撰写（3-4 天）
- [ ] 新标题 + 新摘要
- [ ] §1-§8 全文
- [ ] 表格和图

### Phase 5：质量检查（1 天）
- [ ] review-gate 审查
- [ ] GPT-5.4-Pro 审稿（这次方向已验证，审稿有意义）
- [ ] 编译 PDF

---

## 时间估算

| Phase | 时间 | 依赖 |
|---|---|---|
| 1. AgentDojo 全层评估 | 1 天 | — |
| 2. ToolEmu（可选） | 2-3 天 | Phase 1 结果 |
| 3. 威胁模型形式化 | 1 天 | — |
| 4. 论文撰写 | 3-4 天 | Phase 1+3 |
| 5. 质量检查 | 1 天 | Phase 4 |
| **总计** | **~1 周（不含 ToolEmu）/ ~2 周（含 ToolEmu）** | |

---

## 检查清单（来自反思报告）

- [x] 文献检索完成，确认 Owner-Harm 是空白
- [x] 一句话创新声明，无增量词汇
- [x] 有权威评测集（AgentDojo / ToolEmu）
- [x] "所以呢？"测试：通用防御在主人伤害上只有 3.7% → 这个 gap 需要被正视
- [ ] Phase 1 结果出来后做"快速否定门"：如果全 4 层在 AgentDojo 上也只有 ~10% → 说明我们的系统本身不够强，需要调整论述
- [ ] 论文 extended abstract 写完后做一轮毒舌审稿

---

## 红线

- 🚫 不把 3.7% 的结果藏起来——这恰恰是最有力的证据
- 🚫 不再在自建评测集上声称 held-out independent
- 🚫 不把 L4 的 hijacking 93.3% 当主线——它是支线发现
- ✅ 主线是 "Owner-Harm 作为新威胁模型"
- ✅ 3.7% 是"通用防御在新威胁上失效"的证据
- ✅ 85.3% 是"针对性防御可以显著改善"的证据
