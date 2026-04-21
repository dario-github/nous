"""
Experiment 2026-04-21 — ensemble (portfolio_construction) vs simple (round2_simple)

目的：
1. 验证 `invest/skills/portfolio_construction.py` 的 MultiModelEnsemble 能跑通
2. 跟 `run_round2_simple.py` 的单 LGB 在同一份数据上做 IC/ICIR 对比
3. 测试 InstitutionalPipeline.daily_run() 是否能端到端走完（mock data）
4. 记录：runtime、crash、API 摩擦点、数字差异

局限：
- sandbox 无真实 tushare CSV，数据为合成（带跨截面 cross-section 结构的 A 股 like）
- 合成数据的 IC 数字**不代表真实表现**，只证明代码通路
- 真实数据对比需要在东丞本机跑
"""
import sys
import os
import time
import json
import traceback
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
import lightgbm as lgb

# repo root on path so invest.* imports work
ROOT = Path(__file__).resolve().parents[3]  # nous/
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "invest"))


# ═══════════════════════════════════════════════════════════════════
# 1. 合成 A 股 like 数据
# ═══════════════════════════════════════════════════════════════════

def make_synthetic_data(
    n_stocks: int = 300,
    n_days: int = 500,
    n_signals: int = 3,
    seed: int = 42,
) -> pd.DataFrame:
    """生成 A 股 like OHLCV 数据，带若干可预测的截面 signal，
    保证 round2 / ensemble 能学出 non-zero IC。"""
    rng = np.random.default_rng(seed)

    # 持久的 stock-level alpha（让模型能学到截面排序）
    true_alpha = rng.normal(0, 0.001, size=n_stocks)  # 日频 bps 级 alpha
    vol_scale = rng.uniform(0.01, 0.03, size=n_stocks)  # 每只股票波动率 1-3%
    drift = rng.normal(0, 0.0003, size=n_stocks)

    rows = []
    codes = [f"{i+1:06d}.{'SH' if i % 2 == 0 else 'SZ'}" for i in range(n_stocks)]

    for s_idx, code in enumerate(codes):
        price = 10.0 + rng.uniform(-2, 20)
        for d in range(n_days):
            ret = (
                drift[s_idx]
                + true_alpha[s_idx] * rng.normal(1.0, 0.3)  # persistent component
                + rng.normal(0, vol_scale[s_idx])            # idiosyncratic
            )
            new_price = price * (1 + ret)
            o = price * (1 + rng.normal(0, vol_scale[s_idx] / 3))
            h = max(o, new_price) * (1 + abs(rng.normal(0, vol_scale[s_idx] / 4)))
            l = min(o, new_price) * (1 - abs(rng.normal(0, vol_scale[s_idx] / 4)))
            v = rng.uniform(1e6, 5e7) * (1 + abs(ret) * 10)
            rows.append({
                "ts_code": code,
                "trade_date": f"2024{d+1:04d}"[-8:],  # fake date string
                "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=d),
                "open": o,
                "high": h,
                "low": l,
                "close": new_price,
                "vol": v,
                "amount": v * new_price / 1000,  # thousand yuan
                "total_mv": (rng.uniform(50e4, 5000e4)),  # 万元
                "circ_mv": (rng.uniform(30e4, 4000e4)),
                "turnover_rate": rng.uniform(0.5, 5.0),
            })
            price = new_price

    df = pd.DataFrame(rows)
    return df


# ═══════════════════════════════════════════════════════════════════
# 2. round2_simple 逻辑（复刻 invest/run_round2_simple.py）
# ═══════════════════════════════════════════════════════════════════

SIMPLE_FEATURES = [
    "return_1d", "return_5d", "return_20d",
    "ma5_ratio", "ma20_ratio",
    "volatility_20d", "vol_ratio", "price_position",
]


def compute_simple_features(df: pd.DataFrame) -> pd.DataFrame:
    def _calc(group):
        g = group.copy().sort_values("date")
        g["return_1d"] = g["close"].pct_change()
        g["return_5d"] = g["close"].pct_change(5)
        g["return_20d"] = g["close"].pct_change(20)
        g["ma5"] = g["close"].rolling(5).mean()
        g["ma20"] = g["close"].rolling(20).mean()
        g["ma5_ratio"] = g["close"] / g["ma5"] - 1
        g["ma20_ratio"] = g["close"] / g["ma20"] - 1
        g["volatility_20d"] = g["return_1d"].rolling(20).std() * np.sqrt(252)
        g["vol_ma5"] = g["vol"].rolling(5).mean()
        g["vol_ratio"] = g["vol"] / g["vol_ma5"]
        g["high_20d"] = g["high"].rolling(20).max()
        g["low_20d"] = g["low"].rolling(20).min()
        g["price_position"] = (g["close"] - g["low_20d"]) / (g["high_20d"] - g["low_20d"] + 1e-10)
        g["target"] = g["close"].shift(-5) / g["close"] - 1
        return g

    return df.groupby("ts_code", group_keys=False).apply(_calc).dropna()


def run_round2_simple(df_feat: pd.DataFrame) -> dict:
    t0 = time.time()
    # train/valid/test split
    dates = sorted(df_feat["date"].unique())
    n = len(dates)
    train_end = dates[int(n * 0.5)]
    valid_end = dates[int(n * 0.75)]

    train = df_feat[df_feat["date"] <= train_end]
    valid = df_feat[(df_feat["date"] > train_end) & (df_feat["date"] <= valid_end)]
    test = df_feat[df_feat["date"] > valid_end].copy()

    dtrain = lgb.Dataset(train[SIMPLE_FEATURES], label=train["target"])
    dvalid = lgb.Dataset(valid[SIMPLE_FEATURES], label=valid["target"], reference=dtrain)

    params = {
        "objective": "regression",
        "metric": "mse",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "max_depth": 6,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "verbose": -1,
    }
    model = lgb.train(
        params, dtrain, num_boost_round=200,
        valid_sets=[dvalid],
        callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(0)],
    )
    test["pred"] = model.predict(test[SIMPLE_FEATURES])

    daily_ic = test.groupby("date").apply(
        lambda g: stats.spearmanr(g["pred"], g["target"])[0] if len(g) > 2 else np.nan
    ).dropna()
    ic_mean = float(daily_ic.mean())
    ic_std = float(daily_ic.std())
    icir = ic_mean / ic_std if ic_std > 0 else 0.0
    annual_ir = icir * np.sqrt(252)

    return {
        "ic_mean": ic_mean,
        "ic_std": ic_std,
        "icir": icir,
        "annual_ir": annual_ir,
        "ic_positive_ratio": float((daily_ic > 0).mean()),
        "runtime_sec": time.time() - t0,
        "best_iteration": int(getattr(model, "best_iteration", 0) or 0),
    }


# ═══════════════════════════════════════════════════════════════════
# 3. portfolio_construction.MultiModelEnsemble（同数据同特征同 split）
# ═══════════════════════════════════════════════════════════════════

def run_ensemble(df_feat: pd.DataFrame, use_sane_params: bool = False) -> dict:
    """
    use_sane_params=False: 用 portfolio_construction.py 的 default
      默认 L1=205 L2=580 严重过度正则化，小数据上根本学不到
    use_sane_params=True : 用跟 round2_simple 同级别的 params
    """
    from invest.skills.portfolio_construction import MultiModelEnsemble

    t0 = time.time()
    dates = sorted(df_feat["date"].unique())
    n = len(dates)
    train_end = dates[int(n * 0.5)]
    valid_end = dates[int(n * 0.75)]

    train = df_feat[df_feat["date"] <= train_end]
    valid = df_feat[(df_feat["date"] > train_end) & (df_feat["date"] <= valid_end)]
    test = df_feat[df_feat["date"] > valid_end].copy()

    if use_sane_params:
        sane_lgb = {
            "objective": "regression", "metric": "mse",
            "learning_rate": 0.05, "num_leaves": 31, "max_depth": 6,
            "feature_fraction": 0.8, "bagging_fraction": 0.8,
            "lambda_l1": 0.1, "lambda_l2": 0.1,
            "verbose": -1,
        }
        sane_xgb = {
            "objective": "reg:squarederror",
            "learning_rate": 0.05, "max_depth": 6, "n_estimators": 300,
            "subsample": 0.8, "colsample_bytree": 0.8,
            "reg_alpha": 0.1, "reg_lambda": 0.1,
            "early_stopping_rounds": 30, "verbosity": 0,
        }
        ens = MultiModelEnsemble(lgb_params=sane_lgb, xgb_params=sane_xgb)
    else:
        ens = MultiModelEnsemble()

    try:
        fit_result = ens.fit(
            train[SIMPLE_FEATURES], train["target"],
            valid[SIMPLE_FEATURES], valid["target"],
            use_stacking=True,
        )
    except Exception as e:
        return {
            "status": "fit_crashed",
            "error": str(e),
            "trace": traceback.format_exc(),
            "runtime_sec": time.time() - t0,
        }

    try:
        preds_weighted = ens.predict(test[SIMPLE_FEATURES], method="weighted")
        test["pred_weighted"] = preds_weighted
        preds_stacking = ens.predict(test[SIMPLE_FEATURES], method="stacking")
        test["pred_stacking"] = preds_stacking
    except Exception as e:
        return {
            "status": "predict_crashed",
            "error": str(e),
            "trace": traceback.format_exc(),
            "runtime_sec": time.time() - t0,
        }

    results = {"fit_result": {k: (v if isinstance(v, (int, float, dict, type(None))) else str(v)) for k, v in fit_result.items()}}
    for method, col in [("weighted", "pred_weighted"), ("stacking", "pred_stacking")]:
        daily_ic = test.groupby("date").apply(
            lambda g, c=col: stats.spearmanr(g[c], g["target"])[0] if len(g) > 2 else np.nan
        ).dropna()
        ic_mean = float(daily_ic.mean())
        ic_std = float(daily_ic.std())
        results[method] = {
            "ic_mean": ic_mean,
            "ic_std": ic_std,
            "icir": ic_mean / ic_std if ic_std > 0 else 0.0,
            "annual_ir": (ic_mean / ic_std * np.sqrt(252)) if ic_std > 0 else 0.0,
            "ic_positive_ratio": float((daily_ic > 0).mean()),
        }

    results["runtime_sec"] = time.time() - t0
    results["status"] = "ok"
    return results


# ═══════════════════════════════════════════════════════════════════
# 4. InstitutionalPipeline.daily_run() — end-to-end smoke test
# ═══════════════════════════════════════════════════════════════════

def run_institutional_smoke(df_raw: pd.DataFrame, ml_scores: pd.Series) -> dict:
    """用合成数据喂 InstitutionalPipeline.daily_run 看哪里崩。"""
    try:
        from invest.institutional.pipeline import InstitutionalPipeline
    except Exception as e:
        return {"status": "import_failed", "error": str(e), "trace": traceback.format_exc()}

    t0 = time.time()
    pipe = InstitutionalPipeline()

    # build sector_map + stock_betas (random)
    codes = ml_scores.index.tolist()
    sectors = ["银行", "食品饮料", "医药", "电子", "计算机", "化工", "汽车", "机械"]
    rng = np.random.default_rng(7)
    sector_map = {c: sectors[rng.integers(0, len(sectors))] for c in codes}
    stock_betas = pd.Series(rng.normal(1.0, 0.3, size=len(codes)), index=codes)

    # fund_nav 3-month fake trajectory for VaR
    nav = pd.Series(
        100 * np.cumprod(1 + rng.normal(0.0003, 0.01, size=120)),
        index=pd.date_range("2025-01-01", periods=120, freq="B"),
    )

    try:
        out = pipe.daily_run(
            stock_data=df_raw,
            ml_scores=ml_scores,
            fund_nav=nav,
            sector_map=sector_map,
            stock_betas=stock_betas,
            date="20260421",
        )
        runtime = time.time() - t0
        return {
            "status": out.get("status", "unknown"),
            "universe_total": out.get("universe", {}).get("total"),
            "universe_eligible": out.get("universe", {}).get("eligible"),
            "portfolio_long_n": len(getattr(out.get("portfolio"), "long_codes", [])) if out.get("portfolio") else 0,
            "portfolio_short_n": len(getattr(out.get("portfolio"), "short_codes", [])) if out.get("portfolio") else 0,
            "gross_leverage": getattr(out.get("portfolio"), "gross_leverage", None) if out.get("portfolio") else None,
            "net_leverage": getattr(out.get("portfolio"), "net_leverage", None) if out.get("portfolio") else None,
            "n_compliance_checks": len(out.get("compliance_checks") or []),
            "risk_level": getattr(out.get("risk_metrics"), "overall_risk_level", None).value
                if out.get("risk_metrics") else None,
            "runtime_sec": runtime,
            "message": out.get("message"),
        }
    except Exception as e:
        return {
            "status": "crashed",
            "error": str(e),
            "trace": traceback.format_exc()[:2000],
            "runtime_sec": time.time() - t0,
        }


# ═══════════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════════

def main():
    results = {"meta": {
        "timestamp": pd.Timestamp.now().isoformat(),
        "hint": "synthetic data — numbers are structural, not production alpha",
    }}

    print("[1/4] Synth data...")
    df_raw = make_synthetic_data(n_stocks=300, n_days=500)
    print(f"  rows={len(df_raw)}, stocks={df_raw['ts_code'].nunique()}, days={df_raw['date'].nunique()}")

    print("[2/4] compute features...")
    df_feat = compute_simple_features(df_raw)
    print(f"  usable rows after NaN drop: {len(df_feat)}")

    print("[3a] run round2_simple...")
    res_simple = run_round2_simple(df_feat)
    print(f"  IC {res_simple['ic_mean']:.4f}  ICIR {res_simple['icir']:.3f}  runtime {res_simple['runtime_sec']:.1f}s")
    results["round2_simple"] = res_simple

    print("[3b] run ensemble with DEFAULT params (as shipped)...")
    res_ens_default = run_ensemble(df_feat, use_sane_params=False)
    if res_ens_default["status"] == "ok":
        for m in ("weighted", "stacking"):
            print(f"  [{m}] IC {res_ens_default[m]['ic_mean']:.4f}  ICIR {res_ens_default[m]['icir']:.3f}")
    else:
        print(f"  FAILED: {res_ens_default['status']}")
    print(f"  total runtime {res_ens_default['runtime_sec']:.1f}s")
    results["ensemble_default_params"] = res_ens_default

    print("[3c] run ensemble with SANE params (matched to round2)...")
    res_ens_sane = run_ensemble(df_feat, use_sane_params=True)
    if res_ens_sane["status"] == "ok":
        for m in ("weighted", "stacking"):
            print(f"  [{m}] IC {res_ens_sane[m]['ic_mean']:.4f}  ICIR {res_ens_sane[m]['icir']:.3f}")
    else:
        print(f"  FAILED: {res_ens_sane['status']}")
    print(f"  total runtime {res_ens_sane['runtime_sec']:.1f}s")
    results["ensemble_sane_params"] = res_ens_sane

    print("[4] institutional pipeline smoke...")
    # build ml_scores — use df_raw last day directly to avoid groupby column issues
    last_day = df_raw["date"].max()
    last_codes = df_raw[df_raw["date"] == last_day]["ts_code"].unique()
    ml_scores = pd.Series(
        np.random.RandomState(0).normal(0, 1, size=len(last_codes)),
        index=list(last_codes),
    )
    res_inst = run_institutional_smoke(df_raw, ml_scores)
    print(f"  status: {res_inst.get('status')}  runtime {res_inst.get('runtime_sec'):.1f}s")
    if res_inst.get("status") == "crashed":
        print(f"  error: {res_inst.get('error')[:300]}")
    results["institutional"] = res_inst

    out_path = Path(__file__).parent / "results.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nresults → {out_path}")
    return results


if __name__ == "__main__":
    main()
