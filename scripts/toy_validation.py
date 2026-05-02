"""Toy validation for Theorem 1' (approximate transcript indistinguishability).

Setup:
- Finite alphabets: |C|=10, |Y_A|=5, |Y_R|=8.
- Stationary kernel K_G(y_R, y_A | c) hand-built so that L(M_G) > 0
  (Y_A depends on a latent reasoning bit R derived from c).
- Construct K_D^eps via empirical joint-kernel distillation (Proposition 1):
  draw n in {100, 500, 2000} samples per context from K_G and use the empirical
  joint as K_D^eps with R^D causally disconnected from Y_A.
- Distinguishability test: for budgets Q in {10, 50, 200}:
    1. Sample N_test transcripts from each agent (no adaptive auditor in toy;
       a fixed uniform-over-C auditor suffices for this finite illustration).
    2. Train a logistic regression on transcript count features
       (bag of (c, y_A, y_R) triples).
    3. Report held-out classifier AUC.
    4. Also report the *true* per-context joint-kernel TV between K_G and the
       empirical K_hat (this is computable since both are finite).
- Expected shape: AUC ≈ 0.5 when Q*eps is small; AUC grows toward 1 as Q*eps -> 1.
- Honest framing (per R5 polish #4): this is a computational illustration of
  the finite-alphabet construction, not a validation of the impossibility theorem.
"""

from __future__ import annotations

import json
import math
import os
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# --------------------------------------------------------------- #
# Repro                                                           #
# --------------------------------------------------------------- #
SEED = 20260427
random.seed(SEED)
np.random.seed(SEED)

# --------------------------------------------------------------- #
# Setup                                                           #
# --------------------------------------------------------------- #
NC = 10  # |C|
NA = 5   # |Y_A|
NR = 8   # |Y_R|


def build_K_G() -> np.ndarray:
    """Build K_G(y_R, y_A | c) of shape (NC, NR, NA) such that:
        - Latent R = R(c) is a hidden reasoning bit, fully determined by c.
        - Y_A depends on R (and c) so NDE_{R -> Y_A} > 0.
        - Y_R is mostly aligned with R (faithful explanation).
    The marginal K_G(y_R, y_A | c) is what we expose."""
    K = np.zeros((NC, NR, NA), dtype=np.float64)
    rng = np.random.default_rng(SEED)

    for c in range(NC):
        # latent reasoning bit r in {0,1}, deterministic in c
        r = c % 2
        # Y_A distribution depends on r: r=0 favors actions {0,1}, r=1 favors {3,4}
        if r == 0:
            base_a = np.array([0.40, 0.30, 0.15, 0.10, 0.05])
        else:
            base_a = np.array([0.05, 0.10, 0.15, 0.30, 0.40])
        # add small per-context noise
        base_a = base_a + rng.uniform(-0.02, 0.02, size=NA)
        base_a = np.clip(base_a, 1e-3, None)
        base_a /= base_a.sum()

        # Y_R given (c, y_A) is a smooth function of r, mostly emitting low-index
        # tokens when r=0 and high-index tokens when r=1; slightly modulated by y_A
        for y_a in range(NA):
            if r == 0:
                base_r = np.array(
                    [0.30, 0.25, 0.15, 0.10, 0.08, 0.06, 0.04, 0.02]
                )
            else:
                base_r = np.array(
                    [0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.25, 0.30]
                )
            # tiny y_a-coupling so the conditional is non-degenerate
            base_r = base_r + rng.uniform(-0.01, 0.01, size=NR)
            base_r = np.clip(base_r, 1e-3, None)
            base_r /= base_r.sum()

            # K(y_R, y_A | c) = K(y_A | c) * K(y_R | c, y_A)
            for y_r in range(NR):
                K[c, y_r, y_a] = base_a[y_a] * base_r[y_r]

    # Per-context normalization (already normalized by construction; double-check)
    for c in range(NC):
        K[c] /= K[c].sum()
    return K


def sample_transcript(
    K: np.ndarray, Q: int, contexts: np.ndarray | None = None
) -> list[tuple[int, int, int]]:
    """Draw a length-Q transcript [(c, y_R, y_A)*Q] under uniform-over-C auditor."""
    transcript: list[tuple[int, int, int]] = []
    for t in range(Q):
        c = int(contexts[t]) if contexts is not None else random.randrange(NC)
        flat = K[c].reshape(-1)
        idx = np.random.choice(len(flat), p=flat)
        y_r, y_a = divmod(idx, NA)
        transcript.append((c, int(y_r), int(y_a)))
    return transcript


def empirical_K_from_samples(
    K_G: np.ndarray, n_per_context: int
) -> np.ndarray:
    """Distill K_D^eps as the empirical joint kernel from n_per_context samples
    per context drawn from K_G. This is the Proposition 1 construction."""
    K_hat = np.zeros_like(K_G)
    for c in range(NC):
        flat = K_G[c].reshape(-1)
        draws = np.random.choice(len(flat), size=n_per_context, p=flat)
        for d in draws:
            y_r, y_a = divmod(int(d), NA)
            K_hat[c, y_r, y_a] += 1
    # Laplace smoothing to keep TV-finite
    K_hat += 1e-6
    K_hat /= K_hat.sum(axis=(1, 2), keepdims=True)
    return K_hat


def per_context_TV(K_a: np.ndarray, K_b: np.ndarray) -> np.ndarray:
    """Per-context d_TV between two finite kernels of shape (NC, NR, NA)."""
    diff = np.abs(K_a - K_b).sum(axis=(1, 2)) / 2
    return diff


# --------------------------------------------------------------- #
# Logistic regression on transcript count features (pure numpy)   #
# --------------------------------------------------------------- #
def encode_transcript(transcript: list[tuple[int, int, int]]) -> np.ndarray:
    """Bag-of-(c, y_R, y_A)-triples count vector of length NC*NR*NA."""
    vec = np.zeros(NC * NR * NA, dtype=np.float64)
    for c, y_r, y_a in transcript:
        idx = c * NR * NA + y_r * NA + y_a
        vec[idx] += 1
    return vec


def logreg_train(X: np.ndarray, y: np.ndarray, lr: float = 0.05,
                 n_epochs: int = 200, l2: float = 1e-3) -> np.ndarray:
    """Plain L2-regularized logistic regression via gradient descent."""
    n, d = X.shape
    w = np.zeros(d + 1)  # last is bias
    Xb = np.concatenate([X, np.ones((n, 1))], axis=1)
    for _ in range(n_epochs):
        z = Xb @ w
        p = 1.0 / (1.0 + np.exp(-z))
        grad = Xb.T @ (p - y) / n + l2 * w
        w = w - lr * grad
    return w


def logreg_predict(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    Xb = np.concatenate([X, np.ones((X.shape[0], 1))], axis=1)
    return 1.0 / (1.0 + np.exp(-(Xb @ w)))


def auc_score(scores: np.ndarray, labels: np.ndarray) -> float:
    """Compute ROC AUC with the rank-based formula."""
    n_pos = int((labels == 1).sum())
    n_neg = int((labels == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(scores)
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(scores) + 1)
    sum_ranks_pos = float(ranks[labels == 1].sum())
    auc = (sum_ranks_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return auc


# --------------------------------------------------------------- #
# Experiment                                                      #
# --------------------------------------------------------------- #
@dataclass
class RunResult:
    n_per_context: int
    Q: int
    auc_test: float
    sup_TV: float
    mean_TV: float


def run_one_setting(
    K_G: np.ndarray, n_per_context: int, Q: int,
    n_train: int = 600, n_test: int = 400,
) -> RunResult:
    K_D = empirical_K_from_samples(K_G, n_per_context)
    tv_per_c = per_context_TV(K_G, K_D)
    sup_tv = float(tv_per_c.max())
    mean_tv = float(tv_per_c.mean())

    X_tr, y_tr = [], []
    for _ in range(n_train // 2):
        X_tr.append(encode_transcript(sample_transcript(K_G, Q)))
        y_tr.append(0)
    for _ in range(n_train // 2):
        X_tr.append(encode_transcript(sample_transcript(K_D, Q)))
        y_tr.append(1)
    X_tr = np.stack(X_tr)
    y_tr = np.asarray(y_tr, dtype=np.float64)

    X_te, y_te = [], []
    for _ in range(n_test // 2):
        X_te.append(encode_transcript(sample_transcript(K_G, Q)))
        y_te.append(0)
    for _ in range(n_test // 2):
        X_te.append(encode_transcript(sample_transcript(K_D, Q)))
        y_te.append(1)
    X_te = np.stack(X_te)
    y_te = np.asarray(y_te, dtype=np.float64)

    w = logreg_train(X_tr, y_tr)
    scores = logreg_predict(X_te, w)
    auc = auc_score(scores, y_te)

    return RunResult(n_per_context, Q, auc, sup_tv, mean_tv)


def main() -> None:
    K_G = build_K_G()
    n_grid = [100, 200, 500, 1000, 2000]
    Q_grid = [1, 5, 10, 25, 50, 100, 200, 500]
    seeds = [20260427, 20260428, 20260429, 20260430, 20260501]  # 5 seeds for ±std bands
    rows: list[dict[str, float]] = []
    for n in n_grid:
        for q in Q_grid:
            runs = []
            for s in seeds:
                random.seed(s); np.random.seed(s)
                runs.append(run_one_setting(K_G, n_per_context=n, Q=q))
            aucs = [r.auc_test for r in runs]
            sup_tvs = [r.sup_TV for r in runs]
            mean_tvs = [r.mean_TV for r in runs]
            auc_mean = float(np.mean(aucs))
            auc_std = float(np.std(aucs, ddof=1))
            sup_tv_mean = float(np.mean(sup_tvs))
            mean_tv_mean = float(np.mean(mean_tvs))
            print(
                f"n={n:5d} Q={q:4d}  "
                f"sup_TV={sup_tv_mean:.4f} mean_TV={mean_tv_mean:.4f}  "
                f"AUC={auc_mean:.4f}±{auc_std:.4f}  Q*sup_TV={q * sup_tv_mean:.3f}"
            )
            rows.append({
                "n_per_context": n,
                "Q": q,
                "sup_TV": sup_tv_mean,
                "mean_TV": mean_tv_mean,
                "Q_times_sup_TV": q * sup_tv_mean,
                "auc_test": auc_mean,
                "auc_std": auc_std,
                "auc_per_seed": aucs,
                "n_seeds": len(seeds),
            })

    out_dir = Path(__file__).resolve().parent.parent / "paper" / "toy-validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "results.json"
    with out.open("w") as fh:
        json.dump(
            {
                "seeds": seeds,
                "n_seeds": len(seeds),
                "alphabets": {"NC": NC, "NA": NA, "NR": NR},
                "Q_grid": Q_grid,
                "n_grid": n_grid,
                "n_train_per_label": 300,
                "n_test_per_label": 200,
                "rows": rows,
            },
            fh,
            indent=2,
        )
    print(f"\nResults written to {out}")


if __name__ == "__main__":
    main()
