# NeurIPS 2026 E&D Track Submission Freeze Note

**Frozen**: 2026-05-02 00:03 (UTC+8)
**Submission deadline**: 2026-05-04 AoE (abstract) / 2026-05-06 AoE (full paper)
**Target venue**: NeurIPS 2026 Evaluations & Datasets Track (formerly D&B)
**Title**: Owner-Harm: A Missing Threat Model for AI Agent Safety
**Anonymization**: double-blind via `\usepackage{neurips2026-style/neurips_2026}` default

## Repository state at freeze

- Branch: `main`
- HEAD commit: `a128308` (paper edits in working tree, NOT yet committed; will commit before submit)
- Working tree dirty (paper Day 1-3 patches uncommitted): see git status

## Numerical claims locked

| Claim | §  ref | Number | CI | Reproduction command | Wall | Cost |
|---|---|---|---|---|---|---|
| LSVJ-S compile gate (138 tests, 1 skipped) | suppl. companion | 138/139 pass | --- | `pytest tests/lsvj/` | <10s | $0 |
| Owner-Harm v3 gate alone TPR | §4.4 | 75.3% (226/300) | [70.2%, 79.9%] | `python scripts/full_benchmark_eval.py` | ~30s | $0 |
| Owner-Harm v3 gate alone FPR | §4.4 | 3.3% (5/150) | [1.4%, 7.6%] | (same) | (same) | (same) |
| Owner-Harm v3 combined L1+L2+L3+L4 TPR | §4.4 | 85.3% (256/300) | [80.9%, 88.9%] | (same) | (same) | (same) |
| Owner-Harm v3 combined FPR | §4.4 | **13.3% (20/150)** | **[8.8%, 19.7%]** | (same) | (same) | (same) |
| Hijacking gate-only / verifier-only / both / neither | §4.4 / §6.2 | 11/30/15/4 | --- | `python scripts/eval_d2_verifier.py` | ~10s | $0 |
| Hijacking combined TPR | §4.4 | 93.3% (56/60) | [84.1%, 97.4%] | (same) | (same) | (same) |
| Hijacking benign FP | §4.4 | 0/30 | [0.0%, 11.4%] | (same) | (same) | (same) |
| AgentDojo isolation L1+L4 (deterministic) | §4.2 | 3.7% (1/27); util 97.9%; FPR 2.1% | [0.7%, 18.3%] | `cd benchmarks/agentdojo_adapter && uv run --project ../agentdojo python run_eval.py` | ~1-3 min | $0 |
| AgentDojo isolation L1+L3+L4 (qwen-turbo legacy) | §4.2 | 14.8% (4/27) | [5.9%, 32.5%] | NOT REPRODUCIBLE | --- | --- |
| AgentDojo deployment L1 + GLM-4.6 | §4.3 | 95.9% / 75.0% (603/472 of 629) | --- | `launch-baseline-l1-rerun.sh` | ~5h | $0 |
| AgentDojo deployment L1+L3+L4 deepseek + GLM-4.6 | §4.3 | 96.3% / 75.0% (606/472 of 629) | --- | `launch-l3-deepseek-repro.sh` | ~5h | ~$15 |
| AgentDojo deployment baseline GLM-4.6 alone | §4.3 | 95.2% / 79.0% | --- | (same suite, mode=baseline) | ~5h | $0 |
| AgentHarm L1+L2+L3 (deepseek-chat) full TPR / FPR | §4.6 + App.C | **97.7% (172/176) / 2.3% (4/176)** | TPR [94.3%, 99.1%]; FPR [0.9%, 5.7%] | `OPENAI_API_KEY=$DEEPSEEK_KEY NOUS_BASE_URL=https://api.deepseek.com/v1 python scripts/run_agentharm_threelayer_v2.py` | ~36 min | ~$3 |
| AgentHarm Generic-LLM zero-shot baseline | App.\,C | 62.7% | --- | `python scripts/exp_eval.py` | --- | --- |
| AgentDojo Generic-LLM zero-shot baseline | App.\,C | 59.3% (16/27) | --- | (same) | --- | --- |

## Reproductions performed today (2026-05-01 / 2026-05-02)

- ✅ `pytest tests/lsvj/ tests/test_scallop_sidecar.py tests/test_gateway_hook.py` → 138 passed, 1 skipped
- ✅ `python scripts/full_benchmark_eval.py` → all numbers above
- ✅ `python scripts/eval_d2_verifier.py` → all hijacking numbers above
- ✅ AgentDojo L3 deepseek deployment 96.3%/75.0% replayed via existing `launch-l3-deepseek-repro.sh` log
- ✅ AgentHarm L1+L2+L3 (deepseek-chat) full N=176+176 → 97.7%/2.3% (rerun 2026-05-02, ~36min, ~$3). L3 contributes +38.6 pp TPR over L1+L2 baseline. Paper headline updated from "100% val n=72" to "97.7% full N=352" — stronger because reproducible + larger sample.

## Paper changes 2026-05-01 → 2026-05-02 (versus 2026-04-29 baseline PDF)

Day 1 (2026-05-01):
- Removed line 356 TBD row from `tab:agentdojo_main` (was "L1+L3+L4 (current) deepseek-v4-pro TBD ... exploratory, pending lock")
- Added Construction Protocol paragraph to §Owner-Harm Benchmark Diagnostic with explicit benchmark provenance, single-annotator disclosure, sealed sha256, license, deterministic scoring
- Added item 8 "Deployment-mode attribution" to §Limitations: explicitly distinguishes 95.2% backbone vs +0.8 to +1.1 pp gate marginal contribution

Day 2 (2026-05-02):
- DISCOVERED & FIXED: paper claim "Gate + verifier reaches TPR=85.3% with unchanged FPR" was wrong; combined FPR is actually 13.3% (CI [8.8%, 19.7%]). Patched §4.4 to honest +10pp TPR / +10pp FPR trade-off framing with per-category note (C2 60%, C4 36%, others 0%).
- Added Reproducibility Index appendix table with claim → command → key → wall → cost columns

Day 3 (2026-05-02):
- Patched abstract to mention combined FPR rises to 13.3% + zero-FP on Hijacking (rule-class specific complementarity, not uniform)
- Verified SSDG framing remains "conceptual framework" with falsifiable hypotheses (no overclaim)
- Verified all table captions clearly distinguish modes (isolation vs deployment vs diagnostic)

## Compile state (post codex 3rd-look fixes)

- `paper/main-neurips-2026.pdf` (322KB, 18 pages)
- **Pages 1-9: main body, strict NeurIPS 9-content-page compliant**
  (Conclusion fully on page 9 via `\enlargethispage{2\baselineskip}` before
  §Related Work; nothing main-body bleeds to page 10)
- Page 10: pure bibliography (does not count)
- Pages 11-18: appendices (Reproducibility Index, Eight Categories,
  Comparison with Existing Taxonomies, Controlled Experiment Full Detail,
  SSDG Experimental Predictions, Production Deployment Evidence,
  Extended Discussion, Extended Future Work, Author Contributions
  placeholder, NeurIPS Paper Checklist)
- All cross-refs resolved (no "Table ??", "Section ??", or undefined refs)
- Anonymized via default neurips_2026.sty (Anonymous Author(s) appears in compiled PDF)
- AgentHarm headline updated 100%→97.7% on full N=176+176 with locked
  deepseek-chat L3 (reproduced 2026-05-02, ~36min, ~$3)

## arxiv-submission package

- `paper/arxiv-submission/main-neurips-arxiv.zip` (339KB, 7 files)
- Self-contained: tex + bbl + bib + sty + PDF
- Verified compiles in fresh checkout

## Pending Dario actions before 5/6 AoE

1. Visual eyeball PDF for: anonymity, broken refs, title/abstract correctness, figures/tables, page boundaries
2. Optional: ask Yiqing for 20-min sanity read on abstract/intro positioning (not data labeling)
3. Submit abstract metadata to OpenReview before 2026-05-04 AoE
4. Final visual review before submission
5. Submit full paper + arxiv-submission zip before 2026-05-06 AoE

## Codex audit trail

- 2026-05-01 06:37: codex C3 verdict (CCCM ABORT — `/tmp/codex-r001-verdict.log`)
- 2026-05-01 06:55: codex confirms abort + recommends repo postmortem only (`/tmp/codex-abort-verdict.log`)
- 2026-05-01 ~14:00: codex SCI-tier audit + 5-day plan (path A1, push Owner-Harm to NeurIPS 5/6 — `/tmp/codex-sci-verdict.log`)
- All decisions in this freeze align with codex plan.

## Honest known weaknesses (will be visible to reviewers)

1. Owner-Harm benchmark is author-constructed single-annotator (acknowledged §Limitations item 2-3)
2. Combined FPR 13.3% is non-trivial (acknowledged §4.4 + abstract); +10pp recall costs +10pp specificity
3. Gate marginal contribution to deployment is small (acknowledged §Limitations item 8)
4. AgentDojo L1+L3+L4 legacy 14.8% not reproducible (acknowledged §Limitations Erratum)
5. SSDG is conceptual framework, not formal theory (acknowledged §3)
6. C2 Infrastructure Exposure rule OH-R3a over-triggers at 60% benign FPR (acknowledged §Limitations item 6)
