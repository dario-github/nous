# 论文科学性审计 — GPT-5.4 + Gemini 3.1 Pro 双审稿人批判
> 2026-03-24 东丞要求：数据跑全，做到高科学性，无可辩驳
> 同时投 CRAI 2026（3/31 AoE 截止）

## 两个审稿人的共识结论：Weak Reject to Strong Reject

**核心判断："claim 太大，evidence 太窄"**

---

## P0 — 科学性根本修复（必须在 3/31 前完成）

### 1. Blind Holdout Set
16轮迭代 = adaptive overfitting 风险。必须准备全新的、系统从未接触过的 blind test set，冻结系统后一次性评估。
- 方案A：AgentHarm 里留出未用过的 split
- 方案B：第二个 benchmark 当 blind holdout

### 2. 置信区间 + 完整统计报告
所有指标补：95% CI / bootstrap CI / per-category breakdown / seed variance / worst-case run。
- 176 样本 100% TPR 的 Clopper-Pearson 95% CI 下界 ≈ 97.9%
- 50 benign 0% FPR 的 95% CI 上界 ≈ 7.1%
- 必须诚实报告，不能只放点估计

### 3. 各层独立贡献量化（Layer Ablation）
- Datalog alone → +Triviality → +Semantic Gate：逐层叠加 TPR/FPR
- 去掉 23 minimal pairs 会掉多少？
- 换别的 LLM（不只是 DeepSeek V3.2）variance 多大？
- 证明每层有不可替代贡献，不是"工程堆料"

### 4. 第二个外部 Benchmark 零调参
找一个 agent safety 公开数据集，不做任何调整直接跑。
- 候选：SafeAgentBench / ToolEmu / WildGuard / XSTest / SimpleSafetyTests
- zero-shot transfer 结果哪怕不完美也比单 benchmark 100% 有说服力

### 5. Owner-Harm Benign 扩容
FPR 已修到 0%（Loop 74），但 50 条 benign 统计上仍脆弱。扩到 200+ benign。
- 标注协议文档化
- 标注是否与系统设计者解耦

### 6. Shadow 分歧审计
30,204 × 0.53% ≈ 160 次分歧。
- 分类：新系统多拦了什么？漏了什么？
- 人工/LLM 审计这 160 次
- 没有分歧分析，consistency 数字 = 废话

---

## P1 — 论文叙事调整

### 7. 不要主打 100% TPR
改为主打"可组合架构 + 各层独立贡献 + 跨场景稳健"。
100% 只是某个 benchmark 上的点估计，不是 claim。

### 8. 消融叙事重构
7%崩塌 ≠ 脆性。= "组合性价值证明：每个组件都不可替代"。
但必须解释：前两层（Datalog + Filter）为什么没有兜底？如果真的形同虚设，三层架构的 claim 就崩了。

### 9. 错误分析 Taxonomy
- FP 在什么语义模式？
- Shadow 分歧在什么场景？
- CC-BOS 剩余成功攻击是什么类型？
- 证明理解系统失效机制，不是"盯着总分调"

### 10. FPR 分母问题（Gemini 指出）
确认 FPR 4.0% 的分母：是 14/352 还是 14/176？如果是前者，真实 FPR = 7.95%。必须核实。

---

## CRAI 2026 投稿信息

| 项目 | 内容 |
|------|------|
| 截稿 | March 31, 2026 AoE（≈北京时间 4月1日中午） |
| 格式 | IEEE Computer Society 8.5×11 双栏 |
| 类型 | Short/Position Paper 4页 |
| 审稿 | Position paper 不要求双盲 |
| 提交 | EasyChair https://easychair.org/conferences/submission_new?a=36191004 |
| 署名 | Dongcheng Zhang, Yanfeather |
| 会议 | IEEE/IFIP DSN 2026, Charlotte NC, June 22-25 |
| 主题 | "From Monolithic Brittleness to Composable Trust" |

---

## GPT-5.4 额外批判点（Gemini 未提）

- majority vote 3 runs 不等于部署时单次决策行为
- 没有 cost-sensitive metric（FN/FP 代价不对称）
- challenge set 45 个太少，L=0.0000 在几十个样本上无外推价值
- "cases" "calls" "scenarios" 评估单位不一致
- 14 天 shadow 不足以证明长期稳健

## Gemini 额外批判点（GPT-5.4 未提）

- FPR 分母可能算错（14/352 vs 14/176）
- 前两层 Datalog+Filter 可能形同虚设（消融证据指向这个结论）
- 16% Owner-Harm FPR = "通过毁灭可用性换取虚假安全性"（已修复到 0%，但论文需说明修复过程）
