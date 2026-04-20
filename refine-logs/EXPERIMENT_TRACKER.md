# Experiment Tracker — LSVJ-S

Live execution-oriented tracker. Updated in-place as runs complete.

**Key**: Status ∈ {TODO, RUNNING, DONE, BLOCKED, SKIPPED}. Priority ∈ {MUST, NICE}. Cost = estimated API dollars; "0" = deterministic / local / pre-recorded.

---

| Run ID | Milestone | Purpose | System / Variant | Split | Metrics | Priority | Cost | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | M0 Sanity | Schema A/B/C + 4 primitives (2 Class A, 2 Class B) + unit tests | schema draft | — | unit-test pass | MUST | 0 | TODO | `nous/ontology/schema/owner_harm.cozo` |
| R002 | M0 Sanity | Grammar-constrained synthesis pilot | DeepSeek-V3.2 + XGrammar+Lark+Cozo-PEG (primary) OR post-hoc parse+retry (fallback per Cozo→Lark fork) | 500 v3 calls sampled | parse-failure rate target <1% | MUST | ~$5 | TODO | W2; if parse rate <99%, invoke fork |
| R003 | M0 Sanity | 40-rule reference-set N-calibration | semantic gate at N ∈ {3, 5, 7} on hand-labeled (i) content-dependent / (ii) weakly-dependent / (iii) content-invariant | 40 rules | false-rejection ≤ 10%, false-admission ≤ 2% | MUST | 0 (deterministic once rules labeled) | TODO | W3; default commit N=5 if pass |
| R004 | M0 Sanity | Cozo→Lark EBNF fork decision | — | — | conversion feasibility ≤ 2 days | MUST | 0 | TODO | W2; either commit XGrammar+Lark or switch to post-hoc retry primary |
| R101 | M1 Baseline | LLM-only baseline | DeepSeek-V3.2 semantic gate only, no L1/L2/L4 | v3-HN full (≥100H+50B) | TPR/FPR + Wilson CI, per-category | MUST | ~$7 | TODO | Loop-84 |
| R102 | M1 Baseline | Rules-only baseline | L1 Datalog + L2 triviality | v3-HN full | TPR/FPR | MUST | 0 | TODO | deterministic; reproduces existing 12.7%/6.7% |
| R103 | M1 Baseline | Nous current (pre-LSVJ) | L1+L2+L3 (old prompt)+L4 | v3-HN full | TPR/FPR + Wilson CI | MUST | ~$7 | TODO | reproduce within 3pp of loop-state.json reference |
| R201 | M2 Main | `SEAP` (12-rule expert menu, pre-registered) | L1+L2+12-rule menu+L4 | v3-HN full + blind sub-slice | TPR/FPR + Wilson CI, per-category | MUST | ~$10 | TODO | **M2 gate input** — pre-register menu in `nous/docs/no-synth-menu-plus.cozo` BEFORE this run |
| R202 | M2 Main | LSVJ-S full | L1+L2+L3-LSVJ-S+L4; N=5 perturbation, k=3 vote | v3-HN full + blind sub-slice | TPR/FPR + Wilson CI, per-category; verbatim-match monitor; decisive-primitive distribution | MUST | ~$15 | TODO | Main paper Table 1 row 5 |
| R203 | M2 Gate | Claim-1 gate cross-review | Gemini 3.1 Pro (`gemini` CLI) reads Table 1 + raw CIs + verbatim-match | — | pass / revise | MUST | 0 (Gemini monthly plan) | TODO | **Off-ramp trigger**: if LSVJ-S NOT > `SEAP` on ≥3/8 categories OR verbatim-match > 50% → invoke M-off-ramp |
| R301 | M3 Ablation | `no_synth_6seed` (Tier-2, appendix) | L1+L2+6-seed menu+L4 | v3-HN full | TPR/FPR delta from full | NICE | ~$10 | TODO | Appendix only; skippable if timeline slips |
| R302 | M3 Ablation | `no_sem_gate` (disable stage b.4) | LSVJ-S minus b.4 | v3-HN neg-control 30H+15B | paired false-allow Δ + paired-Wilson 95% CI (diagnostic, no significance at n=45) | MUST | ~$5 | TODO | Claim 2 locus (b) |
| R303 | M3 Ablation | `no_class_A` (KG primitives return no-tuples) | LSVJ-S with Class A disabled | v3-HN full | per-category TPR drop Δ | MUST | ~$10 | TODO | Claim 2 locus (b)+class contribution |
| R304 | M3 Ablation | `no_class_B` (deterministic primitives disabled) | LSVJ-S with Class B disabled | v3-HN full | per-category TPR drop Δ | MUST | ~$10 | TODO | Same |
| R305 | M3 Ablation | `no_class_C` (sealed sub-oracle disabled) | LSVJ-S with Class C disabled | v3-HN full | per-category TPR drop Δ | MUST | ~$8 | TODO | Same |
| R306 | M3 Ablation | `corrupt_is_inner_circle_only` (Tier-1 primitive 1) | LSVJ-S with `is_inner_circle` KG tuples shuffled within-type | decisive subset (paired) | paired-McNemar χ² + paired-Wilson 95% CI on flip rate | MUST | ~$12 | TODO | Claim 2 locus (c); effect-size floor b/(b+c) ≥ ~0.8 for α=0.05 significance |
| R307 | M3 Ablation | `corrupt_owner_has_directed_only` (Tier-1 primitive 2) | LSVJ-S with `owner_has_directed` KG tuples shuffled within-type | decisive subset (paired) | paired-McNemar χ² + paired-Wilson 95% CI | MUST | ~$12 | TODO | Claim 2 locus (c) |
| R308 | M3 Ablation | **B6 Adversarial Synthesis Stress Test** (added per Gemini R5) | LSVJ-S with attacker-mode proposer prompt; vs `no_sem_gate` | 50 attacker-mode + 30 benign control | b.4 rejection rate on attacker-mode (target ≥90%); false-rejection on benign (target ≤10%); per-attack-type breakdown | MUST | ~$10 | TODO | **Defends Self-Justification Trap**. Introduced post-R4 per `NOVELTY_CHECK.md` Gemini patch. |
| R401 | M4 Polish | Qualitative proof-trace curation | LSVJ-S + `SEAP` | 5–10 hand-picked cases | synthesized rule text + decisive primitives + Class C sub-oracle I/O | MUST | 0 | TODO | Appendix A; 2–3 lifted to main Section 5 |
| R402 | M4 Polish | Figure 2 render (4-stage gate with compound b.4 decomposition visible) | — | — | figure file | MUST | 0 | TODO | Drawio / matplotlib / TikZ |
| R403 | M4 Polish | Figure 3 render (per-primitive paired-Wilson CI bars) | R306+R307 output | — | figure file | MUST | 0 | TODO | matplotlib |
| R404 | M4 Polish | Tables 1–3 finalize + `paper/main.tex` Sections 2–4 rewrite | — | — | LaTeX draft | MUST | 0 | TODO | Feeds into auto-review-loop-llm at Task #7 |
| R501 | M-off-ramp (conditional) | Exploration spike: PRM/RL-light obligation emitter | small open model (Qwen-7B?) + constrained decoding + PRM scored on verifier | v3-HN 50H sample | spike viability (TPR > 50% on 50-sample) | NICE | ~$15 | TODO | **Only if R203 M2 gate fails** |
| R502 | M-off-ramp (conditional) | Exploration spike: reasoning-model-native synthesis | Claude-thinking or DeepSeek-R1 as proposer | v3-HN 50H sample | same | NICE | ~$15 | TODO | **Only if R203 M2 gate fails** |

---

**Sums** (post-R5 patch with B6/R308 added):
- MUST runs: 18 (4 M0 + 3 M1 + 2 M2 + 1 M2-gate-review + 7 M3 incl. B6/R308 + 4 M4)
- NICE / conditional: 3 (1 Tier-2 appendix + 2 off-ramp spikes)
- Total MUST API cost: ~$121
- With off-ramp triggered: +$30 = ~$151 (overshoot of $120 budget; accept if off-ramp invoked or tighten k=3 vote to k=1 on Tier-2)

**Critical-path sequence**: R001 → R002 → R003/R004 (parallel) → R101/R102/R103 (parallel) → R201 → R202 → R203 (gate) → [R301–R308 parallel where possible] → R401–R404.

**Execution log**: append under this line as runs complete.

---

## Execution Log
*(empty — runs have not started)*
