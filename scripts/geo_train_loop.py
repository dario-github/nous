"""Nous Geo RL Training Loop

自动迭代循环：
1. 推理生成预测
2. 评估 reward
3. 分析薄弱环节
4. 策略更新（规则/KG/prompt 调整）
5. 重新推理评估
6. L_geo 下降 → 保留，上升 → 回滚

每轮写 loop-log，更新 geo-state.json
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data" / "geo"
DOCS_DIR = BASE / "docs"
STATE_FILE = DOCS_DIR / "geo-state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "loop": 0,
        "best_L_geo_val": 1.0,
        "best_L_geo_train": 1.0,
        "history": [],
    }


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def run_reasoning(max_preds: int = 12) -> str:
    """运行推理引擎，返回预测文件路径"""
    output = DATA_DIR / "current_predictions.json"
    result = subprocess.run(
        [sys.executable, str(BASE / "scripts" / "geo_reason.py"),
         "--max-predictions", str(max_preds),
         "--output", str(output)],
        capture_output=True, text=True, cwd=str(BASE),
    )
    if result.returncode != 0:
        print(f"❌ Reasoning failed: {result.stderr}")
        sys.exit(1)
    print(result.stdout)
    return str(output)


def run_evaluation(pred_file: str, split: str = "val") -> dict:
    """评估预测，返回 reward 结果"""
    output = DOCS_DIR / f"geo-loop-{split}.json"
    result = subprocess.run(
        [sys.executable, str(BASE / "scripts" / "judge_geo.py"),
         pred_file, "--split", split, "--output", str(output)],
        capture_output=True, text=True, cwd=str(BASE),
    )
    print(result.stdout)
    with open(output) as f:
        return json.load(f)


def diagnose(val_result: dict, train_result: dict) -> dict:
    """分析薄弱环节，给出改进建议"""
    diagnosis = {
        "weakest_component": None,
        "suggestions": [],
        "overfitting": False,
    }

    # 找最差的 R 分项
    components = {
        "R_event": val_result["R_event"],
        "R_causal": val_result["R_causal"],
        "R_timing": val_result["R_timing"],
        "R_calibration": val_result["R_calibration"],
    }
    weakest = min(components, key=components.get)
    diagnosis["weakest_component"] = weakest

    # 过拟合检测：train 显著好于 val
    gap = train_result.get("R_total", 0) - val_result.get("R_total", 0)
    if gap > 0.2:
        diagnosis["overfitting"] = True
        diagnosis["suggestions"].append(
            f"过拟合警告：train R={train_result['R_total']:.3f} vs val R={val_result['R_total']:.3f}，gap={gap:.3f}")

    # 按分项建议
    if components["R_event"] < 0.5:
        diagnosis["suggestions"].append(
            "R_event 低：增加更多事件类型映射，扩展规则覆盖面")
    if components["R_causal"] < 0.3:
        diagnosis["suggestions"].append(
            "R_causal 低：在推理中回溯 signal ID，构建明确的因果链")
    if components["R_timing"] < 0.5:
        diagnosis["suggestions"].append(
            "R_timing 低：调整 predicted_day_range，校准时间估计")
    if components["R_calibration"] < 0.5:
        diagnosis["suggestions"].append(
            "R_calibration 低：校准概率，高概率的事件应该真的发生")

    # 幻觉
    if val_result.get("R_hallucination", 0) > 0.5:
        diagnosis["suggestions"].append(
            f"幻觉率高 ({val_result['R_hallucination']:.0%})：减少预测数量，提高每个预测的置信度阈值")

    return diagnosis


def write_loop_log(loop: int, val_result: dict, train_result: dict,
                   diagnosis: dict):
    """写入循环日志"""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_path = DOCS_DIR / f"geo-loop-{loop:02d}.md"

    content = f"""# Geo Loop {loop} — {ts}

## 指标
| Metric | Train | Val |
|--------|-------|-----|
| L_geo | {train_result['L_geo']:.4f} | {val_result['L_geo']:.4f} |
| R_event | {train_result['R_event']:.4f} | {val_result['R_event']:.4f} |
| R_causal | {train_result['R_causal']:.4f} | {val_result['R_causal']:.4f} |
| R_timing | {train_result['R_timing']:.4f} | {val_result['R_timing']:.4f} |
| R_calibration | {train_result['R_calibration']:.4f} | {val_result['R_calibration']:.4f} |
| R_hallucination | {train_result['R_hallucination']:.4f} | {val_result['R_hallucination']:.4f} |
| Matches | {train_result['n_matches']}/{train_result['n_ground_truth']} | {val_result['n_matches']}/{val_result['n_ground_truth']} |

## 诊断
- 最弱分项: {diagnosis['weakest_component']}
- 过拟合: {'⚠️ YES' if diagnosis['overfitting'] else '✅ No'}

## 改进建议
{chr(10).join('- ' + s for s in diagnosis['suggestions'])}

## 下一步
{"根据诊断结果调整策略" if not diagnosis['overfitting'] else "回滚或减少规则复杂度"}
"""
    with open(log_path, "w") as f:
        f.write(content)
    print(f"📝 Loop log: {log_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-loops", type=int, default=1,
                        help="最大迭代次数")
    parser.add_argument("--max-predictions", type=int, default=12)
    args = parser.parse_args()

    state = load_state()

    for i in range(args.max_loops):
        loop = state["loop"] + 1
        print(f"\n{'='*60}")
        print(f"  GEO RL LOOP {loop}")
        print(f"{'='*60}\n")

        # Step 1: 推理
        print("📊 Step 1: Running geo reasoning...")
        pred_file = run_reasoning(args.max_predictions)

        # Step 2: 评估
        print("\n📊 Step 2: Evaluating...")
        val_result = run_evaluation(pred_file, "val")
        train_result = run_evaluation(pred_file, "train")

        # Step 3: 诊断
        print("\n🔍 Step 3: Diagnosing...")
        diagnosis = diagnose(val_result, train_result)
        for s in diagnosis["suggestions"]:
            print(f"  💡 {s}")

        # Step 4: 记录
        write_loop_log(loop, val_result, train_result, diagnosis)

        # Step 5: 更新状态
        improved = val_result["L_geo"] < state["best_L_geo_val"]
        state["loop"] = loop
        state["history"].append({
            "loop": loop,
            "L_geo_val": val_result["L_geo"],
            "L_geo_train": train_result["L_geo"],
            "R_total_val": val_result["R_total"],
            "weakest": diagnosis["weakest_component"],
            "improved": improved,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        if improved:
            state["best_L_geo_val"] = val_result["L_geo"]
            state["best_L_geo_train"] = train_result["L_geo"]
            # 保存最佳预测
            shutil.copy(pred_file, DATA_DIR / "best_predictions.json")
            print(f"\n✅ IMPROVED! L_geo_val: {val_result['L_geo']:.4f} (new best)")
        else:
            print(f"\n⚠️ No improvement. L_geo_val: {val_result['L_geo']:.4f} "
                  f"(best: {state['best_L_geo_val']:.4f})")

        save_state(state)

    # 最终总结
    print(f"\n{'='*60}")
    print(f"  TRAINING SUMMARY")
    print(f"{'='*60}")
    print(f"  Loops: {state['loop']}")
    print(f"  Best L_geo_val: {state['best_L_geo_val']:.4f}")
    print(f"  Best L_geo_train: {state['best_L_geo_train']:.4f}")
    for h in state["history"][-5:]:
        marker = "✅" if h["improved"] else "—"
        print(f"  Loop {h['loop']}: L_val={h['L_geo_val']:.4f} {marker} "
              f"weakest={h['weakest']}")


if __name__ == "__main__":
    main()
