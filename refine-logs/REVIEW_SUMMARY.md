# Review Summary — LSVJ-S Research Refine

**Problem**: Nous 的目的是让 LLM 做可信推理 (make LLM reasoning trustworthy in agent runtime decisions).
**Initial Approach**: User-given vague direction, turned into a problem-anchored research proposal via the `research-refine` skill.
**Date**: 2026-04-18
**Rounds**: 4 / MAX_ROUNDS=5
**Final Score**: 7.95/10 (R4)
**Final Verdict**: **READY-for-workshop** (below skill-default 9.0 and workshop-default 8.5; granted for honest scope commitment + three-round additive-not-reshuffling revision arc)

**Target venue**: NeurIPS 2026 Workshop on Safe & Trustworthy Agents (primary); ICLR 2027 main-track conditional on Tier-2 + external benchmark.

**Reviewer substitution**: GPT-5.4 via Codex MCP unavailable locally (no Codex CLI, no OPENAI/OPENROUTER API key). Used independent-context Claude Opus 4.7 with anti-sycophancy rubric. Each round's reviewer = fresh subagent session; author (this main session) and reviewers did not share context. Transparent in score-history.md.

---

## Problem Anchor (verbatim, carried across 4 rounds)

### Bottom-line problem
In agentic systems where an LLM authorizes tool calls at runtime, the LLM's judgment is **not trustworthy** in the epistemic sense: the system cannot tell, from the LLM's output alone, whether an "allow" verdict reflects (a) genuine understanding of the action, (b) lucky pattern match on surface features, or (c) confabulation produced under adversarial prompting. Current hybrid architectures (LLM classifier + rule layer + knowledge graph) paper over this by stacking layers, but the LLM's decision is never *verified* by the symbolic substrate — the symbolic parts merely run alongside or feed context. Concretely, Nous demonstrates this pathology: training-set TPR 100%, v3 held-out L1+L2-only TPR **12.7%** with L3 LLM adding +62.6pp, but the `no_kg` ablation shows ΔL=0 — KG not carrying generalization weight.

### Must-solve bottleneck
**LLM-proposed agent decisions lack discharge-able symbolic obligations.**

---

## Round-by-Round Resolution Log

| Round | Score | Verdict | Main Reviewer Concerns | What Was Changed | Solved? | Remaining Risk |
|-------|-------|---------|-------------------------|------------------|---------|----------------|
| **R0 (initial)** | — | — | — (author-written initial proposal) | LSVJ protocol, 12-item obligation taxonomy, KG no_kg ablation, epistemic problem framing. | — | — |
| **R1** | 6.3 | REVISE | Obligation primitives hand-wavy; contribution = "structured tool-use with ritual"; `no_kg` circular; ceiling on weak categories; zero-training on resource grounds; venue unclear. | Synthesized-rule lift (Route A); A/B/C primitive partition; epistemic zero-training; KG-corruption; hard-negative v3-HN; venue commit (workshop-first); 12→6 seeds; delete `proof_sketch`; grammar-constrained decoding; blind 25%. | **partial**: lift substantive but 6-seed + typed arities keeps synthesis close to template-completion; non-triviality syntactic. | Semantic non-triviality missing; bulk KG-corruption not per-primitive; CI reachability. |
| **R2** | 6.95 | REVISE | Syntactic non-triviality admits vacuous rules; bulk Class-A shuffle conflates primitives; `no_synth` weak; blind 25% underpowered; v3-HN co-authored. | Semantic non-triviality gate (perturbation-sensitivity); per-primitive KG-corruption + rule-level decisive-primitive tracing; `no_synth_menu_plus` 12-rule pre-registered; blind 50H+25B; ICLR split conditional; ≥10% neg-control; delete `rule_id`; XGrammar+Lark+Cozo PEG. | **partial**: additions substantive but Claim 2.2 n=15 and Claim 2.3 subset 20–25 remain under-powered; 5 components = bloat creeping. | CI reachability for paired analysis; component bloat; compound gate not surfaced. |
| **R3** | 7.5 | REVISE | Per-primitive 5pp unreachable; neg-control n=15 noise; N=3 false-admission 49% on weakly-dependent; GLOBAL_VACUOUS redundant with b.4; 11+ ablations tight; Cozo→Lark risk. | **Paired McNemar** (uses paired tracing data); neg-control 30H+15B + diagnostic relabel; N=5 default + both-error calibration on 40-rule reference; **merge GLOBAL_VACUOUS into b.4 compound** (5→4 components); Tier-1/Tier-2 ablation split (9 Tier-1); Cozo→Lark fork; neg-control Class-A *decisive*; blind-distance threshold + branch. | **yes (workshop scope)**: all 8 R3 actions RESOLVED at R4. | Effect-size floor not stated quantitatively; b.4 compound not surfaced in Figure 2. |
| **R4** | 7.95 | **READY-for-workshop** | Paired-McNemar power vs realistic b+c not argued; N=5 no strong-dependence guarantee (honestly positioned as soundness); b.4 compound should own 2-checks-in-1; cosine 0.85 is magic; `KG-empty` in Tier-2 is workshop limitation; MP4 failure action missing. | FINAL_PROPOSAL integrates 5 R4 polish items: **effect-size floor sentence** (b/(b+c) ≥ ~0.8); **b.4 decomposition** surfaced in Figure 2 + Complexity Budget; **cosine calibrated** on within/cross-author pairs; **`KG-empty` named as Tier-1 gap** in Risks; **MP4 failure alternative pre-registered**. | **yes**. Workshop-READY granted. | Gap to ICLR main (8.5+) remains — requires soundness theorem, different-model Class C, distinct authorship, or harder empirical claim. Deferred. |

---

## Overall Evolution

- **Method concretization**: R1 forced obligation-as-synthesized-rule lift (not menu-pick). R2 forced typed primitive partition (A/B/C) with sealed Class C. R2 also forced semantic non-triviality + per-primitive causal tracing. R3 compressed these into compound b.4 stage (perturbation-sensitive ∧ has-decisive-primitive) and aligned statistics to instrument power (paired-McNemar, neg-control as diagnostic). R4 surfaced honest effect-size floors + b.4 decomposition.
- **Contribution focus**: started with "LSVJ protocol + obligation taxonomy" (two co-equal). R1 demoted taxonomy to prior; R2 lifted contribution to synthesis + compile-time gate; R3 consolidated gate from 5 to 4 components by merging GLOBAL_VACUOUS into b.4.
- **Complexity removed**: R1 deleted `proof_sketch` + collapsed 12→6 seeds. R2 added semantic gate + tracing (up to 5 components). R3 merged GLOBAL_VACUOUS, deleted `rule_id`, tier-split ablations (11→9 Tier-1). Net: back to 4 non-trainable components at R4.
- **Modern leverage**: R1 acknowledged constrained-decoding (Outlines, XGrammar) as better primitive than "in-context following". R2 committed XGrammar+Lark+Cozo PEG. R3 added fork criterion for conversion risk.
- **Drift avoided**: R1 reviewer flagged latent drift on Class C → now explicitly labeled "procedural independence, not representation-level". R2 flagged v3-HN + menu co-authorship → R3 added blind-distance branch. R3 flagged compound b.4 framing → R4 surfaces decomposition in Figure 2 + Complexity Budget. **Problem anchor verbatim all 4 rounds; no anchor drift.**

---

## Score Trajectory

| Round | Problem Fid. | Method Spec. | Contrib. Qual. | Frontier Lev. | Feas. | Valid. Focus | Venue Ready. | Overall | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| R1 | 8 | 6 | 5 | 6 | 8 | 6 | 5 | 6.3 | REVISE |
| R2 | 9 (+1) | 7 (+1) | 6 (+1) | 7 (+1) | 7 (−1) | 6 (0) | 8 (+3) | 6.95 (+0.65) | REVISE |
| R3 | 9 (0) | 8 (+1) | 7 (+1) | 8 (+1) | 6 (−1) | 6 (0) | 8 (0) | 7.5 (+0.55) | REVISE |
| R4 | 9 (0) | 8 (0) | 7.5 (+0.5) | 8 (0) | 7 (+1) | 7 (+1) | 8.5 (+0.5) | 7.95 (+0.45) | **READY-for-workshop** |

Dimensions that improved most: Venue Readiness (+3.5 total), Method Specificity (+2), Contribution Quality (+2.5), Frontier Leverage (+2). Validation Focus and Feasibility fluctuated inversely as complexity was added (R2) then consolidated (R3–R4).

---

## Final Status

- **Anchor status**: preserved verbatim through 4 rounds. Zero drift.
- **Focus status**: tight — one dominant contribution (SPO protocol + 4-stage compile-time gate with compound b.4), one supporting (verifier-proposer separation as audit property), explicit non-contributions list.
- **Modernity status**: appropriately frontier-aware (grammar-constrained decoding, LLM-for-program-synthesis in new domain; zero-training defended on epistemic grounds).

**Strongest parts of final method**:
- Semantic non-triviality gate (perturbation-sensitivity + decisive-primitive admission) as compile-time soundness check over LLM-synthesized Datalog rules.
- Per-primitive paired-McNemar causal attribution tied to decisive-primitive tracing.
- Honest scope commitment (workshop-primary, main-track conditional on Tier-2 + external benchmark).

**Remaining weaknesses (honest)**:
- Novelty is "structured tool-use + compile-time perturbation-sensitivity gate + Datalog-typed synthesis." Real but workshop-tier. Main-track needs a soundness theorem or substantially harder empirical claim.
- Class C sealed sub-oracle: procedural independence, not representation-level. Acceptable workshop scope; ICLR reviewer will probe.
- v3-HN 50% author-constructed + 12-rule menu co-authored by Yan (with Dario): pre-registration mitigates, does not eliminate leakage.
- Paired-McNemar power: effect-size floor (b/(b+c) ≥ ~0.8) named, but whether real effect meets this is empirical.
- Soundness theorem deliberately absent.

---

## Review Artifacts
- Final proposal: `refine-logs/FINAL_PROPOSAL.md`
- Detailed report: `refine-logs/REFINEMENT_REPORT.md`
- Score history: `refine-logs/score-history.md`
- Raw reviews (4): `refine-logs/round-{1,2,3,4}-review.md`
- Revisions (3): `refine-logs/round-{1,2,3}-refinement.md`
- Initial: `refine-logs/round-0-initial-proposal.md`

---

## Suggested Next Step
Per skill Phase 5 handoff: `/experiment-plan` converts FINAL_PROPOSAL into a detailed claim-driven experiment roadmap. In pipeline context: Task #5 (experiment-plan) → Task #6 (execute Loop 84+) → Task #7 (paper update).
