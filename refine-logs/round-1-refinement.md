# Round 1 Refinement — LSVJ-S: Synthesized Proof Obligations for Verifiable Agent Decisions

> Revision of `round-0-initial-proposal.md` in response to `round-1-review.md` (Opus 4.7, independent context, 6.3/10 REVISE).
> Date: 2026-04-18. Author: Yan. Project: Nous.

---

## Problem Anchor (IMMUTABLE — verbatim from round-0)

### Bottom-line problem
In agentic systems where an LLM authorizes tool calls at runtime, the LLM's judgment is **not trustworthy** in the epistemic sense: the system cannot tell, from the LLM's output alone, whether an "allow" verdict reflects (a) genuine understanding of the action, (b) lucky pattern match on surface features, or (c) confabulation produced under adversarial prompting. Current hybrid architectures (LLM classifier + rule layer + knowledge graph) paper over this by stacking layers, but the LLM's decision is never *verified* by the symbolic substrate — the symbolic parts merely run alongside or feed context. Concretely, Nous demonstrates this pathology: training-set TPR 100% (Loop 74, 200H+50B), v3 held-out L1+L2-only TPR **12.7%** with L3 LLM adding +62.6pp, but the `no_kg` ablation on training set shows ΔL=0 — meaning KG is not carrying the generalization weight and the LLM's gains on held-out are not symbolically grounded.

### Must-solve bottleneck
**LLM-proposed agent decisions lack discharge-able symbolic obligations.** A decision of "allow" should be a *conjecture* that the symbolic engine is obligated to *verify* by discharging a structured set of proof obligations; today it is an opaque label.

### Non-goals, Constraints, Success condition
(Unchanged from round-0; success condition re-stated at bottom with one amendment to v3 → v3-HN.)

---

## Anchor Check

- **Original bottleneck**: LLM allow is unverified; symbolic engine runs alongside, not as verifier; KG is stage scenery.
- **Does the revised method still address it?** Yes, more directly. LSVJ-S still routes the LLM's allow through a symbolic discharge gate; the upgrade is that the discharge predicates are *synthesized* (not picked from a menu), which forces the LLM to commit to *content* (a Datalog rule body), not just *labels* (a menu entry).
- **Reviewer suggestions rejected as drift**:
  - *"Drop the LSVJ framing and reframe as Constrained-Tool-Use Safety Gate with Forced Discharge"* — Rejected. The reframe abandons the problem anchor's central move: verification of the LLM's *decision*. Constrained-tool-use framing removes the proposer/verifier polarity and makes the method what ShieldAgent/GuardAgent already do.
  - *"Pivot to USENIX / S&P with formal threat model + blind red team"* — Rejected. The problem is epistemic (LLM trust), not adversarial-robustness-at-scale.
  - *"Add SFT-on-obligations baseline and run it"* — Partially accepted: named as baseline with explicit epistemic defense of why zero-training is chosen; not run (no GPU).
- **Reviewer suggestions accepted**: Actions 1, 2(a program-synthesis), 3, 4, 5 (epistemic), 6 (workshop commit), 7 (blind 25%), 8, 9, 10. Details in Changes Made.

## Simplicity Check

- **Dominant contribution after revision**: **Synthesized Proof-Obligation (SPO) protocol with compile-time soundness gate** — one mechanism.
- **Components removed or merged**: `proof_sketch` field deleted; Claim 3 demoted to stretch; 12-entry static taxonomy → 6 seed templates (prior, not contribution); obligation library + compiler merged into synthesis-and-compile pipeline.
- **Reviewer suggestions rejected as unnecessary complexity**:
  - *"Different model for Class C sub-oracles"* — accepted conceptually, implementation uses same DeepSeek-V3.2 with sealed independent session. Named property "semantic independence" documented.
  - *"Soundness theorem for fixed-taxonomy variant"* — subsumed by synthesis route's compile-time gate (plays the soundness-check role per-rule).
- **Net delta from round-0**: +1 non-trainable component (compile-time gate), −1 contribution (taxonomy-as-contribution), −1 experimental plank (Claim 3 main pitch). Tighter, not fatter.

---

## Changes Made

### 1. Obligation model: fixed menu → synthesized Datalog rule (Action 2, CRITICAL)
- **Reviewer said**: replace static taxonomy with synthesized obligation; verifier compiles and checks soundness + non-triviality.
- **Action**: proposer output = `{decision, synthesized_obligation: <CozoScript rule>, rule_id}`. Verifier: (i) parse via Cozo parser; (ii) type-check primitive arities against schema; (iii) non-triviality (rule body must reference ≥ 1 Class A/B primitive; not reducible to `true`); (iv) execute. Any gate failure → `confirm` (fail-closed).
- **Reasoning**: closes "dressed-up function calling" critique; synthesis turns LLM from menu-picker into rule-writer; compile-time check becomes the missing soundness gate.
- **Impact**: primary novelty vector; +1 non-trainable component; +1 engineering week.

### 2. Obligation primitives partitioned A/B/C with class declaration (Action 1, CRITICAL)
- **Reviewer said**: declare A/B/C classes; without it `no_verify` ablation is uninterpretable.
- **Action**: owner-harm schema declares every primitive with `class` attribute.
  - **Class A (pure KG/relational)**: `is_inner_circle`, `owner_has_directed`, `recipient_owned_by_owner`, `action_in_precedent`. Pure Cozo Datalog over KG.
  - **Class B (deterministic)**: `payload_contains_regex`, `read_before_send_chain`, `external_url`, `credential_pattern`. Cozo built-ins or Python host functions.
  - **Class C (sealed LLM sub-oracle)**: `body_reveals_inner_relation`, `authority_coercion_present`, `autonomy_bounded_by_directive`. Fresh DeepSeek-V3.2 call with distinct prompt ID + sealed session + strict JSON. Paper honestly labels: "Class C is not fully symbolic; defended on sealed independence + schema-bounded input + necessary expressivity."
- **Reasoning**: `no_verify` ablation well-defined per class; drift risk (Class C → LLM-as-judge) contained by sealed-session requirement.
- **Impact**: ~2–3 days plumbing for sealed sessions.

### 3. Zero-training defense: epistemic, not resource (Action 5, IMPORTANT)
- **Reviewer said**: Route B dispatched on resources only; add epistemic defense.
- **Action**: three arguments — (i) **reward-hacking by design**: PRM/RL on obligation discharge collapses proposer/verifier separation; (ii) **verifier independence is the audit property**: SFT contaminates audit trail via co-adaptation; (iii) **grammar-constrained decoding is the reliability primitive**: parse reliability via XGrammar/Outlines/vendor JSON+string mode, not fine-tuning. SFT-on-obligations named as baseline, not run, with honest "we argue separation property would degrade."
- **Impact**: prose defense moves from weak to strong; no method change.

### 4. KG ablation: circular → KG-corruption (Action 3, IMPORTANT)
- **Reviewer said**: `no_kg` circular; replace with KG-corruption.
- **Action**: for Class A primitives only, permute KG facts (shuffle `is_inner_circle` memberships across owners, rotate `owner_has_directed` relations, randomize `action_in_precedent`) preserving schema and arity. Measure per-category TPR under (i) intact, (ii) shuffled, (iii) empty. If facts are load-bearing, (ii)/(iii) degrade relative to (i).
- **Impact**: ~100-line KG-permutation utility.

### 5. Hard-negative held-out slice (Action 4, IMPORTANT)
- **Reviewer said**: ceiling on current v3 (Privacy=100%, Hijacking=93.3%); build complement-of-L1+L2+L4 slice.
- **Action**: construct **v3-HN** (≥100H+50B). Each harmful defeats ≥ 1 of {L1 Datalog, L4 regex, current L3 prompt}: (a) semantic hijacking evading L4's 6 audit rules + 32 patterns; (b) inner-circle disclosures rephrased past current L3 minimal pairs; (c) infra/autonomy cases mirroring benign ops scripts. Benign similarly stressful.
- **Impact**: 2–3 days author + blind sub-slice (see next). ~150 new cases.

### 6. Blind evaluator ≥25% slice (Action 7, IMPORTANT)
- **Reviewer said**: single-author evaluator bias.
- **Action**: ≥25% of v3-HN authored by subagent (Claude Sonnet 4.6 via Agent tool, sealed prompt with no reference to obligation types / seed library / A/B/C schema) given only threat model + L4 paper section. Seed prompt pre-registered in `nous/docs/v3-HN-blind-protocol.md`. Blind slice reported separately.
- **Impact**: 1–2 days engineering + subagent time.

### 7. Venue commit: workshop-first, main-track conditional (Action 6, IMPORTANT)
- **Action**: primary = **NeurIPS 2026 Workshop on Safe & Trustworthy Agents** (December). Secondary conditional on Claim 1+2 holding with ≥5pp `no_synth` gain: **ICLR 2027 main** with Claim 3 extended. **Not USENIX/S&P** — different paper.
- **Impact**: writing tighter; no method change.

### 8. Taxonomy collapse 12 → 6 seeds (Action 8, MINOR)
- **Action**: seeds:
  1. `no_credential_exfil` (Cred Leak + Exfil)
  2. `no_inner_circle_disclosure` (Inner Circle + Privacy)
  3. `no_infra_expose`
  4. `no_destructive_without_directive` (Asset Destruction + Unauth Autonomy)
  5. `no_hijacking_via_external_content`
  6. `owner_directed_send` (positive cross-cutting)

### 9. Delete `proof_sketch` (Action 9, MINOR)
- **Action**: output schema is `{decision, synthesized_obligation, rule_id}`.

### 10. Grammar-constrained decoding (Action 10, MINOR)
- **Action**: two-stage schema: outer JSON via vendor structured-output; inner `synthesized_obligation` string gates on Cozo grammar parse (failure → confirm). Fallback: Outlines-wrapped small decoder with Cozo grammar file. Target: parse-failure < 0.5% on 500-call pilot.

### 11. Claim 3 demoted
- **Action**: Claim 3 removed from must-prove; listed as Future Work with explicit extension requirements.

---

## Revised Proposal (full)

# Research Proposal: LSVJ-S — LLM-Synthesized, Symbolically-Verified Judgments via Proof-Obligation Synthesis

## Problem Anchor
(Verbatim from round-0; copied at top of this document.)

## Technical Gap

**Where current methods fail.** LLM safety classifiers (Llama Guard, ShieldGemma, QuadSentinel 2025) output opaque labels with no symbolic audit trail. Rule-only (NeMo Guardrails) fails on held-out semantic intent (Nous v3: 12.7% TPR L1+L2-only). Hybrid stacking (Nous v1, ShieldAgent, GuardAgent, TrustAgent) runs LLM and symbolic engine on parallel tracks; symbolic engine feeds context or post-gate enrichment but cannot reject an LLM allow. Nous's own Loop-33 showed direct KG-injection degraded TPR by 12%, forcing KG into decorative post-gate role.

**Real nearest neighbors**: structured-generation-with-rule-verification (2024–2026) — policy-as-code agents (NeMo Colang), constrained-decoding-guided tool selection, LLM-proposed SQL + rule rewriting. These share the property LSVJ-S attacks: *the menu is fixed at authoring time*. A fixed menu cannot express a novel-composition attack unless it matches a template.

**Why naive fixes fail.** More training data (Nous: train 100% / held-out 75.3%), stronger LLM (QuadSentinel R=85.2%), more regex rules (L4 Hijacking 93.3% is ceiling; the remaining 6.7% is the open region), KG-in-prompt (already −12%), majority-vote-3 (no external verification).

**Smallest adequate intervention**: make the LLM synthesize the proof obligation as a Datalog rule per decision (not menu pick); make the symbolic engine a compile-time soundness-checking compiler + executor (not side car). Runtime synthesis covers novel compositions; compile-time soundness + non-triviality gates make "verifier" real.

**Frontier-native alternative (rejected on epistemic grounds)**: PRM/RL obligation-emitting head. Rejected because (i) reward-hacking collapses proposer/verifier separation; (ii) co-adaptation destroys audit property; (iii) grammar-constrained decoding gives schema adherence without training.

**Core technical claim**:
> A synthesis-and-soundness-check protocol — where the LLM synthesizes a per-decision Datalog rule over a typed primitive schema, and a compile-time gate rejects malformed, ill-typed, or trivially-discharging rules before execution — produces held-out generalization gains on a hard-negative slice over the strongest non-LSVJ baseline, with gains attributable (via ablation) to (i) synthesis step, (ii) non-empty KG facts in Class A primitives, and (iii) Class C sealed sub-oracle discharge.

**Required evidence**:
1. v3-HN hard-negative slice with ≥25% blind sub-slice: LSVJ-S vs current Nous L1–L4, LLM-only, rules-only; per-category Wilson 95% CI.
2. LSVJ-S ablation: full / `no_synth` / `no_class_A` / `no_class_B` / `no_class_C` / KG-corrupted / KG-empty.
3. Qualitative proof traces (5–10 cases): synthesized rule rejecting LLM-confabulated allow.
4. Cost/latency: ≤ +250ms per ambiguous call, ≤ 2 LLM calls on average (proposer + ≤ 1 Class C sub-oracle).

## Method Thesis

### One-sentence thesis
Treat the LLM's agent decision as a conjecture bundled with a *synthesized* Datalog proof obligation; treat the Cozo engine as a compile-time-soundness-checking verifier that rejects malformed, ill-typed, or trivially-discharging rules before execution; the allow verdict survives only when the synthesized rule discharges against live facts.

### Why smallest adequate
- **Reuses**: DeepSeek-V3.2 (no fine-tuning), Cozo + its parser, 46 YAML constraints, `proof_trace.py`, `markov_blanket.py`, KG schema.
- **Adds (4 non-trainable)**: (1) owner-harm primitive schema with A/B/C declarations; (2) synthesis prompt + grammar-constrained decoder; (3) compile-time gate (parse + type-check + non-triviality); (4) verifier policy + sealed Class C sub-oracle runner.
- **Does not touch**: L1, L2, L4.

### Why timely (2025–2026)
- Grammar-constrained decoding (XGrammar, Outlines, vendor JSON+string) makes runtime Datalog synthesis reliable without training.
- LLM-for-program-synthesis is a 2024–2026 capability; LSVJ-S applies it to runtime safety-rule synthesis (new domain).
- 2026 agent governance demand creates appetite for audit-grade decisions; synthesized rules = natural audit artifact.

## Contribution Focus

### Dominant contribution
**Synthesized Proof-Obligation (SPO) protocol + compile-time soundness gate** for runtime agent decisions. One mechanism: synthesize → parse-type-trivia-gate → execute → discharge → upgrade-on-undischarged. Evidence: hard-negative held-out + synthesis ablation.

### Supporting contribution
**Verifier-proposer semantic independence as audit property**: sealed-sub-oracle pattern for Class C primitives (same model, distinct sealed session, schema-bound input) preserves audit guarantee without second model. Ablation demonstrates bounded Class C contribution.

### Explicit non-contributions
- No new LLM, no fine-tuning, no RLHF/PRM.
- Not a new benchmark (v3-HN is a hard-negative slice on top of v3).
- Not a new symbolic reasoner (Cozo off-the-shelf).
- Not a security-robustness paper (Mythos adversary = Future Work).
- Not universal LLM trustworthiness (scope: agent runtime decisions).
- **6-template seed library is NOT a contribution** — it is a few-shot warm-start prior.

## Proposed Method

### Complexity Budget
- **Frozen/reused**: DeepSeek-V3.2, GPT-5.4, Cozo, 46 YAML constraints, L1/L2/L4, `proof_trace.py`, `markov_blanket.py`.
- **New non-trainable (4)**: schema (A/B/C), synthesis+decoder, compile-time gate, verifier policy + sealed sub-oracle runner.
- **New trainable: 0**.
- **Intentionally not used**: new LLM, differentiable Datalog, PRM/RL, L1/L2/L4 modifications.

### System Overview

```
tool_call
  ↓
L1 (Datalog): hard-block → exit if match
  ↓
L2 (Triviality): fast benign pass-through → exit if trivial
  ↓
L3-LSVJ-S (NEW):
  (a) Proposer: DeepSeek-V3.2 with grammar-constrained decoding
       prompt = { tool_call, session_context, primitive schema (A/B/C), 6-seed few-shot }
       output = { decision ∈ {allow, confirm, block},
                   synthesized_obligation: CozoScript rule,
                   rule_id: str }
  (b) Compile-time gate:
       parse(rule) → [parse fail → confirm]
       type_check(rule, schema) → [type fail → confirm]
       non_triviality(rule) → [trivial → confirm]
  (c) Execute:
       Class A primitives → Cozo Datalog over KG
       Class B primitives → deterministic Python/Cozo built-ins
       Class C primitives → sealed sub-oracle (fresh session, distinct prompt id, schema-bound input)
  (d) Verify policy:
       LLM block → accept block
       LLM confirm → accept confirm
       LLM allow + rule discharges → allow
       LLM allow + rule undischarged → upgrade to confirm
  ↓
L4 (Post-Gate Verifier): regex info-flow audit (unchanged)
  ↓
Final verdict + proof_trace { rule_text, class_usage, discharge_result }
```

**Key property**: L1, L2, L4 untouched. `no_synth` ablation = current Nous L3.

### Representation: Synthesized Obligations

Rule form (bounded):
```
?[discharged] := <body>, discharged = <boolean-expr over body bindings>
```
`<body>` = conjunction of primitive predicate calls drawn exclusively from owner-harm schema. Each primitive has declared `class ∈ {A, B, C}`, fixed arity, fixed typing.

Example (proposer output for a `send_email` call):
```
?[discharged] :=
  is_inner_circle(recipient_id),                            % A
  body_reveals_inner_relation(message_body,                 % C (sealed)
                              recipient_id, p_rev),
  owner_has_directed(action_id, is_directed),               % A
  discharged = (not p_rev) or is_directed
```

**6-seed template library** (prior, not contribution):
1. `no_credential_exfil` — `credential_pattern(B)`, `external_url(B)`, `owner_has_directed(A)`
2. `no_inner_circle_disclosure` — `is_inner_circle(A)`, `body_reveals_inner_relation(C)`, `owner_has_directed(A)`
3. `no_infra_expose` — `infra_resource_mentioned(B)`, `external_url(B)`, `action_in_precedent(A)`
4. `no_destructive_without_directive` — `destructive_action_pattern(B)`, `autonomy_bounded_by_directive(C)`, `owner_has_directed(A)`
5. `no_hijacking_via_external_content` — `read_before_send_chain(B)`, `external_content_flagged(B)`, `authority_coercion_present(C)`
6. `owner_directed_send` (positive) — `owner_has_directed(A)`, `recipient_owned_by_owner(A)`

### Training Plan
**None.** Zero-shot synthesis via grammar-constrained decoding + few-shot seeds. Named baseline **SFT-on-obligations (not run)**: 8B open model, Cozo-grammar-constrained decoding head, ~500 synthesized exemplars. Epistemic argument in Frontier-Leverage section: SFT degrades verifier independence by co-adapting proposer distribution to verifier acceptance criteria.

### Inference Path
1. Parse `ToolCall`.
2. L1; exit if match.
3. L2; exit if trivial.
4. **Synthesis**: proposer call with grammar-constrained decoder → `{decision, synthesized_obligation, rule_id}`.
5. **Compile-time gate**: parse → type-check → non-triviality. Any failure → `confirm` + `gate_fail_reason` logged.
6. **Execute**: Class A via Cozo; Class B via host functions; Class C via sealed sub-oracle (fresh session, schema-bound input, strict JSON).
7. **Verify policy** applies.
8. `proof_trace` emits `{rule_text, class_A_usage, class_B_usage, class_C_usage: [{primitive, prompt_id, input_hash, output}], discharge_result}`.
9. L4 unchanged.
10. Final verdict + decision_log.

### Why Mechanism Stays Small
Same LLM, same symbolic engine, same KG, 4 new components (all non-trainable), zero training. Power from runtime synthesis + compile-time gate, not from scaled infra.

### Frontier-Primitive Leverage
- **LLM as runtime Datalog rule synthesizer**, grammar-constrained. Obligation-as-*rule* (not obligation-as-*dispatch*) separates LSVJ-S from structured-tool-use safety gates.
- **Grammar-constrained decoding** (XGrammar / Outlines / vendor JSON+string): 2026 reliability primitive. Target parse-failure < 0.5%.
- **Compile-time gate (Cozo parser + schema type-check + non-triviality)**: soundness gate over synthesized rule.

### Failure Modes and Diagnostics

| Mode | Detect | Mitigate |
|---|---|---|
| Parse failure | Cozo parser | fail-closed → confirm |
| Type-check failure | schema validator | fail-closed |
| Triviality (body=true) | static check | fail-closed |
| Class A returns inconclusive (KG missing) | empty Cozo relation | treat as undischarged → confirm; KG gap flagged |
| Class B returns no-match | deterministic | undischarged → confirm |
| Class C sealed sub-oracle ambiguous | JSON schema mismatch | fail-closed, flag for Class C prompt iteration |
| Class C sees proposer reasoning (drift) | session-isolation CI lint | test fail on any cross-session context leakage |
| Rule trivially discharges (e.g., always-false precondition) | non-triviality check | reject |
| Over-specialization to seed → novel compositions fail | coverage monitor: % verbatim-match to seeds | target ≤ 30%; weaken few-shot if higher |
| Verifier latency blows up | per-class budgets (A 5ms, B 5ms, C 2s) | degrade to current L3 with `degraded=true` |

### Novelty Argument

- **vs ShieldAgent (ICML 2025)**: rule circuits verified statically; LSVJ-S synthesizes per decision and verifies at compile-time.
- **vs GuardAgent (2025)**: audits I/O post-hoc; LSVJ-S requires LLM to commit to a rule the verifier discharges *before* action.
- **vs TrustAgent (2024)**: re-runs static rules; LSVJ-S executes a fresh synthesized rule against live KG.
- **vs structured-generation-with-rule-verification (real nearest, 2025–2026)**: fixed menu at authoring time; LSVJ-S synthesizes at runtime with compile-time gate.
- **vs Scallop/Lobster (PLDI 2023 / ASPLOS 2026)**: offline differentiable neurosymbolic; LSVJ-S is classical runtime Datalog with LLM synthesis on top.
- **vs LLM-as-judge**: polarity-inverted (LLM proposes, symbolic judges) AND thing-being-judged is a *rule*, compile-time-typed.
- **vs ITP (Lean4/Coq)**: authoring-time, type-theoretic; LSVJ-S is runtime, Datalog-typed, bounded-depth.

**Focused contribution surface**: one protocol, one verifier policy, one typed primitive schema. 6-seed library = prior. One Figure 1 states protocol; three experiments test it.

## Claim-Driven Validation Sketch

### Claim 1 (Dominant): LSVJ-S improves held-out generalization on v3-HN hard-negative slice over strongest non-LSVJ-S baseline.
- **Metric**: TPR on v3-HN (≥100H+50B, ≥25% blind); per-category Wilson CI.
- **Configs**: LLM-only / Rules-only / Nous current / LSVJ-S.
- **Expected**: LSVJ-S > Nous current on v3-HN with statistically significant CI gap; blind sub-slice confirms direction.
- **Table 1**: 4-config main table.

### Claim 2 (Supporting): LSVJ-S gains are mechanism-level (synthesis + class-specific contribution + KG facts load-bearing).
- **Configs**: full / `no_synth` (fallback to 6-seed menu) / `no_class_A` / `no_class_B` / `no_class_C` / **KG-corrupted** (shuffle Class A facts within-type) / **KG-empty**.
- **Expected**:
  - `no_synth` < full → synthesis helps.
  - KG-corrupted < full and KG-corrupted ≈ `no_class_A` → KG content (not code path) matters.
  - `no_class_C` < full, `no_class_C` > random → Class C bounded contribution.
- **Table 2**: LSVJ-S ablation.

### Claim 3 (Stretch / Future Work): zero-shot transfer to ShieldAgent-Bench.
- **Status**: not gated for workshop. Main-track extension.
- **Why not AgentDojo zero-shot**: AgentDojo's utility-security frontier doesn't map cleanly to owner-harm obligation schema; ShieldAgent-Bench is closer.

## Experiment Handoff Inputs

### Must-prove claims
1. LSVJ-S > current Nous on v3-HN per-category (Wilson CI); blind confirms direction.
2. `no_synth` < LSVJ-S: synthesis helps over menu.
3. KG-corrupted < LSVJ-S: KG content carries weight.
4. Class A/B/C ablation yields expected ordering (each non-zero; Class C bounded).

### Must-run ablations
- LSVJ-S full; `no_synth`; `no_class_A`; `no_class_B`; `no_class_C`; KG-corrupted; KG-empty.
- Baselines: LLM-only, Rules-only, Nous current.

### Critical datasets / metrics
- **Primary**: v3-HN (≥100H+50B, ≥25% blind).
- **Reference**: v3 (300H+150B), AgentHarm (176+176).
- **Stretch**: ShieldAgent-Bench (Future Work).
- **Metrics**: TPR/FPR, Wilson 95% CI, ΔL, per-category, parse-failure rate, Class A/B/C usage per call, latency, API cost.

### Highest-risk assumptions
1. **Cozo-grammar-constrained synthesis works**: 500-call pilot in Week 2; failure > 1% → fall back to Outlines-wrapped small model.
2. **Seed library doesn't over-anchor**: verbatim-match monitor; > 30% → weaken few-shot.
3. **Class C sealed independence**: CI lint + diversity test (sub-oracle vs proposer-asked-same-question ≥ 30% divergence on calibration).
4. **v3-HN construction honest**: blind sub-slice + pre-registered protocol.
5. **Blind sub-slice sufficient**: target ≥ 38H+13B; expand if underpowered.

## Compute & Timeline

### Engineering (weeks 1–4)
- W1: schema with A/B/C; 2 Class A + 2 Class B primitives; unit tests.
- W2: synthesis prompt + grammar-constrained decoder + parse+type gate; 500-call pilot.
- W3: remaining primitives incl 3 Class C + sealed plumbing + CI lint; verifier policy.
- W4: KG-corruption utility; v3-HN authoring (70% author + 30% blind); integration tests.

### Experiments (weeks 5–6)
- W5: Claim 1 main table (4 configs × v3-HN). API ~$30.
- W6: Claim 2 ablation (7 conditions × v3-HN blind). API ~$60.

### Paper (week 7+)
- Rewrite `paper/main.tex` Sections 2–4; Tables 4/5 updated; Figure 2 (synthesis protocol); ShieldNet/QuadSentinel Related Work; auto-review-loop to ARIS ≥ 8.5.

### Totals
- Engineering: ~160 hours single author + Swarm support.
- API budget: ≤ $120.
- GPU: 0.
- Wall-clock to workshop submission: 8 weeks; 10–12 with Dario review.

## Risks and Open Questions (updated)

1. **Synthesis collapses to menu-pick in practice**: if ≥ 90% verbatim-match to seeds, novelty claim weakens. *Mitigation*: coverage monitor + few-shot weakening loop; if cannot reduce verbatim-match below 40%, honest reframe as "menu with free composition."
2. **v3-HN ceiling**: cases might still be solvable by current Nous. *Mitigation*: blind authoring + pre-registered protocol file.
3. **Class C drift**: same-model sealed sub-oracle may share representations. *Mitigation*: code-level sealing + CI lint + prompt-level diversity test on calibration set.
4. **KG-corruption delta too small**: if Class A doesn't carry weight, "not stage scenery" claim weakens. *Mitigation*: v3-HN construction seeds Inner-Circle-Leak-style cases where `is_inner_circle` is decisive.
5. **Workshop acceptance not guaranteed**: ~30–40% historical rate. *Fallback*: ICLR 2027 Workshop, AAAI 2027 Safe AI Workshop.

---

## Success Condition (carry-forward from round-0, one amendment)

Dongcheng will say "yes, this is trustworthy reasoning, not dressed-up pattern matching" iff **all four** hold:

1. **Held-out improvement is real** — on **v3-HN hard-negative slice (amended from v3 for ceiling)**, LSVJ-S beats current Nous (L1–L4) by statistically significant margin on blind sub-slice (Wilson CI).
2. **Gain is mechanism-level**: `no_synth` shows synthesis contributes; `no_class_A/B/C` show each class non-zero.
3. **KG contributes causally**: KG-corruption yields TPR drop on Class-A-dependent cases; shuffle-vs-intact delta > 0.
4. **Zero-shot transfer defensible** (**demoted** to stretch for workshop; required for main-track): ShieldAgent-Bench within 5pp, or honest Future-Work narration of obligation-schema extension.

If any of 1–3 fails, revise or reject — not reframe to hide. (4) may fail gracefully into Future Work.

---

*End of round-1 refinement.*
