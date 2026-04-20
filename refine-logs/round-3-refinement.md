# Round 3 Refinement — LSVJ-S: Statistical Honesty + Component Consolidation

> Revision of `round-2-refinement.md` in response to `round-3-review.md` (Opus 4.7, independent session, 7.5/10 REVISE).
> Date: 2026-04-18. Author: Yan. Project: Nous.
> Reviewer estimate: R3 Actions 1, 2, 5 applied → ~8.3 workshop-READY. Actions 1–8 applied → ~8.5 target.

---

## Problem Anchor (IMMUTABLE — verbatim from round-0)

### Bottom-line problem
In agentic systems where an LLM authorizes tool calls at runtime, the LLM's judgment is **not trustworthy** in the epistemic sense: the system cannot tell, from the LLM's output alone, whether an "allow" verdict reflects (a) genuine understanding of the action, (b) lucky pattern match on surface features, or (c) confabulation produced under adversarial prompting. Current hybrid architectures (LLM classifier + rule layer + knowledge graph) paper over this by stacking layers, but the LLM's decision is never *verified* by the symbolic substrate — the symbolic parts merely run alongside or feed context. Concretely, Nous demonstrates this pathology: training-set TPR 100% (Loop 74, 200H+50B), v3 held-out L1+L2-only TPR **12.7%** with L3 LLM adding +62.6pp, but the `no_kg` ablation on training set shows ΔL=0 — meaning KG is not carrying the generalization weight and the LLM's gains on held-out are not symbolically grounded.

### Must-solve bottleneck, Non-goals, Constraints, Success condition
Unchanged from round-0 through round-2 (v3 → v3-HN amendment from R1; `no_synth_menu_plus` baseline from R2).

---

## Anchor Check

- **Original bottleneck**: LLM allow is unverified; symbolic engine runs alongside.
- **Does revised method still address it?** Yes. R3 changes are statistical-honesty and complexity-consolidation; they do not alter the mechanism.
- **Reviewer suggestions rejected as drift**:
  - *"Soundness theorem for main-track"* — deferred to Future Work; workshop scope is current target.
  - *"Distinct authorship of menu vs v3-HN"* — partially accepted: 12-rule menu co-authored Dario+Yan and pre-registered; v3-HN 50% author + 50% Sonnet-blind. Human collaborator for ICLR slice named as contingent post-workshop action; not blocking workshop.
- **Reviewer suggestions accepted**: R3 actions 1, 2, 3, 4, 5, 6, 7, 8.

## Simplicity Check

- **Dominant contribution unchanged**: SPO protocol + 4-stage compile-time gate + perturbation-sensitivity + decisive-primitive admission check.
- **Components**: **4** (down from 5 — GLOBAL_VACUOUS merged into stage b.4).
- **Removed from required ablation**: `no_synth_6seed` (demoted to Tier-2, ICLR-conditional).
- **Tier split**: Tier-1 (workshop) 9 conditions; Tier-2 (ICLR) +4 conditions.

---

## Changes Made

### 1. Claim 2.3 → Paired McNemar analysis (R3 Action 1, CRITICAL)
- **Reviewer said**: per-primitive TPR drop ≥ 5pp on decisive subset not detectable at n≈20–25 (Wilson ±12pp). Paired data already available via tracing.
- **Action**: for each case in decisive-subset (primitive P decisive in intact-LSVJ-S), record pair `(verdict_intact, verdict_corrupted_P_only)`. Analyze via **McNemar test** on discordant pairs (b = intact-allow → corrupted-block; c = intact-block → corrupted-allow). Significance at p < 0.05. Effect-size = `b / decisive_subset_size` with paired-Wilson 95% CI.
- **Claim 2.3 restated**: "For ≥ 2 of Tier-1 Class A primitives, per-primitive corruption yields **paired TPR drop statistically distinguishable from zero (McNemar p < 0.05)**." No absolute 5pp threshold.
- **Impact**: ~0.5 day analysis-plan edit. Tables 3 report `b, c, McNemar p, paired-Wilson 95% CI`.

### 2. Claim 2.2 honesty: neg-control expansion + diagnostic label (R3 Action 2, CRITICAL)
- **Reviewer said**: n=15 cannot detect 3pp false-allow increase.
- **Action**: both.
  1. **Expand neg-control to 30H + 15B** (from 10H+5B). Wilson ±13pp at n=30 modest but usable.
  2. **Relabel as diagnostic**: "`no_sem_gate` yields *directionally higher* false-allow rate on neg-control; paired-Wilson 95% CI reported. Interpretation: diagnostic, not hypothesis test."
- **Impact**: +2–3 subagent days authoring.

### 3. Semantic gate N: both-error calibration (R3 Action 3, IMPORTANT)
- **Reviewer said**: N=3 false-admission ~49% on weakly-content-dependent rules (flipping under 20% of perturbations).
- **Action**: W3 pilot uses hand-labeled reference set of ~40 rules: (i) genuinely content-dependent, (ii) weakly content-dependent, (iii) content-invariant. Measure at N ∈ {3, 5, 7}: false-rejection (class i) ≤ 10%; false-admission (class iii) ≤ 2%; weak-admission (class ii) recorded as directional signal. **Default N = 5** (up from 3). Paper honestly narrates: gate is *soundness* check (reject invariant), not *strong-dependence* check.
- **Impact**: +0.5 day pilot; reference set authoring; ~+3 rule evaluations per call at N=5 (still negligible).

### 4. Merge GLOBAL_VACUOUS into semantic gate b.4 (R3 Action 4, IMPORTANT)
- **Action**: stage b.4 now defined as: "rule admitted iff (perturbation-sensitive across N trials) AND (has ≥ 1 decisive primitive — single-flip counterfactual changes discharge)." Second clause absorbs GLOBAL_VACUOUS. Decisive-primitive tracing remains for Claim 2.3 analysis but is a *diagnostic utility*, not a gate component.
- **Component count**: 5 → **4**.
- **Impact**: code + paper simplification.

### 5. Tier-1 / Tier-2 ablation split (R3 Action 5, IMPORTANT)
- **Tier-1 (workshop, W6–W7)**: LSVJ-S full, `no_synth_menu_plus`, `no_sem_gate`, `no_class_A`, `no_class_B`, `no_class_C`, `KG-shuffled-all`, `corrupt_is_inner_circle_only`, `corrupt_owner_has_directed_only`. **9 conditions**.
- **Tier-2 (ICLR-conditional, post-workshop)**: `KG-empty`, `no_synth_6seed`, `corrupt_recipient_owned_by_owner_only`, `corrupt_action_in_precedent_only`, neg-control expansion to 60H+30B.
- **Impact**: ~25% experimental budget reduction; cleaner workshop deliverable.

### 6. Cozo→Lark EBNF fork criterion (R3 Action 6, MINOR)
- **Action**: W2 pilot: if Cozo PEG has ≥ 1 left-recursive/PEG-specific construct that does not round-trip through Lark EBNF in ≤ 2 days, **commit to post-hoc parse+retry (3×) as primary**, not fallback. Named decision point, unblocks either way.

### 7. Neg-control "decisive" Class A criterion (R3 Action 7, MINOR)
- **Must-prove 4 revised**: "Neg-control cases show **≤ 20% of LSVJ-S discharges where any Class A primitive is *decisive*** (via tracing)." Separates confabulation from legitimate supportive Class A use.

### 8. Blind-distance threshold + branch (R3 Action 8, MINOR)
- **Action**: measure case-content distance blind↔author via sentence-BERT cosine similarity on prompts + tool-call signatures. **If mean cosine > 0.85**, flag failed-blind and recruit human collaborator for post-workshop ICLR run. Workshop proceeds with 50% Sonnet-blind.

---

## Revised Proposal (full, post-R3 changes)

# Research Proposal: LSVJ-S — LLM-Synthesized, Symbolically-Verified Judgments via Proof-Obligation Synthesis with Perturbation-Sensitivity Gate

## Problem Anchor
(Verbatim from round-0; copied at top.)

## Technical Gap
(Unchanged from round-2.) Smallest adequate intervention: runtime Datalog rule synthesis + 4-stage compile-time gate (parse + type + syntactic + **perturbation-sensitive AND has-decisive-primitive**) + Class A/B/C primitive schema. Decisive-primitive tracing is a diagnostic utility (not a gate component) enabling per-primitive paired-McNemar analysis.

## Method Thesis
Treat the LLM's agent decision as a conjecture bundled with a synthesized Datalog obligation; treat the Cozo engine as a compile-time-soundness-checking verifier that rejects malformed, ill-typed, syntactically-trivial, or perturbation-invariant / decisive-primitive-less rules; admit the allow verdict only when the rule (i) parses, (ii) type-checks, (iii) references ≥1 Class A/B primitive with non-`true` head, (iv) is perturbation-sensitive across N trials, AND (v) has ≥1 decisive primitive (single-flip counterfactual changes discharge).

## Contribution Focus
**Dominant**: SPO protocol + 4-stage compile-time gate with perturbation-sensitivity + decisive-primitive admission check; demonstrated on v3-HN held-out with **paired-McNemar per-primitive causal analysis**.
**Supporting**: verifier-proposer separation as audit property (sealed Class C).
**Non-contributions**: 6-seed library (prior); 12-rule menu (baseline); no LLM training; not new benchmark; not universal trustworthy reasoning.

## Proposed Method

### Complexity Budget (4 components, reduced from 5)
- **Frozen/reused**: DeepSeek-V3.2, GPT-5.4, Cozo, 46 YAML constraints, L1/L2/L4, proof_trace, markov_blanket.
- **New non-trainable (4)**:
  1. Owner-harm primitive schema with A/B/C classes.
  2. Synthesis prompt + grammar-constrained decoder (XGrammar + Lark + Cozo PEG; vendor JSON outer).
  3. **4-stage compile-time gate** (parse + type-check + syntactic + **perturbation-sensitive AND has-decisive-primitive**).
  4. Verifier policy + sealed Class C sub-oracle runner.
- **Diagnostic utility** (not counted): decisive-primitive tracing for Claim 2.3.
- **New trainable**: 0.

### System Overview

```
tool_call
  ↓
L1 → L2 (unchanged)
  ↓
L3-LSVJ-S:
  (a) Proposer (DeepSeek-V3.2, grammar-constrained)
       → { decision, synthesized_obligation }
  (b) Compile-time gate:
       (b.1) parse
       (b.2) type-check
       (b.3) syntactic non-triviality (references ≥1 A/B; head ≠ true)
       (b.4) PERTURBATION-SENSITIVE AND HAS-DECISIVE-PRIMITIVE
              (∃ perturbation in N=5 trials flips discharged)
              AND (∃ single-primitive flip changes discharged)
              → confirm on any failure
  (c) Execute against live bindings (Class A Cozo / B host-fn / C sealed sub-oracle)
  (d) Record decisive_primitives in proof_trace (diagnostic)
  (e) Verify policy:
       LLM block/confirm → accept
       LLM allow + admitted by b.4 + discharges → allow
       otherwise → upgrade to confirm
  ↓
L4 (unchanged)
  ↓
Final verdict + proof_trace { rule_text, class_usage, discharge_result, decisive_primitives }
```

### Semantic Gate (merged b.4, N=5 default)
```python
def admitted(rule, live_bindings, schema, N=5, seed_pool) -> bool:
    discharged_real = execute_rule(rule, live_bindings)
    perturbation_sensitive = any(
        execute_rule(rule, perturb(live_bindings, rule.body_primitives, schema, seed=seed_pool[k]))
          != discharged_real
        for k in range(N)
    )
    has_decisive = any(
        execute_rule(rule, flip_primitive_binding(live_bindings, prim)) != discharged_real
        for prim in rule.body_primitives
    )
    return perturbation_sensitive and has_decisive
```

### Decisive-Primitive Tracing (diagnostic utility)
```python
def decisive_primitives(rule, live_bindings) -> list[str]:
    real = execute_rule(rule, live_bindings)
    if not real: return []
    return [prim.id for prim in rule.body_primitives
            if execute_rule(rule, flip_primitive_binding(live_bindings, prim)) != real]
```
Used only for Claim 2.3 paired-McNemar analysis.

### Representation, Training, Inference, Failure Modes, Novelty Argument
(Unchanged from round-2 except as touched by R3 above: N=5 default, `admitted` combines perturbation + decisive check.)

## Claim-Driven Validation Sketch

### Claim 1 (Dominant, unchanged): LSVJ-S > `no_synth_menu_plus` on v3-HN.
- Configs: LLM-only / Rules-only / Nous current / `no_synth_menu_plus` / LSVJ-S.
- Metric: TPR/FPR + Wilson 95% CI; per-category; direction-consistent on blind.
- Table 1.

### Claim 2 (Supporting, R3-upgraded): LSVJ-S gains are mechanism-level with honest statistics.

**Tier-1 (workshop required, 9 conditions)**:
- full LSVJ-S
- `no_synth_menu_plus`
- `no_sem_gate` (disable b.4; measure false-allow increase on neg-control n=30H+15B, **diagnostic-only**)
- `no_class_A`, `no_class_B`, `no_class_C`
- `KG-shuffled-all`
- `corrupt_is_inner_circle_only`, `corrupt_owner_has_directed_only`
  - Analysis: **paired McNemar on decisive subset**; report b, c, p, paired-Wilson 95% CI on flip rate.

**Tier-2 (ICLR-conditional, post-workshop)**:
- `KG-empty`, `no_synth_6seed`, `corrupt_recipient_owned_by_owner_only`, `corrupt_action_in_precedent_only`, neg-control expansion 60H+30B.

### Claim 3 (Stretch): ShieldAgent-Bench zero-shot (unchanged).

## Experiment Handoff Inputs

### Must-prove claims (Tier-1)
1. LSVJ-S > `no_synth_menu_plus` on v3-HN full (Wilson CI statistical) + direction-consistent on blind (diagnostic).
2. `no_sem_gate` yields *directionally higher* false-allow rate on neg-control (30H+15B); paired-Wilson 95% CI reported; **interpretation diagnostic, not significance test**.
3. For ≥ 2 of Tier-1 Class A primitives, per-primitive corruption yields **paired-McNemar p < 0.05** on decisive subset.
4. Neg-control cases show **≤ 20% of LSVJ-S discharges with any Class A primitive *decisive*** (via tracing).

### Must-run ablations (Tier-1)
LSVJ-S full; `no_synth_menu_plus`; `no_sem_gate`; `no_class_A`; `no_class_B`; `no_class_C`; `KG-shuffled-all`; `corrupt_is_inner_circle_only`; `corrupt_owner_has_directed_only`. **Total 9**.

### Critical datasets / metrics
- **Primary**: v3-HN (≥100H+50B, ≥50H+25B blind, **30H+15B neg-control**).
- **Reference**: v3, AgentHarm.
- **Tier-2**: ShieldAgent-Bench, neg-control 60H+30B.
- **Metrics**: TPR/FPR + Wilson CI; **paired McNemar** per-primitive; ΔL; false-allow rate (diagnostic); parse-failure; class/primitive usage; decisive distribution; latency.

### Highest-risk assumptions
1. Grammar-constrained synthesis ≥ 99% parse rate; **Cozo→Lark fork**: ≥1 PEG construct blocking within 2 days → post-hoc parse+retry primary.
2. Seed library non-over-anchoring: verbatim-match ≤ 30%; neg-control **Class-A-*decisive*** ≤ 20%.
3. Class C sealed independence (CI lint + divergence calibration).
4. Semantic gate N=5 calibration: false-rejection ≤ 10% AND false-admission on content-invariant ≤ 2% (W3 pilot).
5. Decisive-primitive tracing stable.
6. Tier-1 per-primitive paired-McNemar p < 0.05 on at least one of {`is_inner_circle`, `owner_has_directed`}.
7. Blind 50H+25B feasible; **cosine-sim blind↔author ≤ 0.85** (else recruit human collaborator).

## Compute & Timeline

### Engineering (weeks 1–5)
- W1: schema A/B/C; 2 Class A + 2 Class B primitives.
- W2: synthesis + grammar decoder; 500-call pilot; **Cozo→Lark fork decision**.
- W3: 4-stage gate (b.4 = perturbation + decisive merged); 3 Class C sealed; **40-rule reference set for N calibration**.
- W4: decisive-primitive tracing utility; per-primitive corruption harness (Tier-1 × 2 primitives); `no_synth_menu_plus` 12-rule menu co-authored + frozen.
- W5: v3-HN authoring (50% author + 50% blind + 30H+15B neg-control); blind-distance measurement; integration tests.

### Experiments (weeks 6–7)
- W6: Claim 1 (5 configs). API ~$40.
- W7: Claim 2 Tier-1 (9 conditions; paired-McNemar on 2 per-primitive). API ~$70.

### Paper (week 8+)
- Sections 2–4; Tables 1–3; Figures 2 (4-stage gate), 3 (per-primitive paired-McNemar flip rates with Wilson). auto-review-loop to ARIS ≥ 8.5.

### Totals
- Engineering: ~180 hours (down from 200; consolidation + Tier cut).
- API: ≤ $120.
- GPU: 0.
- Wall-clock: 10 weeks nominal; 12 with review.

## Risks and Open Questions

1. Semantic gate N=5 fails calibration → raise to 7 (still negligible); or honest "gate catches invariant rules; weak-dependent admitted (explicit bound)."
2. Seed-anchored synthesis on neg-control → confirmation bias exposed; honest narration.
3. Per-primitive paired-McNemar p ≥ 0.05 on both Tier-1 primitives → Claim 2.3 weakens; honest narration + Tier-2 extension.
4. Blind cosine-sim > 0.85 → recruit human collaborator post-workshop.
5. Cozo→Lark PEG conversion blocked → post-hoc parse+retry primary.
6. Workshop rejection → ICLR/AAAI Safe AI Workshop fallback.

---

## Success Condition (carry-forward through R3)

Dongcheng will say "yes, this is trustworthy reasoning, not dressed-up pattern matching" iff **all four** hold:

1. **Held-out improvement is real** — on v3-HN, LSVJ-S > `no_synth_menu_plus` by statistically significant margin on Wilson CI; direction-consistent on blind sub-slice.
2. **Gain is mechanism-level at three loci**:
   - `no_synth_menu_plus` < full.
   - `no_sem_gate` yields *directionally higher* false-allow on neg-control (diagnostic).
   - Per-class (`no_class_A/B/C`) each non-zero.
3. **KG contributes causally per-primitive**: ≥ 2 Tier-1 Class A primitives show **paired-McNemar p < 0.05** on decisive subset.
4. **Zero-shot transfer defensible** (stretch, Tier-2 / required for main-track): ShieldAgent-Bench within 5pp or Future Work.

If 1–3 fail: revise or reject, not reframe. (4) may fail gracefully.

---

*End of round-3 refinement.*
