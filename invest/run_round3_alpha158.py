"""
Nous Invest — Alpha158 + LightGBM 第三轮 (1800只股票)
使用修复后的 Qlib bin 格式
"""
import multiprocessing
multiprocessing.set_start_method('fork', force=True)

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import json

import qlib
from qlib.config import REG_CN
from qlib.utils import init_instance_by_config
from qlib.data.dataset.handler import DataHandler
from qlib.contrib.data.handler import Alpha158
import lightgbm as lgb


def main():
    print("=" * 70)
    print("Nous Invest — 第三轮: Alpha158 + LightGBM (1800只股票)")
    print("=" * 70)

    qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region=REG_CN)
    print("✅ Qlib 初始化完成")

    # 使用 Alpha158 配置
    task_config = {
        "dataset": {
            "class": "DatasetH",
            "module_path": "qlib.data.dataset",
            "kwargs": {
                "handler": {
                    "class": "Alpha158",
                    "module_path": "qlib.contrib.data.handler",
                    "kwargs": {
                        "start_time": "2023-10-09",
                        "end_time": "2026-04-15",
                        "fit_start_time": "2023-10-09",
                        "fit_end_time": "2024-06-30",
                        "instruments": "csi300",  # 现在包含1800只股票
                    },
                },
                "segments": {
                    "train": ("2023-10-09", "2024-12-31"),
                    "valid": ("2025-01-01", "2025-06-30"),
                    "test":  ("2025-07-01", "2026-04-15"),
                },
            },
        },
    }

    print("\n📊 创建 Alpha158 数据集 (159个因子)...")
    dataset = init_instance_by_config(task_config["dataset"])
    print("✅ 数据集创建完成")

    print("\n🧠 训练 LightGBM 模型...")
    df_train = dataset.prepare("train", col_set=["feature", "label"], data_key=DataHandler.DK_L)
    df_valid = dataset.prepare("valid", col_set=["feature", "label"], data_key=DataHandler.DK_L)

    print(f"   训练集: {len(df_train)} 条")
    print(f"   验证集: {len(df_valid)} 条")

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
    print("\n" + "=" * 70)
    print("📊 IC / ICIR 评估")
    print("=" * 70)

    y_test = df_test["label"].values.squeeze()
    pred_df = pred.reset_index()
    pred_df.columns = ["datetime", "instrument", "score"]
    label_df = df_test["label"].reset_index()
    label_df.columns = ["datetime", "instrument", "label"]
    merged = pred_df.merge(label_df, on=["datetime", "instrument"])

    daily_ic = merged.groupby("datetime").apply(
        lambda g: stats.spearmanr(g["score"], g["label"])[0],
        include_groups=False
    )
    ic_mean = daily_ic.mean()
    ic_std = daily_ic.std()
    icir = ic_mean / ic_std if ic_std > 0 else 0
    annual_ir = ic_mean / ic_std * np.sqrt(252) if ic_std > 0 else 0
    ic_positive_ratio = (daily_ic > 0).mean()

    print(f"IC 均值:      {ic_mean:.4f}")
    print(f"IC 标准差:    {ic_std:.4f}")
    print(f"ICIR:         {icir:.4f}")
    print(f"年化 IR:      {annual_ir:.4f}")
    print(f"IC > 0 比例:  {ic_positive_ratio:.2%}")
    print(f"测试期:       {merged['datetime'].min().strftime('%Y-%m-%d')} ~ {merged['datetime'].max().strftime('%Y-%m-%d')}")
    print(f"交易日数量:   {len(daily_ic)}")
    print(f"股票数量:     {merged['instrument'].nunique()}")

    # 最新选股信号
    print("\n" + "=" * 70)
    print("🎯 最新选股信号 (Top 20)")
    print("=" * 70)

    last_date = pred_df["datetime"].max()
    last_day = pred_df[pred_df["datetime"] == last_date].sort_values("score", ascending=False)

    print(f"\n日期: {last_date.strftime('%Y-%m-%d')}")
    print(f"共 {len(last_day)} 只股票有预测")
    print("\nTop 20:")
    for i, (_, row) in enumerate(last_day.head(20).iterrows(), 1):
        print(f"  {i:2d}. {row['instrument']:>10s}  score: {row['score']:+.4f}")

    # 保存信号
    signals_dir = Path(__file__).parent / "signals"
    signals_dir.mkdir(exist_ok=True)
    signal_file = signals_dir / f"signal_{last_date.strftime('%Y%m%d')}_alpha158_1800.csv"
    last_day.to_csv(signal_file, index=False)
    print(f"\n💾 信号已保存: {signal_file}")

    # 保存指标
    metrics_file = signals_dir / f"metrics_{last_date.strftime('%Y%m%d')}_alpha158_1800.json"
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
        "num_stocks": int(merged['instrument'].nunique()),
    }
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"📊 指标已保存: {metrics_file}")

    print("\n✅ 第三轮 Alpha158 + 1800只股票完成!")


if __name__ == '__main__':
    main()
