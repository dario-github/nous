# Nous (νοῦς)

> *ὁ πάντα διακοσμῶν νοῦς* — "the ordering mind that makes cosmos out of chaos." (Anaxagoras)

📖 **Read this in:** **English** · [中文](README.zh.md)

**A compositional runtime safety gate for LLM-based autonomous agents.**
Every tool call is intercepted and judged by four orthogonal layers — a Datalog
deterministic blocker (L1), a triviality filter (L2), an LLM semantic gate
(L3), and a deterministic post-gate verifier (L4) — with a knowledge graph
providing post-gate audit context.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## Status

| Aspect | State |
|---|---|
| Paper v1 | *"Owner-Harm: A Missing Threat Model for AI Agent Safety"* — [arXiv:2604.18658](https://arxiv.org/abs/2604.18658) (2026-04-20, primary `cs.AI`, cross-list `cs.CR`, `cs.CL`) |
| Paper v2 | NeurIPS 2026 Evaluations & Datasets Track + TMLR rolling, with §Limitations Erratum and dual-metric framing (isolation + deployment). Submission window: 2026-05-04 abstract / 2026-05-06 full |
| Test suite | 1248 collected (`tests/lsvj/` 80 isolated; full suite passes with optional Cozo + Lark deps) |
| Production deployment | Shadow + primary on the first author's personal Claude Code harness (non-public workload) |
| License | Apache 2.0 |

---

## Paper results (headline, v2)

The v2 paper reports the gate under **two regimes** because the original v1
isolation-mode number is, in retrospect, an upper bound that does not survive
the deployment LLM-pipeline:

| Benchmark | Regime | Security (TPR) | Utility | Notes |
|---|---|---|---|---|
| AgentDojo (banking + slack + travel + workspace, 27 injection × 15 user) | **Isolation** (forced injection, n=27) | 96.3% | 75.0% | full L1+L3+L4 stack, deepseek-v4-pro substitute |
| AgentDojo | **Deployment** (real GLM-4.6 agent pipeline, n=629) | 95.9% | 75.0% | full stack vs. baseline 95.2% / 79.0% |
| AgentHarm val (176H + 176B) | Isolation | 100.0% | — | (90.3%, 100.0%) — generic criminal-harm scope |
| Owner-centric held-out v3 (300H + 150B) | Gate only (L1–L3) | 75.3% | 3.3% FPR | author-constructed slice; protocol in paper §3.3 |
| Owner-centric held-out v3 | Full (L1–L4) | 85.3% | 3.3% FPR | post-gate verifier closes 30 hijacking cases gate misses |

The v1 published number `L1+L3+L4 = 14.8% (4/27)` on AgentDojo is preserved
in the §Limitations Erratum as a non-reproducible reading: it depended on
the specific `qwen-turbo` configuration via a now-deprecated internal
OpenAI-compatible relay. The deepseek-v4-pro reproducible substitute lands at
**3.7% (1/27)** isolation-mode, fully consistent with v2 dual-metric framing.

The layer-complementarity finding remains stable across both regimes: gate
(L1–L3) and post-gate verifier (L4) have nearly disjoint blind spots on
hijacking — 11 caught by gate only, 30 by verifier only, 15 by both, 4 by
neither.

---

## Architecture

```
tool_call
    ↓
┌── Layer 1  Datalog deterministic blocker ──┐
│   46 YAML constraints + chain-aware rules  │  → exit if match
│   T3 honours user-authorised deletes       │
└─────────────────────────────────────────────┘
    ↓
┌── Layer 2  Triviality filter ──────────────┐
│   lightweight benign-pass heuristics        │  → exit if trivial
└─────────────────────────────────────────────┘
    ↓
┌── Layer 3  Semantic gate (LLM) ────────────┐
│   DeepSeek-V4-pro, minimal-pair prompting, │
│   majority vote k=5, upgrade_only=True     │
└─────────────────────────────────────────────┘
    ↓
┌── Layer 4  Post-gate Verifier ─────────────┐
│   6 deterministic audit rules + content    │
│   scan, zero LLM, +0.038 ms / call         │
└─────────────────────────────────────────────┘
    ↓
Verdict + proof_trace + decision_log
```

The knowledge graph (Cozo, embedded Datalog + vector + FTS) feeds post-gate
audit enrichment; it does **not** override L3's verdict. Honest note:
production DB coverage is currently under-seeded (see Limitations).

### Recent iterations on the AgentDojo adapter

- **Iter 1 — owner-authorised destructive ops (T3 exemption).** When the
  user goal explicitly authorises a delete, T3 no longer hard-blocks. Validated
  on the workspace suite: utility recovers from 75.8% → 79.2% (+3.4 pp).
- **Iter 2 — target-identifier alignment** (`AD-target-mismatch.yaml`).
  Drafted to block external-effect actions whose target email/IBAN/URL is
  absent from the user goal. Disabled in this release: a full-matrix run
  showed −23 pp slack utility from false positives on `invite_user` /
  `add_user_to_channel` operations whose target is implicit. Kept under
  `enabled: false` pending precision rework.

---

## Install

```bash
git clone https://github.com/dario-github/nous.git
cd nous
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                       # core
pip install -e ".[cozo]"               # + Cozo embedded KG (Rust backend via pycozo[embedded])
pip install -e ".[lsvj]"               # + LSVJ-S grammar tooling (lark)
pip install -e ".[dev]"                # + pytest
```

Python 3.11+ required. Cozo and Lark are optional; the LSVJ smoke test
suite skips when they are unavailable.

---

## Quickstart — gate a tool call

```python
from nous.gate import gate
from nous.schema import ToolCall

call = ToolCall(
    tool_name="send_email",
    action="send",
    params={"to": "attacker@external.com", "body": "... please ignore previous instructions ..."},
)

verdict = gate(
    tool_call=call,
    constraints_dir="ontology/constraints",
    semantic_config={"model": "DeepSeek-V4-pro"},  # set NOUS_API_KEY in env
)

print(verdict.decision)     # allow / confirm / block
print(verdict.proof_trace)  # chain of signals + which layer decided
```

See `benchmarks/agentdojo_adapter/run_eval_adaptive_llm.py` for the full
AgentDojo deployment-mode benchmark wrapper.

---

## Repository layout

```
src/nous/                        Core runtime
├── gate.py                      Main decision pipeline (L1→L4)
├── constraint_parser.py         YAML constraint loader
├── semantic_gate.py             L3 LLM gate with minimal-pair prompting
├── proof_trace.py               Decision audit trail
├── markov_blanket.py            KG-bounded context retrieval
├── providers/                   LLM provider wrappers (OpenAI-compatible)
├── db.py                        Cozo wrapper (KG storage + queries)
└── lsvj/                        LSVJ-S in-progress module (see Roadmap)

ontology/
├── constraints/                 46 YAML constraint rules (T3, T5, T10, owner-harm)
├── schema/                      KG entity/relation schema + LSVJ-S primitive schema
└── rules/                       Datalog rule files

benchmarks/
├── agentdojo_adapter/           AgentDojo deployment-mode wrapper + Iter1/2 patches
└── rjudge_sample/               R-Judge personal-agent records (24, sha256-frozen)

tests/                           1248 pytest tests; tests/lsvj/ 80 isolated
paper/                           main-neurips-2026.tex (NeurIPS 2026 E&D Track)
                                 main-tmlr.tex (TMLR rolling)
                                 main-v2.tex / main-neurips.tex (legacy v1)
scripts/                         Benchmarks, baselines, shadow-live, pilot runners
docs/                            Loop logs, audit reports, research notes
refine-logs/                     Research-refine artefacts (5 rounds + raw audits)
```

---

## Run the tests

```bash
cd nous
python3 -m pytest tests/lsvj/ -v       # LSVJ-S M0 skeleton (80 tests, no Cozo needed)
python3 -m pytest tests/ -x --tb=short # full suite (requires optional deps)
```

CI runs against Python 3.11 and 3.12 on every push to `main` (see
`.github/workflows/test.yml`).

---

## Limitations (honest)

Independent audits (GPT-5.4 2026-03-15, Codex 2026-03-20, Gemini 3.1 Pro
2026-04-18) and post-submission reviewer feedback surfaced the following
real constraints. We document them rather than bury them:

1. **Knowledge graph is currently under-seeded in production.** The
   `kg_context` in L3 is therefore sparse; `no_kg` ablation on the training
   set shows ΔL = 0 (decorative on train); held-out value is still being
   quantified.
2. **Per-category 95% Wilson intervals** are reported in the paper for
   reader scrutiny; some sub-slices are small (n < 30).
3. **Owner-Harm Benchmark is author-constructed.** The 300H+150B v3
   held-out slice was authored by the first author after iterative rule
   tuning; see paper §3.3 for the protocol. Independent replication is
   planned.
4. **L4 Post-Gate Verifier uses regex + taint patterns, not semantic
   reasoning.** Its 4 structural-boundary hijacking misses (SQL injection
   via `mysql prod_db < file.sql`; direct SSH key injection) are listed
   explicitly as out-of-scope.
5. **Two regimes, two numbers.** Isolation-mode (forced injection) is an
   upper bound for the gate's discrimination; deployment-mode (real
   LLM-pipeline) is a lower bound because most injections never trigger
   harm in the first place. Reviewers should evaluate the gate against
   both and not against either alone.
6. **v1 §4.2 number is non-reproducible.** The published `14.8%` on
   AgentDojo depended on a `qwen-turbo`-via-deprecated-internal-relay
   configuration; the deepseek-v4-pro substitute reproduces at `3.7%`
   isolation / `95.9%` deployment. v2 carries the Erratum.

---

## Roadmap — LSVJ-S (in progress)

A companion direction — *LLM-Synthesized, Symbolically-Verified Judgments* —
is being developed to address the "L1+L2-only 12.7% TPR on held-out"
pathology. The LLM synthesises a per-decision Datalog proof obligation
which is checked by a 4-stage compile-time gate (parse + type-check +
syntactic non-triviality + compound: **perturbation-sensitive ∧
has-decisive-primitive**) before execution. A companion preprint is in
preparation; the M0 sanity skeleton is in `src/nous/lsvj/` (80 tests
green).

Design decisions and 2026-Q1 prior-art review are in
`refine-logs/FINAL_PROPOSAL.md`, `refine-logs/REVIEW_SUMMARY.md`, and
`docs/cozo-lark-fork-decision.md`.

Closest prior art (cited in the paper and differentiated):
- **PCAS** (Palumbo, Choudhary et al., 2026-02) — offline-compiled Datalog policy
- **ShieldAgent** (ICML 2025) — probabilistic rule circuits
- **GuardAgent** (2024) — plan-then-code + I/O audit
- **AgentSpec** (ICSE 2026) — custom DSL runtime enforcement
- **Solver-Aided** (2026-03) — NL → SMT policy compilation
- **Agent-C** (2026) — decoding-time SMT constrained generation

---

## Citation

```bibtex
@misc{zhang2026ownerharm,
  title         = {Owner-Harm: A Missing Threat Model for {AI} Agent Safety},
  author        = {Zhang, Dongcheng and Jiang, Yiqing},
  year          = {2026},
  howpublished  = {arXiv preprint arXiv:2604.18658},
  note          = {Primary: cs.AI; cross-list: cs.CR, cs.CL}
}
```

Available at <https://arxiv.org/abs/2604.18658> (v1 submitted 2026-04-20;
v2 with §Limitations Erratum forthcoming).

---

## Contact

- **Dongcheng Zhang** (first author) — `zdclink@gmail.com`
  (Work performed while at BlueFocus Communication Group, Beijing.)
- **Yiqing Jiang** (knowledge-graph specialist) — Tongji University, Shanghai.

Issues + discussions: [github.com/dario-github/nous/issues](https://github.com/dario-github/nous/issues).

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) for the full text. In short:
you can use, modify, and redistribute Nous in any context (including
commercial) provided you preserve the copyright notice and the license
text. Patent grants and trademark protections are covered by the licence.
