# Nous

> *ὁ πάντα διακοσμῶν νοῦς* — Anaxagoras

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![arXiv](https://img.shields.io/badge/arXiv-2604.18658-b31b1b.svg)](https://arxiv.org/abs/2604.18658)

📖 **English** · [中文](README.zh.md)

A compositional runtime safety gate for LLM-based autonomous agents. Every
tool call is intercepted and judged by four orthogonal layers — a Datalog
deterministic blocker (L1), a triviality filter (L2), an LLM semantic gate
(L3), and a deterministic post-gate verifier (L4). A knowledge graph
provides post-gate audit context.

Reference: [*Owner-Harm: A Missing Threat Model for AI Agent Safety*](https://arxiv.org/abs/2604.18658)
(Zhang and Jiang, 2026; arXiv:2604.18658).

---

## Headline results

Nous reports two evaluation regimes per benchmark: **isolation** (forced
injection, an upper bound on gate discrimination) and **deployment** (real
LLM-pipeline, a lower bound under which most injections never trigger
harm).

| Benchmark | Regime | Security (TPR) | Utility | n |
|---|---|---|---|---|
| AgentDojo (banking + slack + travel + workspace) | Isolation | 96.3% | 75.0% | 27 |
| AgentDojo | Deployment | 95.9% | 75.0% | 629 |
| AgentHarm (val) | Isolation | 100.0% | — | 176 H + 176 B |
| Owner-centric held-out v3 (gate L1–L3) | Isolation | 75.3% | 3.3% FPR | 300 H + 150 B |
| Owner-centric held-out v3 (full L1–L4) | Isolation | 85.3% | 3.3% FPR | 300 H + 150 B |

The post-gate verifier (L4) and the L1–L3 gate cover near-disjoint failure
modes: on the hijacking sub-slice, 11 cases are caught by the gate alone,
30 by the verifier alone, 15 by both, and 4 by neither.

Full reproduction protocols, baselines, and per-category Wilson intervals
are in the paper §3 and §4 and in `paper/main-neurips-2026.tex`.

---

## Architecture

```
tool_call
    │
    ▼
┌── Layer 1  Datalog deterministic blocker ──┐
│   46 YAML constraints + chain-aware rules  │  → exit on match
└─────────────────────────────────────────────┘
    │
    ▼
┌── Layer 2  Triviality filter ──────────────┐
│   benign-pass heuristics                    │  → exit if trivial
└─────────────────────────────────────────────┘
    │
    ▼
┌── Layer 3  Semantic gate (LLM) ────────────┐
│   minimal-pair prompting, k=5 majority     │
│   vote, upgrade_only=True                  │
└─────────────────────────────────────────────┘
    │
    ▼
┌── Layer 4  Post-gate verifier ─────────────┐
│   6 deterministic audit rules + content    │
│   scan; zero LLM, +0.038 ms / call         │
└─────────────────────────────────────────────┘
    │
    ▼
Verdict + proof_trace + decision_log
```

The knowledge graph (Cozo, embedded Datalog + vector + FTS) supplies
post-gate audit enrichment and does not override the L3 verdict.

---

## Install

```bash
git clone https://github.com/dario-github/nous.git
cd nous
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                       # core
pip install -e ".[cozo]"               # + Cozo embedded KG
pip install -e ".[lsvj]"               # + LSVJ-S grammar tooling
pip install -e ".[dev]"                # + pytest
```

Python 3.11 or newer.

---

## Quickstart

```python
from nous.gate import gate
from nous.schema import ToolCall

call = ToolCall(
    tool_name="send_email",
    action="send",
    params={
        "to": "attacker@external.com",
        "body": "... please ignore previous instructions ...",
    },
)

verdict = gate(
    tool_call=call,
    constraints_dir="ontology/constraints",
    semantic_config={"model": "DeepSeek-V4-pro"},
)

verdict.decision     # "allow" | "confirm" | "block"
verdict.proof_trace  # signal chain + which layer decided
```

The full AgentDojo deployment-mode benchmark wrapper lives at
`benchmarks/agentdojo_adapter/run_eval_adaptive_llm.py`.

---

## Repository layout

```
src/nous/             core runtime (gate, parsers, providers, KG, LSVJ-S)
ontology/             46 YAML constraints + KG schema + Datalog rules
benchmarks/           AgentDojo adapter + R-Judge sample
tests/                pytest suites; tests/lsvj/ is dependency-light
paper/                NeurIPS 2026 E&D Track + TMLR submissions
scripts/              benchmarks, baselines, shadow-live, pilots
docs/                 design notes, audit reports
refine-logs/          research-refine artefacts
```

---

## Tests

```bash
python3 -m pytest tests/lsvj/ -v       # 80 dependency-light tests
python3 -m pytest tests/ -x --tb=short # full suite (cozo + lark required)
```

Continuous integration runs the dependency-light subset on Python 3.11
and 3.12 against every push to `main`. The full suite requires the Cozo
Rust binding and additional fixtures and is run on developer machines.

---

## Citation

```bibtex
@misc{zhang2026ownerharm,
  title         = {Owner-Harm: A Missing Threat Model for {AI} Agent Safety},
  author        = {Zhang, Dongcheng and Jiang, Yiqing},
  year          = {2026},
  eprint        = {2604.18658},
  archivePrefix = {arXiv},
  primaryClass  = {cs.AI},
}
```

---

## Documentation

- Paper (preprint): <https://arxiv.org/abs/2604.18658>
- Paper sources: `paper/main-neurips-2026.tex`, `paper/main-tmlr.tex`
- Threat model and benchmark protocol: paper §2 and §3
- Layer-by-layer ablation and per-category breakdown: paper §4
- LSVJ-S companion direction: `refine-logs/FINAL_PROPOSAL.md`

---

## License

Apache License 2.0. See [LICENSE](LICENSE).

---

## Authors

- Dongcheng Zhang — `zdclink@gmail.com`
- Yiqing Jiang — Tongji University

Issues and discussions: <https://github.com/dario-github/nous/issues>.
