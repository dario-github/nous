# GPT-5.4-Pro 第二轮审稿报告
**日期**: 2026-04-09
**评分变化**: Weak Reject → **Borderline（偏 WR）**

---

## 逐条回应评估

### 8 Weaknesses
| # | 问题 | 评估 |
|---|---|---|
| W1 | 核心叙事失准 | ✅ Resolved |
| W2 | 数字不一致 43.3% vs 55% | ⚠️ Partially — 摘要把 75.3% gate-only 写成了 "four-layer overall"，实际 full-system 应是 85.3% |
| W3 | Benchmark 构造透明度 | ⚠️ Partially — 补了设计原则，缺标注流程/annotator/复核/release 计划 |
| W4 | 74 loops tuning leakage | ⚠️ Partially — 有 dev/held-out 意识，但 Loops 76-77 patch 来源不清 |
| W5 | Shadow 99.47% 不是强证据 | ⚠️ Partially — 补了 disagreement 审计，但仍放得过于显眼 |
| W6 | Baseline 不公平 | ⚠️ Partially — 承认了弱 baseline，但没补更强对照 |
| W7 | Verifier 证据规模偏小 | ⚠️ Partially — 正式写入论文，但只在 Hijacking 子类评估 |
| W8 | "Neurosymbolic" 过度包装 | ✅ Resolved |

### 6 Questions
| # | 问题 | 评估 |
|---|---|---|
| Q1 | 数字口径 | ⚠️ Partially — 拆开了但没做统一口径说明 |
| Q2 | 全 benchmark 总体 with verifier | ❌ Not addressed — **最关键缺失** |
| Q3 | 过拟合风险 | ⚠️ Partially |
| Q4 | Benchmark 构造 | ⚠️ Partially |
| Q5 | Shadow disagreement 审计 | ⚠️ Partially |
| Q6 | 剩余 structural 升级 | ✅ Resolved |

---

## 剩余问题（按优先级）

### P1 [必须] 报 full-system overall metric
gate-only overall = 75.3%, full L1-L4 overall 应是 ~85.3%。摘要/贡献段口径错误。

### P2 [必须] 74 loops / 76-77 patch / v3 的时间线
做一个可审计 timeline，证明 held-out 独立性。

### P3 [应该] Benchmark construction appendix
标注流程、annotator、复核、release 计划。

### P4 [应该] L4 runtime activation policy
真实运行时谁来判定启用 L4？不能靠 oracle category label。

### P5 [最好] 更强 baseline
至少一个 sequence-aware / agent-runtime baseline。

### P6 [最好] Infrastructure Exposure 20% FPR 诚实讨论

---

## 审稿人新发现的问题
**L4 的 deployment story 没闭环**：论文说 L4 "scoped to Hijacking"，但没说运行时怎么知道当前 case 是 Hijacking。如果需要 oracle label，deployment claim 不成立。
