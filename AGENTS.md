# AGENTS.md

> **For LLM coding agents.** This file is the industry-standard agent
> context manifest (Linux Foundation Agentic AI specification). If you are
> an agent helping a user with this repository, read this *before* the
> README.

---

## What this project is

Nous is a compositional runtime safety gate for LLM-based autonomous
agents. Every tool call is intercepted and judged by four orthogonal
layers (L1 Datalog blocker → L2 triviality filter → L3 LLM semantic gate
→ L4 deterministic post-gate verifier). Knowledge graph (Cozo) provides
post-gate audit context.

Reference paper: [arXiv:2604.18658](https://arxiv.org/abs/2604.18658).

---

## Setup commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[lsvj,dev]"   # core + grammar + pytest
# Optional, only for KG-bound paths:
pip install -e ".[cozo]"
```

Required env vars (store in project-local `.env`, never commit):

```
ZAI_API_KEY=...           # GLM-4.6 (AgentDojo agent backbone)
DEEPSEEK_API_KEY=...      # DeepSeek-V4-pro (L3 semantic gate)
KIMI_API_KEY=...          # Kimi (only for cases/cccm/ scoring; optional)
```

---

## Build / test / verify

```bash
# Path-independent dependency-light tests (CI runs exactly this):
pytest tests/lsvj/ tests/test_scallop_sidecar.py tests/test_gateway_hook.py -v

# Full suite (requires cozo + lark + per-test fixtures):
pytest tests/ -x --tb=short
```

CI scope is intentionally narrow — full suite needs author-private KG seed.
Don't add tests that require `memory/entities/` to the path-independent CI
subset; gate them with `pytest.mark.skipif(not KG_AVAILABLE, ...)`.

---

## Reproducing every paper number

| Claim (paper §) | Command | API key | Wall-clock |
|---|---|---|---|
| §4 LSVJ-S compile gate (80 tests) | `pytest tests/lsvj/` | none | < 10 s |
| §4 Owner-centric v3 (full L1–L4, 85.3 % / 3.3 %) | `python scripts/full_benchmark_eval.py` | none | ~ 30 s |
| §4 Hijacking layer overlap (11/30/15/4) | `python scripts/eval_d2_verifier.py` | none | ~ 10 s |
| §4 AgentDojo isolation (96.3 % / 75.0 %) | `bash benchmarks/agentdojo_adapter/launch-l3-deepseek-repro.sh` | DeepSeek | ~ 5 h |
| §4 AgentDojo deployment (95.9 % / 75.0 %) | `bash benchmarks/agentdojo_adapter/launch-baseline-l1-rerun.sh` | GLM-4.6 | ~ 5 h |
| §4 AgentHarm val (100 % TPR) | `python scripts/run_agentharm_threelayer_v2.py` | DeepSeek | ~ 1 h |

Full table with expected output and variance budget:
[REPRODUCIBILITY.md](REPRODUCIBILITY.md).

---

## Code layout (where to look)

```
src/nous/                     core decision pipeline
├── gate.py                   main entry: gate(tool_call, ...) -> Verdict
├── constraint_parser.py      YAML constraint loader
├── semantic_gate.py          L3 LLM gate (minimal-pair prompting, k-vote)
├── verifier.py               L4 deterministic post-gate audit
├── proof_trace.py            decision audit trail
├── markov_blanket.py         KG-bounded context retrieval
├── fact_extractor.py         tool-call → facts for L1
├── providers/                LLM provider wrappers (OpenAI-compatible)
├── db.py                     Cozo embedded KG wrapper
└── lsvj/                     LSVJ-S compile-time gate (companion direction)

ontology/constraints/         46 YAML constraints (T3 destructive,
                              T5 social URL, T10 oversize write, owner-harm
                              specific rules)
ontology/schema/              KG entity/relation schema, frozen v0.1.0
benchmarks/agentdojo_adapter/ AgentDojo deployment-mode wrapper +
                              Iter1 (T3 owner-authorised delete) +
                              Iter2 (target-mismatch, currently disabled)
data/owner_harm_heldout_v3.json   300 H + 150 B held-out slice (paper §3.3)
paper/main-neurips-2026.tex   NeurIPS 2026 E&D Track submission
paper/main-tmlr.tex           TMLR rolling-track variant
```

---

## Conventions

- Python 3.11+ syntax, type hints on public APIs, no `from __future__`
  unless required.
- Constraints live in `ontology/constraints/*.yaml`. Use `enabled: false`
  to soft-disable; do not delete files.
- Tests for `src/nous/X.py` go in `tests/test_X.py`. KG-bound tests must
  start with `pytestmark = pytest.mark.skipif(not KG_AVAILABLE, …)` (see
  `tests/test_owl_rules.py` for canonical form).
- Constraint priorities are integers in `[1, 100]`. T-rules use 100;
  AgentDojo-specific iterations use 90–95.
- Decision verdict is one of: `allow` | `confirm` | `block`. Never invent
  new verdict strings.

---

## Hard rules for AI agents acting on this repo

1. **Never commit secrets.** `.env`, hard-coded API keys in source, or
   any string matching `sk-[a-zA-Z]{2,}-[A-Za-z0-9]{20,}` is a release
   blocker. Source code that needs an API key reads it from env and
   `raise RuntimeError` if missing — see `cases/cccm/framework/scorer_subscription.py`
   for the canonical fail-fast pattern.
2. **Never re-introduce paths that are in `.gitignore`.** Large blocks of
   the repo (`docs/`, `refine-logs/`, `cases/medical/`, `logs/`,
   `cases/cccm/`, `cases/code-sec/`, `cases/privacy/`, dev-only `tests/test_loop*`,
   etc.) are local-only; the public surface is intentionally small.
3. **Never weaken `.github/workflows/test.yml`** to silence failing tests.
   If a test fails because of a missing fixture on the runner, mark it
   `pytest.mark.skipif(not KG_AVAILABLE, …)`; if it fails because of a real
   regression, fix the regression.
4. **Force-pushes to `main` require explicit user approval.** History
   has been rewritten before; the user is the only authority on whether
   another rewrite is acceptable.
5. **Tests must be deterministic at temperature 0.** L3 semantic-gate
   tests use `k=5` majority vote; isolation-mode results stay within ±1 pp
   across runs.

---

## Known pitfalls

- `pycozo[embedded]` Linux wheels segfault on Ubuntu 24.04 glibc; CI
  pins to a path-independent subset to dodge this. macOS and Ubuntu 22.04
  are safe.
- `memory/entities/` KG seed is host-private. Anything that walks it
  must skip cleanly when absent (see `tests/_paths.py:KG_AVAILABLE`).
- `cases/cccm/framework/scorer_subscription.py` is local-only (in
  `.gitignore`); changes there are not reviewed and do not run in CI.
- `paper/main-neurips-2026.tex` references commit `3e688d6` in the
  Erratum — that SHA refers to the pre-sanitization history and is *not*
  reachable from current `main`. The reference is preserved as a
  historical fact, not as a Git pointer.

---

## Don't read these (size / signal-to-noise)

- `data/owner_harm_heldout_v3.json` (9 314 lines; the dataset itself).
  Read the schema and a few samples; don't load it into context wholesale.
- `docs/agentharm-raw-scenarios.json` (8 565 lines; AgentHarm raw data).
- `paper/main-*.pdf` (binary).
- `paper/arxiv-submission/` (zipped paper bundle).

If you must inspect any of these, grep with a specific pattern; do not
include them in a context window dump.
