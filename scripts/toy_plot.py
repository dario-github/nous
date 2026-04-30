"""Generate Figure 3: AUC vs Q curve for toy validation.

Reads paper/toy-validation/results.json, produces paper/toy-validation/auc-vs-Q.pdf
(vector PDF for inclusion via \\includegraphics).
"""
from __future__ import annotations

import json
from pathlib import Path

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

fig, ax = plt.subplots(figsize=(5.0, 3.4))

markers = {100: "o", 500: "s", 2000: "^"}
colors = {100: "#d62728", 500: "#ff7f0e", 2000: "#2ca02c"}

for n in n_values:
    rs = [r for r in rows if r["n_per_context"] == n]
    rs = sorted(rs, key=lambda r: r["Q"])
    qs = [r["Q"] for r in rs]
    aucs = [r["auc_test"] for r in rs]
    sup_tvs = [r["sup_TV"] for r in rs]
    avg_sup_tv = sum(sup_tvs) / len(sup_tvs)
    ax.plot(
        qs, aucs,
        marker=markers[n],
        color=colors[n],
        linewidth=1.4,
        markersize=6,
        label=fr"$n={n}$  ($\overline{{\sup_c d_{{\mathrm{{TV}}}}}} \approx {avg_sup_tv:.3f}$)",
    )

# Theoretical reference curve: AUC <= 0.5 + min(1, Q*eps)/2 with eps = sup_TV
# Plot for n=2000 (smallest eps) as a dashed reference.
import numpy as np
n_ref = 2000
ref_rows = [r for r in rows if r["n_per_context"] == n_ref]
if ref_rows:
    eps_ref = sum(r["sup_TV"] for r in ref_rows) / len(ref_rows)
    qs_dense = np.linspace(min(Q_values), max(Q_values), 100)
    auc_ref = 0.5 + np.minimum(1.0, qs_dense * eps_ref) / 2.0
    ax.plot(
        qs_dense, auc_ref,
        linestyle="--", color=colors[n_ref], alpha=0.45, linewidth=1.0,
        label=fr"bound $0.5 + \min(1, Q\varepsilon)/2$ at $n={n_ref}$",
    )

# Random-guess line
ax.axhline(0.5, linestyle=":", color="grey", linewidth=0.8, alpha=0.7)
ax.text(11, 0.512, "random", fontsize=8, color="grey")

# Saturation line
ax.axhline(1.0, linestyle=":", color="grey", linewidth=0.8, alpha=0.7)

ax.set_xscale("log")
ax.set_xticks(Q_values)
ax.set_xticklabels([str(q) for q in Q_values])
ax.set_yticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
ax.set_xlabel(r"auditor budget $Q$ (log scale)")
ax.set_ylabel("transcript classifier AUC")
ax.set_title(r"Theorem 1$'$ degradation: AUC vs. $Q$ at three distillation budgets $n$",
             fontsize=10)
ax.set_ylim(0.45, 1.05)
ax.grid(True, which="both", linestyle=":", alpha=0.4)
ax.legend(loc="lower right", fontsize=8, framealpha=0.95)

fig.tight_layout()
fig.savefig(OUT_PDF)
fig.savefig(OUT_PNG, dpi=180)
print(f"wrote {OUT_PDF}")
print(f"wrote {OUT_PNG}")
