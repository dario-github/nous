# Experiment Plan — LSVJ-S

**Problem**: LLM-proposed agent decisions lack discharge-able symbolic obligations; the LLM's "allow" is not mechanically verified by the symbolic substrate.

**Method Thesis**: Make the symbolic engine the verifier — LLM synthesizes a per-decision Datalog rule, a 4-stage compile-time gate (parse + type-check + syntactic-non-trivial + **perturbation-sensitive ∧ has-decisive-primitive**) admits it only if all stages pass, and the rule must discharge against live facts for allow to stand.

**Date**: 2026-04-18
**Target venue**: NeurIPS 2026 Workshop on Safe & Trustworthy Agents (December).
**Final goal (broader than workshop)**: agent trustworthy reasoning, not only owner-harm safety. Off-ramp preserved.

---

## Claim Map

| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|---|---|---|---|
| **C1 (dominant)**: LSVJ-S > `SEAP` on v3-HN held-out | Defeats the "runtime synthesis is just structured function calling" critique by beating a strong expert-curated menu of the same primitive shape | Wilson 95% CI non-overlap on full v3-HN AND direction-consistent improvement on 50H+25B blind sub-slice | B1, B2 |
| **C2 (supporting)**: Gain is mechanism-level, not prompt decoration | Rebuts "the LLM just reads better when asked in Datalog-shape"; localizes credit to the verify step + KG facts | 3 loci: (a) `SEAP` < full; (b) `no_sem_gate` yields directionally higher false-allow on neg-control (diagnostic); (c) ≥ 1/2 Tier-1 Class A primitives show paired-McNemar p<0.05 or paired-Wilson CI > 0 on decisive subset | B2, B3, B4, B5 |

**Anti-claims to rule out**
- "Gain is just prompt shape." Refuted by B2 (`SEAP`) + B3 (`no_sem_gate`).
- "Synthesis is template-completion." Refuted by verbatim-match coverage monitor ≤ 30% (B2 diagnostic).
- "KG is still stage scenery." Refuted by B4 per-primitive McNemar with decisive-primitive tracing.
- "Any one class (A/B/C) is redundant." Refuted by B3 class ablation (each class contributes non-zero).

---

## Paper Storyline

**Main paper must prove**: C1 (Table 1) + C2 loci (a)+(b)+(c) (Tables 2+3, Figure 2 = 4-stage gate, Figure 3 = per-primitive McNemar flip rates with paired-Wilson CI bars).

**Appendix supports**: `no_synth_6seed` (Tier-2); parse-failure/latency/cost per call; N-calibration 40-rule detail; blind-slice cosine-similarity method; qualitative proof-trace case studies (5–10).

**Intentionally cut / Tier-2 / Future Work**: `KG-empty` absolute-absence ablation; remaining 2 per-primitive corruptions (`recipient_owned_by_owner`, `action_in_precedent`); ShieldAgent-Bench zero-shot external benchmark; SFT-on-obligations baseline (named, epistemic argument, not run); different-model Class C sub-oracle.

---

## Experiment Blocks (5 must-run)

### B1 — Main Anchor: Claim 1 Main Table
- **Claim tested**: C1
- **Why**: workshop paper lives or dies on this table
- **Dataset / split**: v3-HN (≥100H + 50B; ≥50H + 25B blind sub-slice)
- **Compared systems (5)**:
  1. LLM-only — DeepSeek-V3.2 with current semantic-gate prompt, no L1/L2/L4
  2. Rules-only — L1 Datalog + L2 triviality, no L3/L4
  3. Nous current — L1+L2+L3 (old prompt) + L4
  4. **`SEAP`** — L1+L2+12-rule expert menu (pre-registered) + L4
  5. **LSVJ-S (ours)** — L1+L2+L3-LSVJ-S+L4
- **Metrics**: TPR / FPR + Wilson 95% CI; per-category; full slice + blind sub-slice separately
- **Setup**: DeepSeek-V3.2 as L3; `upgrade_only=True`; majority-vote k=3; grammar-constrained decoding (XGrammar+Lark+Cozo PEG or fallback); N=5 perturbation in b.4
- **Success criterion**: LSVJ-S per-category TPR ≥ `SEAP` on ≥ 5/8 categories; overall LSVJ-S Wilson CI lower bound > `SEAP` Wilson CI upper bound on ≥ 1 category; direction-consistent on blind
- **Failure interpretation**: if LSVJ-S ≤ `SEAP` statistically → **invoke Claim-1 failure off-ramp** (M-off-ramp below)
- **Table / figure**: Table 1 (main)
- **Priority**: MUST-RUN

### B2 — Novelty Isolation: Synthesis vs Menu
- **Claim tested**: C2 locus (a)
- **Why**: reviewer's sharpest attack — "synthesis is dressed-up menu completion"
- **Dataset / split**: v3-HN full + verbatim-match coverage monitor
- **Compared systems**:
  - LSVJ-S full
  - `no_synth_6seed` (Tier-2, appendix)
  - `SEAP` (main)
- **Metrics**: TPR drop Δ from full; verbatim-match rate (% synthesized rules verbatim-match a seed or menu rule); distinct rule bodies per 100 cases
- **Setup**: synthesis pipeline on v3-HN; compute verbatim-match against 6+12 rule library
- **Success criterion**: LSVJ-S > `SEAP` on ≥ 3/8 categories with CI direction; verbatim-match ≤ 30%
- **Failure interpretation**: if verbatim-match > 50% OR `SEAP` ≈ LSVJ-S → synthesis collapsed to template-completion → weaken few-shot anchor or reframe contribution scope
- **Table / figure**: Table 2a; Appendix: verbatim-match histogram
- **Priority**: MUST-RUN

### B3 — Simplicity Check: Stage + Class Necessity
- **Claim tested**: C2 locus (b) + per-class contribution
- **Why**: defends 4-stage gate against "which stage does work?"
- **Dataset / split**: v3-HN full (class ablation) + v3-HN neg-control 30H+15B (`no_sem_gate` diagnostic)
- **Compared systems**:
  - LSVJ-S full
  - `no_sem_gate` (disable stage b.4 compound)
  - `no_class_A` (Class A primitives return no-tuples)
  - `no_class_B` (Class B deterministic disabled)
  - `no_class_C` (Class C sealed sub-oracle disabled)
- **Metrics**: per-class TPR drop Δ; false-allow rate on neg-control (paired-Wilson 95% CI, **diagnostic-only — no significance claim at n=45**); per-class usage rate per call
- **Setup**: config flag toggling; rerun on same v3-HN; reuse proof_trace class-usage telemetry
- **Success criterion**:
  - `no_sem_gate` directionally higher false-allow on neg-control (delta > 0 with paired-Wilson lower bound > −5pp)
  - Each `no_class_A/B/C` yields overall TPR drop ≥ 3pp
- **Failure interpretation**: if `no_sem_gate` ≈ full on neg-control → b.4 not doing work → rethink gate. If any class ablation ≈ full → class is redundant; collapse schema
- **Table / figure**: Table 2b (stage + class)
- **Priority**: MUST-RUN

### B4 — Frontier Necessity: Per-Primitive Causal via Paired-McNemar
- **Claim tested**: C2 locus (c)
- **Why**: answers "is KG causally load-bearing?" — the critical rebuttal to the original "KG is stage scenery" critique
- **Dataset / split**: v3-HN full + decisive subset per primitive (rule-level tracing on intact LSVJ-S run)
- **Compared systems (paired)**:
  - LSVJ-S intact (reference)
  - `corrupt_is_inner_circle_only` (shuffle only this primitive's KG tuples within-type)
  - `corrupt_owner_has_directed_only`
- **Metrics**: paired McNemar χ² with continuity correction on decisive subset; paired-Wilson 95% CI on flip rate b/(b+c); per-primitive decisive-subset size report
- **Setup**: per-primitive corruption utility (~100 lines); decisive-primitive tracing in `proof_trace.lsvj_obligations[i].binding_decisive_primitive`; paired run on same case IDs
- **Effect-size floor (honest)**: given expected decisive subset 20–30 per Tier-1 primitive and realistic b+c ≈ 7–12, McNemar significance at α=0.05 reachable when b/(b+c) ≥ ~0.8; weaker effects reported as point estimate + paired-Wilson CI only, explicitly not as significance claim
- **Success criterion**: ≥ 1 of 2 Tier-1 primitives shows paired-McNemar p < 0.05 OR (if b+c < 10) paired-Wilson 95% CI entirely above 0
- **Failure interpretation**: if both primitives show no effect → try Tier-2 primitives (`recipient_owned_by_owner`, `action_in_precedent`); if all 4 null → Claim 2 locus (c) fails → report honestly, propose KG-heavy obligation redesign as Future Work
- **Table / figure**: Table 3 (per-primitive McNemar); Figure 3 (paired-Wilson CI bars per primitive)
- **Priority**: MUST-RUN

### B5 — Qualitative Proof-Trace Diagnosis
- **Claim tested**: C1 + C2 qualitative support
- **Why**: converts "numbers improved" into "we can see what the verifier caught"; also reveals what LSVJ-S still misses
- **Dataset / split**: 5–10 hand-picked v3-HN cases: 3 where LSVJ-S caught what `SEAP` missed; 3 where both caught; 2 where neither caught (failure analysis); 1 neg-control showing Class-A-decisive ≤ 20%
- **Compared systems**: LSVJ-S full, `SEAP`
- **Metrics**: qualitative — synthesized rule text, decisive primitives, sealed Class C sub-oracle prompt/response (redacted where needed), verdict diff
- **Setup**: extract from `proof_trace` logs after B1; curate by hand
- **Success criterion**: for each caught case, synthesized rule structure clearly shows which primitive detected what — interpretable
- **Failure interpretation**: if rules are unreadable / don't show mechanism, proof-trace artifact fails its audit purpose → rethink rule shape
- **Table / figure**: Appendix A (5–10 case studies); 2–3 selected into main Section 5 (Discussion)
- **Priority**: MUST-RUN (qualitative is cheap; cut ≤ 3 cases if timeline slips)

### B6 — Adversarial Synthesis Stress Test (added per Gemini R5 novelty patch)
- **Claim tested**: defense against Self-Justification Trap (b.4 is not vacuous)
- **Why**: Gemini review flagged that LSVJ-S proposer writes both the action and the rule admitting it — can collude via tautological, permissive, or crafted-to-pass-b.4 rules. Without a stress test, the "symbolic substrate" claim is undefended.
- **Dataset / split**: 50 attacker-mode cases (hand-crafted); proposer given a sealed prompt explicitly instructing it to **bypass the gate** by emitting a rule that syntactically passes b.1–b.3 but is semantically vacuous. Also run on 30 v3-HN benign cases as control (b.4 should NOT reject genuine non-trivial rules).
- **Compared systems**: LSVJ-S full (b.4 enabled) vs `no_sem_gate` (b.4 disabled)
- **Metrics**: b.4 rejection rate on attacker-mode (target ≥ 90%) + false-rejection rate on benign control (target ≤ 10% = N=5 calibration commitment). Per-attack-type breakdown: (i) tautology (e.g., `true_for_x := true`), (ii) permissive (references KG-rarely-enforcing primitives), (iii) collusion (patterns crafted to pass perturbation but be vacuous), (iv) multi-primitive OR-disjunction where only one primitive drives discharge.
- **Setup**: separate attacker prompt template (not the normal proposer prompt); same DeepSeek-V3.2 (simulates misaligned/prompt-injected proposer); same 4-stage gate
- **Success criterion**: b.4 rejects ≥ 90% of attacker-mode rules; ≤ 10% false-rejection on benign control; per-attack-type rejection ≥ 75% across all 4 types
- **Failure interpretation**: if b.4 rejection < 75% on any attack type → Self-Justification Trap defense is incomplete → rethink b.4 (raise N, add new perturbation operator, or add Class-C-independence check)
- **Table / figure target**: Table 4 (adversarial rejection rates + per-attack-type breakdown)
- **Priority**: MUST-RUN (introduced at R5; ~$10 API + 1 engineering day)

---

## Run Order and Milestones

| Milestone | Goal | Runs | Decision Gate | Cost | Risk |
|---|---|---|---|---|---|
| **M0 Sanity (W1–W3)** | Schema + synthesis + gate + pilots | 500-call parse pilot (W2); 40-rule N-calibration (W3); Cozo→Lark fork decision | Parse rate ≥ 99% AND N=5 false-rejection ≤ 10% AND false-admission ≤ 2% | 0 API; 60 engineering hours | Cozo→Lark blocks — fallback post-hoc parse+retry |
| **M1 Baseline (W5)** | Reproduce strong baselines on v3-HN | B1 configs 1, 2, 3 (LLM-only / Rules-only / Nous current) | Baselines reproduce within 3pp of loop-state.json historical reference | ~$15 (Rules-only free; LLM-only + Nous current each ~$7) | Pipeline regression; test fixtures |
| **M2 Main (W6)** | Claim 1 main table | B1 config 4 (`SEAP`) + config 5 (LSVJ-S) | **M2 gate — Claim 1 off-ramp check**: LSVJ-S > `SEAP` on ≥ 3/8 categories AND verbatim-match ≤ 50%. If NO → invoke M-off-ramp. | ~$25 (2 configs × 150 cases × k=3 vote) | Synthesis failure / verbatim-match too high / no gain over menu |
| **M3 Ablation (W7)** | Claim 2 ablations | B2 `no_synth_6seed` + B3 all conditions + B4 per-primitive × 2 | ≥ 2 of 3 Claim 2 loci hold: (a) `SEAP` < LSVJ-S; (b) `no_sem_gate` directionally higher; (c) ≥ 1 primitive paired-McNemar significant OR CI > 0 | ~$70 (many conditions but smaller slices) | Class ablation redundant; per-primitive null |
| **M4 Polish (W8)** | Qualitative + figures + Related Work | B5 qualitative cases; Figures 2, 3 render; Tables 2c, 3 finalize | Figures pass self-review + Gemini 3.1 Pro cross-read | ~$10 (mostly rendering) | Timeline slip |
| **M-off-ramp (conditional)** | Only if M2 gate fails | Pause; exploration spikes (PRM/RL-light, reasoning-model-native, harder negative-evaluator construction); write off-ramp memo to user | User approval to switch route | 0–$30 spike budget | Opportunity cost |

**Total API cost estimate**: ~$120 (in budget).
**Total engineering**: ~180 hours single-author + Swarm.

---

## Compute and Data Budget

- **Total estimated GPU-hours**: 0 (zero training; all inference).
- **Data preparation needs**:
  - v3-HN construction: 50% author (Yan) + 50% blind (Sonnet 4.6 subagent with sealed prompt, protocol pre-registered in `nous/docs/v3-HN-blind-protocol.md`); 30H+15B neg-control; cosine-similarity threshold calibrated on ~5 within-author + ~5 cross-author case pairs before W5
  - 12-rule `SEAP`: co-authored Dario+Yan before eval, pre-registered in `nous/docs/no-synth-menu-plus.cozo`
  - 40-rule N-calibration reference set (W3): hand-labeled by Yan into (i) content-dependent, (ii) weakly-dependent 10–25% flip, (iii) content-invariant
- **Human evaluation needs**: qualitative proof-trace curation (B5), ~4 hours
- **Biggest bottleneck**: v3-HN authoring (Sonnet-blind 50H+25B + human 50H+25B + 30H+15B neg-control) — ~3–5 subagent days + 2 human days

---

## Model Routing (execution-level)

| Stage | Model | Tool |
|---|---|---|
| Main orchestration (this session) | Opus 4.7 | native |
| Synthesis pilot + semantic gate production | DeepSeek-V3.2 | existing `openai_provider.py` (NOUS_API_KEY) |
| v3-HN blind authoring | Sonnet 4.6 | Agent subagent with sealed prompt |
| Batch experiment execution code | Sonnet 4.6 or Kimi K2.5 | Agent subagent / `kimi` CLI |
| Judge (Wilson CI / McNemar analysis) | Python + scipy.stats (deterministic) | no LLM |
| M2 gate cross-review | Gemini 3.1 Pro | `gemini` CLI |
| M4 figure cross-read | Gemini 3.1 Pro or Opus 4.7 (sparingly) | `gemini` CLI / Agent |
| Final proof-trace qualitative narration | Opus 4.7 | Agent (1 call) |

Opus spawning restricted to **critical decision gates** and **final reports**. Everything else Sonnet/Kimi/Gemini.

---

## Risks and Mitigations

1. **Synthesis collapses to template-completion** (verbatim-match > 30%): weaken few-shot anchor; if still > 50%, reframe contribution as "strong-menu-with-free-composition" and adjust paper scope.
2. **LSVJ-S does not beat `SEAP` at M2 gate**: trigger M-off-ramp. Do not write "we tried and failed" paper. Options: (a) PRM-trained obligation emitter on small open model; (b) reasoning-model-native synthesis (Claude-thinking, DeepSeek-R1); (c) program-synthesized primitives (new predicates, not just rules).
3. **Per-primitive paired-McNemar null on both Tier-1 primitives**: honest narration; try Tier-2 primitives; if all 4 null, locus (c) weakens → KG-heavy obligation redesign as Future Work.
4. **Neg-control n=45 cannot support diagnostic interpretation**: expand to 60H+30B (Tier-2) or label qualitative signal only.
5. **v3-HN blind author (Sonnet) shares biases with proposer (DeepSeek)**: cosine-similarity threshold triggers recruit-human-collaborator branch post-workshop.
6. **API budget overshoot**: k=3 majority vote is dominant cost; if tight, drop to k=1 on Tier-2 (main stays k=3).
7. **10-week timeline slip**: polish stage (M4) compresses first — drop appendix figures before core tables.
8. **M0 sanity fails**: W3 adds 1 week for prompt engineering or switch to Outlines-wrapped small model decoder.

---

## Final Checklist
- [x] Main paper tables covered (Table 1 main; Table 2a synth-vs-menu; Table 2b stage+class; Table 3 per-primitive)
- [x] Novelty isolated (B2 synthesis vs expert menu; verbatim-match diagnostic)
- [x] Simplicity defended (B3 stage + class ablation; `no_sem_gate` on neg-control)
- [x] Frontier contribution justified (B4 per-primitive causal; grammar-constrained decoding as 2026-native primitive)
- [x] Nice-to-have separated from must-run (Tier-2 ablations deferred)
- [x] Failure off-ramp named (M-off-ramp at M2 gate)
- [x] Model routing explicit (Opus only at decision gates; Sonnet/Kimi/Gemini for batch and cross-review)

---

*Handoff options: `/run-experiment` for M0 Sanity stage immediately, OR continue with Task #2/#3 (research-lit + novelty-check) first per pre-coding lit-sweep discipline.*
