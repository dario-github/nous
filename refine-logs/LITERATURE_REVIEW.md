# Literature Review — LSVJ-S 2026-Q1 Landscape

**Date**: 2026-04-18
**Window**: 2026-01 through 2026-04 (knowledge-cutoff gap fill)
**Scope**: prior art threats + adjacent work + landscape framing for LSVJ-S (LLM-Synthesized Symbolically-Verified Judgments for runtime agent decisions)

---

## Executive Summary

The 2026-Q1 "runtime LLM-agent enforcement" area is **far more populated than Round-0 Related Work suggested**. Key discoveries:

1. **One serious prior-art threat — PCAS (Palumbo, Choudhary et al., arXiv 2602.16708, 2026-02)**. "Policy Compiler for Agentic Systems" uses a Datalog-derived language with LLM-authored rules (Claude Code + human review) and a reference monitor that blocks violations before execution. **Mitigating differences survive**: PCAS compiles policies **offline from a fixed specification**; LSVJ-S **synthesizes per-decision at runtime** + adds a 4-stage compile-time gate (perturbation-sensitivity + has-decisive-primitive) that PCAS does not need because its rules are pre-audited. Differentiation is clean but must be explicit in Related Work.

2. **Two serious adjacent works, different layer / time**:
   - **Solver-Aided** (Roy et al., arXiv 2603.20449, 2026-03): NL→SMT translation is offline + human-guided; SMT verifies per-tool-call against static constraints. LSVJ-S differs: LLM itself synthesizes the constraint at decision time.
   - **Agent-C** (OpenReview VeRehDnGJJ): interleaves SMT with constrained decoding at token-generation time. Different layer (decoding vs decision) and very strong reported benchmarks (100% conformance) — we should cite honestly.

3. **Lucky alignment**: our `no_synth_menu_plus` ablation baseline is already **structurally equivalent to a PCAS-style static Datalog rule menu** (12 pre-registered expert rules). This gives us a clean apples-to-apples "per-decision synthesis > offline expert menu" experimental comparison — strengthens novelty argument.

4. **Implications for the FINAL_PROPOSAL**:
   - Related Work section must cite PCAS, Solver-Aided, Doshi-2601, Agent-C, ClawGuard, AgentSpec, Pro2Guard (missing from R0).
   - Frame the contribution as **per-decision runtime synthesis + compile-time gate** — not as "LLM + Datalog + agent safety" (PCAS already occupies that slot).
   - Re-label `no_synth_menu_plus` publicly as "PCAS-style static expert-menu baseline" to sharpen the comparison.

---

## Papers Found (ranked by threat level)

| Paper (arXiv ID / Venue) | Year/Month | Relevance Tag | One-line summary |
|---|---|---|---|
| **PCAS — Policy Compiler for Agentic Systems** (Palumbo & Choudhary et al., [2602.16708](https://arxiv.org/abs/2602.16708)) | 2026-02 | **PRIOR-ART-THREAT** | Datalog-derived policy language + offline-compiled reference monitor; LLM-authored rules with Claude Code + human review. 48%→93% customer-service compliance. |
| **Solver-Aided Policy Compliance in Tool-Augmented LLM Agents** (Roy et al., [2603.20449](https://arxiv.org/abs/2603.20449)) | 2026-03 | ADJACENT (serious) | NL→SMT-LIB offline translation + per-tool-call SMT verification against constraints. LLM does not synthesize constraint. TauBench eval. |
| **Agent-C** (OpenReview [VeRehDnGJJ](https://openreview.net/forum?id=VeRehDnGJJ)) | 2026 | ADJACENT (serious, different layer) | Temporal DSL → FOL → SMT interleaved with constrained decoding at token-generation time. Claims 100% conformance benign+adversarial. |
| **Towards Verifiably Safe Tool Use for LLM Agents** (Doshi et al., [2601.08012](https://arxiv.org/abs/2601.08012)) | 2026-01 | ADJACENT | STPA hazard analysis + MCP capability enhancement; enforceable specifications on data flows + tool sequences. ICSE NIER 2026 (4-page position). |
| **ClawGuard** ([2604.11790](https://arxiv.org/html/2604.11790)) | 2026-04 | ADJACENT | Tool-call boundary rule enforcement, static rules, focus on indirect prompt injection. |
| **AgentSpec** ([2503.18666](https://arxiv.org/abs/2503.18666), ICSE'26) | 2025–2026 | ADJACENT | Lightweight DSL (triggers + predicates + enforcement) for LLM agent runtime constraints. >90% code-agent coverage. |
| **Pro2Guard / ProbGuard** ([2508.00500](https://arxiv.org/abs/2508.00500)) | 2025-08 | ADJACENT | Proactive runtime enforcement via DTMC learned from traces + probabilistic reachability. Built on LangChain. |
| **VeriGuard — Verified Code Generation** ([2510.05156](https://arxiv.org/html/2510.05156v1)) | 2025-10 | ADJACENT | Enhances LLM agent safety via verified code generation (different problem — verify code, not decisions). |
| **ShieldAgent** ([2503.22738](https://arxiv.org/html/2503.22738v1), ICML 2025) | 2025-03 | STRENGTHENS-FRAMING | Probabilistic rule circuits + formal verification from policy documents. 90.1% rule recall; −58.2% inference time. Already cited in R0. |
| **GuardAgent** ([2406.09187](https://arxiv.org/abs/2406.09187)) | 2024-06 | STRENGTHENS-FRAMING | Plan-then-code + I/O audit. Already cited in R0. |
| **TrustAgent** (Hua et al., [2402.01586](https://arxiv.org/abs/2402.01586)) | 2024-02 | STRENGTHENS-FRAMING | Agent Constitution + post-planning safety check. Already cited in R0. |
| **QuadSentinel** (Yang et al., [2512.16279](https://arxiv.org/abs/2512.16279)) | 2025-12 | STRENGTHENS-FRAMING | Sequent-based multi-agent sentinel + priority rule updates. P 97.4% / R 85.2% / FPR 2.3%. Already cited in R0. |
| **XGrammar / Outlines / llguidance** | 2025–2026 | STRENGTHENS-FRAMING (primitives) | Grammar-constrained decoding engines. Already named in FINAL_PROPOSAL. |

---

## PRIOR-ART-THREAT Deep Analysis: PCAS

**PCAS** (Nils Palumbo, Sarthak Choudhary et al., arXiv 2602.16708, 2026-02) is the most serious prior-art threat.

### What PCAS does
- Takes an **existing agent implementation + policy specification** as input.
- Models agent state as a **dependency graph** capturing causal relationships among tool calls, tool results, and messages.
- Policies are **Datalog-derived declarative rules** covering transitive information flow and cross-agent provenance.
- A **reference monitor** intercepts all actions and **blocks violations before execution**.
- "Deterministic enforcement **independent of model reasoning**."
- Policy rules are **authored once, offline, with LLM assistance (Claude Code) + manual review** — then compiled into the instrumented runtime.
- Benchmarks: 48% → 93% policy compliance on customer service; zero violations in instrumented runs.

### Differentiation from LSVJ-S

| Dimension | PCAS | LSVJ-S |
|---|---|---|
| Rule authoring time | **Offline**, once per deployment, human-reviewed | **Runtime, per-decision**, by LLM |
| Who writes the rule | LLM (Claude Code) + human, pre-runtime | LLM, per tool-call |
| Reference monitor | Deterministic blocker over pre-authored policy | Compile-time 4-stage gate over freshly synthesized rule |
| Guard against rule quality | Human review | **Perturbation-sensitivity + has-decisive-primitive** compile-time check |
| Context specificity | Global policy covers all cases | Per-decision rule tailored to call's tool + session context |
| Audit artifact | Pre-authored policy spec | Synthesized rule + discharge trace + decisive-primitive attribution, per call |
| Dependence on LLM runtime capability | Minimal (rules pre-authored) | Required (LLM must synthesize validly) |
| Key benefit | Strong deterministic guarantees in closed-vocabulary domains | Covers open-vocabulary + contextual edge cases offline compile cannot anticipate |
| Key risk | Coverage gap on cases not anticipated by policy author | Synthesized rule quality (addressed by compile-time gate) |

### Why differentiation survives

**Offline compilation covers general policies; runtime synthesis covers per-call contextual specificity.** The case that motivates LSVJ-S: a `send_email` whose safety depends on **who the recipient is + what the body says + what session context preceded it** — not expressible as a single static rule without enumerating all combinations. PCAS's reference monitor is strong inside its policy's closed vocabulary; no mechanism to generate novel predicates for novel situations.

**LSVJ-S's 4-stage compile-time gate is a novel mechanism PCAS does not have**, because PCAS's rules are pre-audited so such automated quality gates are unnecessary. LSVJ-S needs them precisely because rules are LLM-synthesized without human review.

### Impact on our paper

1. **Related Work section must lead with PCAS** in the "runtime Datalog-based agent safety" paragraph.
2. **Contribution framing update**: claim novelty on:
   - per-decision runtime synthesis of Datalog proof obligations (vs. offline policy compilation)
   - 4-stage compile-time gate with perturbation-sensitivity + has-decisive-primitive (novel mechanism)
   - decisive-primitive tracing + paired-McNemar per-primitive causal attribution (novel evaluation)
3. **`no_synth_menu_plus` baseline → rename "PCAS-style static expert-menu baseline"** in paper. 12-rule pre-registered menu is structurally isomorphic to PCAS's offline-authored policy rules. Natural apples-to-apples:
   - If LSVJ-S > PCAS-style menu on v3-HN, evidence that **per-decision synthesis adds value over static Datalog policy of same predicate vocabulary** — exactly the delta PCAS cannot claim.
4. **Scope qualification**: acknowledge in Limitations that PCAS-style offline policies dominate LSVJ-S when domain is closed + pre-enumerable; LSVJ-S targets the complement.

---

## ADJACENT Work Deep Analysis

### Solver-Aided Policy Compliance (Roy et al., arXiv 2603.20449, 2026-03)

- **Offline**: NL tool-use policies → SMT-LIB-2.0 via LLM-assisted + human-guided translation.
- **Runtime**: per-tool-call Z3 verification; blocks violating calls.
- **LLM role**: does **not synthesize** constraints; constraints pre-translated; LLM proposes tool calls only.
- **Delta from LSVJ-S**: constraint-source axis — fixed pre-translated (theirs) vs per-decision LLM-synthesized (ours).
- **Citation plan**: Related Work — closest "LLM agent + formal logic runtime verification" work with explicit delta.

### Agent-C (OpenReview VeRehDnGJJ)

- **Layer**: token-generation-time. Temporal DSL → first-order logic → SMT interleaved with constrained decoding. Backtracking on non-compliant tokens.
- **Delta from LSVJ-S**: different abstraction layer — Agent-C constrains token generation (fine-grained, decoding-time); LSVJ-S verifies decision post-generation (coarse-grained, decision-time). Complementary, not substitutive.
- **Concern**: claimed 100% conformance benign+adversarial — if it holds on published benchmarks, LSVJ-S may want to report on overlapping benchmarks.
- **Action (novelty-check)**: WebFetch full paper to verify claim strength + benchmark overlap.

### Towards Verifiably Safe Tool Use (Doshi et al., arXiv 2601.08012, ICSE NIER 2026)

- 4-page position/early-stage paper.
- STPA hazard analysis + MCP capability enhancement.
- Enforceable specifications on data flows + tool sequences.
- **Delta from LSVJ-S**: offline specification authorship; no LLM synthesis of verification artifacts; no per-call proof obligation discharge.
- **Citation plan**: Related Work — positioning landmark for formal-safety-for-tool-use.

### ClawGuard (arXiv 2604.11790, 2026-04)

- Tool-call boundary rule enforcement, static rules, deterministic + auditable.
- Focus: indirect prompt injection defense (3 primary channels).
- **Delta**: static-rule vs synthesized-rule.
- **Citation plan**: cite as strong static-rule baseline approach.

### AgentSpec (arXiv 2503.18666, ICSE'26)

- DSL with triggers + predicates + enforcement mechanisms.
- >90% coverage on code-agent cases.
- **Delta from LSVJ-S**: static DSL vs LLM-synthesized rules; narrower than Datalog.
- **Citation plan**: cite as custom safety DSL category rep.

### Pro2Guard / ProbGuard (arXiv 2508.00500)

- Proactive enforcement via DTMC learned from execution traces.
- Probabilistic reachability over symbolic states.
- Built on LangChain.
- **Delta from LSVJ-S**: statistical model from trace data vs per-decision symbolic synthesis.
- **Citation plan**: complementary "learned probabilistic guardrail" vs LSVJ-S's "synthesized symbolic obligation."

### VeriGuard (arXiv 2510.05156)

- Verified code generation for LLM agent safety (verifies agent-generated code, not decisions).
- **Delta from LSVJ-S**: verification target is generated code, not decisions.
- **Citation plan**: brief mention as orthogonal verification target.

---

## STRENGTHENS-FRAMING

**Already cited in R0 FINAL_PROPOSAL**: ShieldAgent, GuardAgent, TrustAgent, QuadSentinel, Llama Guard, ShieldGemma, XGrammar, Outlines, Scallop, Lobster, NeMo Guardrails.

**R0 omissions now surfaced**:
- PCAS (critical — add as lead paragraph)
- Solver-Aided (critical — add as closest SMT-based work)
- Doshi-2601 (position landmark)
- ClawGuard (static-rule baseline rep)
- AgentSpec (custom DSL rep)
- Pro2Guard/ProbGuard (probabilistic rep)
- Agent-C (decoding-time layer)

---

## Landscape Summary

**Runtime enforcement for LLM agent safety is a crowded and rapidly-consolidating field in 2026-Q1.** Three broad families converge: (i) **static DSL + deterministic reference monitor** (AgentSpec, ClawGuard, PCAS); (ii) **formal-logic constraint verification** (Solver-Aided, Agent-C); (iii) **learned / probabilistic guardrails** (Pro2Guard, ShieldAgent Markov logic). Unifying trend: **shifting safety from training-time to runtime-enforcement-time** — driven by capability advances (constrained decoding, XGrammar, vendor structured-output) and regulatory pressure (California SB 53/SB 243/AB 489 turning "safety" into enforceable obligations).

**PCAS is the closest prior art** and must be explicitly differentiated. PCAS's Datalog-derived policy compiler is a real achievement: offline-compiled, deterministic, zero violations. Its mechanism fits closed-domain policies (customer service protocols, approval workflows, data access restrictions). LSVJ-S targets **beyond PCAS's closed-domain sweet spot**: open-vocabulary contextual decisions where the policy author cannot anticipate every combination. LSVJ-S's per-decision synthesis fills this gap at the cost of needing a compile-time gate (PCAS does not need one — rules pre-audited).

**Agent-C is an architectural sibling at a different layer** — token-time SMT vs decision-time Datalog synthesis. Complementary not substitutive. Agent-C's claimed 100% conformance on benign+adversarial is strong; needs numerical comparison in our paper if benchmark overlap exists (novelty-check action). Solver-Aided is sibling with offline-translated SMT instead of synthesized Datalog. Doshi-2601 is a 4-page position paper — useful framing citation, not serious competitor.

---

## Implications / Required Changes for FINAL_PROPOSAL

1. **Related Work section expansion** (must-do for workshop):
   - Add paragraph on PCAS with explicit differentiation table.
   - Add paragraph covering Solver-Aided + Agent-C as "formal-logic + LLM" family.
   - Cite ClawGuard, AgentSpec, Pro2Guard in "static DSL / probabilistic" paragraph.
   - Cite Doshi-2601 as position/motivation.

2. **Novelty claim refinement**:
   - From: "LSVJ-S is LLM-proposed, symbolically-verified — closest is ShieldAgent/GuardAgent/TrustAgent"
   - To: "LSVJ-S is **per-decision runtime synthesis** of Datalog proof obligations + 4-stage compile-time gate + decisive-primitive causal tracing. Closest work is PCAS (offline Datalog policy compilation); delta is per-decision synthesis + compile-time gate + causal attribution."

3. **Baseline reframing** (affects Tables 1–3):
   - `no_synth_menu_plus` → "PCAS-style static expert-menu baseline" (12 rules over same owner-harm primitive vocabulary).
   - Narrative: "We compare LSVJ-S's per-decision synthesis against a statically-authored expert Datalog menu of the same vocabulary (analog of PCAS's offline policy compilation). If LSVJ-S > PCAS-style menu on hard-negative slice, per-decision synthesis adds value beyond what offline compilation can achieve for the same predicate set."

4. **Potential experimental addition** (NICE, not MUST):
   - If Agent-C publishes benchmarks that overlap with owner-harm or AgentHarm, run LSVJ-S on same for direct numerical comparison.

5. **Contribution framing hedge**: acknowledge Limitations that PCAS-style offline policies dominate LSVJ-S when domain is closed + pre-enumerable. LSVJ-S scope = open-vocabulary contextual complement.

---

## Follow-up TODO (for novelty-check Task #3)

1. **WebFetch Agent-C OpenReview page** — verify claimed 100% conformance + benchmark used.
2. **WebFetch PCAS full paper (HTML v3)** — look for (a) per-decision synthesis as future work; (b) benchmarks beyond customer service; (c) explicit scope limitations.
3. **WebFetch Solver-Aided full paper** — confirm TauBench numbers + whether constraint translation supports runtime updates.
4. **Search "LLM rule synthesis Prolog Horn clause 2026"** — Prolog-side equivalents we may have missed.
5. **Search "agent trustworthy reasoning benchmark 2026"** — broader than owner-harm (aligns with user's stated final goal).
6. **Check if NeurIPS 2026 Workshop on Safe & Trustworthy Agents submission list is public** — see what's already accepted/submitted.
7. **Reach out (post-workshop)** to PCAS authors (Palumbo, Choudhary) for informal differentiation check — post-submission.

---

*End of literature review. Next step: `/novelty-check` (Task #3) uses this as input to produce a formal novelty-delta report + adjusted FINAL_PROPOSAL Related Work section.*
