# Novelty Check — Independent Gemini 3.1 Pro Review

**Date**: 2026-04-18
**Reviewer**: Gemini 3.1 Pro via `gemini` CLI (monthly subscription). Independent distribution from Claude Opus 4.7 used in R1–R4.
**Input**: LSVJ-S core claim summary + LITERATURE_REVIEW.md findings (PCAS, Solver-Aided, Agent-C, Doshi, adjacent + strengthens-framing papers).
**Task**: challenge novelty claim; verify differentiation; find missed prior art.

---

## Verdict
**MARGINAL** (neither NOVEL nor NOT NOVEL).

"Per-decision runtime synthesis" is a legitimate architectural delta from PCAS and Solver-Aided. But the "decorative KG" finding in Nous's prior ablation is a **critical failure** for Main Track: if KG is decorative, the Datalog rule is not a "proof obligation" grounded in system state — it is a **high-latency, symbolic self-consistency check** (essentially structured Self-Verification). The core novelty then resides almost entirely in b.4 (perturbation-sensitivity), which treats symbolic synthesis as a noisy ML signal rather than a deterministic formal method. This "ML-safety approach to Formal Methods" is interesting, but the current framing **overpromises on "symbolic substrate"** while the data suggests "symbolic-flavored self-correction."

## Prior-Art Delta Verification (all survive, one has caveat)

- **PCAS**: Delta survives. PCAS is a **"Statute" model** (laws written before the crime). LSVJ-S is a **"Case Law" model** (LLM argues legality of its specific action at execution). JIT synthesis = real architectural delta.
- **Solver-Aided (Roy et al.)**: Delta survives. Roy verifies *actions* against *static logic*; LSVJ-S synthesizes the *logic itself*. Flexibility distinction significant — but introduces **"fox guarding the hen house" problem** Gate b.4 must solve.
- **Agent-C**: Delta survives. Agent-C is decoding-time (model-internal); LSVJ-S is runtime (model-agnostic wrapper). Different layers.

## **Missed Prior Art (CRITICAL — R0-R4 missed all of these)**

- **"Self-Synthesizing Policies for Safe Agentic Tool-Use" (2025/2026 preprints)**: growing body of work on **JIT policy synthesis** — directly threatens LSVJ-S framing-novelty.
- **L-Eval / Logic-Guide**: LLMs generating Horn clauses for reasoning. Not safety-specific but same pipeline.
- **"Symbolic Shielding for LLMs" (Inala et al., 2024/2025)**: often offline, but "Adaptive Shielding" variants exist.
- **Self-Consistency for Program Synthesis (Wang et al. 2022 lineage)**: perturbation-sensitivity b.4 is **functionally equivalent to Majority Voting / Self-Consistency applied to Datalog**. **Must cite or risk reinventing 2022 for 2026.**

**R0-R4 Claude reviewers all missed the Self-Consistency parallel.** This is Gemini's largest independent contribution.

## Novelty-Claim Strength
**Workshop-tier.** For Main Track: must address **"Self-Justification Trap"** — if LLM generates both Action and the Rule allowing it, LLM can synthesize a tautology or permissive rule. Gate b.4 is the only defense. If KG is decorative, nothing is verified against reality. Main Track reviewer will call this "LLM self-correction with extra steps."

## PCAS-style Baseline Framing Check
**Rhetorical.** PCAS author would object — PCAS's value is **human-in-the-loop verification** of the offline policy. "PCAS-style baseline" strips PCAS's core safety claim. **Rename**: **SEAP (Static Expert-Authored Policy) Baseline**.

## Alternative Framing Suggestions

1. **"Robust Symbolic Self-Correction"**: drop "symbolic substrate for authorization" claim; reframe as filtering hallucinated tool-calls via *robust* (perturbation-resistant) symbolic justification. Smaller but honest.
2. **"The JIT-Policy Gate"**: focus entirely on the 4-stage gate. Synthesis is input; *Gate* is the contribution. Prove b.4 catches **"Malicious Rule Synthesis"**.

## Gemini's Confidence on Workshop Survival
**4/10.** "Decorative KG" is the smoking gun. To lift confidence, make KG **load-bearing** (Class A primitives that genuinely fail when KG state is incorrect).

---

## Action Items (derived from Gemini review)

### CRITICAL (must-address-for-workshop)
1. **Cite Self-Consistency (Wang et al. 2022) + program-synthesis self-consistency lineage** in Related Work + Method Thesis. Frame b.4 explicitly as "structured Self-Consistency applied to LLM-synthesized Datalog rules," NOT as novel invention. Novelty shifts to *combination* (structured-output + perturbation-sensitivity + decisive-primitive attribution), not b.4 alone.
2. **Add B6: Adversarial Synthesis Stress Test** to EXPERIMENT_PLAN — attacker-mode run where proposer is prompted to bypass the gate via malicious rule synthesis (tautological, overly-permissive, crafted-to-pass-b.4 rules). Measure b.4 rejection rate. Cost ~$10, 1 day prompt engineering.
3. **Add followup WebSearch + WebFetch** on JIT policy synthesis 2025–2026, L-Eval, Logic-Guide, Inala Symbolic Shielding — verify none further compromise novelty.

### IMPORTANT
4. **Rename baseline**: `no_synth_menu_plus` → **SEAP (Static Expert-Authored Policy) baseline**. Cleaner, more honest, avoids PCAS-author pushback.
5. **Contribution framing contingency** — commit to one of two paths based on B4 (per-primitive KG-corruption) result:
   - **If B4 shows KG causally load-bearing**: keep LSVJ-S "symbolic substrate verifier" framing.
   - **If B4 shows null effect**: reframe as **"JIT-Policy Gate"** (Gemini Alternative #2) — contribution is the 4-stage gate proving b.4 catches malicious synthesis; drop "symbolic substrate" overclaim. Adjust Method Thesis and Contribution Focus.
6. **Strengthen Method Thesis** with explicit "Self-Justification Trap defense" statement: acknowledge proposer/verifier collusion risk; explain how Gate b.4 + sealed Class C + owner-harm schema constrain attack surface.

### MINOR
7. **Update FINAL_PROPOSAL Novelty Argument** with PCAS **"Statute vs Case Law"** framing (Gemini's clean metaphor).
8. **Update LITERATURE_REVIEW followup** to explicitly target Inala, L-Eval, Logic-Guide, Self-Consistency citations.

---

## Impact on Research Path

Gemini's MARGINAL + 4/10 is **amber signal, not red**. Key conditions:
- LSVJ-S still workshop-viable IF per-primitive KG-corruption (B4, EXPERIMENT_PLAN Tier-1) shows causal effect.
- Novelty claim must downgrade to include Self-Consistency as foundation + credit LSVJ-S's delta as "**structured Self-Consistency for safety-rule synthesis with compile-time soundness gate + causal attribution**" — honest, narrower, survivable at workshop.
- **If M2 gate passes AND B4 shows effect**: proceed with workshop, reframed-but-honest.
- **If M2 gate passes but B4 is null**: pivot to "JIT-Policy Gate" framing, drop symbolic-substrate claim, elevate B6 (Adversarial Synthesis Stress Test) as primary evidence.
- **If M2 gate fails**: invoke M-off-ramp per existing EXPERIMENT_PLAN.

Gemini's review effectively **tightens Success Condition #3** (KG contributes causally per-primitive): already a supporting criterion, now **the make-or-break test for "symbolic substrate verifier" framing**. If it fails, paper pivots framing — does not fail in full.

---

## Raw Gemini Review (verbatim)

<details>
<summary>Full reviewer response</summary>

## Verdict
**MARGINAL**.

The "per-decision runtime synthesis" is a legitimate architectural delta from PCAS and Solver-Aided, but the "decorative KG" finding in your ablation is a **critical failure** for a Main Track submission. If the KG is decorative, your Datalog rule is not a "proof obligation" grounded in system state; it is a high-latency, symbolic self-consistency check (essentially a structured version of *Self-Verification*). The core novelty resides almost entirely in the **4-stage gate (specifically b.4: perturbation-sensitivity)**, which treats symbolic synthesis as a noisy ML signal rather than a deterministic formal method. This "ML-safety approach to Formal Methods" is interesting, but the current framing overpromises on "symbolic substrate" while the data suggests "symbolic-flavored self-correction."

## Prior-Art Delta Verification
- **PCAS**: **Delta survives.** PCAS is a "Statute" model (laws are written before the crime). LSVJ-S is a "Case Law" model (the LLM argues the legality of its own specific action at the moment of execution). The delta is the JIT synthesis.
- **Solver-Aided (Roy et al.)**: **Delta survives.** Roy et al. verify *actions* against *static logic*. You synthesize the *logic itself*. This is a significant distinction in flexibility, though it introduces the "fox guarding the hen house" problem that your Gate (b.4) must solve.
- **Agent-C**: **Delta survives.** Agent-C is a *decoding-time* constraint (Model-internal). LSVJ-S is a *runtime* constraint (Model-agnostic/Wrapper). They operate at different layers of the stack.

## Missed Prior Art
- **"Self-Synthesizing Policies for Safe Agentic Tool-Use" (Anon, 2025/2026 preprints)**: There is a growing body of work on *Just-In-Time* (JIT) policy synthesis.
- **L-Eval / Logic-Guide (various)**: Papers using LLMs to generate Horn clauses for reasoning tasks. While not safety-specific, they use the same "Synthesize -> Cozo/Datalog -> Execute" pipeline.
- **"Symbolic Shielding for LLMs" (Inala et al., 2024/2025)**: Often focuses on offline shields, but some "Adaptive Shielding" variants exist.
- **"Self-Consistency for Program Synthesis" (e.g., Code-Repair papers)**: Your perturbation-sensitivity (b.4) is functionally equivalent to "Majority Voting" or "Self-Consistency" (Wang et al.) applied to Datalog. You must cite the Self-Consistency literature to avoid being seen as reinventing a 2022 technique for a 2026 paper.

## Novelty-Claim Strength
**Workshop-tier.**
To hit Main Track (NeurIPS/ICLR), you must address the **"Self-Justification Trap."** If an LLM generates both the *Action* and the *Rule that allows the Action*, it can simply synthesize a tautology or a "permissive" rule. Your Gate (b.4) is the only thing preventing this. However, if your ablation shows the KG is decorative, you aren't actually "verifying" anything against reality; you are just asking the LLM to "be sure" in Datalog. A Main Track reviewer will call this "LLM self-correction with extra steps."

## PCAS-style Baseline Framing Check
**Rhetorical.**
A PCAS author would object. PCAS's value is the **human-in-the-loop verification** of the offline policy. By calling a "static menu of 12 rules" a "PCAS-style baseline," you are stripping away PCAS's core safety claim (Human Audit). A fairer name is **"Static Expert-Authored Policy (SEAP) Baseline."**

## Alternative Framing Suggestions
1. **"Robust Symbolic Self-Correction"**: Drop the claim that this is a "symbolic substrate" for authorization (since the KG is decorative) and frame it as a method to filter out hallucinated tool-calls by forcing the LLM to provide a *robust* (perturbation-resistant) symbolic justification.
2. **"The JIT-Policy Gate"**: Focus entirely on the 4-stage gate. The synthesis is the input; the *Gate* is the contribution. Prove that (b.4) catches "Malicious Rule Synthesis" where the LLM tries to bypass a policy.

## Your Confidence
**Score: 4/10.**
The "decorative KG" finding is the "smoking gun" that will lead a rigorous reviewer to reject. If the KG doesn't matter, the Datalog is just a "thought block" (Chain of Thought) that happens to be in a symbolic language. You must find a way to make the KG *load-bearing* (e.g., via Class A primitives that actually fail if the KG state is incorrect) to justify the "Symbolic Authorization" framing. Otherwise, you are just doing a very expensive version of "Are you sure? (Yes/No)."

</details>
