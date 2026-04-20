# Nous (νοῦς)

> *ὁ πάντα διακοσμῶν νοῦς* — "the ordering mind that makes cosmos out of chaos." (Anaxagoras)

**A compositional runtime safety gate for LLM-based autonomous agents.**
Every tool call is intercepted and judged by four orthogonal layers — a Datalog
deterministic blocker, a triviality filter, an LLM semantic gate, and a
deterministic post-gate verifier — with the knowledge graph providing
post-gate audit context.

---

## Status

| Aspect | State |
|---|---|
| Paper | *"Owner-Harm: A Missing Threat Model for AI Agent Safety"* — submitted to arXiv (2026-04, primary `cs.AI`, cross-list `cs.CR`, `cs.CL`); preprint link TBD after moderation |
| Test suite | 829 tests collected; `tests/lsvj/` 80 green in 0.03s |
| Production deployment | Shadow + primary on author's personal Claude Code harness (non-public workload) |
| License | TBD — intended Apache 2.0 at v1.0 |

---

## Paper results (headline)

| Benchmark | Config | TPR | FPR | 95% CI |
|---|---|---|---|---|
| AgentHarm val (176H+176B, generic criminal harm) | full L1–L3 | **100.0%** | **0.0%** | (90.3%, 100.0%) / (0.0%, 9.7%) |
| AgentDojo injection tasks (prompt-injection-mediated owner harm) | full system | 14.8% (4/27) | — | (5.9%, 32.5%) |
| Owner-centric held-out v3 (300H+150B) | gate only (L1–L3) | 75.3% | 3.3% | (70.2%, 79.9%) / (1.4%, 7.6%) |
| Owner-centric held-out v3 | **full (L1–L4)** | **85.3%** | **3.3%** | (80.9%, 88.9%) |
| Hijacking sub-slice (60H) | gate only (43.3%) → full (L4-added) | **93.3%** | 0.0% | (84.1%, 97.4%) |

The layer-complementarity finding: gate (L1–L3) and post-gate verifier (L4)
have nearly disjoint blind spots on Hijacking — 11 caught by gate only, 30 by
verifier only, 15 by both, 4 by neither (genuine structural boundary).

---

## Architecture

```
tool_call
    ↓
┌── Layer 1  Datalog deterministic blocker ──┐
│   46 YAML constraints + chain-aware rules  │  → exit if match
└─────────────────────────────────────────────┘
    ↓
┌── Layer 2  Triviality filter ──────────────┐
│   lightweight benign-pass heuristics        │  → exit if trivial
└─────────────────────────────────────────────┘
    ↓
┌── Layer 3  Semantic gate (LLM) ────────────┐
│   DeepSeek-V3.2, minimal-pair prompting,   │
│   majority vote k=3, upgrade_only=True     │
└─────────────────────────────────────────────┘
    ↓
┌── Layer 4  Post-gate Verifier ─────────────┐
│   6 deterministic audit rules + D2 file    │
│   content scan, zero LLM, +0.038 ms / call │
└─────────────────────────────────────────────┘
    ↓
Verdict + proof_trace + decision_log
```

The knowledge graph (Cozo, embedded Datalog + vector + FTS) provides
post-gate audit enrichment; it does **not** override L3's verdict. Honest
note: production DB coverage is currently under-seeded (see Limitations).

---

## Install

```bash
git clone https://github.com/dario-github/nous.git
cd nous
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                       # core
pip install -e ".[cozo]"               # + Cozo embedded KG
pip install -e ".[lsvj]"               # + LSVJ-S grammar tooling (lark)
pip install -e ".[dev]"                # + pytest
```

Python 3.11+ required. Cozo is optional — tests pass without it.

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
    semantic_config={"model": "DeepSeek-V3.2"},  # requires NOUS_API_KEY
)

print(verdict.decision)     # allow / confirm / block
print(verdict.proof_trace)  # chain of signals + which layer decided
```

See `scripts/run_owner_harm_benchmark.py` for a full benchmarking example.

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

tests/                           829 pytest tests; tests/lsvj/ 80 isolated
paper/                           main-v2.tex (CRAI 2026 IEEE) + main-neurips.tex (arXiv)
scripts/                         Benchmarks, baselines, shadow-live, pilot runners
docs/                            Loop logs, audit reports, research notes
```

---

## Run the tests

```bash
cd nous
python3 -m pytest tests/lsvj/ -v       # LSVJ-S M0 skeleton (80 tests, no Cozo needed)
python3 -m pytest tests/ -x --tb=short # full suite (requires optional deps)
```

---

## Limitations (honest)

Independent audits (GPT-5.4 2026-03-15, Codex 2026-03-20, Gemini 3.1 Pro
2026-04-18) surfaced the following real constraints. We document them here
rather than bury them:

1. **Knowledge graph is currently under-seeded in production.** The
   production `nous.db` has a small number of owner-harm entities; seeding
   scripts exist (`scripts/seed_*.py`) but have not been run at scale in
   production deployments. The `kg_context` in L3 is therefore sparse.
   `no_kg` ablation on the training set shows ΔL = 0 (decorative on train);
   held-out value is still being quantified.
2. **Evaluation samples in some categories are small.** Per-category 95%
   Wilson intervals are reported in `paper/main-v2.tex` and `main-neurips.tex`
   for reader scrutiny.
3. **Owner-Harm Benchmark is author-constructed.** The 300H+150B v3
   held-out slice was authored by the first author after iterative rule
   tuning; see paper §3.3 for the protocol. Independent replication is
   planned.
4. **L4 Post-Gate Verifier uses regex + taint patterns, not semantic
   reasoning.** Its 4 structural-boundary Hijacking misses (SQL injection
   via `mysql prod_db < file.sql`; direct SSH key injection) are listed
   explicitly as out-of-scope.
5. **Evaluation mode in AgentDojo is ground-truth**; real-world adaptive
   adversaries may achieve different results.

---

## Roadmap — LSVJ-S (in progress)

A companion direction — *LLM-Synthesized, Symbolically-Verified Judgments* —
is being developed to address the "L1+L2-only 12.7% TPR on held-out"
pathology. The LLM synthesizes a per-decision Datalog proof obligation
which is checked by a 4-stage compile-time gate (parse + type-check +
syntactic non-triviality + compound: **perturbation-sensitive ∧
has-decisive-primitive**) before execution. A companion preprint is in
preparation; M0 sanity skeleton is in `src/nous/lsvj/` (80 tests green).

Design decisions and 2026-Q1 prior-art review are in
`refine-logs/FINAL_PROPOSAL.md`, `refine-logs/LITERATURE_REVIEW.md`, and
`docs/cozo-lark-fork-decision.md`.

Closest prior art (cited in paper and differentiated):
- **PCAS** (Palumbo, Choudhary et al., 2026-02) — offline-compiled Datalog policy
- **ShieldAgent** (ICML 2025) — probabilistic rule circuits
- **GuardAgent** (2024) — plan-then-code + I/O audit
- **AgentSpec** (ICSE 2026) — custom DSL runtime enforcement
- **Solver-Aided** (2026-03) — NL → SMT policy compilation
- **Agent-C** (2026) — decoding-time SMT constrained generation

---

## Citation

BibTeX (once arXiv preprint ID is assigned):

```bibtex
@misc{zhang2026ownerharm,
  title         = {Owner-Harm: A Missing Threat Model for {AI} Agent Safety},
  author        = {Zhang, Dongcheng and Jiang, Yiqing},
  year          = {2026},
  howpublished  = {arXiv preprint arXiv:XXXX.XXXXX},
  note          = {Primary: cs.AI; cross-list: cs.CR, cs.CL}
}
```

Update the `arXiv:XXXX.XXXXX` field after moderation completes.

---

## Contact

- **Dongcheng Zhang** (first author) — `zdclink@gmail.com`
  (Work performed while at BlueFocus Communication Group, Beijing.)
- **Yiqing Jiang** (knowledge-graph specialist) — Tongji University, Shanghai.

Issues + discussions: [github.com/dario-github/nous/issues](https://github.com/dario-github/nous/issues).

---

## License

License selection is pending the v1.0 release. Intended: Apache 2.0.
Until then, the repository is provided for academic review and
non-commercial research use; contact the authors for commercial inquiries.
