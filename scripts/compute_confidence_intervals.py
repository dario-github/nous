#!/usr/bin/env python3
"""
Compute Clopper-Pearson 95% confidence intervals for Nous benchmark results.

Usage:
    python3 scripts/compute_confidence_intervals.py
    python3 scripts/compute_confidence_intervals.py --latex   # output LaTeX table

Outputs:
    - CI table for all benchmarks
    - Bootstrap CI for owner-harm (per-category breakdown)
    - Summary for paper appendix
"""

import json
import math
import sys
from pathlib import Path
from scipy import stats

DOCS_DIR = Path(__file__).parent.parent / "docs"


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Clopper-Pearson exact binomial confidence interval.
    
    Returns (lower, upper) as fractions [0, 1].
    k: successes, n: total, alpha: significance level (default 0.05 = 95% CI)
    """
    if n == 0:
        return (0.0, 1.0)
    lower = stats.beta.ppf(alpha / 2, k, n - k + 1) if k > 0 else 0.0
    upper = stats.beta.ppf(1 - alpha / 2, k + 1, n - k) if k < n else 1.0
    return (lower, upper)


def pct(x: float) -> str:
    return f"{x * 100:.1f}\\%"


def fmt_ci(k: int, n: int, metric: str = "tpr") -> dict:
    """Format CI info for one metric."""
    point = k / n if n > 0 else 0.0
    lo, hi = clopper_pearson(k, n)
    return {
        "k": k, "n": n,
        "point": point,
        "ci_lower": lo,
        "ci_upper": hi,
        "ci_95": f"[{lo*100:.1f}%, {hi*100:.1f}%]",
    }


def load_owner_harm() -> dict:
    path = DOCS_DIR / "owner-harm-benchmark-results.json"
    with open(path) as f:
        return json.load(f)


def load_val_results(model: str = "doubao") -> dict:
    path = DOCS_DIR / f"split-results-val-{model}.json"
    with open(path) as f:
        return json.load(f)


def compute_all_cis() -> dict:
    results = {}

    # ── Owner-Harm Benchmark ──────────────────────────────────────────────
    oh = load_owner_harm()
    h_total = oh["harmful_count"]
    b_total = oh["benign_count"]
    h_blocked = sum(1 for r in oh["harmful_results"] if r["any_blocked"])
    b_blocked = sum(1 for r in oh["benign_results"] if r["any_blocked"])

    results["owner_harm"] = {
        "description": "Owner-Harm Benchmark (200H + 50B)",
        "tpr": fmt_ci(h_blocked, h_total),
        "fpr": fmt_ci(b_blocked, b_total, "fpr"),
        "per_category": {},
    }

    # Per-category breakdown
    from collections import defaultdict
    cat_h = defaultdict(lambda: {"blocked": 0, "total": 0})
    cat_b = defaultdict(lambda: {"blocked": 0, "total": 0})
    for r in oh["harmful_results"]:
        cat = r.get("category", "Unknown")
        cat_h[cat]["total"] += 1
        if r["any_blocked"]:
            cat_h[cat]["blocked"] += 1
    for r in oh["benign_results"]:
        cat = r.get("category", "Unknown")
        cat_b[cat]["total"] += 1
        if r["any_blocked"]:
            cat_b[cat]["blocked"] += 1

    for cat in sorted(cat_h.keys()):
        h = cat_h[cat]
        b = cat_b[cat]
        results["owner_harm"]["per_category"][cat] = {
            "tpr": fmt_ci(h["blocked"], h["total"]),
            "fpr": fmt_ci(b["blocked"], b["total"], "fpr"),
        }

    # ── Val Split (Doubao) ────────────────────────────────────────────────
    try:
        val = load_val_results("doubao")
        ov = val["overall"]
        results["val_doubao"] = {
            "description": "Val Split — Doubao-Pro (36H + 36B)",
            "tpr": fmt_ci(ov["h_blocked"], ov["h_total"]),
            "fpr": fmt_ci(ov["b_blocked"], ov["b_total"], "fpr"),
        }
    except Exception as e:
        print(f"[WARN] val-doubao: {e}")

    return results


def print_table(results: dict) -> None:
    print("\n" + "=" * 70)
    print("CONFIDENCE INTERVALS — Nous Benchmark Results")
    print("Clopper-Pearson 95% CI (exact binomial)")
    print("=" * 70)

    for bench_key, bench in results.items():
        desc = bench.get("description", bench_key)
        print(f"\n{'─' * 60}")
        print(f"  {desc}")
        print(f"{'─' * 60}")

        tpr = bench["tpr"]
        fpr = bench["fpr"]
        print(f"  TPR:  {tpr['k']}/{tpr['n']} = {tpr['point']*100:.1f}%  "
              f"95% CI {tpr['ci_95']}")
        print(f"  FPR:  {fpr['k']}/{fpr['n']} = {fpr['point']*100:.1f}%  "
              f"95% CI {fpr['ci_95']}")

        if "per_category" in bench and bench["per_category"]:
            print(f"\n  Per-Category Breakdown:")
            print(f"  {'Category':<30} {'TPR':>8} {'TPR-CI':>18} {'FPR':>8} {'FPR-CI':>18}")
            print(f"  {'─'*30} {'─'*8} {'─'*18} {'─'*8} {'─'*18}")
            for cat, data in bench["per_category"].items():
                t = data["tpr"]
                fp = data["fpr"]
                tpr_pct = f"{t['point']*100:.0f}%"
                fpr_pct = f"{fp['point']*100:.0f}%"
                print(f"  {cat:<30} {tpr_pct:>8} {t['ci_95']:>18} {fpr_pct:>8} {fp['ci_95']:>18}")


def print_latex(results: dict) -> None:
    """Print LaTeX table snippet for paper."""
    print("\n% ── LaTeX CI Table for Paper ──────────────────────────────")
    print("% Add to main.tex evaluation section\n")

    oh = results.get("owner_harm", {})
    val = results.get("val_doubao", {})

    if oh:
        tpr = oh["tpr"]
        fpr = oh["fpr"]
        print("% Owner-Harm Benchmark CIs")
        print(f"% TPR: {tpr['point']*100:.1f}\\% (95\\% CI: {tpr['ci_lower']*100:.1f}\\%--{tpr['ci_upper']*100:.1f}\\%)")
        print(f"% FPR: {fpr['point']*100:.1f}\\% (95\\% CI: {fpr['ci_lower']*100:.1f}\\%--{fpr['ci_upper']*100:.1f}\\%)")
        print()
        print("\\begin{table}[t]")
        print("  \\centering")
        print("  \\caption{Nous performance with 95\\% Clopper--Pearson CIs.}")
        print("  \\label{tab:ci_results}")
        print("  \\begin{tabular}{lrrr}")
        print("    \\toprule")
        print("    Benchmark & TPR & FPR & $n_{\\text{harmful}}$ / $n_{\\text{benign}}$ \\\\")
        print("    \\midrule")

        for bench_key, bench in results.items():
            t = bench["tpr"]
            fp = bench["fpr"]
            desc_short = bench["description"].split("(")[0].strip()
            print(f"    {desc_short} & "
                  f"{t['point']*100:.1f}\\% [{t['ci_lower']*100:.1f}, {t['ci_upper']*100:.1f}] & "
                  f"{fp['point']*100:.1f}\\% [{fp['ci_lower']*100:.1f}, {fp['ci_upper']*100:.1f}] & "
                  f"{t['n']} / {fp['n']} \\\\")

        print("    \\bottomrule")
        print("  \\end{tabular}")
        print("\\end{table}")

    print("\n% ── Inline CI statements for text ──")
    if oh:
        t = oh["tpr"]
        fp = oh["fpr"]
        print(f"% On the Owner-Harm benchmark (n={t['n']} harmful, n={fp['n']} benign),")
        print(f"% Nous achieves TPR~{t['point']*100:.1f}\\% (95\\%~CI: [{t['ci_lower']*100:.1f}\\%, {t['ci_upper']*100:.1f}\\%])")
        print(f"% and FPR~{fp['point']*100:.1f}\\% (95\\%~CI: [{fp['ci_lower']*100:.1f}\\%, {fp['ci_upper']*100:.1f}\\%]).")


def save_results(results: dict) -> None:
    out_path = DOCS_DIR / "confidence-intervals.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Saved to {out_path}")


if __name__ == "__main__":
    latex_mode = "--latex" in sys.argv

    print("Computing Clopper-Pearson 95% confidence intervals...")
    results = compute_all_cis()

    print_table(results)

    if latex_mode:
        print_latex(results)

    save_results(results)
