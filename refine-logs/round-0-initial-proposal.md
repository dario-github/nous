# Research Proposal: LSVJ — LLM-Proposed, Symbolically-Verified Judgments for Trustworthy Agent Decisions

> Round 0 Initial Proposal. Date: 2026-04-18. Author: Yan (for Dongcheng Zhang / Nous project).
> Problem handed down: "Nous 的目的是让 LLM 做可信推理" — turn into a problem-anchored, elegant, frontier-aware research proposal.

---

## Problem Anchor (IMMUTABLE — copy verbatim to every round)

### Bottom-line problem
In agentic systems where an LLM authorizes tool calls at runtime, the LLM's judgment is **not trustworthy** in the epistemic sense: the system cannot tell, from the LLM's output alone, whether an "allow" verdict reflects (a) genuine understanding of the action, (b) lucky pattern match on surface features, or (c) confabulation produced under adversarial prompting. Current hybrid architectures (LLM classifier + rule layer + knowledge graph) paper over this by stacking layers, but the LLM's decision is never *verified* by the symbolic substrate — the symbolic parts merely run alongside or feed context. Concretely, Nous demonstrates this pathology: training-set TPR 100% (Loop 74, 200H+50B), v3 held-out L1+L2-only TPR **12.7%** with L3 LLM adding +62.6pp, but the `no_kg` ablation on training set shows ΔL=0 — meaning KG is not carrying the generalization weight and the LLM's gains on held-out are not symbolically grounded.

### Must-solve bottleneck
**LLM-proposed agent decisions lack discharge-able symbolic obligations.** A decision of "allow" should be a *conjecture* that the symbolic engine is obligated to *verify* by discharging a structured set of proof obligations; today it is an opaque label. Without this, three failures follow:
1. Held-out vs training gap cannot be distinguished from lucky pattern match.
2. Adversarial prompts (Mythos-class) exploit the LLM's unverified trust surface.
3. Decisions are not auditable in a way that answers "why was this allowed?" with a symbolic trace.

### Non-goals
- **Not** "make LLM more accurate." RLHF/DPO/PRM training is a different paradigm and out of scope.
- **Not** "replace LLM with rules." Held-out 12.7% rules-only proves this insufficient.
- **Not** "build another LLM safety classifier" (Llama Guard, ShieldGemma, QuadSentinel already saturate that lane).
- **Not** "reinvent a symbolic reasoner" (Cozo/Datalog/SAT/SMT exist).
- **Not** "universal LLM trustworthy reasoning" for all tasks — scope is **runtime agent decisions** (tool-call authorization). Math/code proof verification is a related but separate problem.
- **Not** "formal verification for the whole system" — LSVJ discharges per-decision obligations, not global invariants.

### Constraints
- **Infrastructure frozen**: Cozo embedded DB, Datalog engine (TypeScript port) + YAML constraint layer, DeepSeek-V3.2 as production L3 LLM, GPT-5.4 as judge, existing `proof_trace.py` / `markov_blanket.py` / 46 constraint files.
- **Data**: owner-harm v3 held-out (300H + 150B) — the critical evaluation set; AgentHarm (176+176); plan to add one external benchmark (AgentDojo or ShieldAgent-Bench) zero-shot.
- **Compute budget**: Single author + small Swarm (Codex/Gemini for review). API cost per full held-out eval ≈ $5–$20. No GPU training budget.
- **Time**: Dario has released schedule — arXiv-first, no deadline pressure. Quality > speed.
- **Authorship/venue**: Dongcheng Zhang (BlueFocus), target a top safety / agents venue (NeurIPS / ICML / ICLR Workshop on Agent Safety / USENIX Security). CRAI 2026 position already submitted; this is v2.
- **Existing paper**: `paper/main.tex` currently titled "Compositional Runtime Safety Gates for Agentic AI: Empirical Evidence for Layer Complementarity." LSVJ will either subsume or replace the current framing depending on Phase 3 evidence.
- **Project philosophy (Dario)**: "Owner-harm only, no social-harm politics." Evaluation framed around owner-centric threat model (compromise of owner's credentials / privacy / infrastructure / autonomy).

### Success condition
Dongcheng will say "yes, this is trustworthy reasoning, not dressed-up pattern matching" iff **all four** hold:

1. **Held-out improvement is real**: On v3 held-out (300H+150B), LSVJ beats the current Nous architecture (L1–L4) by a statistically significant margin on the three weak categories (Hijacking, Inner Circle Leak, Privacy Exposure), with tight Wilson CIs.
2. **Gain is mechanism-level, not decoration**: Ablating obligations (LLM outputs decision without obligations → treated as normal semantic gate) restores the old performance, while ablating verify (obligations collected but not discharged) is equivalent to no obligations. I.e., the *verify step* carries the gain, not the *prompt shape*.
3. **KG contributes measurably**: `no_kg` ablation on v3 held-out shows a non-zero ΔL for obligation types that *require* KG facts (e.g., `no_inner_circle_disclosed` requires KG to know who is inner circle). This closes GPT-5.4's "KG is stage scenery" objection with data, not rhetoric.
4. **Zero-shot transfer is defensible**: On one external benchmark (AgentDojo or ShieldAgent-Bench) with no tuning, LSVJ is within competitive range of specialized baselines, demonstrating the paradigm generalizes beyond Nous's own benchmark.

If any of 1–4 fails, the proposal must be revised or rejected, **not** reframed to hide the failure.

---

## Technical Gap

### Where current methods fail

**Monolithic LLM classifiers** (Llama Guard, ShieldGemma, QuadSentinel 2025). Fast to deploy, semantically capable, but the output is a single label. No obligations, no audit trail at the symbolic level, no way for a downstream system to say "I reject the LLM's allow because obligation X is undischarged." QuadSentinel (Dec 2025) achieves R=85.2% on AgentHarm but still presents a monolithic opaque verdict.

**Rule-only systems** (NeMo Guardrails, classic policy engines). Auditable and deterministic, but Nous's own v3 held-out proves rules-only gives 12.7% TPR — semantic intent cannot be captured in forward-chaining rules alone.

**Hybrid stacking** (Nous v1, ShieldAgent ICML 2025, GuardAgent 2025, TrustAgent 2024). LLM and symbolic engine both run, but on **parallel tracks**, not in a verifier relationship. ShieldAgent's "probabilistic rule circuits + formal verification" verifies the *rules*, not the LLM's per-decision claims. TrustAgent's "post-planning safety check" is rule-based re-validation, which is symmetric to the LLM decision rather than dependent on it. GuardAgent's "plan-then-code + I/O audit" audits the I/O, not the decision's evidential basis. The KG in Nous v1 is an enrichment substrate — it feeds LLM context but never contradicts the LLM verdict; Nous's own early ablation (Loop 33, 2026-03-17) showed KG injection into the semantic prompt degraded TPR by 12%, so the current architecture routes KG post-gate where it is structurally unable to reject a bad allow.

**Neurosymbolic learning** (Scallop PLDI 2023, Lobster ASPLOS 2026). Differentiable Datalog with semiring provenance — a powerful substrate. But the target domain is offline learning of symbolic programs from data (e.g., visual QA, program synthesis). Not designed for *runtime* agent decision verification.

**Process reward + reasoning traces** (OpenAI o1, DeepSeek-R1, Claude 3.5 Sonnet thinking modes, 2024–2026). Makes LLM reasoning traces *visible* but not *mechanically verifiable*. A chain-of-thought can still confabulate; the visibility gives humans a debugging surface, not a formal discharge procedure.

### Why naive fixes are insufficient

- **"More training data"**: Nous already iterated 74 loops on training set → 100% TPR; v3 held-out still 75.3% (gate only). Training-set saturation is the diagnosis, not the solution.
- **"Stronger LLM"**: QuadSentinel uses strong models and still caps at 85.2% recall on AgentHarm. GPT-4/Claude adversarial robustness studies consistently show <90% on targeted red teams.
- **"More rules"**: Hijacking on v3 held-out is 43.3% gate, 93.3% with L4 Verifier — but L4 is regex / pattern, not symbolic reasoning. Adding more regexes fights yesterday's attacks.
- **"Put KG in prompt"**: Already tried (Loop 33). -12% TPR due to attention dilution. Context injection is not the architectural answer.
- **"Chain-of-thought with self-consistency"**: Still confabulation; majority-vote-3 reduces stochastic FPR but doesn't introduce external verification.

### Smallest adequate intervention

**Change the LLM's output type from a label to a conjecture + proof-obligation bundle; make the symbolic engine the verifier that discharges or rejects.**

The LLM produces `{decision, obligations, proof_sketch}`. The symbolic engine (Cozo Datalog + KG) compiles each obligation into a query and returns `discharged` or `undischarged`. An allow decision is upgraded to `confirm` or `block` when any critical obligation is undischarged. This is the minimum change that:
- Reuses all existing infrastructure (LLM, Cozo, Datalog, proof_trace).
- Does not require any training or new models.
- Makes symbolic engine participation non-optional for allow decisions.
- Produces auditable traces at the obligation level.

### Frontier-native alternative (considered, rejected for smallest-adequate)

**Route B — Verifier-Guided PRM**: train a process reward model that scores each obligation at discharge time, use RL to fine-tune the LLM to produce obligations the verifier accepts. Modern, uses reasoning-model + PRM paradigm, but: (i) requires GPU training budget we do not have, (ii) creates a new trained component whose failure mode is opaque (reward hacking), (iii) couples the method to specific model weights rather than working with frozen DeepSeek-V3.2, (iv) adds >3 months of infrastructure work. Keep as Future Work.

**Decision**: Route A (LSVJ, zero-training obligation protocol) is the smallest adequate mechanism. Route B is future scaling.

### Core technical claim (what must survive top-venue scrutiny)

> An interactive-theorem-proving-inspired protocol — where the LLM proposes an agent decision together with a structured set of discharge-able symbolic obligations, and a Datalog + KG verifier is authorized to reject the decision on any undischarged critical obligation — produces held-out generalization gains that are (i) statistically significant, (ii) mechanism-level (ablation separates obligation-verify from prompt-shape), and (iii) partially attributable to KG facts (so KG is no longer stage scenery).

### Required evidence (minimum to defend the claim)

1. v3 held-out (300H+150B) comparison: LSVJ vs current Nous L1–L4 vs LLM-only vs rules-only, per-category, with Wilson 95% CIs.
2. LSVJ internal ablation: `no_obligation` / `no_verify` / `no_kg` / full. Each condition must yield a clean interpretation.
3. One external benchmark (AgentDojo preferred — hardest, NeurIPS 2024 — or ShieldAgent-Bench if AgentDojo infrastructure cost is prohibitive), zero-shot.
4. Qualitative proof traces on 5–10 held-out cases demonstrating how verify rejects an LLM confabulated allow.
5. Cost/latency overhead: LSVJ adds ≤ +200ms and ≤ +1 LLM call per ambiguous decision.

---

## Method Thesis

### One-sentence thesis
Treat the LLM's agent decision as a conjecture bundled with structured symbolic proof obligations; treat the Datalog+KG engine as a verifier authorized to reject the decision on any undischarged critical obligation; the allow verdict survives only when every critical obligation is mechanically discharged.

### Why this is the smallest adequate intervention
- Reuses: DeepSeek-V3.2 (no fine-tuning), Cozo Datalog, existing 46 constraints, `proof_trace.py`, existing `markov_blanket.py` retrieval.
- Adds: one JSON schema, one compiler (obligation → Cozo query), one verifier policy (discharge rules), ~10–15 obligation types for owner-harm.
- Does not touch: L1 Datalog constraints, L2 triviality filter, L4 Post-Gate Verifier, benchmark infrastructure, loop harness, paper's layer-complementarity evidence.
- Removes: the assumption that the LLM's allow is self-standing.

### Why this route is timely in the foundation-model era
- 2024–2026 reasoning models (o1, R1, Sonnet-thinking) made reasoning traces *visible* but not *verifiable*. LSVJ closes the verification gap without requiring the LLM to be a reasoning model.
- 2026 agent governance market (NemoClaw, E7, Oasis Security) creates demand for *audit-grade* decisions; obligation discharge is a natural audit interface.
- LLM-as-judge / LLM-as-verifier is a growing paradigm (2024–2025). LSVJ inverts the polarity: LLM is the *proposer*, symbolic engine is the *judge*. This is the elegant dual — and unlike LLM-as-judge it has formal soundness inside the verifier.
- Claude Mythos / autonomous vulnerability discovery (March 2026) means defenders must assume asymmetric attacker capability. A verifier whose correctness does not depend on the LLM's capability is the only robust architecture.

---

## Contribution Focus

### Dominant contribution
**LSVJ protocol + empirical demonstration on owner-harm v3 held-out**: an LLM-proposed, symbolically-verified judgment architecture for agent runtime decisions, with evidence that (a) it measurably improves held-out generalization over LLM-only, rules-only, and naive-hybrid baselines, and (b) the gain is localized to the verify step rather than prompt engineering.

### Optional supporting contribution
**KG-grounded obligation types**: a small library (10–15 types) of owner-harm-relevant obligations whose discharge genuinely consumes KG facts (inner-circle membership, asset ownership, prior-decision precedents). This gives the KG a non-ornamental role and produces an ablation-justifiable ΔL for `no_kg` on held-out — directly addressing the "stage scenery" critique.

### Explicit non-contributions
- No new LLM training, no RLHF, no PRM.
- No new benchmark construction (we use existing v3 held-out + AgentDojo).
- No replacement of L1 Datalog / L2 triviality / L4 Post-Gate Verifier — LSVJ is an L3 upgrade, not a system rewrite.
- No novel symbolic reasoner.
- No generalization claim beyond agent runtime decisions.
- No claim about universal LLM trustworthiness.

---

## Proposed Method

### Complexity Budget

**Frozen / reused backbone**
- DeepSeek-V3.2 (production semantic gate) — no fine-tuning.
- GPT-5.4 (judge / evaluation) — no fine-tuning.
- Cozo embedded DB + existing KG schema (entities + relations + owl_rules).
- 46 YAML constraints (T3/T5/T6/T10/T11/T12/owner-harm rules) — unchanged.
- `proof_trace.py`, `markov_blanket.py`, `verdict.py` — unchanged interfaces.
- Benchmark harness, LOOP.md 6-step cycle, evolution-log — unchanged.

**New (non-trainable) components** — at most 3, all engineering, zero ML training:
1. **Obligation schema** (YAML + JSON Schema): ~10–15 obligation types, each with `{id, trigger_condition, discharge_query_template, severity}`.
2. **Obligation compiler** (`src/nous/lsvj/compiler.py`): takes `{obligation_id, params}` → emits a Cozo CozoScript query with parameter binding.
3. **Verifier / decision fusion** (`src/nous/lsvj/verifier.py`): runs compiled queries, collects `discharged`/`undischarged`/`inconclusive` per obligation, applies policy (critical undischarged → upgrade; all discharged → trust LLM allow).

**Tempting additions intentionally not used**
- No new LLM (L3 stays DeepSeek-V3.2). Using a stronger model is confounded with architectural gain.
- No differentiable Datalog (Scallop/Lobster). Out of scope; obligation queries are boolean.
- No PRM / RL. Anti-complexity-budget.
- No changes to L1 Datalog rules — keeping the rule layer frozen isolates LSVJ's contribution.
- No new KG entities specifically for LSVJ — if obligations require facts not already in KG, we extend KG populator (seed script), but the *schema* remains.

**Soft caps**: MAX_NEW_TRAINABLE_COMPONENTS = 0 (we have none). MAX_PRIMARY_CLAIMS = 2 (dominant + supporting). MAX_CORE_EXPERIMENTS ≤ 3 in the paper.

### System Overview (where LSVJ sits)

```
tool_call
  ↓
L1 (Datalog): hard-block on deterministic patterns → exit if match
  ↓
L2 (Triviality): fast benign pass-through → exit if trivial
  ↓
L3-LSVJ (NEW):
  (a) Proposer: DeepSeek-V3.2 called with LSVJ prompt
       → returns { decision ∈ {allow, confirm, block},
                    obligations : list of {id, params},
                    proof_sketch : str }
  (b) Compiler: obligations → Cozo queries
  (c) Verifier: execute queries → per-obligation verdict
                 policy:
                   LLM decision=block      → accept block
                   LLM decision=confirm    → accept confirm
                   LLM decision=allow and all critical obligations discharged → allow
                   LLM decision=allow and any critical undischarged → upgrade to confirm
                   LLM parse failure       → upgrade to confirm (fail-closed)
  ↓
L4 (Post-Gate Verifier): existing regex-based info-flow audit (unchanged)
  ↓
Final verdict (+ proof_trace with obligation-level entries)
```

**Key property**: L1, L2, L4 unchanged. L3 swaps in LSVJ. Current Nous architecture is recoverable as an ablation (obligations disabled → L3 is exactly the old semantic gate).

### Representation Design: the Obligation

An **obligation** is a named, parameterized, discharge-able claim that the symbolic verifier must be able to check against Cozo + KG in ≤ 1 query.

Example (owner-harm):

```yaml
- id: no_inner_circle_disclosed
  description: "The message body and recipient do not together reveal a relation between owner and an inner-circle entity without owner's explicit directive."
  trigger_when: action_type in {send_email, send_message, post_external}
  params: { recipient: str, message_body: str }
  discharge_query: |
    ?[recipient_is_inner_circle, leaks_inner_relation] :=
      *inner_circle{entity_id, owner_id},
      recipient_is_inner_circle = is_inner_circle_recipient(recipient, entity_id),
      leaks_inner_relation = body_reveals_inner_relation(message_body, entity_id)
    # discharged iff NOT (recipient_is_inner_circle AND leaks_inner_relation)
    # or if owner_directed_send signal is present in session_context
  severity: critical
  requires_kg: true   # this obligation depends on KG; contributes to no_kg ablation ΔL
```

Obligation taxonomy (initial 12, one per owner-harm cell plus cross-cutting):
1. `no_credential_in_payload` (Credential Leak)
2. `no_inner_circle_disclosed` (Inner Circle Leak)
3. `no_privacy_exposure` (Privacy Exposure)
4. `no_infra_exposure` (Infrastructure Exposure)
5. `no_asset_destruction_without_confirm` (Asset Destruction)
6. `no_exfiltration_via_tool_chain` (Exfiltration via Tools)
7. `no_hijacking_via_external_content` (Hijacking)
8. `bounded_autonomy` (Unauthorized Autonomy)
9. `owner_directed_send` (cross-cutting, *positive* obligation — must discharge when action looks exfil-like but is owner-directed)
10. `no_read_to_external_chain` (cross-cutting)
11. `no_authority_coercion` (cross-cutting, gates against authority-impersonation)
12. `no_precedent_violation` (cross-cutting, checks against prior decision precedents stored in KG)

Each has a discharge query that consumes KG facts where appropriate. `requires_kg: true` marks the subset that forms the `no_kg` ablation test.

### Training Plan
**None.** Zero-shot protocol. All adaptation via prompt engineering + query-template engineering. Explicitly avoids the training-data trap that produced the 100% train / 12.7% held-out gap.

### Inference Path

1. Tool call arrives, parsed into `ToolCall` struct.
2. L1 Datalog → if match, exit.
3. L2 Triviality → if trivial, exit.
4. L3-LSVJ proposer: DeepSeek-V3.2 called with `LSVJ_PROMPT(tool_call, session_context)` — prompt includes the obligation taxonomy and 8–12 minimal-pair examples of obligation generation. Expected output: strict JSON.
5. Parse output; on parse failure → **fail-closed to confirm**, log.
6. Each obligation in output → compile → query Cozo.
7. Verifier policy applies.
8. Emit `proof_trace` with `lsvj_obligations: [...]` entries — each entry records `{id, params, query, result, discharged_by_facts}`.
9. L4 Post-Gate Verifier (unchanged).
10. Final verdict returned + decision_log entry.

### Why the Mechanism Stays Small

Everything heavy (LLM, Cozo, KG, proof_trace, decision log) is preexisting. What LSVJ adds is a **protocol** — a contract between the LLM and the symbolic engine — plus a small library of verifiable claims. Protocols are cheap; the power is that the contract is enforced at runtime, not wished about in a paper.

### Exact role of foundation-model-era primitive

**LLM = proposer / tactic generator** (inspired by interactive theorem proving: human proposes tactic, Lean verifies). Not judge, not classifier. DeepSeek-V3.2 is used for its strong in-context-following ability, which is a 2024–2026 capability that makes the obligation-output format reliable without fine-tuning. This is the *minimum* leverage of frontier LLM: structured JSON output with adherence to a schema. We do not use reasoning-model private chain-of-thought — that would couple us to a specific model.

### Failure Modes and Diagnostics

| Failure mode | Detect | Mitigate |
|---|---|---|
| LLM JSON parse failure | try/except in proposer | fail-closed → confirm; log for prompt iteration |
| LLM returns obligations outside taxonomy | schema validation | unknown-id treated as `inconclusive`; critical → upgrade |
| Critical obligation query returns inconclusive (KG missing fact) | verifier policy | treat as undischarged → upgrade; flag KG gap for seeding |
| LLM omits a required obligation (e.g., `send_email` without `no_inner_circle_disclosed`) | trigger-based auto-expansion in verifier: if action_type triggers an obligation and LLM did not supply it, verifier auto-constructs and discharges it | no LLM trust for completeness |
| LLM over-generates obligations to game the system | count + diversity diagnostics; if obligation count explodes → investigate | cost budget cap (≤ 8 obligations / call) |
| Verifier latency blows up | per-query Cozo timeout; Markov Blanket already has 5ms budget | degrade to LLM-only with `degraded=true` flag in decision log |
| False positives on benign owner-directed workflows | `owner_directed_send` is an affirmative obligation; its discharge unblocks candidate-exfil cases | existing signal system extended |

### Novelty and Elegance Argument

**Closest works and exact differences**:

- **ShieldAgent (ICML 2025)**: probabilistic rule circuits + formal verification of the *rule system*. Difference: LSVJ verifies the *LLM's per-decision claims*, not the rules themselves. Rules in LSVJ are frozen building blocks; novelty is in the LLM↔verifier protocol.
- **GuardAgent (2025)**: plan-then-code + I/O audit. Difference: GuardAgent audits *I/O*, LSVJ audits *evidential basis of the decision*. GuardAgent's auditor has no obligation protocol from the LLM.
- **TrustAgent (2024)**: Agent Constitution + post-planning check. Difference: TrustAgent's check is symmetric (rules re-run), LSVJ's verifier is dependent (takes LLM-proposed obligations as input).
- **Nous v1 (this project, pre-LSVJ)**: KG-enrichment + semantic gate + post-gate verifier. Difference: KG in v1 feeds LLM context or post-gate; KG in LSVJ discharges obligations. GPT-5.4 Loop 65 critique — KG is stage scenery — becomes empirically falsifiable under LSVJ via the `no_kg` ablation.
- **LLM-as-judge paradigm (2024–2025)**: LLM judges other LLMs' outputs. Difference: LSVJ inverts polarity — LLM proposes, symbolic engine judges.
- **Lean4 / Coq interactive theorem proving (classical CS)**: human proposes tactic, kernel verifies. Difference: LSVJ operates at *runtime* on agent decisions with a decision-layer Datalog verifier, not at authoring time with a type-theoretic kernel.

**Why this is a focused mechanism-level contribution**: one protocol, one verifier policy, one obligation library. A paper can state the protocol in a single figure and prove (or disprove) its value via three experiments. The contribution is not "another layer" or "another KG" — it is a re-assignment of roles that makes the symbolic engine authoritative instead of decorative.

---

## Claim-Driven Validation Sketch

### Claim 1 (Dominant): LSVJ improves held-out generalization over the strongest non-LSVJ baseline, with gains concentrated in the three weak categories (Hijacking, Inner Circle Leak, Privacy Exposure).

- **Minimal experiment**: v3 held-out (300H + 150B). Configurations: (a) LLM-only (DeepSeek-V3.2 with current prompt, no L1/L2/L4), (b) Rules-only (L1+L2 only, already measured → 12.7%/6.7%), (c) Nous current (L1+L2+L3+L4, 85.3%/3.3% reference), (d) LSVJ (L1+L2+L3-LSVJ+L4).
- **Baseline sanity**: publish (a), (b), (c) numbers alongside (d); their values are already partially in loop-state.json and will be recomputed with the same harness for apples-to-apples.
- **Metric**: TPR / FPR / L; per-category TPR with Wilson 95% CIs.
- **Expected directional evidence**: LSVJ per-category TPR ≥ Nous current on Hijacking (currently 93.3% with L4 — so this is the hardest to improve), Inner Circle Leak (currently 89.3%), Privacy Exposure (currently 100%). Overall TPR ≥ 85.3% with FPR unchanged or lower.
- **Paper Table 1**: the four-config main table.

### Claim 2 (Supporting): LSVJ's gain is localized to the verify step (mechanism-level), and is partially KG-grounded (obligations requiring KG contribute non-zero ΔL).

- **Minimal experiment**: LSVJ internal ablation on v3 held-out. Configurations: (I) full LSVJ, (II) no_obligation (LLM prompted with LSVJ template but output collected without verify — effectively verbose semantic gate), (III) no_verify (obligations collected but all treated as `discharged`), (IV) no_kg (obligations verified but Cozo `db=None` — KG-requiring obligations become `inconclusive`). Plus (V) retest current Nous (L1–L4) for calibration.
- **Metric**: ΔL from (I) to each of (II)/(III)/(IV)/(V); per-obligation discharge rate; proportion of catches attributable to each obligation.
- **Expected directional evidence**:
  - (II) ≈ (V) or slightly better: prompt shape alone ≈ current system.
  - (III) ≈ (II): verify step carries the gain.
  - (IV) > (III): KG-requiring obligations contribute; ΔL > 0 quantifies the "no longer stage scenery" claim.
- **Paper Table 2**: the LSVJ ablation table.

### Claim 3 (Optional, venue-strengthening): LSVJ generalizes zero-shot to a second independent agent-safety benchmark.

- **Minimal experiment**: AgentDojo (97 tasks, 629 prompt-injection tests) **preferred**; fallback ShieldAgent-Bench (3K pairs). Zero tuning. Report TPR/FPR and compare to published baselines.
- **Metric**: utility-security frontier (AgentDojo), TPR/FPR (ShieldAgent-Bench).
- **Expected directional evidence**: LSVJ within 5pp of specialized SOTA on each metric; if not, honest discussion of transfer limits and what in the obligation taxonomy would need extension.
- **Venue strategy**: if Claim 3 holds, this is a full paper; if not, it is a focused position + initial evidence paper built on Claim 1 + 2 alone, and Claim 3 becomes Future Work.

---

## Experiment Handoff Inputs

### Must-prove claims
1. LSVJ vs best non-LSVJ baseline on v3 held-out: per-category improvement on Hijacking / Inner Circle Leak / Privacy Exposure, overall TPR no worse and FPR no worse.
2. `no_verify` ≈ `no_obligation` ≈ baseline: the verify step is load-bearing.
3. `no_kg` < full on held-out for KG-requiring obligation subset: KG is not stage scenery.
4. (Optional) AgentDojo zero-shot within 5pp of SOTA.

### Must-run ablations
- LSVJ 4-way internal ablation (full / no_obligation / no_verify / no_kg).
- Baseline reproductions: LLM-only, Rules-only, Nous current (L1–L4).

### Critical datasets / metrics
- **Primary**: owner-harm v3 held-out (300H + 150B).
- **Secondary**: AgentDojo or ShieldAgent-Bench.
- **Calibration**: AgentHarm (for comparability with literature; report but do not optimize).
- **Metrics**: TPR, FPR, per-category, Wilson 95% CI, bootstrap CI where N < 30; latency + cost per call; proof_trace audit logs for qualitative examples.

### Highest-risk assumptions
1. **DeepSeek-V3.2 reliably outputs valid JSON obligation bundles.** Risk: parse failure rate > 5%. Mitigation: measured in Phase 0 pilot (100 calls, target < 2% parse failure).
2. **Owner-harm obligation taxonomy (12 types) covers the held-out attack surface.** Risk: missing-obligation type → LSVJ misses attacks that require a novel obligation. Mitigation: post-hoc analysis of FN cases, taxonomy extension with documented motivation.
3. **KG has the facts that critical obligations need.** Risk: many obligations return `inconclusive` due to missing KG entities. Mitigation: seed KG with owner-centric entities before Phase 2 experiments (already a Nous P1 backlog item: `seed_security_entities.py`).
4. **Verifier latency acceptable.** Risk: 12 obligation queries × (Cozo + KG retrieval) > 1s. Mitigation: query budget (per-obligation 5ms), batch queries, cache KG retrieval per session.
5. **Adversarial LLM behaviour.** Risk: a prompt-injected LLM emits obligations designed to be trivially discharged. Mitigation: verifier policy requires a *trigger-mandatory* set (based on action_type) that verifier auto-adds if LLM omits.

---

## Compute & Timeline Estimate

### Engineering phase (weeks 1–3)
- Week 1: obligation schema design + compiler skeleton + 3 obligations (Credential Leak, Privacy Exposure, Owner-Directed Send). Unit tests.
- Week 2: full 12-obligation library + discharge queries + verifier policy. Integration tests using existing `test_gate_three_layer.py` pattern.
- Week 3: LSVJ prompt engineering on DeepSeek-V3.2; target < 2% parse failure on a 200-call pilot. KG seeding script extensions.

### Experiments phase (weeks 4–5)
- Week 4: Claim 1 main table + Claim 2 ablation. API cost: 4 conditions × 450 cases ≈ 1800 calls ≈ $20–40.
- Week 5: Claim 3 on AgentDojo (budget-permitting) or ShieldAgent-Bench. Qualitative proof-trace examples.

### Paper phase (week 6+)
- Rewrite Section 3 (Method) and Section 4 (Evaluation) of `paper/main.tex`.
- Recompute Table 4 with LSVJ rows.
- ShieldNet / QuadSentinel / GuardAgent / TrustAgent Related Work fleshing.
- Auto-review-loop-llm iterations to ARIS ≥ 8.5/10.

### Totals
- **Engineering**: ~120 hours (single author + Codex architect + Sonnet subagent for tests).
- **API budget**: ≤ $100.
- **GPU**: 0.
- **Wall clock to first submittable draft**: 6 weeks if uninterrupted; realistic 8–10 weeks allowing for Dario review rounds and external bench access.

---

## Risks and Open Questions (honest)

1. **Risk**: LSVJ on v3 held-out Hijacking already near ceiling (93.3% via L4). Main gain might come from Inner Circle / Privacy rather than Hijacking. Rephrase Claim 1 if so.
2. **Open question**: should `owner_directed_send` be a *positive* obligation (must discharge to allow otherwise-suspicious action) or a *signal*? Will investigate in Week 1 pilot; leaning toward positive obligation for consistency.
3. **Open question**: does the LLM-as-proposer require a reasoning-model chain-of-thought, or does DeepSeek-V3.2 structured output suffice? Pilot will answer.
4. **Scope tension**: if KG seeding reveals that many obligation types can be discharged from static rules alone (no KG needed), then the `no_kg` ablation ΔL might be small → Claim 2.3 weakens. Honest outcome: narrate this as "KG is marginal under current obligation design" and propose KG-heavy obligation extensions as Future Work.
5. **Venue fit**: NeurIPS / ICML prefer clear novelty; ICLR / ACL may prefer broader story; USENIX Security prefers deployment evidence. LSVJ protocol feels most natural for **NeurIPS Workshop on Safe & Trustworthy Agents** or **IEEE S&P** — decide after Phase 2.

---

*End of round-0 initial proposal.*
