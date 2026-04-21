"""
Nous Invest — Qlib LightGBM + Alpha158 基线跑通脚本
目标：at least useful — 输出 IC/ICIR + 每日选股信号
"""
import multiprocessing
multiprocessing.set_start_method('fork', force=True)

import json
import pandas as pd
from pathlib import Path

import qlib
from qlib.config import REG_CN
from qlib.utils import init_instance_by_config
from qlib.workflow.record_temp import SignalRecord, SigAnaRecord


def main():
    print("=" * 60)
    print("Nous Invest — Qlib LightGBM + Alpha158 基线")
    print("=" * 60)

    qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region=REG_CN)
    print("✅ Qlib 初始化完成")

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
                        "start_time": "2023-10-09",
                        "end_time": "2025-12-31",
                        "fit_start_time": "2023-10-09",
                        "fit_end_time": "2024-06-30",
                        "instruments": "csi300",
                    },
                },
                "segments": {
                    "train": ("2023-10-09", "2024-12-31"),
                    "valid": ("2025-01-01", "2025-06-30"),
                    "test": ("2025-07-01", "2026-03-31"),
                },
            },
        },
        "record": [
            {"class": "SignalRecord", "module_path": "qlib.workflow.record_temp"},
            {"class": "SigAnaRecord", "module_path": "qlib.workflow.record_temp"},
        ],
    }

    # 直接使用 LightGBM，绕过 Qlib MLflow recorder 的编码 bug
    from qlib.contrib.model.gbdt import LGBModel

    print("\n📊 创建数据集 (Alpha158 因子计算中，首次需要几分钟)...")
    dataset = init_instance_by_config(task_config["dataset"])
    print("✅ 数据集创建完成")

    print("\n🧠 训练 LightGBM 模型...")
    model = LGBModel(
        loss="mse",
        colsample_bytree=0.8879,
        learning_rate=0.0421,
        subsample=0.8789,
        lambda_l1=205.699,
        lambda_l2=580.976,
        max_depth=8,
        num_leaves=210,
        num_threads=4,
        verbose=-1,
    )

    # 获取训练/验证数据
    from qlib.data.dataset.handler import DataHandler

    df_train = dataset.prepare("train", col_set=["feature", "label"], data_key=DataHandler.DK_L)
    df_valid = dataset.prepare("valid", col_set=["feature", "label"], data_key=DataHandler.DK_L)

    x_train, y_train = df_train["feature"], df_train["label"]
    x_valid, y_valid = df_valid["feature"], df_valid["label"]

    import lightgbm as lgb
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

    # 预测
    print("\n📈 生成预测信号...")
    df_test = dataset.prepare("test", col_set=["feature", "label"], data_key=DataHandler.DK_L)
    x_test = df_test["feature"]
    pred_values = gbm.predict(x_test.values)

    # 构造预测 Series（和 qlib 格式对齐）
    pred = pd.Series(pred_values, index=x_test.index)
    print(f"✅ 预测完成，共 {len(pred)} 条预测")

    # IC 计算
    print("\n" + "=" * 60)
    print("📊 IC / ICIR 评估")
    print("=" * 60)

    y_test = df_test["label"].values.squeeze()
    from scipy import stats
    # 按日期计算 IC
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

    print(f"IC 均值:  {ic_mean:.4f}")
    print(f"IC 标准差: {ic_std:.4f}")
    print(f"ICIR:     {icir:.4f}")
    print(f"IC > 0 比例: {ic_positive_ratio:.2%}")
    print(f"测试期: {merged['datetime'].min().strftime('%Y-%m-%d')} ~ {merged['datetime'].max().strftime('%Y-%m-%d')}")

    # 输出最新选股信号
    print("\n" + "=" * 60)
    print("🎯 最新选股信号 (Top 20)")
    print("=" * 60)

    if isinstance(pred, pd.Series) and len(pred) > 0:
        pred_df = pred.reset_index()
        pred_df.columns = ["datetime", "instrument", "score"]

        last_date = pred_df["datetime"].max()
        last_day = pred_df[pred_df["datetime"] == last_date].sort_values("score", ascending=False)

        print(f"\n日期: {last_date.strftime('%Y-%m-%d')}")
        print(f"共 {len(last_day)} 只股票有预测")
        print("\nTop 20:")
        for i, (_, row) in enumerate(last_day.head(20).iterrows(), 1):
            print(f"  {i:2d}. {row['instrument']:>10s}  score: {row['score']:+.4f}")

        signals_dir = Path(__file__).parent / "signals"
        signals_dir.mkdir(exist_ok=True)
        signal_file = signals_dir / f"signal_{last_date.strftime('%Y%m%d')}.csv"
        last_day.to_csv(signal_file, index=False)
        print(f"\n💾 信号已保存: {signal_file}")
    else:
        print("⚠️ 预测结果为空")

    print("\n✅ 完成!")


if __name__ == '__main__':
    main()
