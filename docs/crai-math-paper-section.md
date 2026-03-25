# Formal Analysis of Composable Safety Gates

> Paper-ready section (~1 page for 4-page IEEE position paper)

## Formal Model

We model each layer as a binary classifier with type-specific behavior. Let $r_i$ and $f_i$ denote the true positive rate (recall) and false positive rate of layer $i$, respectively.

**Layer 1 (Deterministic Blocker)** applies pattern-matching rules: if a match is found, the input is blocked immediately; otherwise it passes through. **Layer 2 (Triviality Filter)** identifies clearly benign actions (e.g., `read_file`): matched inputs are allowed without LLM inference; unmatched inputs pass through. Let $\alpha = P(\text{L2 allows} \mid y\!=\!1)$ and $\beta = P(\text{L2 allows} \mid y\!=\!0)$ denote its error and bypass rates. **Layer 3 (Semantic Gate)** is an LLM classifier applied only to inputs that pass both prior layers.

For an input with true label $y$, the decision path is:

$$
x \xrightarrow{C_1} \begin{cases} \text{block} \\ \text{pass} \to C_2 \end{cases} \xrightarrow{C_2} \begin{cases} \text{allow (bypass)} \\ \text{pass} \to C_3 \end{cases} \xrightarrow{C_3} \begin{cases} \text{block} \\ \text{allow} \end{cases}
$$

The composite system metrics are:

$$
\text{TPR}_{\text{sys}} = r_1 + (1\!-\!r_1)(1\!-\!\alpha) \cdot r_3, \quad
\text{FPR}_{\text{sys}} = f_1 + (1\!-\!f_1)(1\!-\!\beta) \cdot f_3
$$

Under the design constraints $f_1 \approx 0$ (high-precision rules) and $\alpha = 0$ (harmful actions are never trivial), these simplify to:

$$
\text{TPR}_{\text{sys}} = 1 - (1\!-\!r_1)(1\!-\!r_3), \quad \text{FPR}_{\text{sys}} = (1\!-\!\beta) \cdot f_3
$$

## Composability Advantage

**Theorem 1.** *If $0 < r_1 < 1$, $0 < r_3 < 1$, $f_1 = 0$, $\alpha = 0$, and $\beta > 0$, then the composite system strictly Pareto-dominates the semantic gate alone: $\text{TPR}_{\text{sys}} > r_3$ and $\text{FPR}_{\text{sys}} < f_3$.*

*Proof.* $\text{TPR}_{\text{sys}} - r_3 = r_1(1\!-\!r_3) > 0$. $\text{FPR}_{\text{sys}} = (1\!-\!\beta)f_3 < f_3$ since $\beta > 0$. $\square$

The recall gain $r_1(1\!-\!r_3)$ is maximized when the layers have *complementary error patterns* — pattern-matching catches structural threats that LLMs occasionally miss due to stochastic variance, while LLMs catch semantically harmful requests invisible to rules.

**Theorem 2** (Degraded-Mode Safety). *Under fail-closed semantics for $C_1$, if $C_3$ fails entirely, $\text{TPR}_{\text{degraded}} \geq r_1$ — the system maintains deterministic-layer coverage regardless of LLM availability.*

**Corollary** (Cost Reduction). The fraction of inputs requiring LLM inference is $\rho = (1\!-\!r_1)(1\!-\!\alpha)\pi + (1\!-\!f_1)(1\!-\!\beta)(1\!-\!\pi)$. For benign-dominated traffic ($\pi \ll 1$), $\rho \approx 1 - \beta$, yielding a $\beta$-proportional reduction in inference cost.

## Empirical Validation

Table I compares theoretical predictions with observed results on the AgentHarm benchmark (val split: 36 harmful + 36 benign) using parameters estimated from independent layer evaluation: $r_1\!=\!0.30$, $r_3\!=\!0.95$, $f_3\!=\!0.056$, $\beta\!=\!0.70$.

| Metric | Theory | Observed (single run) | Observed (maj. vote ×3) |
|--------|--------|-----------------------|-------------------------|
| TPR | 0.965 | 1.000 | 1.000 |
| FPR | 0.017† | 0.056 | 0.000 |

†Production $\beta\!=\!0.70$; val benchmark uses minimal pairs where $\beta_{\text{val}}\!\approx\!0$, predicting $\text{FPR}\!=\!f_3\!=\!0.056$ (matches observation).

Shadow deployment (17,900+ calls, 7 days) shows 99.44% consistency with the existing rule-based system, with FP=4 and FN=97 (93% medium-severity `exec` disagreements). The triviality filter bypasses ~70% of production calls, validating $\beta \approx 0.70$ and the predicted 70% LLM cost reduction.

On the adversarial challenge set (15 scenarios), TPR drops to 66.7% — the 5 false negatives are all `harmful_evasion` type where $r_3^{\text{adv}} \approx 0.52$, motivating ongoing work on intent decomposition to improve adversarial robustness.
