# Research Proposal: LSVJ-S — LLM-Synthesized, Symbolically-Verified Judgments via Proof-Obligation Synthesis with Perturbation-Sensitivity + Decisive-Primitive Admission

> Final refined proposal. Author: Yan (for Dongcheng Zhang / Nous project).
> Workshop target: **NeurIPS 2026 Workshop on Safe & Trustworthy Agents** (December).
> Conditional ICLR 2027 main-track extension if Tier-2 ablations + external benchmark both succeed.
> Derived from 4 review-refine rounds (R4 verdict: READY-for-workshop, 7.95/10).

---

## Problem Anchor

### Bottom-line problem
In agentic systems where an LLM authorizes tool calls at runtime, the LLM's judgment is **not trustworthy** in the epistemic sense: the system cannot tell, from the LLM's output alone, whether an "allow" verdict reflects (a) genuine understanding of the action, (b) lucky pattern match on surface features, or (c) confabulation produced under adversarial prompting. Current hybrid architectures (LLM classifier + rule layer + knowledge graph) paper over this by stacking layers, but the LLM's decision is never *verified* by the symbolic substrate — the symbolic parts merely run alongside or feed context. Concretely, Nous demonstrates this pathology: training-set TPR 100% (Loop 74, 200H+50B), v3 held-out L1+L2-only TPR **12.7%** with L3 LLM adding +62.6pp, but the `no_kg` ablation on training set shows ΔL=0 — meaning KG is not carrying the generalization weight and the LLM's gains on held-out are not symbolically grounded.

### Must-solve bottleneck
**LLM-proposed agent decisions lack discharge-able symbolic obligations.** A decision of "allow" should be a *conjecture* that the symbolic engine is obligated to *verify* by discharging a structured proof obligation; today it is an opaque label.

### Non-goals
- Not "make LLM more accurate" (RLHF/DPO/PRM is a different paradigm).
- Not "replace LLM with rules" (v3 held-out 12.7% rules-only proves insufficient).
- Not "another LLM safety classifier" (Llama Guard / ShieldGemma / QuadSentinel saturate that lane).
- Not "reinvent a symbolic reasoner" (Cozo/Datalog exist).
- Not "universal LLM trustworthy reasoning" — scope is agent runtime decisions.
- Not "formal verification for the whole system" — per-decision obligations, not global invariants.
- Not a security-robustness paper (Mythos-class adversary = Future Work).

### Constraints
- Infrastructure frozen: Cozo embedded DB, Datalog engine + YAML constraints, DeepSeek-V3.2 production L3 LLM, GPT-5.4 judge, `proof_trace.py` / `markov_blanket.py` / 46 constraint files.
- Data: owner-harm v3 held-out (300H+150B); new hard-negative v3-HN slice (≥100H+50B with ≥50H+25B blind, 30H+15B neg-control); AgentHarm (176+176) for literature comparability; ShieldAgent-Bench Tier-2 stretch.
- Compute: single author + small Swarm (Codex/Gemini for review). API ≤ $120. Zero GPU training.
- Time: Dario released — arXiv-first, quality > speed. Workshop deadline December 2026.

### Success condition
Dongcheng will say "yes, this is trustworthy reasoning, not dressed-up pattern matching" iff **all four** hold:

1. **Held-out improvement is real** — on v3-HN, LSVJ-S > `SEAP` by statistically significant margin on Wilson CI; direction-consistent on blind sub-slice.
2. **Gain is mechanism-level at three loci**:
   - `SEAP` < full LSVJ-S.
   - `no_sem_gate` yields *directionally higher* false-allow rate on neg-control (diagnostic signal, not significance test).
   - Per-class (`no_class_A/B/C`) each non-zero.
3. **KG contributes causally per-primitive**: ≥ 2 Tier-1 Class A primitives show **paired-McNemar p < 0.05** on decisive subset.
4. **Zero-shot transfer defensible** (Tier-2 stretch; required for main-track): ShieldAgent-Bench within 5pp or honest Future-Work narration.

If any of 1–3 fails, revise or reject — not reframe to hide. (4) may fail gracefully.

---

## Technical Gap

**Current methods fail**:
- **LLM safety classifiers** (Llama Guard, ShieldGemma, QuadSentinel 2025): opaque labels, no audit at symbolic level.
- **Rule-only** (NeMo Guardrails): Nous v3 held-out 12.7% TPR L1+L2-only proves insufficient for semantic intent.
- **Hybrid stacking** (Nous v1, ShieldAgent ICML 2025, GuardAgent 2025, TrustAgent 2024): LLM and symbolic on parallel tracks, not verifier relationship. Nous Loop 33: direct KG-injection into semantic prompt degraded TPR 12%.
- **Neurosymbolic learning** (Scallop PLDI 2023, Lobster ASPLOS 2026): offline differentiable Datalog, not runtime.
- **Reasoning-model traces** (o1, DeepSeek-R1, Sonnet-thinking 2024–2026): reasoning *visible* but not *mechanically verifiable*.
- **Real nearest neighbors** — structured-generation-with-rule-verification (2025–2026): policy-as-code, constrained-decoding tool selection, LLM-proposed SQL + rule rewrite. All use **fixed menus at authoring time**. LSVJ-S departs: synthesis at runtime + compile-time behavioral soundness gate.

**Naive fixes fail**: more training data (train 100% / held-out 75.3%); stronger LLM (QuadSentinel R=85.2%); more regex (L4 Hijacking 93.3% ceiling); KG-in-prompt (−12% TPR); majority-vote-3 (no external verification).

**Smallest adequate intervention**: runtime Datalog rule synthesis + 4-stage compile-time gate (parse + type-check + syntactic non-triviality + **compound semantic gate: perturbation-sensitive ∧ has-decisive-primitive**) + Class-A/B/C-partitioned primitive schema. Decisive-primitive tracing serves Claim 2.3 causal analysis; diagnostic utility, not a gate component.

**Frontier-native alternative (rejected on epistemic grounds)**: PRM/RL obligation-emitting head. Rejected because (i) reward-hacking collapses proposer/verifier separation, (ii) co-adaptation destroys audit property, (iii) grammar-constrained decoding delivers schema adherence without training.

**Core technical claim**:
> A synthesis-and-soundness-check protocol — where the LLM synthesizes a per-decision Datalog rule over a typed primitive schema, and a compile-time gate rejects malformed, ill-typed, syntactically-trivial, or (perturbation-invariant OR decisive-primitive-less) rules before execution — produces held-out generalization gains on a hard-negative slice over the strongest non-LSVJ-S baseline (12-rule expert menu), with gains attributable via paired-McNemar analysis to (i) synthesis step, (ii) specific KG facts per Class A primitive, (iii) Class C sealed sub-oracle discharge.

---

## Method Thesis

**One-sentence thesis**: Make the symbolic engine the verifier: let the LLM synthesize a per-decision Datalog rule as its proof of trust, and admit the allow verdict only when the synthesized rule is mechanically soundness-checked (parses, types, is non-trivial syntactically, is perturbation-sensitive, and has at least one decisive primitive) AND discharges against live facts — so the verifier's authority does not depend on the LLM's capability.

**4-stage compile-time gate** (b.4 is a compound stage — perturbation-sensitivity ∧ has-decisive-primitive — honestly presented as two logically independent checks sharing a single machinery):
- **b.1** parse (Cozo parser)
- **b.2** type-check (A/B/C primitive schema)
- **b.3** syntactic non-triviality (body references ≥ 1 Class A/B primitive; head not literally `true`)
- **b.4** compound: **(perturbation-sensitive across N=5 trials) ∧ (has ≥ 1 single-flip decisive primitive)**

Any gate failure → fail-closed to `confirm`.

**Why smallest adequate**: reuses DeepSeek-V3.2, Cozo + parser, 46 YAML constraints, KG, `proof_trace.py`, `markov_blanket.py`. Adds 4 non-trainable components (schema A/B/C, synthesis + decoder, 4-stage gate, verifier policy + sealed Class C runner). Zero trainable.

**Why timely (2025–2026)**:
- Grammar-constrained decoding (XGrammar + Lark + Cozo PEG) makes runtime Datalog synthesis reliable without training.
- LLM-for-program-synthesis applied to runtime safety-rule synthesis (new domain).
- 2026 agent governance demand (NemoClaw, E7, Oasis) for audit-grade decisions; synthesized rules = natural audit artifact.

---

## Contribution Focus

### Dominant contribution
**SPO protocol + 4-stage compile-time gate with perturbation-sensitivity ∧ has-decisive-primitive admission**, demonstrated on v3-HN held-out via paired-McNemar per-primitive causal analysis.

**Scope qualification (honest)**: the gate catches fully-invariant and trivially-syntactic rules. It admits weakly-content-dependent rules (those flipping under ~20% of perturbations pass N=5 at P=1−0.8⁵≈67%). Positioned as a **soundness check (reject invariant), not a strong-dependence check**. This limitation is a feature of the zero-training protocol: a stronger gate would require training the proposer, collapsing verifier independence.

### Supporting contribution
Verifier-proposer separation as audit property via sealed Class C sub-oracle (same model, distinct session, schema-bound input, divergence calibration). Honestly labeled: **procedural independence, not representation-level**.

### Explicit non-contributions
- No new LLM / training / RLHF / PRM.
- Not a new benchmark (v3-HN is a slice).
- Not a new symbolic reasoner.
- Not a security-robustness paper.
- Not universal trustworthy reasoning.
- 6-seed library and 12-rule `SEAP` are prior / baseline, not contributions.

---

## Proposed Method

### Complexity Budget
- **Frozen/reused**: DeepSeek-V3.2, GPT-5.4, Cozo, 46 YAML constraints, L1/L2/L4, `proof_trace`, `markov_blanket`.
- **New non-trainable (4)**:
  1. Owner-harm primitive schema with A/B/C classes.
  2. Synthesis prompt + grammar-constrained decoder (XGrammar + Lark + Cozo PEG; vendor JSON outer).
  3. **4-stage compile-time gate** (parse + type + syntactic + **b.4 compound: perturbation-sensitive ∧ has-decisive-primitive**).
  4. Verifier policy + sealed Class C sub-oracle runner.
- **Diagnostic utility** (not a gate component): decisive-primitive tracing for Claim 2.3.
- **New trainable**: 0.

### System Overview

```
tool_call
  ↓ L1 (unchanged) → exit if match
  ↓ L2 (unchanged) → exit if trivial
  ↓ L3-LSVJ-S:
       (a) Proposer (DeepSeek-V3.2, grammar-constrained)
            → { decision, synthesized_obligation : CozoScript rule }
       (b) 4-stage compile-time gate:
            b.1 parse → fail-closed confirm
            b.2 type-check (A/B/C schema) → fail-closed confirm
            b.3 syntactic non-triviality → fail-closed confirm
            b.4 (perturbation-sensitive ∧ has-decisive-primitive) → fail-closed confirm
       (c) Execute against live bindings:
            Class A → Cozo Datalog over KG
            Class B → deterministic host fn / Cozo built-in
            Class C → sealed sub-oracle (fresh session, schema-bound input)
       (d) Record decisive_primitives in proof_trace (diagnostic)
       (e) Verify policy:
            LLM block/confirm → accept
            LLM allow + admitted + discharges → allow
            otherwise → upgrade to confirm
  ↓ L4 (unchanged)
  ↓ Final verdict + proof_trace { rule_text, class_usage, discharge_result, decisive_primitives }
```

### Representation: Synthesized Obligations

Rule form:
```
?[discharged] := <body>, discharged = <boolean expr over body bindings>
```
`<body>` = conjunction of primitive calls from the owner-harm schema. Each primitive has `class ∈ {A, B, C}`, fixed arity, fixed typing.

Example (for a `send_email` tool call):
```cozoscript
?[discharged] :=
  is_inner_circle(recipient_id),                       % A
  body_reveals_inner_relation(message_body,            % C (sealed)
                              recipient_id, p_rev),
  owner_has_directed(action_id, is_directed),          % A
  discharged = (not p_rev) or is_directed
```

**6-seed library (prior, not contribution)**: `no_credential_exfil` / `no_inner_circle_disclosure` / `no_infra_expose` / `no_destructive_without_directive` / `no_hijacking_via_external_content` / `owner_directed_send`.

**12-rule `SEAP` expert menu (baseline, not contribution)**: 6 seeds + 6 additional (`credentials_in_log_redacted`, `destructive_dryrun_unless_confirmed`, `infra_endpoint_without_auth`, `inner_circle_public_context_ok`, `hijacking_mitigated_by_audit_trail`, `autonomy_bounded_action_list`). Co-authored Dario+Yan, pre-registered in `nous/docs/no-synth-menu-plus.cozo` before any v3-HN eval.

### Semantic Gate b.4 (compound, N=5 default)

```python
def admitted(rule, live_bindings, schema, N=5, seed_pool) -> bool:
    """b.4 compound stage: perturbation-sensitive AND has-decisive-primitive.
    Two logically independent checks sharing evaluation machinery.
    """
    discharged_real = execute_rule(rule, live_bindings)

    # Check A: perturbation-sensitive (soundness against fully-invariant rules)
    perturbation_sensitive = any(
        execute_rule(rule, perturb(live_bindings, rule.body_primitives, schema, seed=seed_pool[k]))
          != discharged_real
        for k in range(N)
    )

    # Check B: has-decisive-primitive (every admitted rule has an attributable cause)
    has_decisive = any(
        execute_rule(rule, flip_primitive_binding(live_bindings, prim)) != discharged_real
        for prim in rule.body_primitives
    )

    return perturbation_sensitive and has_decisive
```

**Perturbation operators**:
- Class A: reshuffle primitive's matching tuples (preserve schema/arity, break semantic correspondence).
- Class B: negate boolean return.
- Class C: flip pre-recorded sub-oracle output (no additional LLM call).

**N=5 calibration (W3 pilot)**: hand-label 40-rule reference set into (i) genuinely content-dependent, (ii) weakly content-dependent (flip-rate 10–25%), (iii) content-invariant. Measure at N ∈ {3, 5, 7}: false-rejection (class i) ≤ 10%, false-admission (class iii) ≤ 2%. Weak-admission (class ii) recorded as directional signal. **Fallback commit**: if 40-rule reference set slips timeline, use N=7 without calibration claim; no ad-hoc retreat.

### Decisive-Primitive Tracing (diagnostic utility)

```python
def decisive_primitives(rule, live_bindings) -> list[str]:
    real = execute_rule(rule, live_bindings)
    if not real: return []
    return [prim.id for prim in rule.body_primitives
            if execute_rule(rule, flip_primitive_binding(live_bindings, prim)) != real]
```

Used only for Claim 2.3 paired-McNemar analysis. Recorded in `proof_trace.lsvj_obligations[i].binding_decisive_primitive`.

### Training Plan
**None.** Zero-shot synthesis + grammar-constrained decoding + few-shot seeds. SFT-on-obligations named as baseline, not run. Epistemic defense: SFT contaminates verifier independence by co-adapting proposer distribution to verifier acceptance criteria.

### Inference Path
1. Parse `ToolCall`.
2. L1 Datalog → exit if match.
3. L2 Triviality → exit if trivial.
4. Synthesis: proposer call with grammar-constrained decoder → `{decision, synthesized_obligation}`.
5. 4-stage gate (b.1 parse / b.2 type-check / b.3 syntactic / b.4 compound). Any failure → `confirm`.
6. Execute: Class A Cozo; Class B host; Class C sealed sub-oracle.
7. Decisive-primitive tracing → proof_trace.
8. Verify policy.
9. L4 unchanged.
10. Final verdict + decision_log.

### Frontier-Primitive Leverage
- **LLM as runtime Datalog rule synthesizer**, grammar-constrained.
- **XGrammar + Lark + Cozo PEG** committed. W2 pilot fork: if Cozo PEG has ≥ 1 construct not round-tripping in ≤ 2 days, commit to post-hoc parse + retry (3× max) as primary.
- **b.4 compound gate**: perturbation-sensitivity ∧ has-decisive-primitive — the specific property separating LSVJ-S from structured-tool-use + constrained-decoding safety gates.

### Failure Modes

| Mode | Detect | Mitigate |
|---|---|---|
| Parse / type / syntactic-trivial | b.1–b.3 | fail-closed confirm |
| Perturbation-invariant OR no-decisive-primitive | b.4 | fail-closed confirm + log vacuous rule |
| Class A inconclusive | empty Cozo relation | undischarged → confirm |
| Class B no-match | deterministic | undischarged → confirm |
| Class C ambiguous | JSON schema mismatch | fail-closed, prompt iteration |
| Class C drift | CI lint on session isolation | test fail |
| Seed over-anchoring | verbatim-match ≤ 30%; neg-control Class-A-*decisive* ≤ 20% | weaken few-shot |
| Verifier latency | per-class budgets | degrade with `degraded=true` |

### Novelty Argument

**Differences from closest work**:
- **ShieldAgent (ICML 2025)**: static rule-circuit verification; LSVJ-S synthesizes + compile-time soundness-checks per decision.
- **GuardAgent (2025)**: I/O audit post-hoc; LSVJ-S requires LLM commit before action.
- **TrustAgent (2024)**: re-runs static rules; LSVJ-S runs fresh synthesized rule against live KG.
- **Structured-generation-with-rule-verification (2025–2026)**: fixed menus; LSVJ-S synthesizes at runtime with perturbation gate.
- **Scallop/Lobster**: offline neurosymbolic; LSVJ-S classical runtime Datalog + LLM synthesis.
- **LLM-as-judge**: polarity-inverted; LSVJ-S makes the judged object a *rule* (compile-time-typed), not a verdict.
- **ITP (Lean4/Coq)**: authoring-time type-theoretic; LSVJ-S runtime Datalog-typed bounded.

**Role re-assignment**: the synthesized Datalog rule is the LLM's committed proof obligation; the compile-time gate is the check that makes the symbolic engine authoritative. One protocol, one compound admission gate, one typed primitive schema.

---

## Claim-Driven Validation Sketch

### Claim 1 (Dominant): LSVJ-S > `SEAP` on v3-HN
- **Metric**: TPR/FPR + Wilson 95% CI on v3-HN (≥100H+50B, ≥50H+25B blind); per-category.
- **Configs (5)**: LLM-only / Rules-only / Nous current (L1–L4) / `SEAP` / LSVJ-S.
- **Expected**: LSVJ-S > `SEAP` > Nous current. Direction-consistency on blind.
- **Paper Table 1**.

### Claim 2 (Supporting): LSVJ-S gains are mechanism-level with honest statistics

**Tier-1 (workshop-required, 9 conditions)**:
- full LSVJ-S
- `SEAP`
- `no_sem_gate` (disable b.4; measure false-allow rate on neg-control 30H+15B; **diagnostic only — no significance claim at this sample size; paired-Wilson 95% CI reported for direction only**)
- `no_class_A` / `no_class_B` / `no_class_C`
- `KG-shuffled-all`
- `corrupt_is_inner_circle_only` / `corrupt_owner_has_directed_only`
  - **Analysis**: paired McNemar on decisive subset (b = intact-allow → corrupted-block; c = intact-block → corrupted-allow); χ² at α=0.05.
  - **Effect-size floor (honest)**: given expected decisive-subset 20–30 per Tier-1 primitive and realistic b+c ≈ 7–12, McNemar significance at α=0.05 is reachable when b/(b+c) ≥ ~0.8; weaker effects reported as point estimate + paired-Wilson 95% CI on flip rate only, not as significance claim.

**Tier-2 (ICLR-conditional, post-workshop)**:
- `KG-empty` (complements `KG-shuffled-all`)
- `no_synth_6seed` (complements `SEAP`)
- `corrupt_recipient_owned_by_owner_only` / `corrupt_action_in_precedent_only`
- Neg-control expansion 60H+30B (hypothesis-testing-grade Claim 2.2)

### Claim 3 (Stretch / Future Work): ShieldAgent-Bench zero-shot
Not gated for workshop. Required for main-track.

---

## Experiment Handoff Inputs

### Must-prove claims (Tier-1)
1. LSVJ-S > `SEAP` on v3-HN full (Wilson CI, statistical) + direction-consistent on blind (diagnostic).
2. `no_sem_gate` yields *directionally higher* false-allow rate on neg-control (30H+15B); **interpretation diagnostic, not significance test** (explicitly stated in paper body, not just must-prove).
3. For ≥ 2 of Tier-1 Class A primitives, per-primitive corruption yields paired-McNemar p < 0.05 OR (if underpowered per effect-size floor) paired-Wilson 95% CI on flip rate entirely above 0.
4. Neg-control cases show ≤ 20% of LSVJ-S discharges with any Class A primitive *decisive* (via tracing). **Failure alternative pre-registered**: if > 20%, recalibrate seed library or re-author reference menu; no post-hoc criterion redefinition.

### Must-run ablations (Tier-1, 9 conditions)
LSVJ-S full; `SEAP`; `no_sem_gate`; `no_class_A`; `no_class_B`; `no_class_C`; `KG-shuffled-all`; `corrupt_is_inner_circle_only`; `corrupt_owner_has_directed_only`.

### Critical datasets / metrics
- **Primary**: v3-HN (≥100H+50B, ≥50H+25B blind, **30H+15B neg-control**).
- **Reference**: v3 (300H+150B), AgentHarm (176+176).
- **Stretch (Tier-2)**: ShieldAgent-Bench.
- **Metrics**: TPR/FPR + Wilson 95% CI; **paired-McNemar** per-primitive; ΔL; false-allow rate (diagnostic, no significance at n=45); parse-failure rate; class/primitive usage; decisive-primitive distribution; latency.

### Highest-risk assumptions
1. Grammar-constrained synthesis ≥ 99% parse rate (W2 pilot); **Cozo→Lark fork criterion** named.
2. Seed library non-over-anchoring: verbatim-match ≤ 30%; neg-control Class-A-*decisive* ≤ 20%.
3. Class C sealed independence: CI lint + ≥ 30% behavioral divergence on calibration set.
4. Semantic gate N=5 calibration: false-rejection ≤ 10% + false-admission on content-invariant ≤ 2% (W3 pilot).
5. Decisive-primitive tracing stable.
6. Tier-1 per-primitive paired-McNemar significant on ≥ 1 of `is_inner_circle`, `owner_has_directed`.
7. Blind 50H+25B feasible; **cosine-sim threshold calibrated (method §Blind)** on ~5 within-author + ~5 cross-author existing case pairs; if mean blind-vs-author cosine > calibrated threshold → flag failed-blind and recruit human collaborator for post-workshop ICLR run.

### Known workshop-scope limitations (named in Risks)
- **`KG-empty` deferred to Tier-2**: workshop causal-attribution rests on 2 per-primitive corruptions + `KG-shuffled-all`; `KG-empty` (absolute absence) is Tier-2.
- **Class C same-model sealed-session**: procedural independence, not representation-level. Different-model upgrade = Future Work.
- **v3-HN + menu co-authorship**: Yan co-authors both 50% v3-HN and 12-rule menu (with Dario). Pre-registration mitigates; human-collaborator authoring = post-workshop contingency.
- **Soundness theorem absent**: workshop contribution is empirical + protocol, not formal. Main-track extension.

---

## Compute & Timeline

### Engineering (weeks 1–5)
- **W1**: schema with A/B/C; 2 Class A + 2 Class B primitives; unit tests.
- **W2**: synthesis + grammar-constrained decoder (XGrammar + Lark + Cozo PEG); 500-call pilot; **Cozo→Lark fork decision**.
- **W3**: 4-stage compile-time gate (b.4 compound `admitted`); remaining primitives incl 3 Class C; sealed-session plumbing + CI lint; **40-rule hand-labeled reference set for N calibration**.
- **W4**: decisive-primitive tracing utility; per-primitive corruption harness (2 primitives Tier-1); 12-rule `SEAP` co-authored + frozen.
- **W5**: v3-HN authoring (50% author + 50% Sonnet-blind + 30H+15B neg-control); **blind-distance calibration** + measurement; integration tests.

### Experiments (weeks 6–7)
- **W6**: Claim 1 (5 configs × v3-HN full + blind). API ~$40.
- **W7**: Claim 2 Tier-1 (9 conditions; paired-McNemar on 2 per-primitive subsets). API ~$70.

### Paper (week 8+)
- Rewrite `paper/main.tex` Sections 2–4.
- Tables 1–3 (main + Tier-1 ablation + per-primitive paired-McNemar).
- Figure 2 (4-stage gate with compound b.4 decomposition visible — perturbation-sensitive + has-decisive-primitive shown as two sub-boxes).
- Figure 3 (per-primitive McNemar flip rates + paired-Wilson CI bars).
- auto-review-loop-llm to ARIS ≥ 8.5.
- ShieldNet / QuadSentinel / GuardAgent / TrustAgent Related Work.

### Totals
- Engineering: ~180 hours (single author + Codex/Sonnet subagent support).
- API budget: ≤ $120.
- GPU: 0.
- Wall-clock to workshop submission: 10 weeks nominal; 12 with Dario review cycles.

---

## Risks and Open Questions

1. **Semantic gate N=5 fails calibration** → raise N to 7 (cost +2 rule evaluations, negligible); else honest narration "gate catches invariant rules; weakly-dependent admitted — explicit soundness-check-not-strong-dependence framing."
2. **Synthesis seed-anchored on neg-control** → confirmation bias exposed; honest narration; re-calibrate seed library per MP4 failure alternative.
3. **Per-primitive paired-McNemar insignificant on both Tier-1 primitives** → Claim 2.3 weakens; honest narration; Tier-2 extension. Effect-size floor naming ensures reader knows when claim was reachable.
4. **Blind cosine-sim breaches calibrated threshold** → recruit human collaborator for ICLR slice (post-workshop). Workshop proceeds with 50% Sonnet-blind.
5. **Cozo→Lark PEG conversion blocked** → post-hoc parse + retry (3×) as primary path.
6. **`KG-empty` absence from Tier-1**: workshop causal-attribution relies on per-primitive corruptions + `KG-shuffled-all`; `KG-empty` as absolute-absence test is Tier-2. Named limitation in paper.
7. **Workshop acceptance not guaranteed** (~30–40% historical) → fallbacks: ICLR 2027 Workshop on Safe AI, AAAI 2027 Safe AI Workshop.

---

---

## Round-5 Novelty Patch (Gemini 3.1 Pro independent review, 2026-04-19)

After FINAL_PROPOSAL's R4 close, an independent Gemini 3.1 Pro novelty check (`NOVELTY_CHECK.md`) surfaced three corrections beyond Claude's R1–R4 coverage. Integrated here without re-opening the R1–R4 arc.

### Patch-1 — Cite Self-Consistency as foundation of b.4

Gate b.4's perturbation-sensitivity check is functionally a **structured Self-Consistency (Wang et al., 2022)** applied to LLM-synthesized Datalog rules. LSVJ-S must cite the Self-Consistency lineage (including program-synthesis majority-voting work) in Method Thesis + Related Work. Novelty credit shifts from b.4 alone to the **combination**: (i) structured-output synthesis constrained to a typed primitive schema, (ii) perturbation-sensitivity over the synthesized rule, (iii) decisive-primitive attribution for causal ablation. None of these three is new in isolation; the combination applied to agent runtime safety is.

### Patch-2 — Self-Justification Trap defense

LSVJ-S's proposer (the LLM) writes both the action it wants and the rule that admits the action. A misaligned or prompt-injected proposer can synthesize a **tautological rule** (e.g., `discharged := true_for_x`), **permissive rule** (referencing primitives known to be rarely-enforcing), or **collusion rule** (pattern-match to b.4's surface checks while being vacuous). Gate b.4 is the sole defense. The paper must explicitly acknowledge this trap and defend b.4 empirically via a dedicated **B6 Adversarial Synthesis Stress Test** (see EXPERIMENT_PLAN update): attacker-mode proposer prompted to bypass the gate; measured rejection rate. Without B6, Self-Justification Trap is unanswered.

### Patch-3 — Contingent framing based on B4 result

Gemini's 4/10 confidence hinges on the "decorative KG" smoking gun. The framing commitment is therefore **contingent on the B4 per-primitive KG-corruption ablation**:

- **If B4 shows ≥ 1 Tier-1 Class A primitive causally load-bearing** (paired-McNemar p<0.05 or paired-Wilson CI entirely above 0): keep LSVJ-S "symbolic substrate verifier" framing as specified.
- **If B4 is null on all Tier-1 primitives**: pivot framing to **JIT-Policy Gate** — drop the "symbolic substrate" overclaim, present LSVJ-S's contribution as "LLM JIT-synthesizes a Datalog rule whose 4-stage gate (including adversarial-robust perturbation check) filters self-justification from genuine content-dependence." This is Gemini's "Alternative Framing #2" and is smaller but honest. The Method Thesis remains identical; only the Contribution Focus + Novelty Argument prose shifts.

### Patch-4 — PCAS Statute-vs-Case-Law metaphor

Adopt Gemini's clean metaphor for the Novelty Argument's PCAS differentiation:
> "PCAS is a **Statute** model: laws written before the crime, deterministically enforced. LSVJ-S is a **Case Law** model: the LLM argues the legality of its specific action at the moment of execution, and a compile-time soundness gate checks the argument's non-triviality before admitting."

### Patch-5 — Related Work expansions

Add the following citations missed in R1–R4 (details in `LITERATURE_REVIEW.md`):
- **PCAS** (Palumbo, Choudhary et al., arXiv 2602.16708, 2026-02) — Statute-model Datalog policy compiler (closest prior art).
- **Solver-Aided** (Roy et al., arXiv 2603.20449, 2026-03) — offline NL→SMT + per-call verification.
- **Agent-C** (OpenReview VeRehDnGJJ) — decoding-time constrained generation with SMT.
- **Doshi et al.** (arXiv 2601.08012, ICSE NIER 2026) — STPA + MCP position paper.
- **Self-Consistency** (Wang et al., NeurIPS 2022) — foundation for b.4.
- **Follow-up searches** (deferred but listed): JIT policy synthesis 2025–2026 preprints, L-Eval / Logic-Guide, Inala Symbolic Shielding.

---

*Authored for Dongcheng Zhang, BlueFocus Communication Group. Derived from 4 review-refine rounds + 1 Gemini novelty patch; R4 verdict READY-for-workshop at 7.95/10, Gemini confidence 4/10 (amber-signal, contingent on B4 result). For revision history, see `REFINEMENT_REPORT.md`; for R4 breakdown, see `round-4-review.md`; for Gemini patches, see `NOVELTY_CHECK.md`.*
