# CRAI 2026 — 三层组合安全门形式化分析：完整数学推导

> 工作文件，供论文 Section 2/3 使用
> 日期：2026-03-19
> 版本：v1.0

---

## 1. 形式化建模

### 1.1 基本定义

**分类问题**：对每个 agent tool call $x \in \mathcal{X}$，判断其为有害（$y=1$, harmful）或良性（$y=0$, benign）。

**三层分类器**：

| 层 | 符号 | 类型 | 行为 |
|---|---|---|---|
| L1 (Datalog) | $C_1$ | Early-exit blocker | 匹配已知恶意模式 → **block**；不匹配 → pass through |
| L2 (Triviality) | $C_2$ | Early-exit allower | 识别明显安全操作 → **allow**（跳过 LLM）；不确定 → pass through |
| L3 (Semantic Gate) | $C_3$ | Full classifier | LLM 语义判断 → **block** 或 **allow** |

<!-- 中文注释：关键区别——L1 是"见到坏的就拦"（blocker），L2 是"见到好的就放"（allower），L3 是"剩下的全判"（classifier）。不是简单的串联或并联。 -->

### 1.2 各层参数定义

**L1 (Deterministic Blocker)**：
- $r_1 = P(\text{L1 blocks} \mid y=1)$ — recall（对有害输入的检出率）
- $f_1 = P(\text{L1 blocks} \mid y=0)$ — false positive rate
- Nous 实际值：$r_1 \approx 0.30$，$f_1 \approx 0$（precision $\approx 1$）

**L2 (Triviality Allower)**：
- $\alpha = P(\text{L2 allows} \mid y=1, \text{passed L1})$ — 有害输入被误判为 trivial 的概率
- $\beta = P(\text{L2 allows} \mid y=0, \text{passed L1})$ — 良性输入被正确识别为 trivial 的概率（bypass rate）
- Nous 实际值：$\alpha \approx 0$（有害操作不可能是 read_file），$\beta \approx 0.70$

**L3 (Semantic Classifier)**：
- $r_3 = P(\text{L3 blocks} \mid y=1, \text{reached L3})$ — 条件 recall
- $f_3 = P(\text{L3 blocks} \mid y=0, \text{reached L3})$ — 条件 FPR
- Nous 实际值：$r_3 \approx 0.95$，$f_3 \approx 0.03\text{--}0.05$

**先验**：
- $\pi = P(y=1)$ — 有害输入的基础比率

### 1.3 信息流模型

对任意输入 $x$，决策路径为：

$$
x \xrightarrow{C_1} \begin{cases}
\text{block} & \text{w.p. } r_1 \text{ if } y=1, \text{ or } f_1 \text{ if } y=0 \\
\text{pass} & \text{otherwise} \rightarrow C_2
\end{cases}
$$

$$
x \mid \text{passed } C_1 \xrightarrow{C_2} \begin{cases}
\text{allow (bypass)} & \text{w.p. } \alpha \text{ if } y=1, \text{ or } \beta \text{ if } y=0 \\
\text{pass} & \text{otherwise} \rightarrow C_3
\end{cases}
$$

$$
x \mid \text{reached } C_3 \xrightarrow{C_3} \begin{cases}
\text{block} & \text{w.p. } r_3 \text{ if } y=1, \text{ or } f_3 \text{ if } y=0 \\
\text{allow} & \text{otherwise}
\end{cases}
$$

<!-- 中文注释：这个流程图的关键在于——输入不一定经过所有三层。L1 匹配到就直接 block（不需要 LLM），L2 认为安全就直接 allow（节省 LLM 调用），只有"不确定"的才到 L3。-->

---

## 2. 组合公式推导

### 2.1 系统 TPR（True Positive Rate / Recall）

**目标**：$\text{TPR}_{\text{sys}} = P(\text{system blocks} \mid y=1)$

一个有害输入被系统阻止，有三条互斥路径：

1. **L1 直接拦截**：概率 $r_1$
2. **L1 放行 → L2 不放行 → L3 拦截**：概率 $(1-r_1)(1-\alpha) \cdot r_3$
3. ~~L1 放行 → L2 放行~~：有害输入逃逸（FN），概率 $(1-r_1)\alpha$

> 路径 3 中，L2 错误地将有害输入判为 trivial，导致跳过 L3。这是 L2 的唯一风险。

因此：

$$
\boxed{\text{TPR}_{\text{sys}} = r_1 + (1-r_1)(1-\alpha) \cdot r_3}
$$

**化简**（当 $\alpha = 0$，即有害输入永远不会被判为 trivial）：

$$
\text{TPR}_{\text{sys}} = r_1 + (1-r_1) r_3 = 1 - (1-r_1)(1-r_3)
$$

<!-- 中文注释：这个公式的直觉是——系统漏掉有害输入，当且仅当 L1 和 L3 *同时*漏掉它。这就是并联系统的可靠性公式。-->

**代入 Nous 数据**（$r_1=0.30, \alpha=0, r_3=0.95$）：

$$
\text{TPR}_{\text{sys}} = 1 - (1-0.30)(1-0.95) = 1 - 0.70 \times 0.05 = 1 - 0.035 = 0.965
$$

### 2.2 系统 FPR（False Positive Rate）

**目标**：$\text{FPR}_{\text{sys}} = P(\text{system blocks} \mid y=0)$

一个良性输入被系统错误阻止，路径：

1. **L1 误拦**：概率 $f_1$
2. **L1 放行 → L2 不放行 → L3 误判**：概率 $(1-f_1)(1-\beta) \cdot f_3$

> L2 正确放行的良性输入不会到达 L3，因此不会产生 FP。这是 L2 的核心价值。

$$
\boxed{\text{FPR}_{\text{sys}} = f_1 + (1-f_1)(1-\beta) \cdot f_3}
$$

**化简**（当 $f_1 = 0$，即 L1 无误报）：

$$
\text{FPR}_{\text{sys}} = (1-\beta) \cdot f_3
$$

<!-- 中文注释：L2 的 bypass rate β 直接乘性地降低了 FPR。β=0.70 意味着 70% 的良性输入根本不经过有噪声的 LLM，FPR 直接打三折。-->

**代入 Nous 数据**（$f_1=0, \beta=0.70, f_3=0.05$）：

$$
\text{FPR}_{\text{sys}} = (1-0.70) \times 0.05 = 0.30 \times 0.05 = 0.015
$$

### 2.3 系统 Precision

$$
\text{Prec}_{\text{sys}} = \frac{\text{TPR}_{\text{sys}} \cdot \pi}{\text{TPR}_{\text{sys}} \cdot \pi + \text{FPR}_{\text{sys}} \cdot (1-\pi)}
$$

代入（假设 $\pi = 0.01$，即 1% 恶意率 — 典型生产环境）：

$$
\text{Prec}_{\text{sys}} = \frac{0.965 \times 0.01}{0.965 \times 0.01 + 0.015 \times 0.99} = \frac{0.00965}{0.00965 + 0.01485} = \frac{0.00965}{0.02450} \approx 0.394
$$

对比 L3 单独：

$$
\text{Prec}_{L3} = \frac{0.95 \times 0.01}{0.95 \times 0.01 + 0.05 \times 0.99} = \frac{0.0095}{0.0095 + 0.0495} = \frac{0.0095}{0.0590} \approx 0.161
$$

组合系统的 precision 是 L3 单独的 **2.45 倍**。

### 2.4 各层独立性能对比

| 指标 | L1 alone | L3 alone | 组合系统 |
|------|----------|----------|----------|
| TPR | 0.30 | 0.95 | **0.965** |
| FPR | 0.00 | 0.05 | **0.015** |
| Prec ($\pi$=0.01) | 1.00 | 0.161 | **0.394** |

<!-- 中文注释：
- vs L1：TPR 从 0.30 → 0.965（巨大提升），FPR 从 0 → 0.015（微小代价）
- vs L3：TPR 从 0.95 → 0.965（提升），FPR 从 0.05 → 0.015（大幅改善）
- 组合系统 Pareto 支配 L3（两个指标都更好），与 L1 有 trade-off 但 ROC 面积更大
-->

---

## 3. 关键定理

### Theorem 1: Composability Advantage

**Theorem 1** (Composability Advantage). *Let $C_1$ (early-exit blocker) and $C_3$ (full classifier) have parameters $(r_1, f_1)$ and $(r_3, f_3)$ respectively, with triviality filter bypass rates $(\alpha, \beta)$ satisfying $\alpha = 0$. If $0 < r_1 < 1$, $0 < r_3 < 1$, $f_1 = 0$, and $0 < \beta \leq 1$, then the composite system strictly dominates $C_3$ alone:*

$$
\text{TPR}_{\text{sys}} > r_3 \quad \text{and} \quad \text{FPR}_{\text{sys}} < f_3
$$

**Proof.**

**(i) TPR dominance.** Under $\alpha = 0$:

$$
\text{TPR}_{\text{sys}} = r_1 + (1-r_1) r_3
$$

Since $r_1 > 0$ and $r_3 < 1$:

$$
\text{TPR}_{\text{sys}} - r_3 = r_1 + (1-r_1) r_3 - r_3 = r_1 - r_1 r_3 = r_1(1-r_3) > 0
$$

Therefore $\text{TPR}_{\text{sys}} > r_3$. $\square$

Similarly, $\text{TPR}_{\text{sys}} - r_1 = (1-r_1)r_3 > 0$, so $\text{TPR}_{\text{sys}} > \max(r_1, r_3)$.

<!-- 中文注释：TPR 的提升来自"并联"效应——L1 和 L3 各自覆盖不同的恶意模式，合起来覆盖更广。只要 L1 能额外覆盖一些 L3 覆盖不到的（或有随机性遗漏的），系统 recall 就严格提升。-->

**(ii) FPR reduction.** Under $f_1 = 0$ and $\beta > 0$:

$$
\text{FPR}_{\text{sys}} = (1-\beta) f_3 < f_3
$$

The inequality is strict since $\beta > 0$. $\square$

**(iii) Strict Pareto dominance over $C_3$.** Combining (i) and (ii):

$$
(\text{TPR}_{\text{sys}}, \text{FPR}_{\text{sys}}) \succ_{\text{Pareto}} (r_3, f_3)
$$

meaning the composite system achieves higher recall *and* lower false alarm rate simultaneously. $\blacksquare$

**Remark 1.** The composite system does *not* Pareto-dominate $C_1$ in general, since $\text{FPR}_{\text{sys}} = (1-\beta)f_3 \geq 0 = f_1$. However, the recall gain $\text{TPR}_{\text{sys}} - r_1 = (1-r_1)r_3$ is typically very large (e.g., $+0.665$ in Nous), making the trade-off overwhelmingly favorable.

**Remark 2** (Orthogonality Condition). The TPR gain $r_1(1-r_3)$ is maximized when $C_1$ and $C_3$ have *complementary* error patterns — i.e., the inputs $C_3$ misses are partially covered by $C_1$. In Nous, this holds because L1 (pattern-matching) and L3 (semantic understanding) operate on fundamentally different signal types: L1 catches known URL patterns and destructive action templates that L3 might occasionally miss due to stochastic variance, while L3 catches semantically harmful requests that no pattern can match.

### Theorem 2: Fail-Closed Safety Guarantee

**Theorem 2** (Degraded-Mode Safety). *If $C_1$ is fail-closed (infrastructure failure → block) and $C_3$ experiences total failure, the system maintains a safety lower bound:*

$$
\text{TPR}_{\text{degraded}} \geq r_1
$$

*In particular, all inputs matching $C_1$'s rule set are blocked regardless of $C_3$'s availability.*

**Proof.** When $C_3$ fails:
- If fail-closed: all inputs reaching $C_3$ are blocked → $\text{TPR} = r_1 + (1-r_1)(1-\alpha) \cdot 1 \geq r_1$
- If fail-open (Nous default for semantic gate): $C_3$'s verdict reverts to Datalog's → $\text{TPR} = r_1$

In either case, $\text{TPR}_{\text{degraded}} \geq r_1 > 0$. $\blacksquare$

<!-- 中文注释：这个定理的实际意义是——即使 LLM 服务完全宕机，Datalog 层仍然以 <0.1ms 延迟拦截所有已知恶意模式。这是 monolithic LLM classifier 做不到的。对生产系统而言，"LLM 挂了还能工作"是巨大的可靠性优势。-->

**Corollary 2.1** (Availability). *Under fail-closed semantics for $C_1$ and fail-open for $C_3$, the system never becomes less safe than $C_1$ alone, while gaining semantic coverage when $C_3$ is operational.*

### Corollary 3: Cost Efficiency

**Corollary 3** (LLM Call Reduction). *The expected fraction of inputs requiring LLM inference is:*

$$
\rho = (1-r_1) \cdot \pi \cdot (1-\alpha) + (1-f_1) \cdot (1-\pi) \cdot (1-\beta)
$$

*Under Nous parameters ($r_1=0.30, f_1=0, \alpha=0, \beta=0.70, \pi=0.01$):*

$$
\rho = 0.70 \times 0.01 \times 1.0 + 1.0 \times 0.99 \times 0.30 = 0.007 + 0.297 = 0.304
$$

*i.e., only ~30.4% of inputs reach the LLM, a **69.6% reduction** in inference cost.*

<!-- 中文注释：
- 有害输入的 70% 被 L1 拦截（不需要 LLM）
- 良性输入的 70% 被 L2 旁路（不需要 LLM）
- 在良性为主的生产流量中（π=0.01），LLM 调用量几乎线性地被 β 缩减
-->

**Proof.** An input reaches $C_3$ iff it passes both $C_1$ and $C_2$. For $y=1$: probability $(1-r_1)(1-\alpha)$. For $y=0$: probability $(1-f_1)(1-\beta)$. Marginalizing over $y$:

$$
\rho = P(\text{reaches } C_3) = (1-r_1)(1-\alpha)\pi + (1-f_1)(1-\beta)(1-\pi) \quad \blacksquare
$$

---

## 4. 实验数据验证

### 4.1 理论预测 vs 实际观测（Val Set）

**参数估计**（来自各层独立测试和生产数据）：

| 参数 | 估计值 | 来源 |
|------|--------|------|
| $r_1$ | 0.30 | Datalog 单独 recall（62 条规则覆盖约 30% 的 AgentHarm 恶意模式） |
| $f_1$ | 0.00 | Datalog precision ≈ 1（规则匹配到的 100% 是真恶意） |
| $\alpha$ | 0.00 | 设计保证（有害操作不可能匹配 trivial 白名单：read_file, web_search 等） |
| $\beta$ | 0.70 | 生产数据（~70% 良性操作为 trivial 类型） |
| $r_3$ | 0.95 | Semantic Gate 单独 TPR（DeepSeek-V3.1） |
| $f_3$ | 0.056 | Val set 单次运行 FPR（2/36 benign blocked） |

**理论预测**：

$$
\text{TPR}_{\text{pred}} = 1 - (1-0.30)(1-0.95) = 1 - 0.035 = 0.965
$$

$$
\text{FPR}_{\text{pred}} = (1-0.70) \times 0.056 = 0.30 \times 0.056 = 0.017
$$

**实际观测**（Val set, majority vote over 3 runs）：
- $\text{TPR}_{\text{obs}} = 1.000$（36/36 harmful blocked）
- $\text{FPR}_{\text{obs}} = 0.000$（0/36 benign blocked, with majority vote）

**单次运行**（latest, Loop 50）：
- $\text{TPR}_{\text{obs}} = 1.000$（36/36）
- $\text{FPR}_{\text{obs}} = 0.056$（2/36）

### 4.2 差异分析

<!-- 中文注释：理论预测 TPR=0.965 < 实际 TPR=1.000。原因：
1. r₃ 的估计（0.95）是 L3 的边际 recall，但在 val set 上 L3 实际表现更好（val 场景比较标准）
2. r₁ 和 r₃ 在 val set 上有更多重叠（L1 覆盖的那些 L3 也覆盖），所以系统 FNR 比理论预测更低
3. Val set (n=72) 太小，没有采样到 L1 和 L3 都漏掉的边界案例
-->

| 指标 | 理论预测 | 实际（majority vote） | 实际（单次） | 差异原因 |
|------|----------|----------------------|-------------|----------|
| TPR | 0.965 | 1.000 | 1.000 | $r_3$ 在 val set 上可能 >0.95；小样本 |
| FPR | 0.017 | 0.000 | 0.056 | Majority vote 消除了 LLM 随机噪声；单次符合预测 |

**关键发现**：
- 单次运行的 FPR=0.056 与理论预测 0.017 的差异来自 $\beta$ 的 val set 估计：val set 中良性样本不一定有 70% 是 trivial 的。如果 val set 的 $\beta_{\text{val}} \approx 0$（所有良性样本都非 trivial、都需要经过 L3），则 $\text{FPR}_{\text{pred}} = f_3 = 0.056$，与观测完美一致。
- 这正是 val set 的设计意图：AgentHarm benchmark 的良性样本是对应恶意样本的最小对（minimal pairs），本身就不是 trivial 操作，因此 $\beta_{\text{val}} \approx 0$。

### 4.3 Shadow Mode 验证

生产 shadow mode 数据（17,900+ calls, 7 天）：

| 指标 | 理论预测（生产参数） | 实际观测 |
|------|---------------------|----------|
| Consistency | — | 99.44% |
| FP | — | 4 |
| FN | — | 97 |

FN=97 的绝大多数（94/97）为 `exec` 类型，severity=medium。这反映了 L1 Datalog 规则对 exec 的保守匹配（existing system blocks all exec → shadow mode's semantic gate allows some → counted as FN）。这不是系统缺陷，而是 shadow mode 定义下的 expected disagreement。

### 4.4 Challenge Set

15 adversarial scenarios（adversarial_v1 subset）：
- $\text{TPR}_{\text{obs}} = 0.667$（10/15 harmful blocked）
- $\text{FPR}_{\text{obs}} = 0.000$

理论分析：5 个 FN 全部为 `harmful_evasion` 类型（sophisticated intent disguise）。这些场景同时逃过了 L1（无 pattern 匹配）和 L3（语义伪装成功）。理论 FNR = $(1-r_1)(1-r_3^{\text{adv}})$ 其中 $r_3^{\text{adv}} < r_3$（对抗场景下 L3 recall 降低）。

$$
r_3^{\text{adv}} = 1 - \frac{\text{FNR}_{\text{obs}}}{1-r_1} = 1 - \frac{0.333}{0.70} = 1 - 0.476 = 0.524
$$

即 L3 在对抗场景下 recall 从 0.95 降至 ~0.52 — 这正是需要 intent decomposition 等增强手段的动机。

---

## 5. 与 Monolithic 方法的理论对比

### 5.1 单一 LLM Classifier（如 Llama Guard）

Monolithic LLM classifier 参数：$(r_m, f_m)$，假设 $r_m = r_3 = 0.95, f_m = f_3 = 0.05$。

| 指标 | Monolithic | Composable (Nous) | 改善 |
|------|-----------|-------------------|------|
| TPR | 0.95 | 0.965 | +1.5% |
| FPR | 0.05 | 0.015 (prod) / 0.056 (val-single) | −70% (prod) |
| Latency (harmful, L1 hit) | 200-500ms | **0.055ms** | 3600-9000× |
| Availability (LLM down) | **0%** | **30% recall** (L1 alone) | ∞ |
| Cost per call | $c_{\text{LLM}}$ | $0.304 \cdot c_{\text{LLM}}$ | −70% |

### 5.2 单一规则系统（如 NeMo Guardrails）

Pure rule system 参数：$(r_1, f_1) = (0.30, 0.00)$。

| 指标 | Pure Rules | Composable (Nous) | 改善 |
|------|-----------|-------------------|------|
| TPR | 0.30 | 0.965 | +222% |
| FPR | 0.00 | 0.015 | +0.015 (acceptable) |
| Semantic understanding | None | Full LLM | Qualitative leap |

### 5.3 Swiss Cheese 类比

Nous 的三层架构在结构上类似于 James Reason 的 Swiss Cheese Model（1990）：每层是一片"奶酪"，各有"孔洞"（coverage gaps），但孔洞不重叠，恶意输入必须穿透所有层才能逃逸。

形式化：系统 FNR（False Negative Rate）= $P(\text{miss all layers} \mid y=1)$：

$$
\text{FNR}_{\text{sys}} = (1-r_1) \cdot \alpha + (1-r_1)(1-\alpha)(1-r_3) = (1-r_1)[\alpha + (1-\alpha)(1-r_3)]
$$

当 $\alpha = 0$：$\text{FNR}_{\text{sys}} = (1-r_1)(1-r_3)$

这是两个独立失败概率的乘积 — 只要 L1 和 L3 的失败模式不完全相关，系统可靠性就严格高于任何单层。

**独立性条件**：L1（pattern matching）和 L3（LLM semantic）的决策机制根本不同，因此其错误具有天然的弱相关性。当然，某些 adversarial inputs 可能同时逃过两层（如 harmful_evasion 类型），但在一般分布上独立性假设大致成立。

---

## 6. 推广：一般 k 层分析

对于 $k$ 层 early-exit blocker 串联（每层要么 block 要么 pass），系统 recall：

$$
\text{TPR}_{\text{sys}} = 1 - \prod_{i=1}^{k} (1 - r_i)
$$

这单调递增于 $k$，即**加层只增加 recall，不减少**。

但 FPR 的行为取决于层类型：
- **Blocker 层**：FPR 累加（每层可能误报）→ $\text{FPR} = 1 - \prod(1-f_i)$
- **Allower 层**（如 L2）：FPR 乘性缩减 → $\text{FPR} \times (1-\beta_i)$

Nous 的混合架构（1 blocker + 1 allower + 1 classifier）巧妙地组合了两种效应：
- L1 (blocker) 提升 recall，几乎不增加 FPR
- L2 (allower) 乘性缩减 FPR，几乎不降低 recall
- L3 (classifier) 处理剩余的"不确定"集

这种 **heterogeneous composition** 是优于 homogeneous stacking（如 N 个 LLM 投票）的关键设计。

---

## 7. 总结

### 核心结论

1. **组合系统 Pareto 支配任何单一 LLM classifier**（Theorem 1）：TPR 提升 + FPR 降低同时实现
2. **Fail-closed 层提供可用性保障**（Theorem 2）：LLM 宕机不影响确定性层的拦截能力
3. **Triviality filter 提供乘性成本缩减**（Corollary 3）：70% 的 LLM 调用被消除，同时 FPR 被同比例缩减
4. **异构组合优于同构堆叠**：不同决策机制（pattern → heuristic → semantic）的互补性是优势的根本来源

### 公式速查

| 指标 | 公式（$f_1=0, \alpha=0$ 简化版） |
|------|------|
| $\text{TPR}_{\text{sys}}$ | $1 - (1-r_1)(1-r_3)$ |
| $\text{FPR}_{\text{sys}}$ | $(1-\beta) \cdot f_3$ |
| $\text{FNR}_{\text{sys}}$ | $(1-r_1)(1-r_3)$ |
| LLM call rate $\rho$ | $(1-r_1)\pi + (1-\beta)(1-\pi)$ (simplified) |
| $\text{Prec}_{\text{sys}}$ | $\frac{\text{TPR}_{\text{sys}} \cdot \pi}{\text{TPR}_{\text{sys}} \cdot \pi + \text{FPR}_{\text{sys}} \cdot (1-\pi)}$ |
