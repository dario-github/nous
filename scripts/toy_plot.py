"""Generate Figure 3: AUC vs Q curve for toy validation.

Reads paper/toy-validation/results.json (multi-seed densified grid)
and produces paper/toy-validation/auc-vs-Q.pdf with mean ± std bands.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "paper" / "toy-validation" / "results.json"
OUT_PDF = ROOT / "paper" / "toy-validation" / "auc-vs-Q.pdf"
OUT_PNG = ROOT / "paper" / "toy-validation" / "auc-vs-Q.png"

with RESULTS.open() as fh:
    data = json.load(fh)

rows = data["rows"]
n_values = sorted({r["n_per_context"] for r in rows})
Q_values = sorted({r["Q"] for r in rows})
n_seeds = data.get("n_seeds", 1)

fig, ax = plt.subplots(figsize=(6.4, 4.2))

# Distinct color/marker per n
n_palette = {
    100:  ("#b2182b", "o"),
    200:  ("#ef8a62", "s"),
    500:  ("#fddbc7", "D"),
    1000: ("#92c5de", "v"),
    2000: ("#2166ac", "^"),
}
fallback_palette = plt.cm.viridis(np.linspace(0, 0.9, max(len(n_values), 1)))

for idx, n in enumerate(n_values):
    rs = sorted([r for r in rows if r["n_per_context"] == n], key=lambda r: r["Q"])
    qs = np.array([r["Q"] for r in rs], dtype=float)
    aucs = np.array([r["auc_test"] for r in rs], dtype=float)
    stds = np.array([r.get("auc_std", 0.0) for r in rs], dtype=float)
    sup_tv_avg = float(np.mean([r["sup_TV"] for r in rs]))

    color, marker = n_palette.get(n, (None, "o"))
    if color is None:
        color = fallback_palette[idx]

    ax.plot(
        qs, aucs,
        marker=marker, color=color,
        linewidth=1.6, markersize=6, markerfacecolor=color, markeredgecolor="black",
        markeredgewidth=0.5,
        label=fr"$n={n}$  ($\overline{{\sup_c\,d_{{\mathrm{{TV}}}}}} \approx {sup_tv_avg:.3f}$)",
    )
    if n_seeds > 1 and stds.max() > 0:
        ax.fill_between(qs, aucs - stds, aucs + stds, color=color, alpha=0.18, linewidth=0)

# Theoretical reference curves (one per n, dashed faint): AUC ≤ 0.5 + min(1, Q*eps)/2
qs_dense = np.geomspace(min(Q_values), max(Q_values), 200)
for idx, n in enumerate(n_values):
    rs = [r for r in rows if r["n_per_context"] == n]
    eps = float(np.mean([r["sup_TV"] for r in rs]))
    color, _ = n_palette.get(n, (fallback_palette[idx], "o"))
    auc_bound = 0.5 + np.minimum(1.0, qs_dense * eps) / 2.0
    ax.plot(qs_dense, auc_bound, linestyle="--", color=color, alpha=0.35, linewidth=0.9)

# Random-guess + saturation
ax.axhline(0.5, linestyle=":", color="grey", linewidth=0.8, alpha=0.7)
ax.axhline(1.0, linestyle=":", color="grey", linewidth=0.8, alpha=0.7)
ax.text(min(Q_values), 0.515, "random", fontsize=8, color="grey")

ax.set_xscale("log")
ax.set_xticks(Q_values)
ax.set_xticklabels([str(int(q)) for q in Q_values])
ax.set_yticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
ax.set_xlabel(r"auditor budget $Q$ (log scale)")
ax.set_ylabel("transcript classifier AUC (held-out)")
ax.set_title(
    rf"Theorem 1$'$ degradation: AUC vs.\ $Q$ "
    rf"(mean $\pm$ std over {n_seeds} seeds; dashed = $0.5 + \min(1, Q\varepsilon)/2$ bound)",
    fontsize=9.5,
)
ax.set_ylim(0.45, 1.05)
ax.grid(True, which="both", linestyle=":", alpha=0.4)
ax.legend(loc="lower right", fontsize=8.5, framealpha=0.95, title=fr"distillation budget")

fig.tight_layout()
fig.savefig(OUT_PDF)
fig.savefig(OUT_PNG, dpi=180)
print(f"wrote {OUT_PDF}")
print(f"wrote {OUT_PNG}")
