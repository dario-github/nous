"""
Nous Invest — tests for the two bugs fixed 2026-04-21.

Bug 1 (FIXED): skills/portfolio_construction.py — default LGB/XGB params
  had L1=205.7 / L2=580.9, causing model to early-stop at iteration 1.
  Fixed to L1=0.1 / L2=0.1.

Bug 2 (FIXED): institutional/market_neutral/__init__.py
  StockUniverse.screen() called self._screen_single(code, grp) (2 args)
  but _screen_single signature was (self, recent) (1 arg).
  Fixed call site to drop the code arg.

These tests prevent regression. Run:
    cd invest && python3 -m pytest tests/ -v
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # nous/
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import pytest


# ══════════════════════════════════════════════════════════════════════
# Bug 2 — StockUniverse.screen()
# ══════════════════════════════════════════════════════════════════════


def _synth_stock_data(n_stocks: int = 50, n_days: int = 30, seed: int = 0) -> pd.DataFrame:
    """Tushare-schema sample data for StockUniverse.screen()."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_stocks):
        code = f"{i+1:06d}.SH"
        # 市值 600-2500 亿（tushare total_mv 单位：万元 → 值 6e6-2.5e7）
        mcap_wanyuan = rng.uniform(6_000_000, 25_000_000)
        circ_wanyuan = mcap_wanyuan * rng.uniform(0.4, 0.9)
        for d in range(n_days):
            rows.append({
                "ts_code": code,
                "trade_date": f"2026{3 + d // 30:02d}{(d % 30) + 1:02d}",
                # amount tushare 千元；screen 要求日均成交额 > 5 亿 = 500_000_000 元
                # 传入 amount 会被乘 1000 → 保持约 6 亿元
                "amount": rng.uniform(600_000, 1_200_000),
                "close": rng.uniform(10, 50),
                "total_mv": mcap_wanyuan,
                "circ_mv": circ_wanyuan,
                "turnover_rate": rng.uniform(0.5, 3.0),
            })
    return pd.DataFrame(rows)


def test_stock_universe_screen_does_not_crash():
    """Bug 2 regression: screen() used to crash with
    "_screen_single() takes 2 positional arguments but 3 were given"."""
    from invest.institutional.market_neutral import StockUniverse

    df = _synth_stock_data(n_stocks=10, n_days=25)
    universe = StockUniverse()
    results = universe.screen(df, date=df["trade_date"].max())

    assert isinstance(results, list)
    assert len(results) == 10  # one StockLiquidity per ticker


def test_stock_universe_screen_eligible_marked():
    """Screen should mark eligible stocks (satisfying liquidity + mcap)."""
    from invest.institutional.market_neutral import StockUniverse

    df = _synth_stock_data(n_stocks=20, n_days=30)
    universe = StockUniverse(
        min_amount=500_000_000,      # 5 亿
        min_mcap=20_000_000_000,     # 200 亿
        max_mcap=200_000_000_000,    # 2000 亿
    )
    results = universe.screen(df, date=df["trade_date"].max())
    eligible = [r for r in results if r.eligible]
    # 市值在 60-250 亿范围，所以应有一批 eligible
    assert len(eligible) > 0, "合成样本应至少有一只 eligible"
    for r in eligible:
        assert r.avg_amount_20d >= 500_000_000
        assert 20_000_000_000 <= r.market_cap <= 200_000_000_000


# ══════════════════════════════════════════════════════════════════════
# Bug 1 — MultiModelEnsemble default params
# ══════════════════════════════════════════════════════════════════════


def _synth_features_targets(n_rows: int = 5000, n_features: int = 8, seed: int = 0):
    """合成有信号的数据：target 中约 15% 的方差由 features 解释。"""
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, size=(n_rows, n_features))
    # 真实 linear combination
    true_beta = np.array([0.3, -0.2, 0.15, 0.1, 0, 0, 0.05, -0.05])[:n_features]
    y_signal = X @ true_beta
    y_noise = rng.normal(0, 1.0, size=n_rows)  # high noise
    y = y_signal + y_noise

    X_df = pd.DataFrame(X, columns=[f"f{i}" for i in range(n_features)])
    y_sr = pd.Series(y, name="target")
    return X_df, y_sr


def test_ensemble_default_params_actually_learn():
    """Bug 1 regression: with original defaults (L1=205, L2=581), models
    early-stopped at iteration 1 and IC was NaN. After fix both should
    train for > 5 iterations and ensemble predictions should correlate
    with true signal."""
    from invest.skills.portfolio_construction import MultiModelEnsemble

    X_tr, y_tr = _synth_features_targets(n_rows=4000, seed=1)
    X_va, y_va = _synth_features_targets(n_rows=1000, seed=2)
    X_te, y_te = _synth_features_targets(n_rows=2000, seed=3)

    ens = MultiModelEnsemble()  # defaults only
    fit_result = ens.fit(X_tr, y_tr, X_va, y_va, use_stacking=True)

    # 核心防退化：LGB 和 XGB 至少要训练到多轮而不是 1 轮
    assert fit_result["lgb_iteration"] is not None
    assert fit_result["lgb_iteration"] >= 5, (
        f"LGB best_iteration={fit_result['lgb_iteration']} — 看起来又被过度正则化压回 1 轮"
    )
    assert fit_result["xgb_iteration"] is not None
    assert fit_result["xgb_iteration"] >= 5, (
        f"XGB best_iteration={fit_result['xgb_iteration']} — 同上"
    )

    # 预测不应全 NaN 或全常数
    preds = ens.predict(X_te, method="weighted")
    assert not np.any(np.isnan(preds)), "weighted preds 含 NaN — 模型没学出来"
    assert np.std(preds) > 1e-6, "weighted preds 近常数 — 模型没学出来"

    # 真实 target 和预测应正相关（合成数据带信号 → 健康模型一定能看到）
    from scipy.stats import spearmanr
    rho, _ = spearmanr(preds, y_te)
    assert rho > 0.1, f"weighted IC 只有 {rho:.3f}，太低 — 模型几乎没学"


def test_ensemble_params_overridable():
    """确认用户传 custom params 仍能覆盖默认值。"""
    from invest.skills.portfolio_construction import MultiModelEnsemble

    custom_lgb = {
        "objective": "regression", "metric": "mse",
        "learning_rate": 0.1, "num_leaves": 7, "max_depth": 3,
        "lambda_l1": 0.01, "lambda_l2": 0.01, "verbose": -1,
    }
    ens = MultiModelEnsemble(lgb_params=custom_lgb)
    assert ens.lgb_params["learning_rate"] == 0.1
    assert ens.lgb_params["lambda_l1"] == 0.01


if __name__ == "__main__":
    import subprocess
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
