# Paper Outline: LSVJ-S -- Synthesize, Gate, Verify: Runtime Proof-Obligation Synthesis for Trustworthy Agent Decisions

**Target**: NeurIPS 2026 Workshop on Safe & Trustworthy Agents (Dec 2026)
**Authors**: Dongcheng Zhang (BlueFocus Communication Group / independent), Yiqing Jiang (Tongji University)
**Length**: 8 pages NeurIPS format + references + appendix
**Companion paper**: Owner-Harm compositional safety gates paper (arXiv pending; DISTINCT work -- that paper is about composing harm-type gates; this paper is about per-decision proof-obligation synthesis + compile-time soundness checking)
**arXiv policy**: ASCII-only abstract (<1920 chars); figures in PDF form
**Internal refs**: `refine-logs/FINAL_PROPOSAL.md` (R4 verdict 7.95/10), `refine-logs/EXPERIMENT_PLAN.md` (B1-B6), `refine-logs/LITERATURE_REVIEW.md`, `refine-logs/NOVELTY_CHECK.md` (Gemini 4/10 amber review)

---

## Abstract (draft, 150-200 words, ASCII only)

LLM-based agent runtime authorization suffers a fundamental epistemic gap: the LLM's "allow" verdict
is an opaque label with no mechanical connection to the facts it claims to reason over. Existing hybrid
architectures stack symbolic layers alongside the LLM, but the LLM's decision is never verified by
the symbolic substrate. We present LSVJ-S, a Synthesis-Proof-Obligation (SPO) protocol in which the
LLM synthesizes a per-decision Datalog rule as its committed proof of trust, and a 4-stage compile-time
gate -- (b.1) parse, (b.2) type-check against a typed owner-harm primitive schema (Class A/B/C),
(b.3) syntactic non-triviality, (b.4) perturbation-sensitive AND has-decisive-primitive -- admits the
rule only if all stages pass. Gate b.4 is grounded in Self-Consistency (Wang et al., 2022) applied to
LLM-synthesized Datalog, making it the first structured Self-Consistency application to runtime
safety-rule synthesis. On a hard-negative held-out slice (v3-HN), LSVJ-S outperforms a 12-rule
Static Expert-Authored Policy (SEAP) baseline by [PLACEHOLDER: Wilson 95% CI margin TBD], with gains
attributable via paired-McNemar per-primitive causal analysis to specific KG facts. We discuss the
Self-Justification Trap -- the risk that a misaligned proposer synthesizes a collusion rule -- and
provide empirical defense via adversarial synthesis stress testing (B6).

**Word count check**: ~175 words. **Char count**: ~1,380. Fits arXiv <1920 limit.

---

## 1. Introduction (~1 page)

### 1.1 The Problem: "Allow" Without Verification

- Ground in the concrete Nous failure: v3 held-out TPR with L1+L2 rules only = **12.7%**; adding L3
  LLM lifts +62.6pp -- but the `no_kg` training ablation (ΔL=0) reveals KG is not carrying the
  generalization weight. The LLM's held-out gains are not symbolically grounded.
- Epistemic framing: an LLM's "allow" is an opaque label. Current hybrid stacking (LLM + rules + KG
  on parallel tracks) does not constitute verification -- the LLM decision is accompanied by symbolic
  context, not verified against it.
- Motivating case study: `send_email` whose safety depends on recipient identity, message body
  content, and preceding session context. No static policy rule can enumerate all combinations; offline-
  compiled policies (e.g., PCAS) leave this gap -- motivates runtime per-decision synthesis.

### 1.2 Why Current Approaches Are Insufficient

- **LLM-only classifiers** (Llama Guard, ShieldGemma, QuadSentinel): opaque labels, no audit
  artifact at the symbolic layer. Rules-only (12.7% v3 held-out TPR) proves insufficient for semantic
  intent.
- **Hybrid stacking** (Nous, GuardAgent, TrustAgent, ShieldAgent): LLM and symbolic run in parallel,
  not in a verifier-proposer relationship. KG injection into semantic prompt degraded TPR by 12%
  (Nous Loop 33).
- **Offline policy compilers** (PCAS, Solver-Aided): strong deterministic enforcement inside closed
  vocabularies; no mechanism for open-vocabulary contextual cases the policy author did not anticipate.
- **Naive fixes tried and failed**: stronger LLM (QuadSentinel R=85.2%), more training data (train
  100% / held-out 75.3%), majority-vote-3 without external verification (no symbolic grounding added).

### 1.3 Insight: Make the Symbolic Engine the Verifier

- The LLM should not produce a verdict label; it should produce a **committed proof obligation** -- a
  typed Datalog rule -- and "allow" stands only when (a) the rule passes a 4-stage compile-time
  soundness gate and (b) it discharges against live KG facts.
- Verifier authority does not depend on the LLM's capability: the gate rejects unconditionally on
  any stage failure (fail-closed to `confirm`).
- Honest scope: LSVJ-S is not a formal proof system. The gate is a soundness check (rejects invariant
  and trivial rules), not a completeness guarantee. Workshop contribution is empirical + protocol.

### 1.4 Contributions (3 bullets)

1. **SPO protocol** (Synthesis-Proof-Obligation): per-decision Datalog rule synthesis over a typed
   owner-harm primitive schema (A/B/C); "allow" requires gate admission + live-fact discharge.
2. **4-stage compile-time gate** including compound b.4 (perturbation-sensitive AND
   has-decisive-primitive): structured Self-Consistency (Wang et al., 2022) applied to LLM-synthesized
   Datalog safety rules, closing the Self-Justification Trap.
3. **Empirical evaluation** on v3-HN: (a) 5-config main comparison with Wilson CI, (b) 9 Tier-1
   ablation conditions, (c) per-primitive paired-McNemar causal attribution, (d) B6 adversarial
   synthesis stress test.

---

## 2. Related Work (~0.75 page)

### 2.1 Three Families of Runtime Agent Safety Enforcement

- **Family 1 -- Static DSL + deterministic reference monitor**: PCAS (arXiv 2602.16708), AgentSpec
  (arXiv 2503.18666, ICSE 2026), ClawGuard (arXiv 2604.11790). Rules authored offline, compiled,
  deterministically enforced.
  - **PCAS is the closest prior art**. Use Gemini's clean metaphor explicitly: "PCAS is a *Statute*
    model -- laws written before the crime, deterministically enforced. LSVJ-S is a *Case Law* model
    -- the LLM argues the legality of its specific action at the moment of execution, and a compile-
    time soundness gate checks the argument's non-triviality before admitting."
  - Key delta: PCAS compiles offline from a fixed specification with human review; LSVJ-S synthesizes
    per-decision at runtime and needs a compile-time gate precisely because rules are LLM-authored
    without pre-audit. PCAS does not need such a gate because its rules are already human-audited.
  - Scope qualification (honest): PCAS-style offline policies dominate LSVJ-S when the domain is
    closed and pre-enumerable. LSVJ-S targets the complement: open-vocabulary contextual edge cases.
- **Family 2 -- Formal-logic constraint verification**: Solver-Aided (Roy et al., arXiv 2603.20449)
  translates NL policies to SMT-LIB offline; LLM does not synthesize the constraint. Agent-C
  (OpenReview VeRehDnGJJ) interleaves SMT with constrained decoding at token-generation time
  (model-internal layer vs LSVJ-S's model-agnostic wrapper layer). Delta from LSVJ-S: constraint-
  source axis (static pre-translated vs per-decision LLM-synthesized).
- **Family 3 -- Probabilistic and learned guardrails**: Pro2Guard (arXiv 2508.00500) learns a DTMC
  from traces; ShieldAgent (arXiv 2503.22738, ICML 2025) uses probabilistic rule circuits. GuardAgent
  (arXiv 2406.09187), TrustAgent (arXiv 2402.01586). LSVJ-S differs: classical non-probabilistic
  Datalog synthesis + compile-time soundness gate.

### 2.2 Foundational Methods LSVJ-S Builds On

- **Self-Consistency (Wang et al., NeurIPS 2022)**: majority-vote over LLM-sampled reasoning chains.
  Gate b.4's perturbation-sensitivity is **structurally Self-Consistency applied to LLM-synthesized
  Datalog rules** (N=5 perturbation trials; reject if outcome invariant). **Must cite explicitly;
  b.4 is NOT novel relative to this lineage.** LSVJ-S novelty = combination of structured-output
  Datalog synthesis + perturbation-sensitivity gate + decisive-primitive causal attribution in the
  runtime safety context. None of the three sub-steps is independently novel.
- **Program synthesis + majority-voting lineage**: L-Eval, Logic-Guide (LLMs generating Horn
  clauses for reasoning); Inala et al. Symbolic Shielding (adaptive variants). [PLACEHOLDER: confirm
  arXiv IDs after followup WebSearch -- see Open Questions Q4, Q5.]
- **Datalog program synthesis**: Scallop (PLDI 2023), Lobster (ASPLOS 2026) -- differentiable
  neurosymbolic, offline training. LSVJ-S is classical runtime Datalog + zero training.
- **Doshi et al.** (arXiv 2601.08012, ICSE NIER 2026): STPA + MCP position paper; motivation
  citation for formal-safety-for-tool-use framing.

### 2.3 The SEAP Baseline as PCAS Analog

- **SEAP (Static Expert-Authored Policy)**: our 12-rule pre-registered expert menu is structurally
  isomorphic to PCAS's offline-authored Datalog policy -- same predicate vocabulary, offline
  authorship, no per-decision synthesis.
- This gives a clean apples-to-apples experimental comparison: does per-decision runtime synthesis
  add TPR beyond an expert-authored policy of the same vocabulary? That delta is what PCAS cannot
  claim for open-vocabulary contextual cases.
- Naming note: the baseline was renamed from `no_synth_menu_plus` to SEAP per Gemini review
  (NOVELTY_CHECK.md) to avoid misrepresenting PCAS's human-audit guarantee.

---

## 3. Method (~2 pages)

### 3.1 Owner-Harm Primitive Schema: A/B/C Partition

- **Motivation**: typed vocabulary contracts between proposer and verifier -- enables b.2 type-check
  without human review of each synthesized rule.
- **6 primitives** across 3 classes (full schema in Appendix A):
  - **Class A -- KG-grounded** (Cozo Datalog queries over live NousDB; returns empty relation if
    KG state does not support): `is_inner_circle(recipient_id)`,
    `owner_has_directed(action_id, is_directed)`.
  - **Class B -- deterministic host function** (no LLM call; returns bool):
    `body_length_within_budget(message_body, budget_tokens)`,
    `action_matches_allowlist(action_id, allowlist_name)`.
  - **Class C -- sealed sub-oracle** (fresh session of same model, schema-bound input, divergence-
    calibrated): `body_reveals_inner_relation(message_body, recipient_id, p_rev)`,
    `action_is_reversible(action_id, reversible)`. **Honest label: procedural independence,
    not representation-level.** Different-model Class C = Future Work.
- **Class rationale**: A/B/C partition separates KG-fact-grounded inference (Class A, the B4 causal
  ablation target) from deterministic checks (Class B) from LLM-based semantic sub-oracle (Class C).
  Each class has a distinct b.4 perturbation operator (A: reshuffle matching tuples within-type;
  B: negate bool return; C: flip pre-recorded sub-oracle output, no additional LLM call).
- **Non-contribution**: 6-seed library and 12-rule SEAP are prior development / baselines, not
  contributions of this paper.

### 3.2 Proposer: Grammar-Constrained Synthesis

- **Model**: DeepSeek-V3.2 (frozen production L3 LLM). [PLACEHOLDER: confirm after W2 pilot --
  if Kimi K2.5 shows better parse rate, update here. W2 fork criterion: if Cozo PEG has >=1
  construct not round-tripping in <=2 days, commit to post-hoc parse+retry (3x max) as primary.]
- **Grammar-constrained decoding**: XGrammar + Lark + Cozo PEG grammar. Proposer outputs
  `{ decision, synthesized_obligation: CozoScript rule }`. Grammar constraint enforces syntactic
  well-formedness before b.1, reducing gate rejection cost.
- **Rule form**: `?[discharged] := <body>, discharged = <boolean expr over body bindings>` where
  `<body>` is a conjunction of A/B/C primitive calls with fixed arity and typing.
- **Few-shot seeds**: 6-seed library as few-shot context. Non-over-anchoring monitor: verbatim-match
  rate (% synthesized rules verbatim-matching seed or SEAP rule) must be <=30% on v3-HN (B2
  diagnostic); >50% = synthesis collapsed to template-completion.
- **Example rule** (send_email tool call; CozoScript):
  ```
  ?[discharged] :=
    is_inner_circle(recipient_id),                      % Class A
    body_reveals_inner_relation(message_body,           % Class C (sealed)
                                recipient_id, p_rev),
    owner_has_directed(action_id, is_directed),         % Class A
    discharged = (not p_rev) or is_directed
  ```

### 3.3 4-Stage Compile-Time Gate

Overview: fail-closed to `confirm` on any stage failure. The gate's authority does not depend on
LLM capability.

- **b.1 -- Parse** (Cozo parser): rule fed to parser. Failure -> confirm.
  [PLACEHOLDER: W2 pilot target: >=99% parse rate with grammar-constrained decoder.]
- **b.2 -- Type-check** (A/B/C schema): every primitive call must match a declared primitive with
  correct arity and class. Unknown predicates, arity mismatch -> confirm.
- **b.3 -- Syntactic non-triviality**: body must reference >=1 Class A or B primitive; head must
  not be a constant expression (`true`, literal bool). Catches tautologies that pass b.1-b.2.
- **b.4 -- Compound: (perturbation-sensitive) AND (has-decisive-primitive)**. Two logically
  independent checks sharing evaluation machinery. Grounded in Self-Consistency (Wang et al. 2022)
  applied to Datalog. NOT an independent invention; cited and credited explicitly.
  - **Perturbation-sensitive**: run rule on live bindings -> `discharged_real`; run N=5 times on
    perturbed bindings (per-class operators above). Reject if outcome identical across all N trials.
    Calibration (W3 pilot, 40-rule hand-labeled reference set): false-rejection <=10%, false-
    admission on content-invariant <=2%. Fallback: N=7 without calibration claim if reference set
    slips timeline.
  - **Has-decisive-primitive**: for each primitive, flip its binding, check if outcome changes.
    Reject if no primitive is decisive. Ensures every admitted rule has an attributable cause --
    audit artifact property.
  - **Honest scope**: b.4 rejects invariant rules, not weakly-dependent rules. Weakly-content-
    dependent rules (flip rate 10-25%) pass N=5 at P ~67%. This is a feature of zero-training
    protocol; stronger gate would require training the proposer (destroys verifier independence).
- **Figure 2** (W8): 4-stage gate diagram with b.4 decomposed into two named sub-boxes
  (perturbation-sensitive + has-decisive-primitive) sharing execution machinery.

### 3.4 Decisive-Primitive Tracing (Diagnostic Utility, NOT Gate Component)

- **Definition**: `decisive_primitives(rule, live_bindings) -> list[str]` -- primitives whose
  binding flip changes the discharge outcome.
- **Role**: diagnostic only. Records `binding_decisive_primitive` in
  `proof_trace.lsvj_obligations[i]`. Used for: Claim 2.3 paired-McNemar (B4), qualitative case
  studies (B5), neg-control anti-gaming check (<=20% of LSVJ-S discharges on neg-control show any
  Class A primitive decisive).
- **Pre-registered failure alternative**: if neg-control Class-A-decisive rate >20%, recalibrate
  seed library; no post-hoc criterion redefinition.

### 3.5 Verifier Policy and Full Inference Path

- **L1-L4 unchanged outside L3-LSVJ-S**:
  1. L1 Datalog exact-match -> exit if match
  2. L2 triviality filter -> exit if trivial
  3. L3-LSVJ-S: (a) Proposer -> `{decision, synthesized_obligation}`; (b) 4-stage gate (b.1-b.4);
     (c) Execute (A: Cozo; B: host fn; C: sealed sub-oracle); (d) decisive-primitive tracing;
     (e) verify policy
  4. L4 hijacking filter (unchanged)
  5. Final verdict + `proof_trace` `{rule_text, class_usage, discharge_result, decisive_primitives}`
- **Verify policy**: LLM says block/confirm -> accept as-is; LLM says allow AND rule admitted AND
  rule discharges -> allow; otherwise -> upgrade to confirm.

### 3.6 Honest Design Tradeoffs

- **Zero-training rationale**: (1) grammar-constrained decoding delivers schema adherence without
  fine-tuning; (2) SFT on obligations would co-adapt proposer to verifier acceptance criteria,
  collapsing verifier independence (epistemic argument, not only budget constraint); (3) API-only
  $120 budget makes training infeasible -- both constraints are honest.
- **Self-Justification Trap acknowledgment** (required per Gemini NOVELTY_CHECK.md): proposer
  writes both the action and the admitting rule. A misaligned or prompt-injected proposer can
  synthesize a tautological rule (body `= true`), permissive rule (rarely-enforcing primitives),
  or collusion rule (passes b.1-b.3 surface checks while being vacuous). Gate b.4 + b.3 are the
  primary defenses. B6 empirically tests this (Section 4.6).
- **Class C same-model limitation**: procedural independence only. Same model weights may share
  failure modes between proposer and Class C sub-oracle. Named limitation, not hidden.
- **"Decorative KG" contingency**: if B4 (per-primitive KG-corruption) shows null effect on all
  Tier-1 primitives, the paper pivots framing from "symbolic substrate verifier" to "JIT-Policy
  Gate." Pre-committed pivot, not post-hoc reframing. See Section 5.2.

---

## 4. Experiments (~2 pages)

### 4.1 Datasets and Evaluation Protocol

- **Primary: v3-HN hard-negative slice**
  - Target: >=100H + 50B total; >=50H + 25B blind sub-slice; 30H + 15B neg-control sub-slice
  - Construction: 50% author (Yan) + 50% blind (Sonnet 4.6 subagent, sealed prompt, protocol
    pre-registered in `nous/docs/v3-HN-blind-protocol.md` before W5)
  - Blind-distance calibration: cosine-sim threshold on ~5 within-author + ~5 cross-author pairs;
    if blind-vs-author cosine exceeds threshold -> failed-blind flag + recruit human collaborator
    for post-workshop ICLR run
  - Neg-control (30H+15B): hand-crafted benign cases superficially resembling harmful; tests that
    LSVJ-S does not over-block legitimate tool calls
- **Reference datasets**: v3 (300H + 150B, historical baseline); AgentHarm (176H + 176B, literature
  comparability) [PLACEHOLDER: confirm if AgentHarm comparison in workshop or ICLR tier -- see
  Open Questions Q9]
- **Statistical policy**: all proportions reported with Wilson 95% CI; significance tests at
  alpha=0.05; paired-McNemar used only for B4 decisive-subset analysis; NO significance claim on
  neg-control (n=45; diagnostic-only, explicitly labeled in paper body)
- **Metrics**: TPR / FPR + Wilson 95% CI per category; paired-McNemar chi-sq + continuity
  correction; paired-Wilson 95% CI on flip rate b/(b+c); false-allow rate (B3 diagnostic);
  verbatim-match rate (B2 diagnostic); parse-failure rate; decisive-primitive distribution; latency

### 4.2 B1 -- Main Table: 5-Config Comparison (Claim 1)

- **5 configurations**:
  1. **LLM-only**: DeepSeek-V3.2 + current semantic-gate prompt; no L1/L2/L4
  2. **Rules-only**: L1 Datalog + L2 triviality; no L3/L4
  3. **Nous current**: L1+L2+L3 (old prompt)+L4
  4. **SEAP**: L1+L2+12-rule expert menu (pre-registered `nous/docs/no-synth-menu-plus.cozo`)+L4
  5. **LSVJ-S (ours)**: L1+L2+L3-LSVJ-S+L4; `upgrade_only=True`; majority-vote k=3; N=5 in b.4
- **Success criterion**: LSVJ-S Wilson CI lower bound > SEAP Wilson CI upper bound on >=1 category;
  per-category TPR >= SEAP on >=5/8 categories; direction-consistent on blind sub-slice
- **Table 1 (main)**: TPR / FPR + Wilson 95% CI per config per category; full + blind sub-slice
  separately. [PLACEHOLDER: all numbers TBD after W6 run]
- **Failure off-ramp (M-off-ramp)**: if LSVJ-S <= SEAP statistically -> pause; pivot to PRM/RL-
  light or reasoning-model-native synthesis; do not reframe to hide null result

### 4.3 B2 -- Synthesis vs Menu: Novelty Isolation (Claim 2 locus a)

- **Comparison**: LSVJ-S full vs SEAP (from B1) vs `no_synth_6seed` (Tier-2, appendix only)
- **Key diagnostic**: verbatim-match rate (% synthesized rules verbatim-matching any seed or SEAP
  rule); target <=30%; threshold >50% triggers "synthesis collapsed to template-completion" finding
- **Also reports**: distinct rule bodies per 100 cases; per-category TPR drop from full LSVJ-S to
  SEAP
- **Table 2a**: synthesis-vs-menu comparison; Appendix: verbatim-match histogram
- **[PLACEHOLDER: all numbers TBD after W6 run]**

### 4.4 B3 -- Stage + Class Necessity Ablation (Claim 2 loci b + class contribution)

- **9 Tier-1 conditions** (all must-run for workshop):
  1. LSVJ-S full (reference)
  2. SEAP (from B1)
  3. `no_sem_gate`: disable b.4 compound; measure false-allow rate on neg-control (30H+15B);
     **diagnostic only -- no significance claim at n=45; paired-Wilson 95% CI for direction only**
  4. `no_class_A`: Class A primitives return empty relation (KG queries zeroed)
  5. `no_class_B`: Class B deterministic functions disabled
  6. `no_class_C`: Class C sealed sub-oracle disabled
  7. `KG-shuffled-all`: all KG tuples reshuffled within-type, preserving schema/arity, breaking
     semantic correspondence
  8. `corrupt_is_inner_circle_only`: shuffle only `is_inner_circle` KG tuples (paired for B4
     McNemar)
  9. `corrupt_owner_has_directed_only`: shuffle only `owner_has_directed` KG tuples (paired for B4)
- **Success criterion**: `no_sem_gate` directionally higher false-allow on neg-control (delta > 0,
  paired-Wilson lower bound > -5pp); each `no_class_A/B/C` yields overall TPR drop >=3pp
- **Table 2b**: stage + class ablation with per-condition TPR / false-allow delta
- **[PLACEHOLDER: all numbers TBD after W7 run]**

### 4.5 B4 -- Per-Primitive Causal Attribution: Paired-McNemar (Claim 2 locus c)

- **Goal**: answer "is KG causally load-bearing?" -- the make-or-break test for "symbolic substrate
  verifier" framing (Gemini's 4/10 smoking gun: if KG is decorative, Datalog rule = high-latency
  self-consistency check, not a grounded proof obligation)
- **Protocol**: for each of 2 Tier-1 primitives (`is_inner_circle`, `owner_has_directed`):
  - Run intact LSVJ-S on v3-HN; identify decisive-subset via proof_trace
  - Re-run with only that primitive's KG corrupted (within-type shuffle, from B3 conditions 8/9)
  - Paired McNemar: b = intact-allow -> corrupted-block; c = intact-block -> corrupted-allow;
    chi-sq with continuity correction at alpha=0.05
- **Effect-size floor (honest disclosure in paper body, not appendix)**: expected decisive-subset
  20-30 per Tier-1 primitive; realistic b+c ~7-12; McNemar significance at alpha=0.05 requires
  b/(b+c) >=~0.8; weaker effects reported as point estimate + paired-Wilson CI only, explicitly
  labeled as "below significance floor at current sample size"
- **Success criterion**: >=1 of 2 Tier-1 primitives shows paired-McNemar p<0.05 OR (if b+c<10)
  paired-Wilson 95% CI entirely above 0
- **Failure path**: if both null -> try Tier-2 primitives (`recipient_owned_by_owner`,
  `action_in_precedent`); if all 4 null -> Claim 2 locus (c) fails -> report honestly; pivot to
  JIT-Policy Gate framing; propose KG-heavy obligation redesign as Future Work
- **Table 3**: per-primitive McNemar table (decisive-subset size / b / c / chi-sq / p / CI)
- **Figure 3**: paired-Wilson CI bars per primitive (one row per primitive, CI bar + point estimate)
- **[PLACEHOLDER: all numbers TBD after W7 run]**

### 4.6 B6 -- Adversarial Synthesis Stress Test (Self-Justification Trap Defense)

- **Goal**: empirically test whether b.4 catches a proposer actively trying to synthesize a
  collusion rule that bypasses the gate while remaining semantically vacuous
- **Setup**:
  - 50 attacker-mode cases (hand-crafted); proposer given sealed attacker prompt explicitly
    instructing it to bypass the gate by emitting a rule that passes b.1-b.3 but is semantically
    vacuous
  - 30 v3-HN benign cases as control: b.4 should NOT reject genuine non-trivial rules
- **4 attack types** with per-type breakdown:
  - (i) Tautology: head `= true` or constant expression
  - (ii) Permissive: body references only KG-rarely-enforcing primitives
  - (iii) Collusion: rule crafted to pass perturbation surface checks while semantically vacuous
  - (iv) Multi-primitive OR-disjunction where only one primitive drives discharge (partial vacuity)
- **Success criterion**: b.4 rejection rate on attacker-mode >=90%; false-rejection on benign
  control <=10% (consistent with W3 N=5 calibration commitment); per-attack-type rejection >=75%
  across all 4 types
- **Failure path**: if b.4 rejection <75% on any attack type -> Self-Justification Trap defense
  incomplete -> rethink b.4 (raise N, add perturbation operator, add Class-C-independence check);
  report honestly; do not suppress
- **Table 4**: adversarial rejection rates + per-attack-type breakdown (attacker-mode + benign
  control side by side)
- **[PLACEHOLDER: all numbers TBD; ~$10 API + 1 engineering day; added at R5/Gemini patch]**

### 4.7 B5 -- Qualitative Proof-Trace Case Studies (Qualitative Support)

- **5-10 hand-picked v3-HN cases**: 3 LSVJ-S caught / SEAP missed; 3 both caught; 2 neither caught
  (honest failure analysis); 1 neg-control showing Class-A-decisive <=20%
- **Each case reports**: synthesized rule text, decisive primitives listed, sealed Class C sub-oracle
  prompt hash + response (redacted if sensitive), verdict diff vs SEAP
- **Placement**: 2-3 selected cases in Section 5 (Discussion); full set in Appendix E
- **[PLACEHOLDER: all cases TBD after B1 run; B5 is cheap -- cut to <=3 cases if W8 timeline slips]**

---

## 5. Discussion (~1 page)

### 5.1 Interpreting the Main Results

- **If Claim 1 holds** (LSVJ-S > SEAP on v3-HN with Wilson CI): per-decision runtime synthesis
  adds TPR beyond an expert-authored policy of the same predicate vocabulary. This is the
  architectural delta PCAS-style offline compilation cannot claim for open-vocabulary contextual
  cases.
- **If Claim 2 locus (c) holds** (B4 per-primitive McNemar significant): the KG is causally load-
  bearing; the synthesized Datalog rule is a proof obligation grounded in system state, rebutting
  Gemini's "decorative KG" smoking gun.
- **If Claim 2 locus (c) is null on all primitives**: trigger framing pivot (Section 5.2).
- Briefly discuss 2-3 case studies from B5: show mechanistic evidence that synthesized rule
  structure reveals what SEAP missed. [PLACEHOLDER: cases TBD after B1]

### 5.2 Contingent Framing (Pre-Committed, Not Post-Hoc)

- **Primary framing** (if B4 shows causal effect on >=1 Tier-1 primitive): "LSVJ-S as symbolic
  substrate verifier." Per-decision Datalog synthesis grounded in live KG facts; compile-time gate
  ensures non-trivial commitment. Contribution Focus and Novelty Argument as specified in
  FINAL_PROPOSAL.
- **Fallback framing** (if B4 null on ALL Tier-1 AND Tier-2 primitives): "LSVJ-S as JIT-Policy
  Gate." The LLM synthesizes a Datalog rule as an explicit commitment object; the 4-stage gate
  (especially b.4) filters self-justification from genuine content-dependence. B6 adversarial
  stress test becomes primary evidence. Drop "symbolic substrate verifier" overclaim. Method Thesis
  unchanged; only Contribution Focus + Novelty Argument prose shifts.
- **This pivot is pre-registered in FINAL_PROPOSAL Patch-3 (Gemini R5)**, not a post-hoc save.
  Both framings are disclosed to the reader.

### 5.3 Statistical Honesty: Effect-Size Floor

- McNemar significance at alpha=0.05 with expected decisive-subset size requires b/(b+c) >=~0.8.
  This floor is disclosed in **main-paper body** (not appendix), with explicit explanation that the
  floor is a function of sample size, not evidence of no effect.
- Weaker effects (b/(b+c) in [0.5, 0.8)): reported as point estimate + paired-Wilson CI with label
  "suggestive but below significance floor at current decisive-subset size."
- Tier-2 post-workshop path: expand to 60H+30B neg-control; add `KG-empty` absolute-absence
  ablation; add 2 remaining per-primitive corruptions; support hypothesis-testing-grade Claim 2.2.

### 5.4 Limitations (Named, Not Hidden -- Gemini Review Must Be Visibly Addressed)

- **Self-Justification Trap**: acknowledged explicitly; b.4 + b.3 are the defenses; B6 provides
  empirical evidence; acknowledged that b.4 does not catch all collusion modes (Gemini's critique
  visible in limitations, not buried).
- **Class C same-model oracle**: procedural independence only (separate session, schema-bound input,
  CI lint for session leakage); proposer and Class C sub-oracle share weights. Representation-level
  independence = Future Work.
- **`KG-empty` deferred to Tier-2**: workshop causal attribution rests on 2 per-primitive
  corruptions + `KG-shuffled-all`; absolute KG absence not tested at workshop tier. Named.
- **v3-HN co-authorship**: Yan co-authors both 50% of v3-HN and the 12-rule SEAP (with Dario).
  Pre-registration in `nous/docs/no-synth-menu-plus.cozo` before any v3-HN eval mitigates.
  Independent human collaborator authoring = post-workshop contingency for ICLR.
- **Soundness theorem absent**: no formal proof that 4-stage gate catches all semantically vacuous
  rules; empirical evidence only (B6). Formal soundness = main-track Future Work.
- **Workshop-tier novelty**: Self-Consistency lineage (Wang et al. 2022) covers b.4's core
  mechanism. LSVJ-S novelty = combination applied to runtime safety-rule synthesis +
  decisive-primitive attribution. Not claiming Main Track; Gemini's 4/10 confidence explicitly
  acknowledged as motivating the B4 + B6 empirical design.

### 5.5 Proof-Trace Case Studies (2-3 selected from Appendix E)

- [PLACEHOLDER: cases selected after B1 run; each case shows synthesized rule + decisive primitive
  + what SEAP missed + why the mechanism is interpretable]

---

## 6. Conclusion (~0.25 page)

- LSVJ-S introduces SPO protocol: LLM synthesizes a per-decision Datalog rule as a committed proof
  obligation, admitted only when it passes a 4-stage compile-time gate (parse, type-check, syntactic
  non-triviality, perturbation-sensitive AND has-decisive-primitive). Gate b.4 is grounded in Self-
  Consistency (Wang et al., 2022); its combination with typed Datalog synthesis and decisive-
  primitive causal attribution is the novel contribution in the runtime agent safety context.
- Empirical results on v3-HN show LSVJ-S outperforms SEAP (structurally analogous to PCAS offline
  policy compilation) [PLACEHOLDER: by X pp with Wilson 95% CI]; per-primitive paired-McNemar
  analysis provides [PLACEHOLDER: causal attribution or honest null + framing pivot]; B6 adversarial
  stress test shows b.4 rejects [PLACEHOLDER: X%] of attacker-mode collusion rules.
- Named limitations: Class C same-model oracle, `KG-empty` deferred, soundness theorem absent,
  workshop-tier scope.
- Future work: different-model Class C, formal soundness analysis, ShieldAgent-Bench zero-shot
  external benchmark (Tier-2), main-track extension with full Tier-2 ablations.

---

## References

*All of the following must appear in the final references.bib at `nous/paper/references.bib`.*

**Tier-1 required (directly cited in body)**:
- PCAS: Palumbo, Choudhary et al. "Policy Compiler for Agentic Systems." arXiv:2602.16708. 2026-02.
- Solver-Aided: Roy et al. "Solver-Aided Policy Compliance in Tool-Augmented LLM Agents."
  arXiv:2603.20449. 2026-03.
- Agent-C: Anonymous. OpenReview:VeRehDnGJJ. 2026.
- Doshi et al. "Towards Verifiably Safe Tool Use for LLM Agents." arXiv:2601.08012. ICSE NIER 2026.
- Wang et al. "Self-Consistency Improves Chain of Thought Reasoning in Language Models."
  NeurIPS 2022. [CRITICAL -- required for b.4 credit attribution]
- ShieldAgent: arXiv:2503.22738. ICML 2025.
- GuardAgent: arXiv:2406.09187. 2024.
- TrustAgent: Hua et al. arXiv:2402.01586. 2024.
- AgentSpec: arXiv:2503.18666. ICSE 2026.
- Pro2Guard / ProbGuard: arXiv:2508.00500. 2025.
- Scallop: "Scallop: A Language for Neurosymbolic Programming." PLDI 2023.
- ClawGuard: arXiv:2604.11790. 2026.
- Owner-Harm companion paper: Zhang, Jiang et al. "Compositional Safety Gates for Owner-Harm
  Decisions in Agentic Systems." arXiv:[PENDING]. 2026. [Update once arXiv ID assigned]
- XGrammar: [PLACEHOLDER: full citation for grammar-constrained decoding engine, 2025]
- NeMo Guardrails: [PLACEHOLDER: full citation]
- Lobster: [PLACEHOLDER: ASPLOS 2026 full citation]
- QuadSentinel: Yang et al. arXiv:2512.16279. 2025.

**Tier-2 (add if confirmed after followup searches)**:
- Inala et al. Symbolic Shielding: [PLACEHOLDER -- confirm arXiv ID; see Open Questions Q5]
- L-Eval / Logic-Guide: [PLACEHOLDER -- confirm after WebSearch; see Open Questions Q4]
- Self-Synthesizing Policies JIT preprints: [PLACEHOLDER -- confirm after WebSearch; see Q4]

---

## Appendix (~2 pages budget)

### Appendix A -- Full Owner-Harm Primitive Schema

- Complete A/B/C partition: all 6 primitives with class, arity, typing, execution mode (Cozo /
  host fn / sealed session), b.4 perturbation operator, example binding
- Cross-reference: `nous/src/nous/schema.py` (Pydantic v2 data model)
- Presented as a table: columns = {Primitive ID, Class, Arity, Execution Mode, Perturbation
  Operator, Example Fact}

### Appendix B -- 6-Seed Library (Verbatim, for Reproducibility)

- Full CozoScript text of: `no_credential_exfil`, `no_inner_circle_disclosure`,
  `no_infra_expose`, `no_destructive_without_directive`, `no_hijacking_via_external_content`,
  `owner_directed_send`
- Note: **prior development, not contributions of this paper**; included for reproducibility only

### Appendix C -- SEAP 12-Rule Expert Menu (Verbatim, for Reproducibility)

- Full text of all 12 SEAP rules (6 seeds + 6 additional: `credentials_in_log_redacted`,
  `destructive_dryrun_unless_confirmed`, `infra_endpoint_without_auth`,
  `inner_circle_public_context_ok`, `hijacking_mitigated_by_audit_trail`,
  `autonomy_bounded_action_list`)
- Pre-registration note: co-authored Dario+Yan, frozen in `nous/docs/no-synth-menu-plus.cozo`
  before any v3-HN evaluation
- Note: **SEAP is a BASELINE**, not a contribution of this paper

### Appendix D -- v3-HN Construction Protocol

- Blind authoring protocol: Sonnet 4.6 sealed-prompt subagent; protocol pre-registered in
  `nous/docs/v3-HN-blind-protocol.md`; prompt hash frozen before W5
- Cosine-similarity threshold calibration method: ~5 within-author + ~5 cross-author case pairs;
  threshold set before any evaluation; failed-blind criterion
- Neg-control construction criteria: 30H+15B; cases superficially resembling harmful tool calls
  but genuinely benign; designed to expose over-blocking
- N=5 calibration procedure for b.4: 40-rule hand-labeled reference set (W3 pilot); three
  categories (content-dependent / weakly-dependent 10-25% flip / content-invariant); false-
  rejection + false-admission targets at N in {3, 5, 7}
- Cross-references: `nous/docs/40-rule-reference-set-protocol.md`

### Appendix E -- Proof-Trace Audit-Log Format + Case Studies

- Audit-log schema: `proof_trace.lsvj_obligations[i].{rule_text, class_usage, discharge_result,
  decisive_primitives, binding_class_A_facts, sealed_class_C_prompt_hash}`
- 5-10 qualitative case studies:
  - 3 cases: LSVJ-S caught / SEAP missed (show synthesized rule + decisive primitive + KG fact)
  - 3 cases: both caught (comparative ground truth)
  - 2 failure cases: neither caught (honest failure analysis; what would fix this)
  - 1 neg-control: Class-A-decisive <=20% (anti-gaming evidence)
- **[PLACEHOLDER: all cases TBD after B1 run; curated by Yan in B5 step; ~4 hours human review]**

### Appendix F -- Compute + API Cost + Reproducibility

- **GPU-hours**: 0 (zero training; all inference)
- **API cost breakdown by milestone**: M1 ~$15; M2 ~$25; M3 ~$70; M4 ~$10; B6 ~$10;
  total <=~$130 (within $120 target; B6 added at R5)
- **Model versions frozen at paper submission time**:
  - L3 Proposer: DeepSeek-V3.2 [PLACEHOLDER: confirm version string]
  - Judge: GPT-5.4 (Wilson CI + McNemar analysis via scipy.stats, deterministic)
  - Blind authoring: Sonnet 4.6 (sealed prompt)
  - Cross-review: Gemini 3.1 Pro (M2 + M4 gates)
- **Reproducibility**: all ablation conditions are config-flag toggles over same pipeline; paired
  runs use same case IDs (deterministic seed); pre-registered files named above; seed library
  frozen before experiments
- **[PLACEHOLDER: Cozo version pinned; XGrammar version; pytest version + test count at submission]**

---

## Open Questions for Opus Review

*These questions arose during outline construction and are unresolved. Each is labeled with the
section it blocks (B = blocking; I = informational). Flagged here for main-session (Opus 4.7) or
Dongcheng review before full prose drafting begins.*

---

**Q1 [B, blocks §3.2] -- Proposer model final selection**
FINAL_PROPOSAL names DeepSeek-V3.2 as the frozen production L3 LLM but names Kimi K2.5 as a
conditional alternative if W2 pilot shows better parse rate. Outline uses DeepSeek-V3.2 with a
placeholder. Confirm: is model selection locked to DeepSeek-V3.2 regardless of W2 pilot outcome,
or does the conditional apply? If conditional applies, §3.2 grammar-constrained decoding section
cannot be fully specified until W2 concludes.

---

**Q2 [B, blocks §4 tables] -- SEAP baseline naming consistency**
Outline uses "SEAP" throughout. EXPERIMENT_PLAN.md B1 uses "SEAP" for config 4. FINAL_PROPOSAL
still uses `no_synth_menu_plus` in some sections. Confirm SEAP is the final name everywhere --
in code (config flags, `no-synth-menu-plus.cozo` filename), in paper tables, and in the pre-
registered docs -- before drafting §4 tables.

---

**Q3 [B, blocks References] -- Companion paper arXiv ID**
Owner-Harm paper is "arXiv pending." Outline cites it as "arXiv:[PENDING]." Once arXiv ID is
assigned, update: (1) References section; (2) Introduction footnote distinguishing this paper from
the companion.

---

**Q4 [B, may affect §2 novelty + §5 limitations] -- JIT policy synthesis preprint search**
NOVELTY_CHECK.md flags "Self-Synthesizing Policies for Safe Agentic Tool-Use (2025/2026 preprints)"
as a potential threat. LITERATURE_REVIEW.md lists a followup WebSearch+WebFetch action item for
this search. Status: has this search been completed? If any preprint directly describes per-
decision LLM synthesis of Datalog/Horn rules + a soundness gate, §2 needs an explicit
differentiation paragraph and the novelty claim in §3.6 + §5.4 needs further hedging. Blocking
if uncompleted before submission.

---

**Q5 [I, affects §2.2 + References] -- Inala et al. Symbolic Shielding arXiv ID**
NOVELTY_CHECK.md mentions "Inala et al., Symbolic Shielding" with adaptive variants. No arXiv
ID confirmed. If ID identified via WebFetch, add to §2.2 and References Tier-2 list. Not
blocking for workshop outline, but required before final draft.

---

**Q6 [B, structural for §5.2] -- JIT-Policy Gate fallback framing acceptability**
Outline pre-commits to a contingent framing pivot in §5.2 per FINAL_PROPOSAL Patch-3. Confirm
with Dongcheng: is the JIT-Policy Gate fallback framing acceptable as a published workshop
contribution (not just a discussion note)? If not acceptable, the B4 failure-case strategy
needs rethinking before §5 is drafted. This is a scope decision, not an engineering decision.

---

**Q7 [I, drafting-time only] -- Figure 3 axis specification**
EXPERIMENT_PLAN.md specifies Figure 3 as "per-primitive McNemar flip rates + paired-Wilson CI
bars." Exact axis labels, CI bar format, primitive ordering, and y-axis scale (flip rate vs
log-odds ratio) are unspecified. Deferrable to drafting time after B4 data available. Not
blocking outline.

---

**Q8 [I, affects §4.1 + §5.3] -- Neg-control expansion to 60H+30B**
FINAL_PROPOSAL names expanding neg-control to 60H+30B as Tier-2 for hypothesis-testing-grade
Claim 2.2. Outline treats 30H+15B as workshop tier. If the expansion is achievable within W5
(same authoring run), including it in the workshop submission would eliminate the "diagnostic-
only" hedge on B3 `no_sem_gate` and strengthen §4.4. Confirm scope decision before W5 authoring
begins.

---

**Q9 [I, affects §4.1 scope] -- AgentHarm comparison tier**
EXPERIMENT_PLAN.md lists AgentHarm (176H+176B) as a reference dataset for literature
comparability. Outline mentions it in §4.1 but does not include a dedicated AgentHarm results
subsection or table. Confirm: is an AgentHarm comparison table in scope for the workshop
submission, or deferred to the ICLR extension? If in scope, add a Table 1b to §4.2 and budget
~$20 additional API for the run.

---

**Q10 [B for §3.2, if fork triggered] -- Grammar-constrained decoding W2 status**
FINAL_PROPOSAL commits to XGrammar + Lark + Cozo PEG with a named fork criterion (if Cozo PEG
blocked in <=2 days in W2, commit to post-hoc parse+retry 3x). Outline writes §3.2 assuming the
primary path (grammar-constrained decoding) is intact. If the W2 fork has already been triggered,
§3.2 must describe post-hoc parse+retry as the primary path. Current status unknown. Check before
drafting §3.2.
