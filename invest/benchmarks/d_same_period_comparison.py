"""
D-benchmark：在同一 train/valid/test 切分上对比
  A. 我们的 round2_simple 基线（CSI300 + 8 因子 LGB，Spearman IC 0.0212）
  B. Qlib 官方 Alpha158 + LGB（canonical params L1=205.7 / L2=580.9）

目的：把"我们 IC 0.0212 是否合理"这件事，在**同时段**上跟 Qlib 官方基线对齐，
给董事长汇报时提供 apples-to-apples 的 context。

运行前置：
1. tushare 数据在 invest/data/tushare_csi300_*.csv
2. Qlib bin 数据在 ~/.qlib/qlib_data/cn_data（已跑过 convert_to_qlib_bin.py）
3. Python 环境同 invest/requirements.txt

输出：
- invest/benchmarks/d_results.json
- 控制台打印 side-by-side 表

用法：
    cd invest && python3 benchmarks/d_same_period_comparison.py
"""
import multiprocessing
multiprocessing.set_start_method("fork", force=True)

import sys
import json
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy import stats
import lightgbm as lgb

ROOT = Path(__file__).resolve().parents[1]  # invest/
sys.path.insert(0, str(ROOT))

# ═══════════════════════════════════════════════════════════════════
# 对齐 round2_simple 的切分（hardcoded，不改）
# ═══════════════════════════════════════════════════════════════════
TRAIN_END = pd.Timestamp("2024-06-30")
VALID_END = pd.Timestamp("2025-03-31")
TEST_START_STR = "2025-04-01"  # 同 round2_simple


# ═══════════════════════════════════════════════════════════════════
# A. round2_simple 复现（只用 8 因子）
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


def run_round2_simple(csv_path: Path) -> dict:
    print(f"\n[A] round2_simple on {csv_path.name}")
    t0 = time.time()
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df = df.sort_values(["ts_code", "date"])

    df_feat = compute_simple_features(df)
    train = df_feat[df_feat["date"] <= TRAIN_END]
    valid = df_feat[(df_feat["date"] > TRAIN_END) & (df_feat["date"] <= VALID_END)]
    test = df_feat[df_feat["date"] > VALID_END].copy()
    print(f"    rows train/valid/test = {len(train)}/{len(valid)}/{len(test)}")

    dtrain = lgb.Dataset(train[SIMPLE_FEATURES], label=train["target"])
    dvalid = lgb.Dataset(valid[SIMPLE_FEATURES], label=valid["target"], reference=dtrain)
    params = {
        "objective": "regression", "metric": "mse",
        "learning_rate": 0.05, "num_leaves": 31, "max_depth": 6,
        "feature_fraction": 0.8, "bagging_fraction": 0.8, "verbose": -1,
    }
    model = lgb.train(
        params, dtrain, num_boost_round=500,
        valid_sets=[dvalid],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )
    test["pred"] = model.predict(test[SIMPLE_FEATURES])

    daily_ic = test.groupby("date").apply(
        lambda g: stats.spearmanr(g["pred"], g["target"])[0] if len(g) > 2 else np.nan
    ).dropna()
    # 额外算 Pearson IC 用于跟 Qlib "IC" 列对比
    daily_pearson_ic = test.groupby("date").apply(
        lambda g: stats.pearsonr(g["pred"], g["target"])[0] if len(g) > 2 else np.nan
    ).dropna()

    return {
        "pearson_ic_mean": float(daily_pearson_ic.mean()),
        "spearman_ic_mean": float(daily_ic.mean()),
        "pearson_icir": float(daily_pearson_ic.mean() / daily_pearson_ic.std()) if daily_pearson_ic.std() > 0 else 0.0,
        "spearman_icir": float(daily_ic.mean() / daily_ic.std()) if daily_ic.std() > 0 else 0.0,
        "annual_rank_ir": float(daily_ic.mean() / daily_ic.std() * np.sqrt(252)) if daily_ic.std() > 0 else 0.0,
        "ic_positive_ratio": float((daily_ic > 0).mean()),
        "num_trading_days": int(len(daily_ic)),
        "num_predictions": int(len(test)),
        "best_iteration": int(model.best_iteration or 0),
        "test_start": str(test["date"].min().date()),
        "test_end": str(test["date"].max().date()),
        "runtime_sec": time.time() - t0,
    }


# ═══════════════════════════════════════════════════════════════════
# B. Qlib Alpha158 + LGB（canonical params）
# ═══════════════════════════════════════════════════════════════════

def run_qlib_alpha158(
    provider_uri: str = "~/.qlib/qlib_data/cn_data",
    instruments: str = "csi300",
    start_time: str = "2015-01-01",
) -> dict:
    print(f"\n[B] Qlib Alpha158 + LGB, instruments={instruments}")
    t0 = time.time()

    import qlib
    from qlib.config import REG_CN
    from qlib.utils import init_instance_by_config
    from qlib.data.dataset.handler import DataHandler

    qlib.init(provider_uri=provider_uri, region=REG_CN)
    print("    qlib inited")

    task_config = {
        "dataset": {
            "class": "DatasetH",
            "module_path": "qlib.data.dataset",
            "kwargs": {
                "handler": {
                    "class": "Alpha158",
                    "module_path": "qlib.contrib.data.handler",
                    "kwargs": {
                        "start_time": start_time,
                        "end_time": "2026-04-15",
                        "fit_start_time": start_time,
                        "fit_end_time": str(TRAIN_END.date()),
                        "instruments": instruments,
                    },
                },
                "segments": {
                    "train": (start_time, str(TRAIN_END.date())),
                    "valid": (str(TRAIN_END.date() + pd.Timedelta(days=1)), str(VALID_END.date())),
                    "test": (TEST_START_STR, "2026-04-15"),
                },
            },
        },
    }

    dataset = init_instance_by_config(task_config["dataset"])
    df_train = dataset.prepare("train", col_set=["feature", "label"], data_key=DataHandler.DK_L)
    df_valid = dataset.prepare("valid", col_set=["feature", "label"], data_key=DataHandler.DK_L)
    df_test = dataset.prepare("test", col_set=["feature", "label"], data_key=DataHandler.DK_L)
    print(f"    rows train/valid/test = {len(df_train)}/{len(df_valid)}/{len(df_test)}")

    x_train, y_train = df_train["feature"], df_train["label"]
    x_valid, y_valid = df_valid["feature"], df_valid["label"]
    x_test, y_test = df_test["feature"], df_test["label"]

    dtrain = lgb.Dataset(x_train.values, label=y_train.values.squeeze())
    dvalid = lgb.Dataset(x_valid.values, label=y_valid.values.squeeze(), reference=dtrain)

    # Qlib canonical params — 对 158 维特征合理
    params = {
        "objective": "mse",
        "colsample_bytree": 0.8879, "learning_rate": 0.0421, "subsample": 0.8789,
        "lambda_l1": 205.699, "lambda_l2": 580.976,
        "max_depth": 8, "num_leaves": 210,
        "num_threads": 4, "verbose": -1, "metric": "mse",
    }
    gbm = lgb.train(
        params, dtrain, num_boost_round=500,
        valid_sets=[dvalid],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )
    preds = gbm.predict(x_test.values)

    pred_df = pd.DataFrame({"pred": preds, "target": y_test.values.squeeze()},
                           index=x_test.index)
    # Qlib index: (datetime, instrument)
    daily_rank_ic = pred_df.groupby(level="datetime").apply(
        lambda g: stats.spearmanr(g["pred"], g["target"])[0] if len(g) > 2 else np.nan
    ).dropna()
    daily_pearson_ic = pred_df.groupby(level="datetime").apply(
        lambda g: stats.pearsonr(g["pred"], g["target"])[0] if len(g) > 2 else np.nan
    ).dropna()

    return {
        "pearson_ic_mean": float(daily_pearson_ic.mean()),
        "spearman_ic_mean": float(daily_rank_ic.mean()),
        "pearson_icir": float(daily_pearson_ic.mean() / daily_pearson_ic.std()) if daily_pearson_ic.std() > 0 else 0.0,
        "spearman_icir": float(daily_rank_ic.mean() / daily_rank_ic.std()) if daily_rank_ic.std() > 0 else 0.0,
        "annual_rank_ir": float(daily_rank_ic.mean() / daily_rank_ic.std() * np.sqrt(252)) if daily_rank_ic.std() > 0 else 0.0,
        "ic_positive_ratio": float((daily_rank_ic > 0).mean()),
        "num_trading_days": int(len(daily_rank_ic)),
        "num_predictions": int(len(pred_df)),
        "best_iteration": int(gbm.best_iteration or 0),
        "test_start": TEST_START_STR,
        "test_end": "2026-04-15",
        "instruments": instruments,
        "runtime_sec": time.time() - t0,
    }


# ═══════════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════════

def main():
    out = {
        "meta": {
            "purpose": "D-benchmark same-period comparison (round2_simple vs Qlib Alpha158 LGB)",
            "split": {
                "train_end": str(TRAIN_END.date()),
                "valid_end": str(VALID_END.date()),
                "test_start": TEST_START_STR,
            },
            "timestamp": pd.Timestamp.now().isoformat(),
        }
    }

    # A: round2_simple on CSI300 CSV
    csv_candidates = [
        ROOT / "data" / "tushare_csi300_202310_202604.csv",
        ROOT / "data" / "tushare_csi300_2023_2026.csv",
    ]
    csv = next((p for p in csv_candidates if p.exists()), None)
    if csv is None:
        print(f"[A] SKIP — 没找到 CSV，检查路径：{[str(p) for p in csv_candidates]}")
        out["round2_simple"] = {"status": "skipped_no_csv"}
    else:
        out["round2_simple"] = run_round2_simple(csv)
        out["round2_simple"]["status"] = "ok"

    # B: Qlib Alpha158
    try:
        out["qlib_alpha158_lgb"] = run_qlib_alpha158(instruments="csi300")
        out["qlib_alpha158_lgb"]["status"] = "ok"
    except Exception as e:
        import traceback
        out["qlib_alpha158_lgb"] = {
            "status": "crashed", "error": str(e),
            "trace": traceback.format_exc()[:2000],
        }

    # 保存 + 打印 side-by-side
    results_file = Path(__file__).parent / "d_results.json"
    results_file.write_text(json.dumps(out, indent=2, default=str))

    print("\n" + "=" * 78)
    print("D benchmark — same period comparison")
    print(f"Train ≤ {TRAIN_END.date()}   Valid = {(TRAIN_END+pd.Timedelta(days=1)).date()}..{VALID_END.date()}   "
          f"Test = {TEST_START_STR}..2026-04-15")
    print("=" * 78)
    print(f"\n{'Metric':<28} {'round2_simple':<20} {'Qlib Alpha158 LGB':<20}")
    print("-" * 78)
    a = out.get("round2_simple", {})
    b = out.get("qlib_alpha158_lgb", {})

    def _fmt(d, k):
        v = d.get(k)
        if v is None:
            return "—"
        if isinstance(v, float):
            return f"{v:.4f}" if abs(v) < 10 else f"{v:.2f}"
        return str(v)

    for metric in [
        "pearson_ic_mean", "spearman_ic_mean",
        "pearson_icir", "spearman_icir", "annual_rank_ir",
        "ic_positive_ratio",
        "num_trading_days", "num_predictions",
        "best_iteration", "runtime_sec",
    ]:
        print(f"{metric:<28} {_fmt(a, metric):<20} {_fmt(b, metric):<20}")

    print(f"\nresults → {results_file}")
    print("\n读法：")
    print("  - 如果 Qlib Alpha158 的 spearman_ic 在此时段也 < 0.03，说明")
    print("    2025-04~2026-04 市场对所有因子模型都更难，我们的 0.0212 在此背景下合理。")
    print("  - 如果 Qlib Alpha158 达到 0.04+ 而我们只有 0.0212，则确实是我们")
    print("    的模型（8 因子 vs 158）还有明显改进空间。")


if __name__ == "__main__":
    main()
