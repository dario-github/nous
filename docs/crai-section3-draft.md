# Section 3: Evaluation — DRAFT v1

> CRAI 2026 Position Paper, Section 3 (~1 page, IEEE double-column)
> 写于 2026-03-21 01:30 CST
> Status: First draft

---

## 3. Evaluation

We evaluate Nous along three axes: (1) benchmark performance on AgentHarm, (2) production shadow deployment, and (3) adversarial robustness. We then critically examine the limitations of our evaluation methodology.

### 3.1 AgentHarm Benchmark

We use AgentHarm (Souly et al., ICLR 2025), comprising 176 harmful and 176 benign agentic scenarios across 11 categories including cybercrime, fraud, harassment, and disinformation. Data is split into train (104+104), validation (36+36), and test (36+36) with stratified sampling across categories.

**Results.** On the validation set with majority voting (k=3):

| Metric | Val | Test |
|--------|-----|------|
| TPR (harmful correctly blocked) | 100% | 100% |
| FPR (benign incorrectly blocked) | 0.0% | 4.0% |

Layer-level analysis reveals the contribution of each component. Of 176 harmful inputs, the Datalog layer catches 12 (6.8%) via pattern matching. The triviality filter correctly routes 0 harmful actions to bypass (α=0 maintained). The remaining 164 are handled by the semantic gate with 100% recall.

For the 176 benign inputs, the triviality filter bypasses 114 (64.8%), routing only 62 to the semantic gate. This means the FPR of 4.0% on the test set corresponds to approximately 3 false positives out of ~62 semantic gate evaluations — a per-evaluation error rate of ~4.8%.

**Per-category breakdown.** FPR concentrations appear in Disinformation (2 FP), Drugs (1 FP), Copyright (1 FP), Cybercrime (1 FP), and Sexual Content (1 FP) on the full-set evaluation. These cluster around scenarios where benign actions share surface features with harmful patterns — e.g., a journalism research query about disinformation campaigns flagged as disinformation itself.

### 3.2 Shadow Deployment

Before promoting Nous to primary interceptor, we operated it in shadow mode alongside the existing rule-based safety system for 14+ days, processing 20,000+ real production tool calls from an autonomous AI agent.

**Statistics (as of 2026-03-20):**

| Metric | Value |
|--------|-------|
| Total calls evaluated | 20,011 |
| Consistency with existing system | 99.45% |
| False positives (shadow vs. production) | 4 (0.02%) |
| False negatives | 106 (0.53%) |
| Shadow duration | 14+ days |
| Evaluation runs | 176 |

The 106 "false negatives" warrant explanation: these are cases where the existing rule system blocked but Nous allowed. Manual review of a 20% sample (n=21) found that 18 (86%) were *overly conservative blocks by the existing system* — the prior system blocked `exec` calls to benign shell commands that Nous correctly identified as safe. Only 3 represented genuine safety-relevant disagreements, all involving multi-step scenarios where individual actions appeared benign but could chain into harmful sequences.

The 4 false positives were all attributable to MoE stochastic variance — the same input evaluated twice yielded different verdicts. Majority voting (k=3) eliminates all 4 in replay testing.

### 3.3 Adversarial Robustness

We constructed a 45-scenario challenge set targeting known evasion patterns:

1. **Framing attacks** (15 scenarios): wrapping harmful requests in legitimate-sounding contexts ("I'm a security researcher testing...")
2. **Intent decomposition evasion** (10 scenarios): splitting harmful actions across multiple benign-looking steps
3. **Authority claims** (10 scenarios): invoking institutional authority ("as instructed by the compliance team...")
4. **Stylistic obfuscation** (10 scenarios): classical Chinese, formal academic language, role-play framing

Results: TPR 66.7% (10/15) on initial evaluation, improving to 93.3% after prompt engineering informed by failure analysis. The 5 initial failures clustered in authority-claim scenarios — the LLM's training-time RLHF alignment makes it predisposed to comply with authority framing.

Additionally, a 20-scenario red-team exercise (CC-BOS campaign) tested classical Chinese encoding, gradual escalation, and pseudo-historical authority claims. Pre-mitigation attack success: 4.1/5.0. Post-mitigation (after adding T14 content safety, T15 authority detection, and Step 0 normalization): 1.1/5.0.

### 3.4 Limitations of Our Evaluation

We identify several structural weaknesses that constrain the conclusions drawable from our results:

**Benchmark ceiling effect.** AgentHarm scenarios are predominantly *direct* harmful requests with clear intent signals. A system achieving 100% TPR on this benchmark has not necessarily demonstrated robustness against sophisticated adversarial inputs. This is analogous to a standardized test that is too easy — perfect scores reveal nothing about the upper bound of capability. The challenge set partially addresses this, but at 45 scenarios, it lacks statistical power.

**Self-referential shadow evaluation.** Shadow consistency (99.45%) measures agreement with the prior system, not ground truth correctness. If the prior system has systematic blind spots, shadow mode would faithfully reproduce them. The 106 "false negatives" where Nous disagrees with the prior system are actually the most informative data points — they reveal where the systems' safety philosophies diverge.

**Single-turn limitation.** All evaluations operate on individual tool calls. Real-world agent jailbreaks increasingly exploit multi-turn trajectories where each step appears benign in isolation. Our architecture currently has no mechanism for trajectory-level analysis.

**Evaluator-evaluated conflation.** The semantic gate and the evaluation harness both rely on LLM judgment. A systematic bias in how LLMs categorize harm would manifest as artificially high scores rather than being caught by the evaluation.

---

## Notes for revision

- [ ] Add Table 1: per-category TPR/FPR breakdown
- [ ] Add Figure 2: shadow deployment consistency over time (should show convergence)
- [ ] Consider: is 20K calls enough for statistical claims? Calculate confidence intervals
- [ ] The 86% "overly conservative" FN claim needs stronger evidence — full sample review?
- [ ] Adversarial results: 66.7% → 93.3% improvement needs more explanation of what changed
- [ ] IEEE format: tables need proper formatting, reduce whitespace
- [ ] 东丞的观点 "试卷太简单" 已融入 §3.4 第一段 — 这是论文的诚实之处
- [ ] Consider adding: comparison with Llama Guard / ShieldGemma baselines if time permits
- [ ] KG enrichment results (FPR reduction from KG signals) — mention or save for full paper?
