"""
Nous Invest — Qlib LightGBM + Alpha158 第二轮（最新数据 2023.10~2026.04）
目标：at least useful — 输出 IC/ICIR + 每日选股信号
"""
import multiprocessing
multiprocessing.set_start_method('fork', force=True)

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

import qlib
from qlib.config import REG_CN
from qlib.utils import init_instance_by_config
from qlib.data.dataset.handler import DataHandler


def main():
    print("=" * 60)
    print("Nous Invest — 第二轮: LightGBM + Alpha158 (数据 2023.10~2026.04)")
    print("=" * 60)

    qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region=REG_CN)
    print("✅ Qlib 初始化完成")

    # 数据集配置 (延长测试集到最新数据)
    task_config = {
        "model": {
            "class": "LGBModel",
            "module_path": "qlib.contrib.model.gbdt",
            "kwargs": {
                "loss": "mse",
                "colsample_bytree": 0.8879,
                "learning_rate": 0.0421,
                "subsample": 0.8789,
                "lambda_l1": 205.699,
                "lambda_l2": 580.976,
                "max_depth": 8,
                "num_leaves": 210,
                "num_threads": 4,
                "verbose": -1,
            },
        },
        "dataset": {
            "class": "DatasetH",
            "module_path": "qlib.data.dataset",
            "kwargs": {
                "handler": {
                    "class": "Alpha158",
                    "module_path": "qlib.contrib.data.handler",
                    "kwargs": {
                        "start_time": "2015-01-01",
                        "end_time": "2026-04-15",  # 更新到最新
                        "fit_start_time": "2015-01-01",
                        "fit_end_time": "2021-12-31",
                        "instruments": "csi300",
                    },
                },
                "segments": {
                    "train": ("2015-01-01", "2021-12-31"),
                    "valid": ("2022-01-01", "2023-09-30"),
                    "test":  ("2023-10-01", "2026-04-15"),  # 重点测试新数据
                },
            },
        },
    }

    print("\n📊 创建数据集 (Alpha158 因子计算中)...")
    dataset = init_instance_by_config(task_config["dataset"])
    print("✅ 数据集创建完成")

    print("\n🧠 训练 LightGBM 模型...")
    import lightgbm as lgb

    df_train = dataset.prepare("train", col_set=["feature", "label"], data_key=DataHandler.DK_L)
    df_valid = dataset.prepare("valid", col_set=["feature", "label"], data_key=DataHandler.DK_L)

    x_train, y_train = df_train["feature"], df_train["label"]
    x_valid, y_valid = df_valid["feature"], df_valid["label"]

    dtrain = lgb.Dataset(x_train.values, label=y_train.values.squeeze())
    dvalid = lgb.Dataset(x_valid.values, label=y_valid.values.squeeze(), reference=dtrain)

    params = {
        "objective": "mse",
        "colsample_bytree": 0.8879,
        "learning_rate": 0.0421,
        "subsample": 0.8789,
        "lambda_l1": 205.699,
        "lambda_l2": 580.976,
        "max_depth": 8,
        "num_leaves": 210,
        "num_threads": 4,
        "verbose": -1,
        "metric": "mse",
    }

    gbm = lgb.train(
        params,
        dtrain,
        num_boost_round=500,
        valid_sets=[dvalid],
        callbacks=[lgb.early_stopping(50, verbose=True), lgb.log_evaluation(0)],
    )
    print(f"✅ 模型训练完成，best iteration: {gbm.best_iteration}")

    print("\n📈 生成预测信号...")
    df_test = dataset.prepare("test", col_set=["feature", "label"], data_key=DataHandler.DK_L)
    x_test = df_test["feature"]
    pred_values = gbm.predict(x_test.values)

    pred = pd.Series(pred_values, index=x_test.index)
    print(f"✅ 预测完成，共 {len(pred)} 条预测")

    # IC / ICIR 计算
    print("\n" + "=" * 60)
    print("📊 IC / ICIR 评估")
    print("=" * 60)

    y_test = df_test["label"].values.squeeze()
    pred_df = pred.reset_index()
    pred_df.columns = ["datetime", "instrument", "score"]
    label_df = df_test["label"].reset_index()
    label_df.columns = ["datetime", "instrument", "label"]
    merged = pred_df.merge(label_df, on=["datetime", "instrument"])

    daily_ic = merged.groupby("datetime").apply(
        lambda g: stats.spearmanr(g["score"], g["label"])[0]
    )
    ic_mean = daily_ic.mean()
    ic_std = daily_ic.std()
    icir = ic_mean / ic_std if ic_std > 0 else 0
    ic_positive_ratio = (daily_ic > 0).mean()
    
    # 添加年化IR
    annual_ir = ic_mean / ic_std * np.sqrt(252) if ic_std > 0 else 0

    print(f"IC 均值:      {ic_mean:.4f}")
    print(f"IC 标准差:    {ic_std:.4f}")
    print(f"ICIR:         {icir:.4f}")
    print(f"年化 IR:      {annual_ir:.4f}")
    print(f"IC > 0 比例:  {ic_positive_ratio:.2%}")
    print(f"测试期:       {merged['datetime'].min().strftime('%Y-%m-%d')} ~ {merged['datetime'].max().strftime('%Y-%m-%d')}")
    print(f"交易日数量:   {len(daily_ic)}")

    # 最新选股信号
    print("\n" + "=" * 60)
    print("🎯 最新选股信号 (Top 20)")
    print("=" * 60)

    last_date = pred_df["datetime"].max()
    last_day = pred_df[pred_df["datetime"] == last_date].sort_values("score", ascending=False)

    print(f"\n日期: {last_date.strftime('%Y-%m-%d')}")
    print(f"共 {len(last_day)} 只股票有预测")
    print("\nTop 20:")
    for i, (_, row) in enumerate(last_day.head(20).iterrows(), 1):
        print(f"  {i:2d}. {row['instrument']:>10s}  score: {row['score']:+.4f}")

    signals_dir = Path(__file__).parent / "signals"
    signals_dir.mkdir(exist_ok=True)
    signal_file = signals_dir / f"signal_{last_date.strftime('%Y%m%d')}_round2.csv"
    last_day.to_csv(signal_file, index=False)
    print(f"\n💾 信号已保存: {signal_file}")

    # 保存评估指标
    metrics_file = signals_dir / f"metrics_{last_date.strftime('%Y%m%d')}_round2.json"
    import json
    metrics = {
        "date": last_date.strftime('%Y-%m-%d'),
        "ic_mean": float(ic_mean),
        "ic_std": float(ic_std),
        "icir": float(icir),
        "annual_ir": float(annual_ir),
        "ic_positive_ratio": float(ic_positive_ratio),
        "test_period": {
            "start": merged['datetime'].min().strftime('%Y-%m-%d'),
            "end": merged['datetime'].max().strftime('%Y-%m-%d'),
        },
        "num_trading_days": int(len(daily_ic)),
        "num_predictions": int(len(pred)),
    }
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"📊 指标已保存: {metrics_file}")

    print("\n✅ 第二轮完成!")


if __name__ == '__main__':
    main()
