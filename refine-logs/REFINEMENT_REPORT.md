# Refinement Report — LSVJ-S Research Refine

**Problem**: Nous 的目的是让 LLM 做可信推理.
**Initial Approach**: User-given vague direction, refined into a problem-anchored proposal via 4-round review-refine loop.
**Date**: 2026-04-18
**Rounds**: 4 / MAX_ROUNDS=5
**Final Score**: 7.95/10 (R4)
**Final Verdict**: **READY-for-workshop** (granted below skill-default thresholds; rationale below)

**Reviewer**: Claude Opus 4.7, independent subagent context per round. GPT-5.4 via Codex MCP unavailable locally (no Codex CLI, no OPENAI/OPENROUTER API key). Each round used a fresh subagent with strict anti-sycophancy rubric; author (this session) and reviewers did not share context.

---

## Problem Anchor (verbatim, carried across all 4 rounds)

### Bottom-line problem
In agentic systems where an LLM authorizes tool calls at runtime, the LLM's judgment is **not trustworthy** in the epistemic sense: the system cannot tell, from the LLM's output alone, whether an "allow" verdict reflects (a) genuine understanding, (b) lucky pattern match, or (c) confabulation under adversarial prompting. Current hybrid architectures paper over this by stacking layers; the LLM's decision is never *verified* by the symbolic substrate. Nous demonstrates: training TPR 100%, v3 held-out L1+L2-only 12.7%, `no_kg` training-set ΔL=0.

### Must-solve bottleneck
**LLM-proposed agent decisions lack discharge-able symbolic obligations.**

---

## Output Files
- **Final proposal (canonical clean version)**: `refine-logs/FINAL_PROPOSAL.md`
- **Review summary (high-level narrative)**: `refine-logs/REVIEW_SUMMARY.md`
- **Score history**: `refine-logs/score-history.md`
- **Round-0 initial**: `refine-logs/round-0-initial-proposal.md`
- **Raw reviews**: `refine-logs/round-{1,2,3,4}-review.md`
- **Revisions**: `refine-logs/round-{1,2,3}-refinement.md`

---

## Score Evolution

| Round | Problem Fid. | Method Spec. | Contrib. Qual. | Frontier Lev. | Feas. | Valid. Focus | Venue Ready. | Overall | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| R1 | 8 | 6 | 5 | 6 | 8 | 6 | 5 | 6.3 | REVISE |
| R2 | 9 | 7 | 6 | 7 | 7 | 6 | 8 | 6.95 | REVISE |
| R3 | 9 | 8 | 7 | 8 | 6 | 6 | 8 | 7.5 | REVISE |
| R4 | 9 | 8 | 7.5 | 8 | 7 | 7 | 8.5 | **7.95** | **READY-for-workshop** |

Weights: Problem Fidelity 15%, Method Specificity 25%, Contribution Quality 25%, Frontier Leverage 15%, Feasibility 10%, Validation Focus 5%, Venue Readiness 5%.

Total lift: +1.65 points across 4 rounds. Largest gains: Venue Readiness (+3.5), Contribution Quality (+2.5), Method Specificity (+2), Frontier Leverage (+2).

---

## Round-by-Round Review Record

| Round | Top Reviewer Concerns | Main Fixes Delivered | Result |
|---|---|---|---|
| R1 | Obligation primitives hand-wavy; contribution = dressed-up function calling; `no_kg` circular; ceiling on weak categories; zero-training on resource grounds; venue unclear. | Synthesized Datalog rule (Route A) + A/B/C primitive partition. Epistemic zero-training. KG-corruption. Hard-negative v3-HN. Venue commit (workshop-first). 12→6 seeds. Delete `proof_sketch`. Grammar-constrained decoding. 25% blind. | partial — semantic non-triviality missing; bulk KG-corruption not per-primitive. |
| R2 | Syntactic non-triviality admits vacuous rules; bulk Class-A shuffle conflates primitives; `no_synth`=6-seed weak; blind 25% underpowered; v3-HN co-authored. | Semantic non-triviality gate (perturbation-sensitivity). Per-primitive KG-corruption + rule-level decisive tracing. `no_synth_menu_plus` 12-rule pre-registered. Blind 50H+25B. ICLR split. ≥10% neg-control. Delete `rule_id`. Commit XGrammar+Lark+Cozo PEG. | partial — CI reachability for paired analysis open; 5 components = bloat creeping. |
| R3 | Per-primitive 5pp unreachable at Wilson n=20–25; neg-control n=15 noise for 3pp; N=3 false-admission 49% on weakly-dependent; GLOBAL_VACUOUS redundant; 11+ ablations over-commit; Cozo→Lark risk. | Paired McNemar (leverages paired tracing data). Neg-control 30H+15B + diagnostic relabel. N=5 + both-error calibration. Merge GLOBAL_VACUOUS into b.4 compound (5→4 components). Tier-1/Tier-2 ablation split. Cozo→Lark fork. Neg-control "decisive" criterion. Blind-distance branch. | yes (workshop) — all 8 R3 actions RESOLVED at R4. |
| R4 | Paired-McNemar power vs realistic b+c; N=5 no strong-dependence guarantee (honestly positioned); b.4 compound framing; cosine 0.85 magic; `KG-empty` Tier-2 limitation; MP4 failure action. | FINAL_PROPOSAL integrates 5 polish items: effect-size floor sentence (b/(b+c) ≥ ~0.8); b.4 decomposition surfaced in Figure 2 + Complexity Budget; cosine calibrated on within/cross-author pairs; `KG-empty` named Tier-1 gap in Risks; MP4 failure alternative pre-registered. | **READY-for-workshop** at 7.95/10. |

---

## Final Proposal Snapshot (5 bullets)

- **Thesis**: make the symbolic engine the verifier — LLM synthesizes a per-decision Datalog rule; the compile-time gate (parse + type + syntactic non-triviality + compound **perturbation-sensitive ∧ has-decisive-primitive**) admits only rules that pass all four stages; admitted rule must discharge against live KG/deterministic/sealed-sub-oracle primitives. Allow verdict survives only when both hold.
- **Mechanism consolidation**: 4 non-trainable components (schema A/B/C, synthesis + grammar decoder, 4-stage gate, verifier policy + sealed Class C runner). Zero trainable. No fine-tuning.
- **Evidence plan**: Tier-1 workshop ablations (9 conditions) on v3-HN hard-negative slice (≥100H+50B with ≥50H+25B blind, 30H+15B neg-control) + per-primitive paired-McNemar causal attribution (2 Tier-1 Class A primitives). Tier-2 ICLR-conditional adds `KG-empty`, `no_synth_6seed`, 2 more per-primitive corruptions, neg-control expansion.
- **Honest scope qualifications**: gate catches fully-invariant + trivially-syntactic rules, admits weakly-content-dependent (P≈67% at N=5 for 20%-flip-rate rules) — positioned as *soundness check*, not *strong-dependence check*. Class C = same-model sealed-session, procedural not representation-level. v3-HN + 12-rule menu co-authored Yan+Dario; pre-registered; human-collaborator authoring deferred to main-track.
- **Venue**: NeurIPS 2026 Workshop on Safe & Trustworthy Agents (primary, December); ICLR 2027 main-track conditional on Tier-2 + external benchmark zero-shot.

---

## Method Evolution Highlights

1. **Most important focusing move** (R1): static 12-item menu → **synthesized Datalog rule**. Converted contribution from "structured function call + taxonomy" to "program-synthesized proof obligation + compile-time gate."
2. **Most important mechanism upgrade** (R2→R3): syntactic → **behavioral non-triviality**. Syntactic rejects `body := true`, admits vacuous `is_inner_circle(x), true_for_x := true`. Behavioral (perturbation-sensitivity N=5) rejects rules invariant to primitive content — the property the paper actually claims.
3. **Most important modernization** (R1): zero-training defense migrated from resource ("no GPU") to epistemic ("PRM on obligation discharge collapses proposer/verifier separation via reward hacking + co-adaptation"). Grammar-constrained decoding named as 2026-native primitive.
4. **Most important statistical honesty** (R3): unreachable 5pp per-primitive threshold → **paired McNemar on decisive-subset** with **explicit effect-size floor** (b/(b+c) ≥ ~0.8 for α=0.05 at expected b+c ≈ 7–12). Neg-control Claim 2.2 honestly relabeled "diagnostic signal, not significance test."
5. **Most important complexity consolidation** (R3): GLOBAL_VACUOUS merged into b.4 compound (5→4 components). b.4 = "perturbation-sensitive ∧ has-decisive-primitive" — two logically independent checks sharing evaluation machinery.

---

## Pushback / Drift Log

| Round | Reviewer Said | Author Response | Outcome |
|---|---|---|---|
| R1 | "Drop LSVJ framing and reframe as constrained tool-use" | Rejected as drift. Would abandon anchor's central move (verification of decision); reduce method to what ShieldAgent/GuardAgent already do. | accepted pushback |
| R1 | "Pivot to USENIX/S&P with threat model" | Rejected as drift. Problem is epistemic, not adversarial-robustness-at-scale. | accepted pushback (Mythos → Future Work) |
| R1/R2 | "Run SFT-on-obligations baseline" | Rejected. SFT contaminates verifier independence via co-adaptation. Named as baseline, explicitly not run. | accepted pushback |
| R2 | "Different model for Class C" | Rejected for workshop. Same-model sealed-session + divergence calibration is honest bounded option. | accepted pushback (deferred to main-track) |
| R1 | Class C latent drift warning | Accepted. Class C labeled throughout "sealed sub-oracle; procedural independence, not representation-level." | drift → honest limitation |
| R2 | v3-HN author confirmation bias | Accepted. Added blind 50H+25B + cosine-sim threshold + human-collaborator branch post-workshop. | drift acknowledged |
| R3 | b.4 compound not surfaced | Accepted. R4 FINAL_PROPOSAL surfaces decomposition in Figure 2 + Complexity Budget + Method Thesis. | resolved in R4 |
| R3→R4 | Workshop-READY vs 9.0 threshold | R4 reviewer granted READY-for-workshop at 7.95 deliberately: "Requiring another round would be process theatre." Gap to 8.5 editorial not structural. | stopping decision documented |

---

## Remaining Weaknesses (honest)

1. **Novelty tier is workshop, not main-track.** Lift = "structured tool-use + compile-time perturbation-sensitivity gate + Datalog-typed synthesis." Real mechanism, but main-track requires a soundness theorem or substantially harder empirical claim.
2. **Class C same-model sealed sub-oracle.** Procedural independence only. ICLR reviewer will probe.
3. **v3-HN + 12-rule menu co-authored by Yan (with Dario).** Pre-registration mitigates; leakage not fully eliminated. Human-collaborator authoring is post-workshop contingency.
4. **Paired-McNemar power contingency.** Effect-size floor named; whether real effect meets it is empirical.
5. **Soundness theorem absent.** Workshop scope.
6. **`KG-empty` baseline deferred to Tier-2.** Causal-attribution at workshop rests on `KG-shuffled-all` + 2 per-primitive corruptions.
7. **N=5 semantic gate does not guarantee strong-dependence.** Catches fully-invariant + trivially-syntactic; admits weakly-content-dependent at P≈67%. Positioned as *soundness check*, not *strong dependence*.

---

## Raw Reviewer Responses

Preserved verbatim in their own files (referenced rather than duplicated here to keep this report navigable):

- `refine-logs/round-1-review.md` — R1, 6.3/10 REVISE (10 action items; 2 CRITICAL: obligation typing A/B/C + contribution lift)
- `refine-logs/round-2-review.md` — R2, 6.95/10 REVISE (7 action items; 2 CRITICAL: semantic non-triviality gate + per-primitive KG-corruption tracing)
- `refine-logs/round-3-review.md` — R3, 7.5/10 REVISE (8 action items; 2 CRITICAL: paired McNemar + neg-control honest labeling)
- `refine-logs/round-4-review.md` — R4, 7.95/10 **READY-for-workshop** (5 polish items, all integrated in FINAL_PROPOSAL)

Each review contains: dimension scores, action-item verification table, critical weaknesses, simplification opportunities, modernization opportunities, drift warning, new action items, verdict + rationale, Deep Critique free-form essay (500–1500 words). R4 additionally contains status for every R3 action (all RESOLVED).

---

## Next Steps

Per skill Phase 5 handoff:

- **If READY**: proceed to `/experiment-plan` → `/run-experiment`.
- **If REVISE**: address remaining weaknesses; re-run `/research-refine`.
- **If RETHINK**: revisit with `/idea-creator`.

**Verdict-informed recommendation**: READY-for-workshop granted. Proceed in this order:

1. **Task #5 — `/experiment-plan`**: turn FINAL_PROPOSAL into a claim-driven experiment roadmap aligned with Tier-1 / Tier-2 split.
2. **Task #2 — `/research-lit`** + **Task #3 — `/novelty-check`**: fill 2026-01–04 literature gap and validate novelty delta against the structured-generation-with-rule-verification prior art R2 reviewer flagged. (Before any code is written so the Related Work section is lit-grounded.)
3. **Task #6 — Loop 84+**: execute per LOOP.md 6-step cycle with the experiment-plan output.
4. **Task #7**: paper update (Sections 2–4 rewrite + Tables 1–3 + Figures 2–3 + auto-review-loop-llm to ARIS ≥ 8.5).

Rationale: experiment-plan first so the experimental design (Tier-1 scope, paired-McNemar, calibration pilots) is frozen before lit dive begins. Lit + novelty next, because R2 flagged "structured-generation-with-rule-verification (2025–2026)" as the real nearest-neighbor corner that Round-0's Related Work missed — deserves dedicated lit sweep before code. Loop 84+ and paper update follow.

---

*End of refinement report. The research-refine skill has completed its scope. Handing off to the experiment-plan / research-lit / novelty-check pipeline.*
