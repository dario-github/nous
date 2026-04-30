# Reproducibility

Artefact-level reproduction guide for *Owner-Harm: A Missing Threat Model
for AI Agent Safety* (Zhang and Jiang, 2026; arXiv:2604.18658). Every
table and headline number in §4 of the paper has a corresponding entry
point below.

---

## Reproduction matrix

| Paper claim | Entry point | LLM API | Wall-clock | Hardware |
|---|---|---|---|---|
| §1 — LSVJ-S compile-time gate (80 tests pass) | `pytest tests/lsvj/` | none | < 10 s | any |
| §4 Owner-centric v3 — full L1–L4 (85.3% TPR / 3.3% FPR) | `python scripts/full_benchmark_eval.py` | none (deterministic) | ~ 30 s | any |
| §4 Owner-centric v3 — gate ∩ verifier overlap (Hijacking) | `python scripts/eval_d2_verifier.py` | none | ~ 10 s | any |
| §4 AgentDojo — isolation (96.3% / 75.0%) | `bash benchmarks/agentdojo_adapter/launch-l3-deepseek-repro.sh` | DeepSeek v4-pro | ~ 5 h | 1 process, 1 GPU not required |
| §4 AgentDojo — deployment (95.9% / 75.0%) | `bash benchmarks/agentdojo_adapter/launch-baseline-l1-rerun.sh` | GLM-4.6 | ~ 5 h | same |
| §4 AgentHarm val (100% TPR) | `python scripts/run_agentharm_threelayer_v2.py` | DeepSeek v4-pro | ~ 1 h | same |

---

## Setup

```bash
git clone https://github.com/dario-github/nous.git
cd nous
python3 -m venv .venv && source .venv/bin/activate

pip install -e ".[lsvj,dev]"
# Optional, only needed for KG-bound and DB-bound tests:
pip install -e ".[cozo]"
```

Python 3.11 or 3.12 is required.

API keys — store in a project-local `.env` (already in `.gitignore`):

```
ZAI_API_KEY=...           # GLM-4.6 (AgentDojo agent backbone, deployment runs)
DEEPSEEK_API_KEY=...      # DeepSeek-V4-pro (L3 semantic gate, isolation runs)
```

The launch scripts source `.env` automatically.

### AgentDojo benchmark

The AgentDojo benchmark is a separate, public, MIT-licensed package and
is **not vendored** in this repository:

```bash
# adjacent to nous/, so benchmarks/agentdojo_adapter/ can find it via ../agentdojo
git clone https://github.com/ethz-spylab/agentdojo.git
cd agentdojo && pip install -e . && cd -
```

### Known issues

* **`cozo_embedded` wheels on Ubuntu 24.04 occasionally segfault** under
  Python 3.11 / 3.12; the repository’s CI pins to a tested subset
  (`tests/lsvj/`, `tests/test_scallop_sidecar.py`, `tests/test_gateway_hook.py`).
  On macOS and on Ubuntu 22.04 the full `pytest tests/` suite runs cleanly.
* **`memory/entities/` KG seed is host-private.** Tests that walk the
  personal KG are decorated with `pytest.mark.skipif(not KG_AVAILABLE)`
  and are silent on a clean clone. The numbers in the paper do not
  depend on those tests passing.

---

## §4 — Owner-centric v3 (full L1–L4)

The held-out set `data/owner_harm_heldout_v3.json` (300 harmful + 150
benign) ships with the repository. The full L1–L4 reproduction is
deterministic (no LLM call) because L3 verdicts on this slice are
checkpointed in the evidence table; only L1 and L4 are recomputed.

```bash
python scripts/full_benchmark_eval.py
```

Expected output (matches paper Table 4):

```
OVERALL (300H + 150B)
Gate alone:      TPR 226/300 = 75.3%  FPR 5/150 = 3.3%
Verifier alone:  TPR 195/300 = 65.0%
Combined:        TPR 256/300 = 85.3%  FPR 5/150 = 3.3%

HIJACKING OVERLAP ANALYSIS (60H)
Gate alone:     26/60 = 43.3%
Verifier alone: 45/60 = 75.0%
Combined:       56/60 = 93.3%
  Gate-only:     11
  Verifier-only: 30
  both:          15
  neither:       4
```

The `Gate alone` row reproduces the L1–L3 baseline (75.3% TPR / 3.3% FPR);
the `Combined` row reproduces the full L1–L4 stack (85.3% TPR /
3.3% FPR). Per-category Wilson 95% CIs match paper §4 Table 4.

---

## §4 — AgentDojo isolation (96.3% / 75.0%)

This is the L1 + L3 + L4 stack on AgentDojo's 27 forced-injection
ground-truth tasks (banking + slack + travel + workspace). L3 uses
DeepSeek-V4-pro as the public substitute for the original
qwen-turbo-via-internal-relay configuration (paper §Limitations Erratum).

```bash
export DEEPSEEK_API_KEY=...   # or set in .env
bash benchmarks/agentdojo_adapter/launch-l3-deepseek-repro.sh
```

The script launches a `screen` session named `nous-l3-deepseek-repro`,
takes ~ 5 h, and writes the per-task JSON traces to
`benchmarks/agentdojo_adapter/results-l3-repro/` and a summary JSON at
`results-l3-repro/l1_3_4_deepseek-glm-fullmatrix.json`.

Expected aggregate:

```
banking   security 136/144 (94.4%)  utility 109/144 (75.7%)
slack     security  96/105 (91.4%)  utility  71/105 (67.6%)
travel    security 140/140 (100.0%) utility 117/140 (83.6%)
workspace security 234/240 (97.5%)  utility 175/240 (72.9%)
total     security 606/629 (96.3%)  utility 472/629 (75.0%)
```

(The 27-task isolation number quoted in the abstract is the harmful
subset of these 629 tasks; full per-suite breakdown matches paper
Table 2.)

---

## §4 — AgentDojo deployment (95.9% / 75.0%)

Same 4-suite × 629-task matrix, but with the GLM-4.6 agent backbone
running the real LLM-pipeline rather than the forced-injection oracle.
This is the lower-bound regime described in §4.X.

```bash
export ZAI_API_KEY=...        # or set in .env
bash benchmarks/agentdojo_adapter/launch-baseline-l1-rerun.sh
```

The script launches three `screen` sessions in parallel:

1. `nous-baseline` — GLM-4.6 agent only, no Nous gate (control: 95.2% / 79.0%)
2. `nous-l1`       — agent + L1 Datalog (96.0% / 75.0%)
3. `nous-l1_4`     — agent + L1 + L4 (95.9% / 75.0%, paper headline)

Each takes ~ 5 h. Results land in
`benchmarks/agentdojo_adapter/results-fullmatrix/`.

---

## §4 — AgentHarm val (100% TPR)

Reproduces the L1 + L2 + L3 stack on the AgentHarm validation slice
(176 harmful + 176 benign). Raw scenarios live in
`docs/agentharm-raw-scenarios.json`.

```bash
export DEEPSEEK_API_KEY=...
python scripts/run_agentharm_threelayer_v2.py
```

Expected output (paper §4 AgentHarm row):

```
TPR 100.0% [90.3%, 100.0%]   FPR 0.0% [0.0%, 9.7%]
```

---

## §4 — Layer complementarity (gate ∩ verifier overlap on Hijacking)

```bash
python scripts/eval_d2_verifier.py
```

Expected:

```
Hijacking 60 H: gate=11 only, verifier=30 only, both=15, neither=4
```

This is the structural-boundary disjointness claim cited in §4 and §5.

---

## Variance and seed control

* Owner-centric v3 (deterministic L1 + L4) — no variance.
* AgentDojo isolation — L3 majority vote `k=5` at temperature `0.0`;
  variance across runs is < 1 pp on the aggregate.
* AgentDojo deployment — GLM-4.6 agent at temperature `0.0`, `k=1`;
  per-task LLM behaviour is reasonably stable but the 629-task aggregate
  may move ± 0.5 pp between runs.
* AgentHarm — `k=3` self-consistency at temperature `0.0`.

---

## Compute and cost estimates

* Deterministic (Owner-centric v3, LSVJ-S, layer overlap) — < 1 min, free.
* AgentHarm L1 + L2 + L3 — ~ 1 h, ~ US$ 5 in DeepSeek tokens.
* AgentDojo isolation L1 + L3 + L4 — ~ 5 h, ~ US$ 30 in DeepSeek tokens.
* AgentDojo deployment baseline + L1 + L1 + L4 (3 modes parallel) —
  ~ 5 h, ~ US$ 0 if using a GLM coding-plan subscription, otherwise
  ~ US$ 50 metered.

No GPU is required for any reproduction step; all LLM calls go to remote
APIs.

---

## Versioned artefacts

* Code: this repository, commit recorded in `paper/main-neurips-2026.tex`
  Erratum.
* Owner-centric v3 dataset: `data/owner_harm_heldout_v3.json`
  (sha256 frozen at submission; see `paper/main-neurips-2026.tex` §3.3).
* R-Judge personal-agent slice: `benchmarks/rjudge_sample/` (24 records,
  sha256 frozen).
* AgentDojo: pinned to upstream commit `agentdojo @ v1.x` (see
  `benchmarks/agentdojo_adapter/run_eval_adaptive_llm.py` setup banner
  printed at run start).

---

## Filing reproduction issues

If a step in this guide produces a number outside the variance budget
above, please open an issue at
<https://github.com/dario-github/nous/issues> with:

* the entry-point command run,
* the OS / Python / pip-freeze output,
* the produced summary JSON (under `results-*/`),
* the model used at L3 (DeepSeek vs. other) and the temperature.
