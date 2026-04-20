# Round 3 Review

**Reviewer**: Claude Opus 4.7 (independent subagent, fresh session)
**Date**: 2026-04-18
**Proposal reviewed**: `refine-logs/round-2-refinement.md` (Revised Proposal section)
**Previous reviews**: R1 (6.3), R2 (6.95), both REVISE

---

## Dimension Scores

| Dimension | Score | Δ from R2 | Notes |
|---|---|---|---|
| Problem Fidelity | 9/10 | 0 | Anchor verbatim; v3-HN + neg-control carries honestly. |
| Method Specificity | 8/10 | +1 | Semantic gate + decisive-primitive tracing pseudocoded; perturbation operators per class; 4-stage gate explicit. |
| Contribution Quality | 7/10 | +1 | Perturbation-sensitivity gate is concrete novelty lift. But decisive-primitive tracing is largely diagnostic; "5 non-trainable" bloat surfacing. |
| Frontier Leverage | 8/10 | +1 | XGrammar + Lark + Cozo PEG named, committed with fallback chain. |
| Feasibility | 6/10 | −1 | 10-week / ~200h single-author is tight-to-overcommitted with 5 components + grammar engineering + 50H+25B blind + 11+ ablations. |
| Validation Focus | 6/10 | 0 | Claim 2.2 (3pp at n=15) and 2.3 (5pp at n=20-25 decisive subset) are statistically noise-level. Paired-McNemar analysis would fix it. |
| Venue Readiness | 8/10 | 0 | Workshop primary + split ICLR conditional correctly framed. |
| **OVERALL** | **7.5/10** | +0.55 | weighted ≈ 7.60 rounded for validation under-powering |

**Verdict**: **REVISE** (gap to READY = 1.5)

---

## Action-Item Verification (R2)

| # | Action | Status | Evidence | Residual concern |
|---|---|---|---|---|
| 1 | Semantic non-triviality gate | RESOLVED (algorithm) / PARTIAL (statistics) | §Changes 1 + Proposal algorithm | N=3 calibration is false-rejection only; false-admission on weakly-content-dependent rules untreated. |
| 2 | Per-primitive KG-corruption + tracing | RESOLVED (mechanism) / PARTIAL (statistical power) | §Changes 2; 4 per-primitive configs; `decisive_primitives` pseudocode | Subset sizes ~20-25 at p=0.9 → ±12pp CI; 5pp claim unfalsifiable. Needs paired-McNemar. `GLOBAL_VACUOUS` redundant with gate b.4. |
| 3 | `no_synth_menu_plus` | RESOLVED | §Changes 3 | Yan co-authors both menu + 50% v3-HN; pre-reg mitigates not eliminates leakage. |
| 4 | Blind ≥50H+25B or split | RESOLVED | §Changes 4 | "No significance claim" on blind is honest but concedes conditional is decided on full slice. |
| 5 | Neg-control ≥10% pre-reg | RESOLVED (quantity) / PARTIAL (threshold) | §Changes 5 | n=15 noise for 3pp; "≤20% Class A usage" criterion doesn't distinguish confabulation vs legitimate Class-A supportive use. |
| 6 | Delete rule_id | RESOLVED | §Changes 6 | None. |
| 7 | XGrammar+Lark+Cozo PEG | RESOLVED | §Changes 7 | Cozo→Lark EBNF non-trivial; 2-3 day budget optimistic if left-recursion/PEG constructs. |

---

## Critical Weaknesses

### Feasibility (6/10) — IMPORTANT
- **Weakness**: 10-week/200h/single-author absorbing 5 components + W3 semantic-gate pilot with new reference set + per-primitive harness + 12-rule menu pre-reg + 50H+25B blind authoring + 10H+5B neg-control + Cozo→Lark grammar + 11+ ablations × subsets. +40h from R1→R2 is just new stuff; compound integration-test surface not costed.
- **Fix**: Explicit Tier-1 (workshop) vs Tier-2 (ICLR) ablation split. Drop per-primitive to 2 primitives for workshop (`is_inner_circle`, `owner_has_directed`), defer 4 to ICLR conditional.

### Validation Focus (6/10) — IMPORTANT
- **W1 (Claim 2.2)**: `no_sem_gate` ≥3pp false-allow increase on 15-case neg-control. Wilson ±14-20pp at that size. Noise.
- **W2 (Claim 2.3)**: 5pp per-primitive TPR drop on decisive subset. If subset is 25, Wilson ±12pp. 5pp inside CI. Sole-decisive halves to ~10. Even worse.
- **W3 (jointly-decisive)**: author promises "sole vs jointly separately", but separation halves sample, exacerbating power problem.
- **Fix**:
  1. Switch Claim 2.3 to **paired McNemar** — same cases intact-vs-corrupted, rule-level tracing already gives paired data. Paired Wilson on discordant pairs tightens CI ~3×.
  2. Either expand neg-control to 30H+15B (+2-3 subagent days) OR label Claim 2.2 as "diagnostic signal, not significance claim."

---

## Simplification Opportunities
1. **Merge `GLOBAL_VACUOUS` override into semantic gate stage b.4**. Both check "rule invariant to primitive flips". If b.4 already catches these, GLOBAL_VACUOUS is dead code; if it catches residual b.4 misses, explicitly state why b.4 lets them through. Collapses 5 components back to 4.
2. **Drop `no_synth_6seed` condition** — once `no_synth_menu_plus` is strong baseline, 6-vs-12-menu is redundant unless author has specific hypothesis.
3. **Tier per-primitive ablation**: 2 primitives for workshop, 4 for ICLR conditional.

## Modernization Opportunities
NONE. XGrammar + Lark + Cozo PEG is current frontier.

## Drift Warning
**LATENT (unchanged)**:
- Class C same-model sealed-session: procedural not representation-level independence.
- v3-HN + menu co-authorship: Yan authors both menu (with Dario) + 50% v3-HN; pre-reg helps but intuitions leak.

---

## New Action Items (R3 additions)

1. [CRITICAL] **Switch Claim 2.3 to paired-McNemar analysis.** Same cases intact-vs-corrupted; paired Wilson on discordant pairs. ~0.5 day analysis-plan edit.
2. [CRITICAL] **Honestly label Claim 2.2 as diagnostic at n=15.** Either expand neg-control to 30H+15B OR label as "directional signal only, not significance claim." Must-prove wording needs fix.
3. [IMPORTANT] **Calibrate semantic gate N on both error rates.** Current N=3 false-rejection ≤10%; measure false-admission on weakly-content-dependent rules (those flipping under ~20% of perturbations pass N=3 at ~49% rate). If false-admission >5% on hand-labeled set, raise N to 5 or 7.
4. [IMPORTANT] **De-duplicate semantic gate b.4 vs GLOBAL_VACUOUS override.** Either merge (collapse 5 → 4 components) or document which class b.4 misses.
5. [IMPORTANT] **Explicit Tier-1 / Tier-2 ablation split.** Tier-1 workshop-required; Tier-2 ICLR-conditional. Current 11+ conditions over-commits at 10-week wall-clock.
6. [MINOR] **Document Cozo→Lark EBNF conversion fork point.** If PEG constructs block direct conversion, post-hoc retry becomes primary.
7. [MINOR] **Tighten neg-control Class A criterion** to "≤20% Class A *decisive* usage" (not merely *used*) — via decisive-primitive tracing.
8. [MINOR] **State blind-distance threshold + action.** Current "measure distance" is check without branch. Add: if cosine-sim > X → recruit human collaborator.

---

## Verdict
**REVISE**

Substantive work on both R2-CRITICAL items. Method specificity + contribution quality + frontier leverage each +1. However: (i) per-primitive and neg-control ablation claims not honestly costed against Wilson CI at declared subsets; (ii) complexity creeping (5 components, 11+ ablations, grammar engineering inside 10 weeks). Paired-McNemar fix for Claim 2.3 is cheap; diagnostic-labeling for 2.2 cheap; tier-1/2 split cheap. With those 3 applied, reaches ~8.3 (workshop-READY). Without, workshop likely accepts but stats-savvy reviewer will find the same holes.

---

## Raw Review (verbatim excerpts)

<details>
<summary>Full reviewer response — Deep Critique (verbatim)</summary>

**Angle 1 (N=3 statistics on weakly-content-dependent rules) — LANDED PARTIALLY.** "False-rejection ≤ 10% at N=3" is a claim about false rejection. Adversarial failure mode is the mirror: a weakly-content-dependent rule whose discharge flips under ~20% of perturbations. On N=3, P(at least one flip) = 1 − 0.8³ = 48.8% — nearly half admitted. N=3 may be too small; calibrate both errors. Not fatal; N can be raised to 5 or 7 cheaply (Cozo queries cache, Class C pre-recorded).

**Angle 2 (perturbation operator soundness; disjunctive rules) — LANDED.** A rule `discharged := is_inner_circle(x) OR owner_has_directed(y)` where disjunction's truth carried by `owner_has_directed` passes N=3 when only `is_inner_circle` tuples shuffled. Gate admits as "perturbation-sensitive" but sensitivity is to `owner_has_directed`. Decisive-primitive tracing correctly handles downstream — means gate + tracing overlap. Thread this.

**Angle 3 (multi-conjunct decisive, subset-size statistics) — LANDED, BIGGEST HIT.** Author aware (Risk 3). Separation halves subset; sole-decisive is minority. At v3-HN=100H, per-primitive decisive ~30, sole-decisive ~10. Wilson half-width at p=0.9, n=10 ≈ ±19pp. 5pp claim vacuous. Paired-McNemar is right move.

**Angle 4 (no_synth_menu_plus leakage) — LANDED.** Pre-reg necessary not sufficient. Cleanest: distinct authorship (Dario menu; Yan v3-HN; no cross-review). Not what's stated. Workshop OK; ICLR reviewer flags.

**Angle 5 (neg-control over-attributing criterion) — LANDED.** "≤20% Class A usage" doesn't distinguish confabulation vs legitimate Class-A supportive use. Should be: "≤20% Class A *decisive* (via tracing)".

**Angle 6 (neg-control n=15 statistical power) — LANDED, SECOND-BIGGEST HIT.** Wilson at n=15 on 3pp delta is noise.

**Angle 7 (complexity creep, 5 non-trainable) — LANDED WEAK.** Decisive-primitive tracing is load-bearing for Claim 2.3 but overlaps with semantic gate. Fix: merge GLOBAL_VACUOUS check into b.4 — one component two outputs. Collapse 5 → 4.

**Load-bearing for paper.** Semantic non-triviality gate is actual novelty. Per-primitive KG-corruption with tracing is causal-attribution method strengthening KG claim population → entity level — valuable, supporting. 12-rule menu is baseline strength, not contribution. Blind + neg-control are honesty measures. Paper story: "we found a way to reject synthesized rules that syntactically look fine but don't actually depend on what they claim to depend on, and we can show per-case which primitive earned the verdict."

**Workshop-READY vs main-READY.** Workshop-READY after R3 Actions 1, 2, 5 (cheap). Not ICLR-main-READY: Class C compromise + v3-HN co-authorship + complexity all need stronger answers; novelty lift still "structured tool-use with perturbation-sensitivity gate", not a new verifier class. Workshop-tier novelty; main wants soundness theorem or harder empirical claim. Given workshop-primary framing, right stopping point. One more iteration applying R3 Actions 1, 2, 3, 5 gets to solid workshop-READY.

</details>
