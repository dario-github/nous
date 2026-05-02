# Morning brief (Dario): NeurIPS Owner-Harm paper at PASS state

**Generated**: 2026-05-02 ~05:00 UTC+8 (autonomous overnight work)
**Deadline**: 2026-05-04 AoE (abstract) / 2026-05-06 AoE (full paper)
**Status**: ✅ Codex (4 rounds) confirms PASS — submission-ready

## TL;DR (1 sentence)

NeurIPS 2026 E&D Track paper is in submission-ready PASS state with
all numbers reproduced today, AgentHarm L3 rerun lifted headline from
"100% val n=36" (uncertain provenance) to **97.7% / 2.3% full
N=176+176** with locked deepseek-chat (more rigorous + larger sample),
and 11 local commits — Dario's morning todo is just visual-eyeball +
submit.

## Files to look at

- **`paper/main-neurips-2026.pdf`** (322 KB, 18 pages, anonymized)
  - Pages 1-9: main body, strict NeurIPS 9-page-content compliant
  - Page 10: pure bibliography
  - Pages 11-18: appendices (Reproducibility Index, 8 Categories,
    Comparison with Existing Taxonomies, Controlled Experiment, SSDG
    Predictions, Production Deployment Evidence, Extended Discussion +
    Future Work, NeurIPS Paper Checklist)
- **`paper/arxiv-submission/main-neurips-arxiv.zip`** (350 KB)
  — self-contained source + bbl + bib + style + PDF
- **`paper/arxiv-submission/nous-supplementary.zip`** (487 KB) —
  anonymized OpenReview supplementary code drop, extract-and-run
  smoke-verified (105 lsvj tests pass + full_benchmark_eval runs)
- **`paper/FREEZE-NOTE-2026-05-02.md`** — full claim-to-command audit
  + lessons + open weaknesses
- **`paper/main-tmlr.pdf`** + **`paper/arxiv-submission/main-tmlr-arxiv-v2.zip`**
  (768 KB w/ toy-validation figures) — Impossibility Theorem companion
  paper, numbers synced to NeurIPS frame, no deadline pressure

## Today's commits (11 local, NOT pushed yet)

```
3603876 paper: codex 4th-look 2 tiny edits → PASS — DEEPSEEK_KEY→DEEPSEEK_API_KEY consistency + legacy 14.8% qualifier (val n=36)
28d2a54 freeze-note: 9-page strict + 97.7% AgentHarm post 3rd-look
6939be7 paper: codex 3rd-look must-fix all addressed; NeurIPS 9-page strict-compliant
517d1a4 freeze-note: refresh AgentHarm row to 97.7%/2.3% full N=352
920dbc6 paper: AgentHarm 100%/0% val (n=72) → 97.7%/2.3% full (N=352, deepseek-chat L3, reproduced 2026-05-02)
294e14c paper: §"Cross-Bench Comparison Detail" stale tab:agentdojo_main ref → tab:deployment_ablation
efffbd9 paper: appendix Tab 9 (control) — fix Nous AgentHarm row label L1+L4 → L1+L2+L3 val
3296f76 paper: Table 5 add Combined FPR column (codex must-fix #3 deferred from prior commit) + Limitations omnibus compress
efc40a2 paper: codex pre-submit must-fix patches + AgentHarm honest demotion
88d2330 paper: AgentDojo isolation 3.7% reproduced; fix REPRODUCIBILITY label bug; anonymize repo refs
76ea6c9 paper: NeurIPS 2026 E&D Track Day 1-3 polish per codex 5-day plan
```

## Headline numbers — all reproduced 2026-05-01 / 02

| Claim | Number | Reproduction |
|---|---|---|
| LSVJ-S compile gate | 138 pass / 1 skip | `pytest tests/lsvj/` (10s) |
| Owner-Harm v3 gate alone | 75.3% / 3.3% | `python scripts/full_benchmark_eval.py` (30s) |
| Owner-Harm v3 full L1-L4 | **85.3% / 13.3%** (was misclaimed 3.3%) | (same) |
| Hijacking layer overlap | 11/30/15/4 | `python scripts/eval_d2_verifier.py` (10s) |
| AgentDojo isolation L1+L4 | 3.7% / 97.9% / 2.1% | `cd benchmarks/agentdojo_adapter && uv run --project ../agentdojo python run_eval.py` (1-3 min) |
| AgentDojo deployment L1+L3+L4 deepseek | 96.3% / 75.0% | `bash launch-l3-deepseek-repro.sh` (5h) |
| AgentHarm L1+L2+L3 deepseek-chat | **97.7% / 2.3%** (full N=176+176) | `OPENAI_API_KEY=$DEEPSEEK_API_KEY NOUS_BASE_URL=https://api.deepseek.com/v1 NOUS_SEMANTIC_MODEL=deepseek-chat python scripts/run_agentharm_threelayer_v2.py` (36 min, ~$3) |

## Two key paper-quality fixes overnight

1. **AgentHarm 100% claim demotion → upgrade**: Original "100% TPR / 0%
   FPR" was on val n=36+36 with uncertain provenance. Tonight's L3
   rerun on full N=176+176 with locked deepseek-chat got 97.7%/2.3% —
   stronger reviewer-defensible position. L3 contributes +38.6 pp TPR
   over L1+L2 deterministic baseline of 59.1%/52.3%.

2. **Owner-Harm "unchanged FPR" misclaim**: Paper said "Gate + verifier
   raises TPR to 85.3% with unchanged FPR" but reproduction showed
   combined FPR is actually 13.3% (CI [8.8%, 19.7%]). Paper §4.4 +
   abstract patched to honest +10pp TPR / +10pp FPR trade-off framing.

## What Dario needs to do

(Per codex 5-day plan + my reading of NeurIPS 2026 E&D Track CFP)

- [ ] **Visual eyeball PDF** — spot-check pages 1-9 main body, esp.
      abstract / Limitations item 8 (deployment attribution) /
      Tab 5 Combined FPR column, Tab 7 Cross-Benchmark, Tab 9 Control;
      check anonymity (PDF should show "Anonymous Author(s)" not
      Dongcheng/Yiqing names).
- [ ] **(Optional) push commits to public github**:
      `git push origin main` (codex 3rd-look recommended push corrected
      version forward as a normal commit — more honest than leaving
      stale 4-29 PDF visible).
- [ ] **Submit abstract metadata to OpenReview before 2026-05-04 AoE**.
- [ ] **Submit full paper + supplementary materials before 2026-05-06 AoE**.
      Use `paper/arxiv-submission/main-neurips-arxiv.zip` (350 KB) as
      the supplementary code drop, OR build a separate code-only zip
      stripped of the PDF (faster reviewer download).

## Known acceptable weaknesses (acknowledged in §Limitations + paper)

1. AgentDojo ceiling 3.7% deterministic / ~15-40% semantic
2. Owner-Harm Benchmark author-constructed single-annotator
3. 4/60 Hijacking SQL/SSH cases out of structural reach
4. C2 over-trigger 60% combined FPR (acknowledged in Tab 5 footnote)
5. Deployment marginal contribution +0.8 to +1.1 pp (small)

These are pre-emptive disclosures — reviewer should NOT find these as
"gotcha" since paper acknowledges them upfront.

## Ongoing related work (not blocking NeurIPS submit)

- **TMLR Impossibility Theorem paper** (`paper/main-tmlr.tex`) — uses
  CCCM/ASP failures as §Empirical Motivation. Up-to-date with today's
  refreshed numbers. No deadline pressure.
- **CCCM repo postmortem** (`cases/cccm/CCCM-ABORT-REPORT.md`) — done.
  CCCM as paper main path is dead; preserved as motivating evidence
  for TMLR theorem paper instead.

## If anything looks wrong

The full audit trail + codex verdicts are at:
- `/tmp/codex-r001-verdict.log` (CCCM C3 abort)
- `/tmp/codex-abort-verdict.log` (V3 ASP abort)
- `/tmp/codex-sci-verdict.log` (SCI-tier audit + 5-day plan, picked A1)
- `/tmp/codex-presubmit-verdict.log` (1st pre-submit must-fix)
- `/tmp/codex-3rd-verdict.log` (2nd pre-submit must-fix, deeper finds)
- `/tmp/codex-4th-verdict.log` (final 2-tiny-edit list → PASS)

If you want a 5th codex round on something specific, ask me when you
wake.

— Opus 4.7 overnight (autonomous, no decisions taken without codex
proxy except keeping work moving)
