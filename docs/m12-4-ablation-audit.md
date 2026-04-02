# M12.4 — T1 Judge Audit of Ablation Results

**Date**: 2026-04-02
**Loop**: 80
**Auditor**: Opus 4.6 (acting as T1 judge surrogate, pending GPT-5.4 confirmation)
**Data**: `docs/ablation-results.json` (2026-04-01T13:25:37Z)

## Audit Verdict: **PASS (after fix)**

Initial ablation (2026-04-01) had a critical `session_context` bug.
Fixed in Loop 80 (2026-04-02). Re-run results are consistent and publishable.

---

## Finding 1: Missing `session_context` (CRITICAL)

**Discrepancy**: Owner-harm L1+L2 benchmark reports TPR=100% (200/200), but
the ablation `baseline_l1l2` reports TPR=11% (22/200) on the **same dataset**.

**Root Cause**: The ablation script (`scripts/m12_component_ablation.py:80-102`)
calls `gate()` **without** `session_context`, while the canonical benchmark
(`scripts/run_owner_harm_benchmark.py:66-72`) passes
`session_context=prior_calls`. Chain-aware rules (OH-R8, OH-R8b, OH-R9a) that
detect `prior_read_file → external_action` hijacking patterns require session
context to fire. Without it, ~89% of harmful scenarios escape detection.

**Impact**: The ablation measures the effect of **missing tool-call context**,
not the effect of removing Datalog/Semantic/KG components. All ΔL values are
confounded by this bug.

**Evidence**:
```
# Ablation script (BROKEN) — m12_component_ablation.py:81-95
gr = gate(tc, db=db, constraints_dir=CONSTRAINTS_DIR, ...)
# ↑ No session_context parameter

# Real benchmark (CORRECT) — run_owner_harm_benchmark.py:66-72
gr = gate(tc, constraints_dir=CONSTRAINTS_DIR, ...,
          session_context=prior_calls if prior_calls else None)
# ↑ Chain context enables OH-R8/R9a rules
```

## Finding 2: Uninformative `no_semantic` Condition (MINOR)

`ablation_no_semantic` is trivially identical to `baseline_l1l2` because
semantic gate (L3) is disabled in fast mode by design. This is acknowledged
in the data (`"note": "Semantic gate not active in L1+L2 baseline"`) but
should not be presented as a meaningful ablation result.

## Finding 3: Missing `no_kg` Condition (EXPECTED)

`ablation_no_kg` requires full mode (L3 semantic active) which costs ~$5 in
API calls. Skipping is correct per budget constraints. This condition measures
KG context enrichment's contribution to L3 accuracy — valid only with L3 on.

## Finding 4: Loss Function Discrepancy (MINOR)

Ablation script uses `L = 0.7*(1-TPR) + 0.3*FPR` (line 121), while the paper
and `scripts/compute_loss.py` use `L = 0.4*(1-TPR) + 0.3*FPR + 0.2*(1-cap) + 0.1*cat_var`.
For ablation comparison (same formula across conditions) this is acceptable,
but must not be mixed with canonical L_val numbers.

## Recommendations

1. **P0: Fix ablation script** — Add `session_context` tracking identical to
   `run_owner_harm_benchmark.py`. Then re-run fast mode to get valid L1+L2
   baseline and no_datalog numbers. **No API cost** for this fix.

2. **P1: Use existing valid layer data for paper** — The heldout_v2 results
   already provide clean layer contribution data:
   - L1+L2 only: TPR=33.0%, FPR=0.0% (training set: 100%/0%)
   - L1+L2+L3: TPR=78.4%, FPR=0.0%
   - L3 contribution: +45.4pp TPR on heldout

3. **P2: Defer no_kg full mode** — Requires Dario approval (~$5). The paper
   can note KG context as "post-gate enrichment" (as it already does in §2.4)
   without a formal ablation number.

4. **MINOR: Align loss formula or annotate** — Add a note in ablation-results.json
   clarifying the simplified loss formula used.

## Corrected Results (Loop 80, 2026-04-02)

After fixing `session_context`, re-run produced:

| Condition | TPR | FPR | L | ΔL |
|-----------|-----|-----|---|-----|
| baseline_l1l2 | 100.0% | 0.0% | 0.000 | — |
| no_datalog | 0.0% | 0.0% | 0.700 | **+0.700** |
| no_semantic | 100.0% | 0.0% | 0.000 | 0.000 |
| no_kg | — | — | — | skipped |

**Interpretation**: Datalog (L1) is the **sole** detection mechanism at L1+L2.
Removing it causes complete loss of detection (ΔL=+0.700). L3 semantic gate
contribution can only be measured in full mode with API calls (~$5).

## What IS Publishable from Existing Data

| Source | Data Point | Status |
|--------|-----------|--------|
| loop-state.json | Owner-harm L1+L2 TPR=100%/FPR=0% (training, 200H+50B) | ✅ Valid |
| loop-state.json | Heldout v2 L1+L2 TPR=33.0%/FPR=0.0% (306H+154B) | ✅ Valid |
| loop-state.json | Heldout v2 L1+L2+L3 TPR=78.4%/FPR=0.0% | ✅ Valid |
| loop-state.json | Per-category L3 breakdown (8 cats) | ✅ Valid |
| ablation-results.json | baseline_l1l2 TPR=100% | ✅ Valid (fixed) |
| ablation-results.json | no_datalog ΔL=+0.700 | ✅ Valid (fixed) |

## Next Steps

1. ✅ Fixed and re-run — ablation data now consistent
2. Proceed to M12.5-9 paper table fills with validated numbers
3. no_kg full mode deferred pending Dario approval (~$5)
