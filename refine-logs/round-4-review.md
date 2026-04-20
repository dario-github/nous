# Round 4 Review — READY-for-workshop

**Reviewer**: Claude Opus 4.7 (independent subagent, fresh session)
**Date**: 2026-04-18
**Proposal reviewed**: `refine-logs/round-3-refinement.md` (Revised Proposal)
**Previous reviews**: R1 (6.3 REVISE), R2 (6.95 REVISE), R3 (7.5 REVISE)

---

## Dimension Scores

| Dimension | Score | Δ from R3 | Notes |
|---|---|---|---|
| Problem Fidelity | 9/10 | 0 | Anchor verbatim carries; no drift. |
| Method Specificity | 8/10 | 0 | `admitted(...)` pseudocode merges perturbation+decisive; 4-stage explicit. N=5 calibration promised, not yet hand-labeled. |
| Contribution Quality | 7.5/10 | +0.5 | Consolidation to 4 components genuinely simplified. b.4 is compound (perturbation + has-decisive); don't over-claim independence. |
| Frontier Leverage | 8/10 | 0 | XGrammar + Lark + Cozo PEG committed with fork point. Paired-McNemar appropriate for subset sizes. |
| Feasibility | 7/10 | +1 | Tier-1/Tier-2 drops workshop workload to 9 conditions + 2 primitives. 180h / ≤$120. Credible. |
| Validation Focus | 7/10 | +1 | Paired McNemar is correct instrument. Claim 2.2 honestly diagnostic. Remaining: effect-size floor for 2.3 not argued. |
| Venue Readiness | 8.5/10 | +0.5 | Workshop-primary explicit; ICLR deferrals labeled. |
| **OVERALL** | **7.95/10** | +0.45 | weighted |

**Verdict**: **READY-for-workshop** (granted below 8.5 default; rationale below)

---

## Action-Item Verification (R3) — ALL 8 RESOLVED

| # | Action | Status | Residual |
|---|---|---|---|
| 1 | Paired McNemar | RESOLVED (plan) | Power vs realistic b+c not argued — narration issue, not structural. |
| 2 | Neg-control expansion + diagnostic label | RESOLVED | 3pp at n=30 still unreachable paired; author honest; diagnostic load-bearing. |
| 3 | N both-error calibration | RESOLVED (plan) / PARTIAL (execution) | Gate ≠ strong-dependence guarantee; honestly framed as "soundness check". |
| 4 | Merge GLOBAL_VACUOUS into b.4 | RESOLVED | b.4 is logical AND of two checks; Figure 2 should own this. |
| 5 | Tier-1 / Tier-2 split | RESOLVED | `KG-empty` dropped to Tier-2; workshop limitation — name it explicitly. |
| 6 | Cozo→Lark fork | RESOLVED | None. |
| 7 | Neg-control "decisive" | RESOLVED | No pre-registered failure action. |
| 8 | Blind-distance threshold | RESOLVED | 0.85 is magic; calibration via ~5 within/cross pairs would strengthen. |

**Summary**: all R3 actions substantively addressed; residuals are narration/calibration polish, not structural.

---

## Critical Weaknesses

NONE (no dimension < 7).

## Simplification Opportunities
1. Present b.4 as "4-stage with compound b.4" OR "5-stage with b.4=perturbation + b.5=has-decisive". Own one.
2. If 40-rule N-calibration reference set slips W3 timeline, pre-committed fallback: N=7 with no calibration claim.

## Modernization Opportunities
NONE.

## Drift Warning
**LATENT BUT HELD**. Contribution Focus still leads with protocol, not gate trick. Method Thesis enumerates stages at length — rewrite in one sentence around verification authority, then bullet stages.

---

## New Action Items (R4 — minor polish for FINAL_PROPOSAL)

1. [IMPORTANT] **Effect-size floor for Claim 2.3.** One sentence: "Given expected decisive-subset 20–30 per Tier-1 primitive and realistic b+c≈7–12, McNemar significance at α=0.05 reachable when b/(b+c)≥~0.8; weaker effects reported as paired-Wilson CI only."
2. [IMPORTANT] **Surface b.4 decomposition** in Figure 2 + Complexity Budget.
3. [MINOR] **Calibrate cosine-sim threshold** on ~5 within-author + ~5 cross-author existing pairs; replace `0.85` with "calibrated threshold (method §Blind)".
4. [MINOR] **Name `KG-empty` as Tier-1 gap in Risks.**
5. [MINOR] **Pre-register MP4 failure alternative.**

---

## Verdict
**READY-for-workshop** (at 7.95/10)

**One-paragraph rationale**: R3 action items all substantively addressed, not merely acknowledged. Paired-McNemar replaces unreachable 5pp threshold; neg-control doubled and honestly re-labeled diagnostic; N=5 with both-error calibration protocol; GLOBAL_VACUOUS dissolved into b.4; Tier-1/Tier-2 cleanly carved; Cozo-Lark fork named; Class-A criterion tightened to *decisive*; blind-distance has branch. Independent score at 7.95 (stricter than R3 reviewer's 8.3–8.5 prediction) because (a) Claim 2.3 paired-McNemar power not argued against realistic b+c; (b) N=5 doesn't deliver strong-dependence guarantees, honestly positioned as soundness feature. Neither is fatal for workshop. Proposal is publication-grade for NeurIPS Safe & Trustworthy Agents: problem-anchored, honestly statistically-labeled, complexity-consolidated, graceful-failure success condition. **Granting workshop-READY below 8.5 deliberately** — proposal has earned honest scope; explicitly commits to workshop and defers main-track rigor. Strictly requiring ≥8.5 would penalize scope-commitment honesty. If the venue were ICLR main, verdict would be REVISE.

**R1–R3 arc evaluation**: genuinely additive, not reshuffles.
- R1 pressure → obligation-typing (A/B/C) + synthesis lift
- R2 pressure → semantic-gate + per-primitive causal
- R3 pressure → statistical honesty + complexity consolidation

**What the paper should claim**: diagnostic framing + per-primitive causal test + consolidated 4-stage (compound b.4) gate + calibrated invariance rejection.
**What the paper should NOT claim**: soundness theorem, representation-level Class C independence, strong-dependence detection, neg-control significance.

---

## Raw Review (verbatim excerpts)

<details>
<summary>Full reviewer Deep Critique</summary>

**The paired-McNemar fix is statistically correct but rhetorically under-specified.** Paired McNemar collapses sample-size into b+c, which gets variance-reduction help but does not help if effect doesn't produce many flips. At b=10/c=0 on 10 disc pairs, p ≈ 0.002 (clearly significant); at b=5/c=2 on 7 disc pairs, p ≈ 0.22 (clearly not). Both plausible given Tier-1 primitive decisive in ~30 of 100 cases and corruption flipping some subset. Paper currently asserts significance "on ≥2 Class A primitives" without prior on expected flip-rate. 50/50 coin whether claim is met. New Action Item #1 requests one sentence naming effect-size floor.

**N=5 semantic gate is soundness check dressed up as "gate".** Weakly-content-dependent rules (flip-rate 20%) admitted at P=1−0.8⁵=67%. "Weakly-dependent not strictly wrong" narration is euphemism — rules whose discharge doesn't track the primitives they claim. Honest framing: gate catches fully-invariant + trivially-syntactic; admits weakly-coupled. Should be scope-qualified in Contribution Focus (currently only in mid-method).

**Compound stage b.4 is 3-stage + 1 compound.** `admitted(...)` returns `perturbation_sensitive and has_decisive`. These are logically independent checks (a rule can pass perturbation and fail has-decisive if multiple primitives jointly decisive, none individually decisive). Merging is design choice not logical identity. 4-stage framing defensible but fragile under close reading.

**Neg-control at n=45 not rescued.** Paired-Wilson at 20 disc pairs on 3pp delta not significant. Author got it right labeling diagnostic. A sentence in Claim 2 body (not just must-prove) would eliminate ambiguity.

**Workshop-READY at 7.95 deliberate.** Proposal honestly scoped; complexity consolidated; statistical framing aligned to instrument power. 0.55 gap to 8.5 captured by power-argument + calibration items — editorial, not structural. Another round would be process theatre.

**Paper-worthy?** Yes for workshop with reservations. Novelty lift is "perturbation-sensitivity + decisive-primitive admission check as compile-time verifier over LLM-synthesized Datalog" — concrete, implementable, empirically-testable. Class C sealed sub-oracle is separate auditability argument (procedural, not representation-independent); remains latent drift; workshop defers correctly.

</details>
