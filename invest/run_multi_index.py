"""
Nous Invest — 多指数股票池模型训练 (CSI300 + CSI500 + CSI1000)
支持灵活配置股票池，输出 IC/ICIR + 每日选股信号
"""
import multiprocessing
multiprocessing.set_start_method('fork', force=True)

import json
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

import qlib
from qlib.config import REG_CN
from qlib.utils import init_instance_by_config
from qlib.data.dataset.handler import DataHandler

# 指数配置
INDEX_CONFIGS = {
    "csi300": {
        "name": "沪深300",
        "instruments": "csi300",
        "start_time": "2015-01-01",
        "end_time": "2026-04-15",
    },
    "csi500": {
        "name": "中证500",
        "instruments": "csi500",
        "start_time": "2015-01-01",
        "end_time": "2026-04-15",
    },
    "csi1000": {
        "name": "中证1000",
        "instruments": "csi1000",
        "start_time": "2015-01-01",
        "end_time": "2026-04-15",
    },
    "multi_index": {
        "name": "多指数合并(300+500+1000)",
        "instruments": "csi300+csi500+csi1000",  # 自定义标记
        "start_time": "2015-01-01",
        "end_time": "2026-04-15",
    }
}


def get_instrument_list(index_key):
    """获取指定指数的成分股列表"""
    if index_key in ["csi300", "csi500", "csi1000"]:
        # Qlib 内置支持
        return index_key
    elif index_key == "multi_index":
        # 需要自定义合并
        return "multi_index"
    return index_key


def create_task_config(index_key, custom_instruments=None):
    """创建训练配置"""
    config = INDEX_CONFIGS.get(index_key, INDEX_CONFIGS["multi_index"])
    
    # 使用自定义股票池（如果有）
    instruments = custom_instruments if custom_instruments else config["instruments"]
    
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
                        "start_time": config["start_time"],
                        "end_time": config["end_time"],
                        "fit_start_time": "2015-01-01",
                        "fit_end_time": "2021-12-31",
                        "instruments": instruments,
                    },
                },
                "segments": {
                    "train": ("2015-01-01", "2021-12-31"),
                    "valid": ("2022-01-01", "2023-09-30"),
                    "test": ("2023-10-01", "2026-04-15"),
                },
            },
        },
    }
    return task_config, config["name"]


def train_model(dataset, index_name):
    """训练 LightGBM 模型"""
    print(f"\n🧠 训练 {index_name} LightGBM 模型...")
    
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
    print(f"✅ {index_name} 模型训练完成，best iteration: {gbm.best_iteration}")
    
    return gbm


def evaluate_model(gbm, dataset, index_name):
    """评估模型性能"""
    print(f"\n📈 生成 {index_name} 预测信号...")
    
    df_test = dataset.prepare("test", col_set=["feature", "label"], data_key=DataHandler.DK_L)
    x_test = df_test["feature"]
    pred_values = gbm.predict(x_test.values)
    
    pred = pd.Series(pred_values, index=x_test.index)
    print(f"✅ 预测完成，共 {len(pred)} 条预测")
    
    # IC / ICIR 计算
    print("\n" + "=" * 60)
    print(f"📊 {index_name} IC / ICIR 评估")
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
    annual_ir = ic_mean / ic_std * np.sqrt(252) if ic_std > 0 else 0
    
    print(f"IC 均值:      {ic_mean:.4f}")
    print(f"IC 标准差:    {ic_std:.4f}")
    print(f"ICIR:         {icir:.4f}")
    print(f"年化 IR:      {annual_ir:.4f}")
    print(f"IC > 0 比例:  {ic_positive_ratio:.2%}")
    print(f"测试期:       {merged['datetime'].min().strftime('%Y-%m-%d')} ~ {merged['datetime'].max().strftime('%Y-%m-%d')}")
    print(f"交易日数量:   {len(daily_ic)}")
    print(f"预测总数:     {len(pred)}")
    
    return {
        "index_name": index_name,
        "ic_mean": float(ic_mean),
        "ic_std": float(ic_std),
        "icir": float(icir),
        "annual_ir": float(annual_ir),
        "ic_positive_ratio": float(ic_positive_ratio),
        "num_trading_days": int(len(daily_ic)),
        "num_predictions": int(len(pred)),
        "test_period": {
            "start": merged['datetime'].min().strftime('%Y-%m-%d'),
            "end": merged['datetime'].max().strftime('%Y-%m-%d'),
        },
        "pred_df": pred_df,
        "last_date": pred_df["datetime"].max(),
    }


def save_signals(eval_result, suffix=""):
    """保存选股信号和指标"""
    pred_df = eval_result["pred_df"]
    last_date = eval_result["last_date"]
    index_name = eval_result["index_name"]
    
    signals_dir = Path(__file__).parent / "signals"
    signals_dir.mkdir(exist_ok=True)
    
    # 最新选股信号
    last_day = pred_df[pred_df["datetime"] == last_date].sort_values("score", ascending=False)
    
    print(f"\n{'='*60}")
    print(f"🎯 {index_name} 最新选股信号 (Top 20) - {last_date.strftime('%Y-%m-%d')}")
    print(f"{'='*60}")
    print(f"共 {len(last_day)} 只股票有预测\n")
    print("Top 20:")
    for i, (_, row) in enumerate(last_day.head(20).iterrows(), 1):
        print(f"  {i:2d}. {row['instrument']:>10s}  score: {row['score']:+.4f}")
    
    # 保存信号
    signal_file = signals_dir / f"signal_{last_date.strftime('%Y%m%d')}_{suffix}.csv"
    last_day.to_csv(signal_file, index=False)
    print(f"\n💾 信号已保存: {signal_file}")
    
    # 保存指标
    metrics = {
        "date": last_date.strftime('%Y-%m-%d'),
        "index_name": index_name,
        "ic_mean": eval_result["ic_mean"],
        "ic_std": eval_result["ic_std"],
        "icir": eval_result["icir"],
        "annual_ir": eval_result["annual_ir"],
        "ic_positive_ratio": eval_result["ic_positive_ratio"],
        "test_period": eval_result["test_period"],
        "num_trading_days": eval_result["num_trading_days"],
        "num_predictions": eval_result["num_predictions"],
    }
    
    metrics_file = signals_dir / f"metrics_{last_date.strftime('%Y%m%d')}_{suffix}.json"
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"📊 指标已保存: {metrics_file}")
    
    return metrics


def run_single_index(index_key, custom_instruments=None):
    """运行单个指数的模型训练"""
    task_config, index_name = create_task_config(index_key, custom_instruments)
    
    print("\n" + "=" * 60)
    print(f"🚀 开始训练: {index_name}")
    print(f"股票池: {task_config['dataset']['kwargs']['handler']['kwargs']['instruments']}")
    print("=" * 60)
    
    print("\n📊 创建数据集 (Alpha158 因子计算中，可能需要几分钟)...")
    dataset = init_instance_by_config(task_config["dataset"])
    print("✅ 数据集创建完成")
    
    # 训练模型
    gbm = train_model(dataset, index_name)
    
    # 评估
    eval_result = evaluate_model(gbm, dataset, index_name)
    
    # 保存结果
    suffix = index_key.replace("csi", "csi").replace("+", "_")
    metrics = save_signals(eval_result, suffix=suffix)
    
    return metrics


def main():
    print("=" * 60)
    print("Nous Invest — 多指数股票池模型训练")
    print("支持: CSI300 + CSI500 + CSI1000")
    print("=" * 60)
    
    qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region=REG_CN)
    print("✅ Qlib 初始化完成")
    
    # 检查数据可用性
    from qlib.data import D
    
    # 尝试获取各指数的股票列表
    available_indices = []
    for idx_key in ["csi300", "csi500", "csi1000"]:
        try:
            instruments = D.instruments(idx_key)
            df = D.list_instruments(instruments=instruments, start_time="2026-01-01", end_time="2026-04-15", as_list=True)
            if df:
                print(f"  ✅ {idx_key}: {len(df)} 只股票可用")
                available_indices.append(idx_key)
            else:
                print(f"  ⚠️ {idx_key}: 无数据")
        except Exception as e:
            print(f"  ❌ {idx_key}: {e}")
    
    if not available_indices:
        print("\n⚠️ 没有可用的指数数据，请先运行数据下载和转换脚本")
        return
    
    # 运行各指数的模型训练
    all_metrics = {}
    
    for index_key in available_indices:
        try:
            metrics = run_single_index(index_key)
            all_metrics[index_key] = metrics
        except Exception as e:
            print(f"\n❌ {index_key} 训练失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 汇总报告
    print("\n" + "=" * 60)
    print("📊 多指数模型训练完成汇总")
    print("=" * 60)
    
    for idx_key, metrics in all_metrics.items():
        print(f"\n{metrics['index_name']}:")
        print(f"  IC 均值: {metrics['ic_mean']:.4f}")
        print(f"  ICIR:    {metrics['icir']:.4f}")
        print(f"  年化IR:  {metrics['annual_ir']:.4f}")
    
    # 保存汇总
    signals_dir = Path(__file__).parent / "signals"
    summary_file = signals_dir / "multi_index_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(all_metrics, f, indent=2)
    print(f"\n💾 汇总已保存: {summary_file}")
    
    print("\n✅ 全部完成!")


if __name__ == '__main__':
    main()
