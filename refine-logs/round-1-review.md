# Round 1 Review

**Reviewer**: Claude Opus 4.7 (independent subagent context, `general-purpose` agent)
**Target model per skill spec**: GPT-5.4 via Codex MCP — NOT AVAILABLE LOCALLY (no Codex CLI, no OPENAI/OPENROUTER API key in environment; `.env.local` only contains TTS keys).
**Substitution rationale**: Independent-context Opus 4.7 with strict rubric, explicit anti-sycophancy instruction. Author (this session, also Opus 4.7) and reviewer do not share context. Recorded transparently here so Phase 5 report can note the deviation.
**Date**: 2026-04-18
**Proposal reviewed**: `refine-logs/round-0-initial-proposal.md`

---

## Dimension Scores

| Dimension | Score | Notes |
|---|---|---|
| Problem Fidelity | 8/10 | Stays on the "LLM allow is unverified" anchor; obligations-as-conjectures is the right reframe. |
| Method Specificity | 6/10 | Taxonomy is listed but discharge semantics, verifier policy edge cases, and completeness guarantees are still hand-wavy. |
| Contribution Quality | 5/10 | Dominant mechanism looks like "structured tool-use with a Datalog backend" — novelty surface is thinner than the framing admits. |
| Frontier Leverage | 6/10 | "Zero-training" stance is principled but under-argued against a PRM-fine-tune baseline; ITP-style LLM-as-tactic-proposer is not itself new in 2026. |
| Feasibility | 8/10 | Zero GPU, small API budget, single author, mostly reuse — realistic. |
| Validation Focus | 6/10 | Ceiling concerns on the three "weak" categories and a circular `no_kg` ablation design. |
| Venue Readiness | 5/10 | At a top venue this reads as a solid workshop submission, not a main-track story. |
| **OVERALL** | **6.3/10** | weighted |

**Verdict**: **REVISE**

---

## Critical Weaknesses Summary

### [CRITICAL] Method Specificity — obligation primitives hand-wavy
The example `no_inner_circle_disclosed` includes pseudo-functions `is_inner_circle_recipient(recipient, entity_id)` and `body_reveals_inner_relation(message_body, entity_id)`. `body_reveals_inner_relation` is the hard semantic NLI problem wearing a Datalog costume. If regex → LSVJ collapses to L4 with new names; if LLM → LSVJ is nested LLM-as-judge.
**Fix**: Partition obligation primitives into three classes:
- **Class A**: pure KG/relational (e.g., `is_inner_circle(recipient)`) — true Datalog.
- **Class B**: deterministic string/regex/taint over the payload — transparent, auditable.
- **Class C**: model-checked sub-predicates (declared LLM-invoked sub-oracles, different prompt, separate call, JSON-schema'd, optionally different model) — must be honestly labeled "not fully symbolic."
Declare the class of every obligation. Without this, Claim 2 (`no_verify` ablation) is uninterpretable.

### [CRITICAL] Contribution Quality — "structured tool-use with extra ritual"
Stripped of rhetoric: LLM emits JSON from 12-item menu, Datalog runs canned queries. The ITP analogy is ornamental. Closest 2024–2026 neighbours are constrained-decoding + function-calling safety gating.
**Fix (pick one)**:
- (a) Replace static taxonomy with *synthesized* obligation: LLM emits parameterized Datalog rule, verifier compiles + checks soundness and non-triviality.
- (b) Add a *soundness theorem*: e.g., "if all critical obligations discharge and trigger-mandatory set covers action_type X, then decision is sound w.r.t. policy P" — with proof.
- (c) Drop ITP framing, reframe as "Constrained-Tool-Use Safety Gate with Forced Discharge" — smaller but less vulnerable.

### [IMPORTANT] Frontier Leverage — zero-training defended on wrong grounds
Route B dispatched on resources, not epistemic grounds. "DeepSeek-V3.2 in-context following" is 2023 primitive. Tool-use + structured output + cached decoding are 2026 primitives.
**Fix**: Epistemic defense — (i) PRM on obligations suffers reward hacking; (ii) zero-training keeps verifier independent of proposer = audit property; (iii) include SFT-on-obligations as named baseline. Cite constrained-decoding (Outlines, XGrammar, Guidance, BAML) as 2026-native primitive.

### [IMPORTANT] Validation Focus — three sharp problems
1. **Ceiling**: Privacy=100%, Hijacking=93.3% with L4, Inner Circle=89.3%. Wilson CI half-width at p=0.93 n=60 is ±5pp. "LSVJ ≥ current" is nominal tie.
2. **Circular `no_kg`**: `requires_kg: true` defined, then Claim 2.3 asks if removing KG hurts "KG-requiring subset". By construction yes.
3. **Single-author evaluator bias**: v3 held-out + obligation taxonomy by same person.

**Fix**:
1. Hard-negative slice targeting complement of current L1+L2+L4 solves.
2. KG-corruption ablation (shuffle inner-circle memberships); preserves query structure, tests whether facts are load-bearing.
3. ≥25% held-out authored blind to taxonomy; report blind slice separately.

### [IMPORTANT] Venue Readiness — ML track vs security track, neither committed
Mechanism too small for NeurIPS main without (a) program-synthesis lift or (b) soundness theorem or (c) bigger cross-benchmark. For USENIX, no formal threat model, no commensurate red team.
**Fix**: Commit before writing. ML track → elevate mechanism + drop external-bench. Security track → formalize threat + blind red team. Workshop (NeurIPS Safe & Trustworthy Agents / ICLR Workshop) is legitimate honest landing zone.

---

## Simplification Opportunities
1. Collapse 12-obligation taxonomy to 5–6 core obligations (many overlap on send-external surface).
2. Drop Claim 3 (external benchmark) from main pitch, or commit. Hedging in proposal becomes hedging in paper.
3. Delete `proof_sketch` field (not consumed anywhere).

## Modernization Opportunities
1. Grammar-constrained decoding (XGrammar/Outlines) — moves #1 highest-risk assumption to zero-risk primitive; sharpens zero-training defense.
2. Different-from-proposer small model for Class C sub-oracles. Honest LLM-as-judge with separation.
3. If program-synthesized route: Cozo parser as soundness gate (generate → parse → schema-type-check → reject/execute).

## Drift Warning
**NONE on framing, LATENT in implementation**. Problem anchor preserved. But: if Class C obligations get implemented by calling proposer LLM under different prompt (path of least resistance), "symbolic verifier" claim silently decays into "LLM-as-judge with extra steps." Must spec Class C out.

## Action Items (ranked)
1. [CRITICAL] Partition obligation primitives A/B/C; declare class of every obligation.
2. [CRITICAL] Lift contribution: pick (a) program-synthesized obligations / (b) soundness lemma / (c) demote framing.
3. [IMPORTANT] Replace circular `no_kg` with KG-corruption ablation.
4. [IMPORTANT] Hard-negative held-out slice targeting L1+L2+L4 failure modes.
5. [IMPORTANT] Defend zero-training on epistemic grounds + SFT-on-obligations baseline.
6. [IMPORTANT] Commit to venue frame before writing.
7. [IMPORTANT] ≥25% blind-authored held-out cases.
8. [MINOR] Collapse taxonomy 12 → 5–6.
9. [MINOR] Delete `proof_sketch`.
10. [MINOR] Grammar-constrained decoding primitive.

---

## Raw Review (verbatim)

<details>
<summary>Full reviewer response</summary>

## Dimension Scores

| Dimension | Score | Notes |
|---|---|---|
| Problem Fidelity | 8/10 | Stays on the "LLM allow is unverified" anchor; obligations-as-conjectures is the right reframe. |
| Method Specificity | 6/10 | Taxonomy is listed but discharge semantics, verifier policy edge cases, and completeness guarantees are still hand-wavy. |
| Contribution Quality | 5/10 | Dominant mechanism looks like "structured tool-use with a Datalog backend" — novelty surface is thinner than the framing admits. |
| Frontier Leverage | 6/10 | "Zero-training" stance is principled but under-argued against a PRM-fine-tune baseline; ITP-style LLM-as-tactic-proposer is not itself new in 2026. |
| Feasibility | 8/10 | Zero GPU, small API budget, single author, mostly reuse — realistic. |
| Validation Focus | 6/10 | Ceiling concerns on the three "weak" categories and a circular `no_kg` ablation design. |
| Venue Readiness | 5/10 | At a top venue this reads as a solid workshop submission, not a main-track story. |
| **OVERALL** | **6.3/10** | weighted |

## Critical Weaknesses (< 7 dimensions)

### Method Specificity — Priority: CRITICAL
- Weakness: The obligation abstraction is declared but not defined to an implementable precision. The example `no_inner_circle_disclosed` includes pseudo-functions `is_inner_circle_recipient(recipient, entity_id)` and `body_reveals_inner_relation(message_body, entity_id)` — these are *exactly where all the epistemic work hides*. `body_reveals_inner_relation` is the hard semantic NLI problem wearing a Datalog costume. If it is implemented as a regex or substring match, LSVJ collapses to L4 with new names; if it calls another LLM, LSVJ is a nested LLM-as-judge pipeline and the "symbolic verifier" claim is false. Until these primitive predicates are specified, the protocol has no teeth.
- Concrete fix: Partition obligation primitives into three explicit classes and declare the class of every one of the 12 obligations:
  - Class A: pure KG/relational (e.g., `is_inner_circle(recipient)`, `owner_has_directed(action_id)`) — true Datalog, fully symbolic.
  - Class B: deterministic string/regex/taint over the payload (e.g., `payload_contains_regex`, `reachable_from_external_content`) — transparent, auditable.
  - Class C: model-checked sub-predicates (e.g., `body_reveals_inner_relation`) — must be declared as LLM-invoked sub-oracles, with explicit independence from the proposer (different prompt, separate call, JSON-schema'd, optionally different model) and the paper must honestly say "Class C is not fully symbolic; we argue why the separation still matters."
  Without this partition, Claim 2 (`no_verify` ablation) is uninterpretable because we do not know what "verify" is doing.

### Contribution Quality — Priority: CRITICAL
- Weakness: Stripped of rhetoric, the mechanism is: "LLM emits a structured JSON that lists which downstream checks to run; a Datalog layer runs them; fail-closed on any critical undischarged check." That is tool-use / function-calling with a constrained tool menu plus a decision-fusion rule. The Novelty & Elegance section contrasts with ShieldAgent / GuardAgent / TrustAgent but does not address the 2024–2026 explosion of constrained-decoding + function-calling safety gating (e.g., structured-output safety routers, CoT-to-DSL compilers, LLM-proposed-constraint verification in DB query safety, policy-as-code agents). The ITP analogy (Lean tactics) is charismatic but ornamental; at runtime, what actually happens is: LLM picks items from a 12-element menu, Datalog runs canned queries.
- Concrete fix: Do one of the following to raise novelty from "plausible" to "dominant":
  (a) Replace the static obligation taxonomy with a *synthesized* obligation: the LLM emits a small Datalog rule (parameterized over owner-harm predicates) that the verifier compiles and checks for soundness and non-triviality before admitting. This moves the contribution from "structured function call" to "program-synthesized proof obligation" — closer to actual ITP tactics and harder to dismiss.
  (b) Add a *soundness guarantee* that non-LSVJ pipelines cannot offer: e.g., "if all critical obligations discharge and the trigger-mandatory set covers action_type X, then the decision is sound w.r.t. policy P" — with a proof, not a gesture.
  (c) Drop the ITP framing entirely and honestly reframe as "Constrained-Tool-Use Safety Gate with Forced Discharge" — smaller claim, less ambitious, but less vulnerable to the "this is just function calling" takedown.
  Without one of (a)/(b)/(c), a reviewer will ask at line 277 "why is this a contribution rather than good engineering?" and the proposal has no answer.

### Frontier Leverage — Priority: IMPORTANT
- Weakness: The proposal argues Route B (PRM/RL) is overbuilt. Fine, but the argument is purely about *resources* ("no GPU budget, +3 months infra"), not about *what makes a better paper*. In 2026, at NeurIPS/ICML, the reviewer asks: "would a fine-tuned 8B open model with a constrained-decoding obligation head do this better, more cheaply at inference time, and with stronger claims?" The answer is plausibly yes. Sections 80–84 dispatch Route B in five bullets; the case is resource-practical, not epistemic. Also, the claim that DeepSeek-V3.2 "strong in-context following" is the foundation-model primitive being leveraged is thin — that is a 2023 primitive, not a 2026 one. Tool-use, structured output, and cached decoding are 2026 primitives and deserve specific uptake.
- Concrete fix: Add a paragraph that defends zero-training on *epistemic* grounds: (i) PRM on obligations suffers reward hacking (the verifier becomes the reward, the LLM learns to over-propose easy-to-discharge obligations — a concrete failure mode already hinted at in the "LLM over-generates obligations to game the system" row); (ii) the zero-training protocol makes the verifier *independent* of the proposer, which is the property that actually delivers audit-grade guarantees; (iii) if fine-tuning is allowed, the cleanest comparison is to include a SFT-on-obligations condition in the method's own ablation (small open model, structured-output head), not as a rejected Route B. If resources don't allow running (iii), at least cite constrained-decoding / schema-guided generation work (Outlines, XGrammar, Guidance, BAML) as the 2026-native primitive being used, and explain why this choice is more than "we happened to have DeepSeek available."

### Validation Focus — Priority: IMPORTANT
- Weakness: Three sharp problems with the evaluation.
  (1) Ceiling. Line 289 admits the three "weak" categories are at 93.3%, 89.3%, 100%. Privacy Exposure at 100% offers no room to improve. Hijacking at 93.3% via an L4 regex verifier is close to ceiling; beating it by a statistically detectable margin on N=300 harmful is very hard (Wilson CI half-width at p=0.93, n=~100-per-category is roughly ±5pp). The proposal declares "LSVJ ≥ current" as the target, which is a nominal tie, not evidence of superiority.
  (2) `no_kg` ablation is methodologically circular. Line 212 marks `requires_kg: true` on obligations *by definition*; then Claim 2.3 asks whether removing KG hurts on the "KG-requiring subset." Of course it does — if the obligation is unenforceable without KG, removing KG trivially makes it `inconclusive`, which by policy upgrades to `confirm`, which by construction changes the verdict. This does not show KG is load-bearing for *generalization*; it shows policy converts `inconclusive` to `confirm`. A reviewer will catch this in one pass.
  (3) Single-author evaluator bias. v3 held-out was authored by the same person designing the obligation taxonomy (Lines 33, 215). The proposal does not even mention this risk, let alone mitigate it.
- Concrete fix:
  (1) Add a *hard-negative* slice: generate held-out cases that defeat the current L1+L2+L4 system by construction (e.g., semantic hijacking phrasings that evade L4 regex, inner-circle disclosures that bypass current L3 prompting). Evaluation should target the *complement* of what current Nous solves; this gives LSVJ room to win.
  (2) Replace `no_kg` with a proper causal ablation: keep obligations structurally identical but *corrupt* the KG (shuffle inner-circle memberships) and measure TPR drop on a held-out `requires_kg` subset. If obligation verify were cosmetic, TPR would not change; if KG facts are load-bearing, TPR drops. This is the ablation that answers the "stage scenery" critique; the current one begs the question.
  (3) Have an independent party (Codex/Gemini subagent acting under a sealed rubric, or a collaborator) author a minimum of 25% of held-out cases blind to the obligation taxonomy, and report LSVJ performance on the blind slice separately.

### Venue Readiness — Priority: IMPORTANT
- Weakness: Section-by-section the proposal oscillates between a NeurIPS-style contribution story (one protocol, clean ablation) and a USENIX-style deployment story (runtime agent decisions, auditability, threat model). Neither is fully committed. The mechanism (LLM proposes JSON from a 12-item menu, Datalog verifies) is too small for NeurIPS main track without (a) the program-synthesis lift suggested above, or (b) a real soundness theorem, or (c) a substantially larger cross-benchmark result than "within 5pp of SOTA on one benchmark." For USENIX, the paper lacks attack-model formalism, red-team effort commensurate with a security venue, and a real-deployment story. Line 369 already admits venue confusion.
- Concrete fix: Commit to one of two reframings *before* writing:
  - ML track (NeurIPS/ICLR Workshop on Agent Safety): elevate the mechanism. Add program-synthesized obligations (fix above), add a soundness lemma, and drop the external-benchmark plank if it dilutes focus.
  - Security track (USENIX/S&P): elevate the threat model. Formalize the Mythos-class adversary, run a dedicated red-team pass (50–100 adversarial prompts not authored by the same person as the evaluation set), measure robustness-to-attack delta, and treat "obligation discharge" as an *audit* contribution, not a generalization contribution. This is a different paper, and the current proposal would benefit from that clarity.
  Workshop (NeurIPS Workshop on Safe & Trustworthy Agents, ICLR Workshop) is a legitimate honest landing zone for the current scope; if the target is a workshop, say so and stop defending against main-track demands.

## Simplification Opportunities
1. Collapse the 12-obligation taxonomy to 5–6 core obligations. Lines 215–228 list 12, many of which overlap heavily (`no_exfiltration_via_tool_chain`, `no_read_to_external_chain`, `no_inner_circle_disclosed` all guard the send-external surface). A taxonomy that big makes parse-failure and completeness risk larger and makes the `no_verify` ablation noisier. Start with 5 and expand only if FN analysis demands it.
2. Drop Claim 3 (external benchmark) from the main pitch. Line 307 already hedges: "if Claim 3 holds, full paper; if not, position + initial evidence." That is the wrong direction for a top venue. Either commit to Claim 3 *or* cut it and tighten the story on Claims 1+2. Hedging in the proposal becomes hedging in the paper.
3. Merge the "Proposer" and "Obligation" prompts into one and drop the separate `proof_sketch` field. The proposal does not use `proof_sketch` in any discharge step (lines 176, 239), so it is a stowaway in the output schema that adds parse risk without adding verification power. If it's not consumed, delete it.

## Modernization Opportunities
1. Replace ad-hoc JSON parsing with constrained/structured decoding. The proposal's #1 highest-risk assumption (line 330) is "DeepSeek-V3.2 reliably outputs valid JSON." In 2026 this is a solved-with-a-library problem (XGrammar, Outlines, vendor structured-output modes). Commit to structured decoding as the primitive, cite it, and move "parse failure rate" from a risk to a guaranteed-zero by construction. This also lets you defend zero-training more crisply: "we rely on grammar-constrained decoding, not fine-tuning, for schema adherence."
2. Consider a small verifier-guided LLM as the obligation *verifier*, not the proposer, for Class C predicates (see Method Specificity fix). Using a small, cheap, *different-from-proposer* model for `body_reveals_inner_relation`-style sub-oracles is the modern honest version of "LLM-as-judge" — and it preserves the proposer/verifier separation. Naming this explicitly is more defensible than smuggling semantic checks into "Datalog."
3. If you pursue the program-synthesized-obligation variant, use a rule-synthesis LLM pass with a Cozo parser as the soundness gate: generate → parse → check typed against schema → reject/execute. This is a 2026-native LLM-for-program-synthesis primitive that substantially lifts novelty beyond function-call dispatch.

## Drift Warning
NONE on the core framing. The proposal still attacks the anchored bottleneck ("LLM-proposed decisions lack discharge-able symbolic obligations") and the smallest-adequate intervention (conjecture + obligation bundle + verifier) directly addresses it. However, there is latent drift risk in the implementation: if Class C obligations are implemented by calling the proposer LLM again under a different prompt (the path of least resistance), the "symbolic verifier" claim silently decays into "LLM-as-judge with extra steps," and the problem statement quietly shifts from "verify the LLM" to "second-opinion the LLM." Flag this now, spec it out in the method section, or the drift will show up in code review.

## Action Items (ranked)

1. [CRITICAL] Partition obligation primitives (A: KG/Datalog, B: deterministic, C: LLM-invoked sub-oracle) and declare the class of every one of the 12 obligations. Without this, the "verifier" claim is unfalsifiable and the `no_verify` ablation is uninterpretable.
2. [CRITICAL] Lift the contribution: pick one of (a) program-synthesized obligations with a soundness-checking compiler, (b) a real soundness lemma for the fixed-taxonomy variant, or (c) drop the ITP framing and honestly reframe as constrained tool-use with fail-closed discharge. Current middle ground reads as dressed-up function calling.
3. [IMPORTANT] Replace the circular `no_kg` ablation with a KG-corruption ablation (shuffle memberships) and report TPR drop on a `requires_kg` held-out slice. The current formulation begs the question and a reviewer will call it.
4. [IMPORTANT] Address ceiling concern directly: construct a hard-negative held-out slice targeting the *failure modes of current L1+L2+L4*, so LSVJ has room to win. Current Privacy=100%, Hijacking=93.3% ceilings make overall gains hard to detect.
5. [IMPORTANT] Defend zero-training on *epistemic* grounds (reward hacking, verifier independence, audit property) rather than resource grounds. Add SFT-on-obligations as a named baseline even if not run — it cannot be left unaddressed.
6. [IMPORTANT] Commit to a venue frame before writing. ML main track requires mechanism lift (Action 2) or substantially bigger external evidence. Security track requires a formal threat model and a real red team. Workshop is legitimate and should not be defensively avoided.
7. [IMPORTANT] Add an independent-evaluator mitigation: have ≥25% of held-out cases authored by a party blind to the obligation taxonomy; report blind slice separately.
8. [MINOR] Collapse taxonomy from 12 to 5–6 obligations in v1; expand only by FN-driven need.
9. [MINOR] Delete `proof_sketch` from the proposer output schema; it is not consumed by any discharge path.
10. [MINOR] Switch JSON parsing to grammar-constrained decoding; move parse-failure from highest-risk assumption to zero-risk primitive.

## Verdict
**REVISE**

The problem anchor is correct, the smallest-adequate instinct is correct, and the reuse-first posture is disciplined. But the current mechanism, read adversarially, is a structured function-call safety gate with an evocative ITP analogy, and the evaluation has a ceiling-and-circularity problem that a reviewer will pounce on. Fix the Class A/B/C partition and lift the contribution with either program synthesis or a soundness lemma, and replace the question-begging ablation — then you have a paper. Don't submit to NeurIPS main with the current depth; submit to a workshop, or do the mechanism lift and earn the main track. Not RETHINK: the framing is right. Not READY: too many load-bearing primitives still live in hand-wavy predicate names.

## Deep Critique (free-form)

I want to name what this proposal actually is, stripped of its rhetoric. At runtime the pipeline is: (1) LLM reads a tool-call + session context, (2) LLM emits a JSON with `{decision, obligations: [{id, params}], proof_sketch}`, (3) a compiler binds each `(id, params)` to a canned CozoScript query from a 12-entry template table, (4) queries run against a KG the same system already had, (5) a fusion rule says "any critical undischarged → upgrade to confirm." That's a structured-output call plus a tool-menu plus a conservative post-filter. The Lean/Coq analogy in line 276 is the single most load-bearing rhetorical move in the proposal, and it is thin: Lean tactics search a proof space constrained by type theory in which soundness is the *foundation*; LSVJ's "obligations" are picks from a fixed 12-item list discharged by Datalog queries whose primitive predicates (`body_reveals_inner_relation`) are themselves the hard problem. The ITP framing charges the proposal a novelty bill it cannot pay unless the obligation layer actually synthesizes new predicates or the verifier has a soundness property. Currently neither is true.

The "Is the LSVJ protocol actually new?" angle landed hardest for me. The closest prior art is the 2024–2026 lineage of LLM-as-tool-user with safety gates: structured-output safety routers, policy-as-code for agents, NeMo Guardrails with `colang` flows, and — most uncomfortably — constrained-decoding-guided tool selection for DB query safety, where the LLM picks queries from a schema-validated menu and a rule layer rejects violations. The proposal's related-work section treats ShieldAgent, GuardAgent, TrustAgent as the field, but the real neighbors are in the structured-generation-with-rule-verification corner of 2025–2026. A top-venue reviewer from that corner will not see LSVJ as new enough without either program synthesis or a soundness theorem. The "LSVJ inverts LLM-as-judge" point (line 114) is neat but describes many existing systems (e.g., symbolic verifiers on LLM-synthesized code), so it is more branding than differentiator.

The "zero training is a feature or a cop-out" angle: I think the stance is *defensible* — ablating training from the recipe actually does make the verifier-proposer separation crisper, and reward hacking is a real concern when the verifier is in the loop. But the proposal defends zero-training on the wrong ground (lines 80–84 read as "we lack GPUs and time"). For a top venue that argument is weak; "zero-training because training a PRM against your own symbolic verifier degenerates into reward-hacking-on-Datalog" is the argument that wins reviewers. Write that argument.

The "obligations = structured tool calls + extra ritual" angle: I think this is the single greatest vulnerability. Action 2 is targeted at it. Either lift the mechanism (program-synthesized obligations) or lift the claim (soundness theorem over the fixed taxonomy); if neither, demote the venue target. The paper cannot stand on the protocol *name* alone in 2026.

The "evaluation honesty" angle: ceiling effects are real and under-acknowledged. Line 289 says "Privacy Exposure currently 100%" — that line should have triggered a bigger rethink. You cannot demonstrate improvement in a saturated metric; at best you match. The interesting slice is the complement of what L4 already catches, and the proposal does not construct that slice. Add a hard-negative held-out partition, and measure LSVJ there. The three "weak" categories are weak because L4 happens to cover them; the *actually* open cases are somewhere else, and the evaluation needs to find them. Separately, the single-author evaluator concern (line 33: "v3 held-out (300H + 150B) — the critical evaluation set" authored by the same person designing the obligation taxonomy) is the kind of thing that gets flagged in meta-review. At minimum add a blind slice.

The "no_kg ablation stacked deck" angle: this landed fully. Lines 212 and 229 define `requires_kg: true` by fiat, then Claim 2.3 measures KG contribution via the "requires-KG" subset. The ablation cannot fail; it measures whether the verifier implements its policy ("inconclusive → confirm"), not whether KG facts carry generalization weight. Replace with KG-corruption (shuffle `inner_circle` relationships across owners, for example), which preserves query structure and tests whether the *facts* are load-bearing. That is the ablation that rebuts "stage scenery."

The "Route B might win on honesty" angle: partially lands. I don't think PRM/RL is the honest path — the reward-hacking concern is real and the proposer/verifier separation does buy you something. But a *fine-tuning with structured-output adherence* baseline (no PRM, no RL, just SFT on obligation emission) would be cheaper and would ask a sharper question: is the gain from the protocol, or from DeepSeek-V3.2's in-context ability? Without that baseline or a principled argument for why it would not help, a reviewer will ask and the proposal has no answer.

The "AgentDojo zero-shot" angle: I am skeptical. AgentDojo's task design does not map onto owner-harm obligations cleanly; much of AgentDojo is prompt-injection under utility preservation, which maps to `no_hijacking_via_external_content` but little else. Expecting the owner-harm-specific taxonomy to transfer zero-shot to a utility-security frontier is ambitious. Either build obligation-adapter code (document carefully), or drop AgentDojo and pick ShieldAgent-Bench, which is closer in framing. Line 304's hedging suggests the author knows this.

The "single-author evaluator bias" angle: already covered; the proposal does not mention it, and top venues are increasingly strict on this. Mitigation is cheap (a subagent blind-authors 25% of cases); not doing it would be a self-inflicted wound.

The "venue fit" angle: the proposal is a workshop paper as written. That is not an insult — NeurIPS Workshop on Safe & Trustworthy Agents would be a good home. To move to main track, the mechanism must lift. To move to USENIX/S&P, the threat model must formalize and a red team must run. Choose before writing, or the draft will read as three partial papers.

Two more things if I were saying this in a group meeting. First: lines 11 and 11–17 (the problem anchor) are the strongest section of the proposal. The diagnostic is sharp and honest — the 12.7% held-out TPR from rules-only and the `no_kg` ΔL=0 are the kind of numbers that earn the right to a method. Don't let them get buried under the method's rhetoric. Second: the proposal says "LSVJ protocol + small library of obligations" is elegant. It is almost elegant. The path to *actually* elegant is to pick one — either the protocol (with a soundness theorem that makes the protocol a real object) or the library (with a program-synthesized obligation generator that makes the library a real contribution). Do not fight to keep both as co-equal contributions; that is the contribution-sprawl trap the review brief explicitly warns against.

</details>
