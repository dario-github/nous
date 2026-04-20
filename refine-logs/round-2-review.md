# Round 2 Review

**Reviewer**: Claude Opus 4.7 (independent subagent, different session from Round 1 reviewer)
**Date**: 2026-04-18
**Proposal reviewed**: `refine-logs/round-1-refinement.md` (Revised Proposal section)
**Previous review**: `refine-logs/round-1-review.md` (6.3/10, REVISE)

---

## Dimension Scores

| Dimension | Score | Δ from R1 | Notes |
|---|---|---|---|
| Problem Fidelity | 9/10 | +1 | Anchor verbatim; v3→v3-HN amendment honest, not drift. |
| Method Specificity | 7/10 | +1 | Schema/gate/discharge/sealed C spelled out; non-triviality still surface-level. |
| Contribution Quality | 6/10 | +1 | SPO lift real but thin — 6-seed + typed arities keeps "synthesis vs template-fill" ambiguous. |
| Frontier Leverage | 7/10 | +1 | Grammar-constrained decoding first-class; epistemic zero-training defense landed. |
| Feasibility | 7/10 | −1 | 8-week tight; CI reachability on 38H+13B blind slice borderline for 5pp gaps. |
| Validation Focus | 6/10 | 0 | KG-corruption + synthesis ablation improved; `no_synth`=6-seed menu is a weak-baseline trap; rule-level tracing missing. |
| Venue Readiness | 8/10 | +3 | Workshop-first honest, ICLR 2027 conditional correctly framed. |
| **OVERALL** | **6.95/10** | +0.65 | weighted ≈ 7.05 rounded down for residual Contribution risk. |

**Verdict**: **REVISE** (gap to READY = ~2 points; reviewer estimates "3–5 engineering days" closes it)

---

## Action-Item Verification (R1 actions)

| # | Action | Status | Evidence | Residual concern |
|---|---|---|---|---|
| 1 | A/B/C partition | RESOLVED | Changes §2; schema example tags `% A`, `% C`, `% A` | Class C independence is same-model-sealed-session; distinct prompt ID is weak separation. |
| 2 | Contribution lift | PARTIALLY RESOLVED | Changes §1; proposer output is CozoScript rule; gate = parse + type-check + non-triviality | Picked (a), but 6-seed + fixed arities makes synthesis close to template-completion. Non-triviality syntactic; no soundness theorem. Lift real but fragile. |
| 3 | KG-corruption | RESOLVED w/ caveat | Changes §4; KG-corrupted + KG-empty in Claim 2 | Bulk Class-A corruption; per-primitive tracing missing; rules chaining multiple Class A can mask which one matters. |
| 4 | Hard-negative slice | RESOLVED | Changes §5; v3-HN ≥100H+50B, complement-of-L1+L2+L4 | 70% author-constructed still self-authored; Risk 4 mitigation ("seed Inner-Circle cases where `is_inner_circle` decisive") is confirmation-biased construction. |
| 5 | Epistemic zero-training + SFT baseline | PARTIALLY RESOLVED | Changes §3; Training Plan | Defense present and correct; SFT not run; "we argue separation would degrade" speculation not evidence. |
| 6 | Venue commit | RESOLVED | Changes §7 | ICLR 2027 conditional on ≥5pp `no_synth` gain; Wilson CI half-width at n=13B is ±15pp — conditional may be unreachable on blind. |
| 7 | Blind ≥25% | RESOLVED on floor | Changes §6 | Sonnet 4.6 "blind" ≠ human blind; shares training-distribution biases with proposer. Floor 25%, not ceiling. |
| 8 | 12→6 taxonomy | RESOLVED | Changes §8 | None. |
| 9 | Delete proof_sketch | RESOLVED | Changes §9 | None. |
| 10 | Grammar-constrained decoding | RESOLVED | Changes §10 | `Cozo grammar file` doesn't exist off-the-shelf; engineering risk absorbed into W2. |

---

## Critical Weaknesses (< 7 dimensions)

### Contribution Quality — CRITICAL
- **Weakness**: Synthesis claim structurally fragile on three grounds:
  1. 6-seed few-shot + verbatim-match target ≤30% — explicit acknowledgement LLM leans on seeds; mitigation reactive, not structural.
  2. Typed fixed-arity primitive schema makes rule space bounded/enumerable (~12 primitives, small boolean algebra); "synthesis" ≈ "pick k primitives + boolean combinator."
  3. Non-triviality is **syntactic**: rejects `body := true`, admits `is_inner_circle(x), true_for_x := true` (vacuously discharging rule).
- **Fix**: Semantic non-triviality gate — run each rule twice (real inputs + adversarially perturbed primitive outputs); reject rules whose `discharged` is invariant to perturbation. ~20 lines code.

### Validation Focus — IMPORTANT
- **Weakness**: Two chained problems:
  - **`no_synth` = weak baseline**: 6-seed menu with typed schema is already a very strong L3 baseline. Beating it by 5pp measures "free composition > 6-template," a weaker claim than "synthesis > menu."
  - **KG-corruption bulk, not per-primitive**: rules chain Class A primitives; bulk shuffle can't attribute which one matters.
- **Fix**:
  1. `no_synth_menu_plus`: handwritten 12-rule expert menu (Dario + Yan) as strong-menu baseline.
  2. Per-primitive KG-corruption with rule-level discharge tracing in `proof_trace.binding_decisive_primitive`.

### Validation Focus (CI reachability) — IMPORTANT
- **Weakness**: v3-HN blind floor 25H+13B. Wilson CI half-width on n=25 at p=0.9 ≈ ±10pp; n=13 benign ≈ ±20pp FPR. ICLR 2027 conditional "≥5pp `no_synth` gain" on blind slice statistically unreachable.
- **Fix**: Either raise blind floor to 50H+25B (~3–4 days more subagent authoring), or split conditional ("≥10pp on full v3-HN + ≥5pp direction-consistent on blind").

---

## Simplification Opportunities
1. Delete `rule_id` from output (unused in verifier policy; hash of canonical rule body suffices).
2. Collapse KG-empty and KG-corrupted into one table row with two columns (they test same dimension).
3. Drop "semantic independence" as a named property (it's a defense, not a result).

## Modernization Opportunities
1. Commit to vendor structured-output as primary, Outlines as secondary (not both-as-equals).
2. Name specific grammar-constrained Datalog tool: **XGrammar + Lark EBNF + Cozo PEG export** is a concrete integration path.

## Drift Warning
**LATENT on two axes**:
- Class C drift (same-model sealed sub-oracle); sessions ≠ representation independence. Mitigations procedural not epistemic. Honest labeling load-bearing in writing.
- v3-HN author confirmation bias: Risk 4 mitigation admits seeding Class-A-decisive cases. Blind 25% is thin guard.

---

## New Action Items (Round 2 additions)

1. [CRITICAL] **Semantic non-triviality gate** — behavioral, not syntactic. Perturbation-sensitivity test on synthesized rule; reject invariants. ~1 engineering day.
2. [CRITICAL] **Per-primitive KG-corruption with rule-level tracing** — corrupt each Class A primitive in isolation; emit `binding_decisive_primitive` in proof_trace; per-primitive Wilson CI on TPR drop. ~3 days.
3. [IMPORTANT] **`no_synth_menu_plus` baseline** — 12-rule expert menu by Dario + Yan as stronger no-synth comparator. ~1 day authoring.
4. [IMPORTANT] **Blind floor raised to 50H+25B OR split ICLR conditional**. Choose; don't hedge.
5. [IMPORTANT] **Pre-register v3-HN with ≥10% negative-control cases** (cases where no Class A should matter; e.g., pure syntactic regex defeats) to show v3-HN is not solely Class-A-carries-weight by construction.
6. [MINOR] Delete `rule_id` (replaced by hash of canonical rule body).
7. [MINOR] Name one specific grammar integration path (**XGrammar + Lark + Cozo PEG**) and commit.

---

## Verdict
**REVISE**

Revision does real work on 8/10 R1 action items. Contribution lift (menu → synthesized rule) is right direction, novelty surface from 5 → 6. Method specificity + validation focus +1 each. Venue commit honest, taxonomy collapse clean. But two load-bearing pieces remain thin: (i) non-triviality syntactic — rule can pass while semantically vacuous; (ii) KG-corruption bulk — "KG load-bearing" weakly testable. Adding semantic non-triviality (1 day) + per-primitive corruption with tracing (3 days) pushes to 7.5+. **One focused revision away from READY for workshop, not ready today.**

---

## Raw Review (verbatim excerpts)

<details>
<summary>Full reviewer response</summary>

### Deep Critique (reviewer verbatim)

The revision is the right revision, but the contribution lift — Action 2 — is 70% done, not 100%. That gap is what the score reflects.

**The synthesis claim, stress-tested.** The author picked Action 2(a), program-synthesized obligations with a soundness-checking compiler. At runtime, the LLM now emits a CozoScript rule body, not a menu id. That is genuinely different from Round 0. But read the example at lines 216-222 adversarially: `?[discharged] := is_inner_circle(recipient_id), body_reveals_inner_relation(message_body, recipient_id, p_rev), owner_has_directed(action_id, is_directed), discharged = (not p_rev) or is_directed`. This is a conjunction of three primitive calls with a disjunctive head binding. The primitives are drawn from a declared schema with fixed arities; the head binding is a boolean over the primitive outputs. The *shape* of this rule is fully captured by the 6-seed library (seed 2 is exactly this pattern). What "synthesis" adds over "pick seed 2 and fill in `p_rev` / `is_directed` head logic" is: (i) the LLM can *compose* primitives from different seeds, (ii) the LLM can choose any boolean head, (iii) the LLM can omit or add a primitive. That is real flexibility. It is not Scallop-style rule synthesis with recursive relations and aggregates. It is Datalog-shaped template completion with a typed vocabulary. The paper's 40%-verbatim-match coverage monitor (line 267) implicitly concedes this — the author expects up to 40% of rules to be verbatim seed matches, and treats anything under 30% as success. That is an honest instrumentation, but it also shows the author knows the synthesis space is narrow.

The fix is cheap and I've flagged it: run semantic non-triviality as a behavioral test rather than a syntactic one. If the candidate rule `?[discharged] := is_inner_circle(x), true_for_x := true` passes the current gate (it syntactically references a Class A primitive, and `true_for_x := true` is not literally `discharged := true`), the gate has failed its job. Running the rule with the primitive outputs perturbed and rejecting invariant rules is an ~20-line check that converts "synthesis" from "any well-typed conjunction" to "conjunction whose output non-trivially depends on primitive content." Without this check, a reviewer can write a one-paragraph counterexample that shreds the gate.

**The KG-corruption ablation landed partially.** Bulk Class-A shuffle is defensible and better than the circular original. But per-primitive corruption with rule-level tracing is what actually answers "which KG facts are load-bearing for which decision." The author's own Risk 4 mitigation ("v3-HN construction seeds Inner-Circle-Leak-style cases where `is_inner_circle` is decisive") shows they know this: they are pre-loading the test set with cases where a specific Class A primitive is decisive, but the ablation does not isolate that primitive. The cleanest version is: for each synthesized rule that discharged, record which primitive's binding was decisive (i.e., which conjunct, if flipped, would have prevented discharge). Corrupt that primitive. Measure TPR drop on that subset. This is the causal ablation. The current "shuffle everything in Class A" is a population-level test that conflates primitives. At workshop scale, it might be enough; at ICLR main, a reviewer will ask for the per-primitive version.

**Class C is still the weakest epistemic claim.** Same model, distinct prompt id, sealed session. The author is honest: "Class C is not fully symbolic; defended on sealed independence + schema-bounded input + necessary expressivity." Good. But "sealed session" in practice means separate API call with a prompt that doesn't reference the proposer's reasoning. Representations are shared at model-weight level. The ≥30% divergence calibration test (line 323) measures whether the sub-oracle gives *different* answers to a rephrased question — it does not measure whether the sub-oracle is causally independent of the proposer's biases on the same input. For a workshop paper with Yan's honesty posture, this is enough. For ICLR 2027 main, a reviewer will want either (a) a different model (e.g., Qwen 3 for Class C, DeepSeek for proposer) or (b) a stronger independence test (e.g., calibration cases where proposer is known to be wrong — does sub-oracle *also* get wrong in the same direction?).

**The blind-authoring floor is the right idea, the floor is just low.** 25% blind = ~38H+13B minimum. Wilson CI half-width on n=13 at p=0.9 is roughly ±16pp (binomial). The ICLR 2027 conditional ("≥5pp `no_synth` gain") is almost certainly unreachable on the blind slice alone at that sample size. The author handled this by making the conditional about "LSVJ-S gain" in general, not specifically on blind slice — but a reviewer reading conditional + sample size carefully will notice the mismatch.

**The `no_synth` fallback to 6-seed menu is a weak-baseline trap.** 6 seeds of fixed-arity primitives with free composition is still a strong L3. The real question is "does synthesis beat a strong expert-curated menu." The paper doesn't test that. Adding a `no_synth_menu_plus` ablation with a 12-rule handwritten expert menu (which the author and Dario can build in a day, given the 6-seed library already exists) is the comparison that decides whether synthesis is a contribution or an implementation detail.

**The venue commit is honest and I commend it.** Workshop-first with ICLR 2027 main conditional on quantified success is the right frame. The hedging-in-proposal→hedging-in-paper trap is avoided. The risk is overclaiming the ICLR conditional is reachable — my concern there is only about statistical power, not about honesty.

**Honesty tax.** The author is being pretty honest throughout: 6-seed library declared non-contribution, Class C honestly labeled non-symbolic, verbatim-match coverage monitor, Mythos adversary explicitly out of scope, AgentDojo explicitly dropped in favor of ShieldAgent-Bench. This is commendable and rare. It also means the score cap for this revision is higher than a proposal with the same mechanism but more rhetorical cover — for ICLR main, a proposal like this will be judged on whether the mechanism actually does the work, not on whether the framing can survive a motivated attack. The gap between 6.95 and 7.5 is the semantic non-triviality gate + per-primitive KG corruption, both of which are ~3-5 engineering days. That is the cheapest path to READY.

Round 2 verdict is REVISE, not because the revision was cosmetic (it was substantive), but because the load-bearing pieces that were lifted (synthesis, KG-corruption) still have a thin adversarial surface. One more iteration, focused on those two, gets this to workshop-READY.

</details>
