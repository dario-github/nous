"""
Nous Invest — Module 3-4: 模型训练与集成主脚本
整合多模型训练、组合构建全流程
"""

import multiprocessing
multiprocessing.set_start_method('fork', force=True)

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import json
from datetime import datetime

import qlib
from qlib.config import REG_CN
from qlib.utils import init_instance_by_config
from qlib.data.dataset.handler import DataHandler
from qlib.contrib.data.handler import Alpha158

from skills.portfolio_construction import (
    MultiModelEnsemble, 
    IndustryNeutralizer,
    MarketCapLayering,
    RiskParityAllocator,
    PortfolioConstructor,
    evaluate_portfolio
)


def train_ensemble_model(dataset, save_path: Path):
    """训练多模型集成"""
    print("\n" + "=" * 70)
    print("🧠 模块3: 多模型集成训练")
    print("=" * 70)
    
    # 准备数据
    print("\n📊 准备训练数据...")
    df_train = dataset.prepare("train", col_set=["feature", "label"], data_key=DataHandler.DK_L)
    df_valid = dataset.prepare("valid", col_set=["feature", "label"], data_key=DataHandler.DK_L)
    
    x_train, y_train = df_train["feature"], df_train["label"]
    x_valid, y_valid = df_valid["feature"], df_valid["label"]
    
    print(f"   训练集: {len(df_train)} 条")
    print(f"   验证集: {len(df_valid)} 条")
    print(f"   特征数: {x_train.shape[1]}")
    
    # 训练集成模型
    ensemble = MultiModelEnsemble(meta_model_type='linear')
    train_result = ensemble.fit(x_train, y_train, x_valid, y_valid, use_stacking=True)
    
    # 特征重要性
    feature_names = x_train.columns.tolist()
    importance_df = ensemble.get_feature_importance(feature_names)
    
    print("\n🔥 Top 20 重要特征:")
    print(importance_df.head(20).to_string())
    
    # 保存模型
    import pickle
    model_file = save_path / "ensemble_model.pkl"
    with open(model_file, 'wb') as f:
        pickle.dump({
            'ensemble': ensemble,
            'train_result': train_result,
            'feature_names': feature_names,
        }, f)
    print(f"\n💾 模型已保存: {model_file}")
    
    # 保存特征重要性
    importance_file = save_path / "feature_importance.csv"
    importance_df.to_csv(importance_file, index=False)
    print(f"📊 特征重要性已保存: {importance_file}")
    
    return ensemble


def generate_predictions(ensemble, dataset, save_path: Path):
    """生成预测信号"""
    print("\n" + "=" * 70)
    print("📈 模块3: 生成预测信号")
    print("=" * 70)
    
    # 测试集预测
    df_test = dataset.prepare("test", col_set=["feature", "label"], data_key=DataHandler.DK_L)
    x_test = df_test["feature"]
    y_test = df_test["label"]
    
    print(f"   测试集: {len(df_test)} 条")
    
    # 多种集成方法预测
    pred_weighted = ensemble.predict(x_test, method='weighted')
    pred_stacking = ensemble.predict(x_test, method='stacking')
    
    # 使用加权预测作为主结果
    pred = pd.Series(pred_weighted, index=x_test.index)
    
    print(f"✅ 预测完成，共 {len(pred)} 条预测")
    
    # IC / ICIR 计算
    print("\n" + "=" * 70)
    print("📊 IC / ICIR 评估")
    print("=" * 70)
    
    pred_df = pred.reset_index()
    pred_df.columns = ["datetime", "instrument", "score"]
    label_df = y_test.reset_index()
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
    
    # 保存预测结果
    pred_file = save_path / "predictions.csv"
    pred_df.to_csv(pred_file, index=False)
    print(f"\n💾 预测结果已保存: {pred_file}")
    
    # 保存指标
    metrics = {
        "model_type": "MultiModelEnsemble(LGB+XGB+Stacking)",
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
    
    metrics_file = save_path / "metrics.json"
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"📊 指标已保存: {metrics_file}")
    
    return pred, metrics


def construct_portfolios(pred, save_path: Path):
    """构建多种组合"""
    print("\n" + "=" * 70)
    print("📊 模块4: 组合构建")
    print("=" * 70)
    
    # 初始化组件
    neutralizer = IndustryNeutralizer()
    layering = MarketCapLayering(n_layers=3)
    allocator = RiskParityAllocator()
    constructor = PortfolioConstructor(neutralizer, layering, allocator)
    
    # 尝试加载行业数据
    try:
        neutralizer.load_from_tushare(trade_date='20260415')
    except Exception as e:
        print(f"⚠️ 无法加载行业数据: {e}")
    
    # 获取最新日期
    if isinstance(pred.index, pd.MultiIndex):
        dates = pred.index.get_level_values(0).unique()
    else:
        dates = [pred.index[0]]
    
    last_date = dates[-1]
    print(f"\n📅 构建日期: {last_date}")
    
    portfolios = {}
    
    # 策略1: 基础Top20 (等权)
    print("\n--- 策略1: 基础Top20 ---")
    if isinstance(pred.index, pd.MultiIndex):
        daily_pred = pred.xs(last_date, level=0)
    else:
        daily_pred = pred
    
    top20_basic = daily_pred.nlargest(20).reset_index()
    top20_basic.columns = ['code', 'score']
    top20_basic['weight'] = 1.0 / len(top20_basic)
    portfolios['basic_top20'] = top20_basic
    print(f"选股数量: {len(top20_basic)}")
    
    # 策略2: 行业中性化
    print("\n--- 策略2: 行业中性化 ---")
    try:
        neutral_scores = neutralizer.neutralize(daily_pred, str(last_date))
        top20_neutral = neutral_scores.nlargest(20).reset_index()
        top20_neutral.columns = ['code', 'score']
        top20_neutral['weight'] = 1.0 / len(top20_neutral)
        portfolios['industry_neutral'] = top20_neutral
        print(f"选股数量: {len(top20_neutral)}")
    except Exception as e:
        print(f"⚠️ 行业中性化失败: {e}")
        portfolios['industry_neutral'] = top20_basic
    
    # 策略3: 小市值分层
    print("\n--- 策略3: 小市值分层 ---")
    # 简化处理: 使用score作为市值代理(假设小盘股信号更强)
    small_cap_scores = daily_pred[daily_pred > daily_pred.median()]
    top20_small = small_cap_scores.nlargest(20).reset_index()
    top20_small.columns = ['code', 'score']
    top20_small['weight'] = 1.0 / len(top20_small)
    portfolios['small_cap'] = top20_small
    print(f"选股数量: {len(top20_small)}")
    
    # 策略4: 分层选股
    print("\n--- 策略4: 分层选股 ---")
    # 简单分成3层,每层选一些
    all_codes = daily_pred.index.tolist()
    n_per_layer = len(all_codes) // 3
    
    layer0_codes = all_codes[:n_per_layer]
    layer1_codes = all_codes[n_per_layer:2*n_per_layer]
    layer2_codes = all_codes[2*n_per_layer:]
    
    stratified = []
    for layer, codes in enumerate([layer0_codes, layer1_codes, layer2_codes]):
        layer_scores = daily_pred.loc[daily_pred.index.isin(codes)]
        top_in_layer = layer_scores.nlargest(7).reset_index()
        top_in_layer.columns = ['code', 'score']
        top_in_layer['layer'] = layer
        stratified.append(top_in_layer)
    
    stratified_df = pd.concat(stratified, ignore_index=True)
    stratified_df['weight'] = 1.0 / len(stratified_df)
    portfolios['stratified'] = stratified_df
    print(f"选股数量: {len(stratified_df)} (分层: {stratified_df['layer'].value_counts().to_dict()})")
    
    # 保存所有组合
    for name, portfolio in portfolios.items():
        file_path = save_path / f"portfolio_{name}_{last_date.strftime('%Y%m%d') if hasattr(last_date, 'strftime') else str(last_date)[:10].replace('-', '')}.csv"
        portfolio.to_csv(file_path, index=False)
        print(f"💾 {name} 已保存: {file_path}")
    
    return portfolios


def print_summary(ensemble, metrics, portfolios):
    """打印最终汇总"""
    print("\n" + "=" * 70)
    print("🎉 Nous Invest Module 3-4 完成汇总")
    print("=" * 70)
    
    print("\n📈 模型性能:")
    print(f"   模型类型: MultiModelEnsemble (LightGBM + XGBoost + Stacking)")
    print(f"   IC Mean:  {metrics['ic_mean']:.4f}")
    print(f"   ICIR:     {metrics['icir']:.4f}")
    print(f"   年化IR:   {metrics['annual_ir']:.4f}")
    
    print("\n📊 组合策略:")
    for name, portfolio in portfolios.items():
        avg_score = portfolio['score'].mean()
        print(f"   {name:20s}: {len(portfolio):2d}只, 平均分数: {avg_score:+.4f}")
    
    print("\n✅ Module 3-4 全部完成!")


def main():
    """主入口"""
    print("=" * 70)
    print("Nous Invest — Module 3-4: 模型与组合构建")
    print("=" * 70)
    
    # 初始化Qlib
    qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region=REG_CN)
    print("✅ Qlib 初始化完成")
    
    # 数据集配置
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
                        "instruments": "csi300",
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
    
    print("\n📊 创建 Alpha158 数据集...")
    dataset = init_instance_by_config(task_config["dataset"])
    print("✅ 数据集创建完成")
    
    # 创建输出目录
    output_dir = Path(__file__).parent / "models" / "module34"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 步骤1: 训练多模型集成
    ensemble = train_ensemble_model(dataset, output_dir)
    
    # 步骤2: 生成预测和评估
    predictions, metrics = generate_predictions(ensemble, dataset, output_dir)
    
    # 步骤3: 构建组合
    portfolios = construct_portfolios(predictions, output_dir)
    
    # 汇总
    print_summary(ensemble, metrics, portfolios)


if __name__ == '__main__':
    main()