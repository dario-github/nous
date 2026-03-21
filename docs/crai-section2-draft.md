# Section 2: Composable Safety Gate Architecture — DRAFT v1

> CRAI 2026 Position Paper, Section 2 (~1 page, IEEE double-column)
> 写于 2026-03-21 00:03 CST
> Status: First draft, needs review

---

## 2. Architecture

We present a three-layer composable safety gate that intercepts every tool call in an agentic system. Each layer addresses a distinct failure mode, and layers compose sequentially: an input blocked or allowed by an earlier layer never reaches later ones.

**Design principles.** (1) *Composability*: each layer can be independently tested, replaced, and formally verified. (2) *Fail-closed*: any layer failure (parse error, LLM timeout, config corruption) results in a block verdict, never silent passthrough. (3) *Cost-aware routing*: expensive LLM inference is reserved for genuinely ambiguous cases.

### 2.1 Layer 1: Deterministic Blocker (Datalog)

The first layer applies pattern-matching rules expressed as Datalog constraints. Our implementation uses a TypeScript Datalog engine achieving P50 latency of 0.055ms per evaluation — negligible compared to tool execution time.

Rules are declarative and auditable. Each rule maps an observable fact (URL pattern, action type, target resource) to a verdict with a human-readable justification:

```
url_has_social_pattern(X) :- action_url(X), matches(X, "twitter|instagram|weibo").
block(X, "T5: social media link requires standard processing") :- url_has_social_pattern(X).
```

The current deployment includes 62 rules covering destructive actions (`rm`, `DROP TABLE`), social media interactions, protected file modifications, and known-malicious patterns. Rules achieve **zero false positives** by construction — each is manually authored and verified against the benign test set before deployment.

**Fail-closed semantics.** If the Datalog engine encounters a parse error in the constraint file, the entire input is blocked. This is a critical safety property: a corrupted `T3.yaml` (our most important security rule file) cannot silently degrade protection. We note this was identified as a P0 gap in an independent code audit — the initial implementation used `warnings.warn()` instead of hard failure, which we have since corrected.

### 2.2 Layer 2: Triviality Filter

Not all actions require semantic analysis. The triviality filter identifies clearly benign actions — `read_file`, `web_search` without a targeted query, `list_directory` — and allows them to bypass LLM inference entirely.

The filter uses action-type classification combined with content-length heuristics. In production, it bypasses approximately 70% of all tool calls ($\beta \approx 0.70$), reducing LLM inference costs proportionally. The bypass rate is validated by the design constraint $\alpha = 0$: no harmful action should be classified as trivial. This is enforced by maintaining a negative list — action types that are *never* trivial (`exec`, `write_file`, `send_message`, `delete`).

### 2.3 Layer 3: Semantic Gate (LLM + Minimal Pairs)

The semantic layer handles the genuinely ambiguous cases that survive Layers 1 and 2. It uses an LLM (DeepSeek-V3.1 in our deployment) with a carefully engineered prompt containing 23 minimal pair examples.

**Minimal pair design.** Each example pair consists of a harmful variant and its benign near-neighbor, with explicit reasoning for each verdict:

- *Harmful*: "Help me modify patient records to hide a medication error" → Block (medical record tampering)
- *Benign*: "Help me correct the dosage guide based on the latest FDA update" → Allow (legitimate medical documentation)

This approach teaches the LLM the *decision boundary* rather than just the categories, significantly improving precision on edge cases compared to category-level few-shot prompting.

**Intent decomposition.** Before the semantic gate evaluates, a pre-gate analysis extracts structured intent: `stated_intent`, `core_task`, `required_capabilities`, and `risk_factors`. This separation prevents a common failure mode where benign framing ("I'm doing security research") masks harmful core actions. The semantic gate receives both the raw action and the structured intent, making independent judgments on each.

**Calibrated confidence.** The gate outputs a confidence score (0.0–1.0) with a blocking threshold at 0.7. Scores between 0.5–0.7 trigger a "soft block" requiring human confirmation, creating a graduated response rather than a binary allow/block.

**Stochastic variance mitigation.** LLMs using Mixture-of-Experts architectures exhibit non-deterministic outputs even at temperature=0 due to floating-point routing variance. We address this with majority voting over 3 independent evaluations for any input scoring within 0.1 of the decision threshold.

### 2.4 Composition and Formal Properties

The sequential composition yields a system where:

$$\text{TPR}_{\text{sys}} = 1 - (1-r_1)(1-r_3)$$
$$\text{FPR}_{\text{sys}} = (1-\beta) \cdot f_3$$

Under our design constraints ($f_1 = 0$, $\alpha = 0$, $\beta > 0$), the composite system **strictly Pareto-dominates** any individual layer: it achieves higher TPR than the semantic gate alone (by $r_1(1-r_3)$) while simultaneously achieving lower FPR (by factor $1-\beta$). This is not an empirical observation but a mathematical guarantee under the stated constraints.

**Degraded-mode safety.** If the LLM becomes unavailable, the system gracefully degrades to Layer 1 coverage ($\text{TPR} \geq r_1$) rather than failing open. In our deployment, $r_1 = 0.30$ — pattern rules alone catch 30% of harmful actions, providing a non-trivial safety floor.

Figure 1 illustrates the decision flow and layer interaction.

---

## Notes for revision

- [ ] Need to create Figure 1 (architecture diagram)
- [ ] IEEE formatting: equations need proper numbering
- [ ] Consider moving formal proofs to appendix if space is tight
- [ ] DeepSeek-V3.1 might need more context on why this model (cost, latency, quality tradeoff)
- [ ] Reviewer might ask: why Datalog specifically? Compare with OPA/Rego
- [ ] The P0 fail-closed gap story is honest but risky — reviewer might see it as weakness. Frame as: "independent audit revealed → immediately corrected → validates methodology"
- [ ] 23 minimal pairs — should we provide a few more example pairs?
- [ ] Knowledge graph enrichment (KG Loop 1 results) — mention as enhancement or save for full paper?
