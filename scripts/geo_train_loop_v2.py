"""Nous Geo RL Training Loop v2

自动化迭代循环（1+2+3 整合版）：
1. 规则推理 → LLM 综合层精炼
2. LLM judge 语义匹配评估
3. 自动诊断 + 策略更新（概率校准/阈值调整）
4. L_geo 下降 → 保留，上升 → 回滚
5. 连续 N 轮不改善 → 自动停止

每轮写 loop-log，更新 geo-state.json
"""
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data" / "geo"
DOCS_DIR = BASE / "docs"
STATE_FILE = DOCS_DIR / "geo-state.json"
SCRIPTS = BASE / "scripts"


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "loop": 0,
        "best_L_geo_val": 1.0,
        "best_L_geo_train": 1.0,
        "history": [],
        "strategy": {
            "max_predictions": 15,
            "confidence_threshold": 0.50,
            "use_llm_synthesis": True,
            "use_llm_judge": True,
            "llm_model": "DeepSeek-V3.1",
        },
    }


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ── Step 1: 规则推理 ─────────────────────────────────────────────────────

def run_reasoning(max_preds: int = 15) -> tuple[str, list]:
    """运行规则推理引擎"""
    output = DATA_DIR / "rule_predictions.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "geo_reason.py"),
         "--max-predictions", str(max_preds),
         "--output", str(output)],
        capture_output=True, text=True, cwd=str(BASE),
    )
    if result.returncode != 0:
        print(f"  ❌ Reasoning failed: {result.stderr[:200]}")
        return str(output), []
    # 只打印预测摘要（不打全部 stdout）
    lines = result.stdout.strip().split("\n")
    for line in lines:
        if line.strip().startswith("[R") or "Generated" in line:
            print(f"  {line.strip()}")
    with open(output) as f:
        return str(output), json.load(f)


# ── Step 2: LLM 综合层 ──────────────────────────────────────────────────

def run_synthesis(rule_preds: list, model: str = "DeepSeek-V3.1",
                  max_new: int = 3) -> list:
    """LLM 精炼规则预测"""
    try:
        from geo_llm_layer import synthesize
    except ImportError:
        sys.path.insert(0, str(SCRIPTS))
        from geo_llm_layer import synthesize

    signals_path = DATA_DIR / "pre_war_signals.json"
    with open(signals_path) as f:
        signals = json.load(f)

    return synthesize(rule_preds, signals, model=model, max_new=max_new, conservative=True)


# ── Step 3: 评估 ────────────────────────────────────────────────────────

def run_evaluation(predictions: list, split: str = "val",
                   use_llm: bool = False, model: str = "DeepSeek-V3.1") -> dict:
    """评估预测 reward"""
    sys.path.insert(0, str(SCRIPTS))
    from judge_geo import compute_reward, load_ground_truth

    gt = load_ground_truth(split)
    return compute_reward(predictions, gt, use_llm=use_llm, llm_model=model)


# ── Step 4: 诊断 + 自动策略更新 ─────────────────────────────────────────

def diagnose_and_update(val_result: dict, train_result: dict,
                        state: dict) -> dict:
    """分析薄弱环节，自动调整策略"""
    strategy = state.get("strategy", {})
    diagnosis = {
        "weakest_component": None,
        "suggestions": [],
        "overfitting": False,
        "strategy_changes": [],
    }

    components = {
        "R_event": val_result["R_event"],
        "R_causal": val_result["R_causal"],
        "R_timing": val_result["R_timing"],
        "R_calibration": val_result["R_calibration"],
    }
    weakest = min(components, key=components.get)
    diagnosis["weakest_component"] = weakest

    # 过拟合检测
    gap = train_result.get("R_total", 0) - val_result.get("R_total", 0)
    if gap > 0.15:
        diagnosis["overfitting"] = True
        diagnosis["suggestions"].append(
            f"过拟合: train R={train_result['R_total']:.3f} vs val R={val_result['R_total']:.3f}")
        # 自动应对：减少预测数
        old_max = strategy.get("max_predictions", 15)
        strategy["max_predictions"] = max(10, old_max - 2)
        diagnosis["strategy_changes"].append(
            f"max_predictions: {old_max} → {strategy['max_predictions']}")

    # 幻觉率高 → 提高置信度阈值
    halluc = val_result.get("R_hallucination", 0)
    if halluc > 0.5:
        old_thresh = strategy.get("confidence_threshold", 0.50)
        new_thresh = round(min(old_thresh + 0.05, 0.80), 2)
        if new_thresh != old_thresh:
            strategy["confidence_threshold"] = round(new_thresh, 2)
            diagnosis["strategy_changes"].append(
                f"confidence_threshold: {old_thresh} → {new_thresh}")
        diagnosis["suggestions"].append(
            f"幻觉率 {halluc:.0%}：提高置信度阈值")

    # R_calibration 低 → 概率需要校准
    if components["R_calibration"] < 0.6:
        diagnosis["suggestions"].append(
            "R_calibration 低：LLM 综合层应更积极地调整概率")

    # 连续不改善检测
    history = state.get("history", [])
    recent = history[-3:] if len(history) >= 3 else []
    if recent and all(not h.get("improved") for h in recent):
        diagnosis["suggestions"].append(
            "⚠️ 连续 3 轮未改善，考虑换方向")
        # 尝试切模型
        if strategy.get("llm_model") == "DeepSeek-V3.1":
            strategy["llm_model"] = "qwen3-32b"
            diagnosis["strategy_changes"].append("llm_model: DeepSeek-V3.1 → qwen3-32b")
        else:
            strategy["llm_model"] = "DeepSeek-V3.1"
            diagnosis["strategy_changes"].append(f"llm_model: → DeepSeek-V3.1")

    state["strategy"] = strategy
    return diagnosis


# ── Loop Log ─────────────────────────────────────────────────────────────

def write_loop_log(loop: int, val_result: dict, train_result: dict,
                   diagnosis: dict, strategy: dict, elapsed: float):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    log_path = DOCS_DIR / f"geo-loop-{loop:02d}.md"

    suggestions = "\n".join(f"- {s}" for s in diagnosis["suggestions"]) or "- 无"
    changes = "\n".join(f"- {c}" for c in diagnosis.get("strategy_changes", [])) or "- 无"

    content = f"""# Geo Loop {loop} — {ts} UTC

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

## 策略
- LLM synthesis: {strategy.get('use_llm_synthesis', False)}
- LLM judge: {strategy.get('use_llm_judge', False)}
- Model: {strategy.get('llm_model', 'N/A')}
- Max predictions: {strategy.get('max_predictions', 15)}
- Confidence threshold: {strategy.get('confidence_threshold', 0.5)}

## 诊断
- 最弱分项: {diagnosis['weakest_component']}
- 过拟合: {'⚠️ YES' if diagnosis['overfitting'] else '✅ No'}
- 耗时: {elapsed:.1f}s

## 策略变更
{changes}

## 建议
{suggestions}
"""
    with open(log_path, "w") as f:
        f.write(content)


# ── Main Loop ────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Nous Geo RL Loop v2")
    parser.add_argument("--max-loops", type=int, default=5)
    parser.add_argument("--patience", type=int, default=5,
                        help="连续无改善停止的轮数")
    parser.add_argument("--no-llm", action="store_true",
                        help="禁用 LLM（纯规则模式）")
    args = parser.parse_args()

    state = load_state()
    no_improve_count = 0

    for i in range(args.max_loops):
        loop = state["loop"] + 1
        strategy = state.get("strategy", {})
        use_llm = not args.no_llm and strategy.get("use_llm_synthesis", True)
        use_llm_judge = not args.no_llm and strategy.get("use_llm_judge", True)
        model = strategy.get("llm_model", "DeepSeek-V3.1")
        max_preds = strategy.get("max_predictions", 15)

        print(f"\n{'='*60}")
        print(f"  GEO RL LOOP {loop} | model={model} | "
              f"llm={'ON' if use_llm else 'OFF'} | max={max_preds}")
        print(f"{'='*60}\n")

        t0 = time.time()

        # Step 1: 规则推理
        print("📊 Step 1: Rule reasoning...")
        _, rule_preds = run_reasoning(max_preds)

        # Step 2: LLM 综合层
        if use_llm and rule_preds:
            print("\n🧠 Step 2: LLM synthesis...")
            try:
                predictions = run_synthesis(rule_preds, model=model)
            except Exception as e:
                print(f"  ⚠️ LLM synthesis failed: {e}")
                predictions = rule_preds
        else:
            predictions = rule_preds

        # 应用置信度阈值
        threshold = strategy.get("confidence_threshold", 0.50)
        before = len(predictions)
        predictions = [p for p in predictions
                       if p.get("probability", 0.5) >= threshold]
        if len(predictions) < before:
            print(f"  ✂️ Confidence filter: {before} → {len(predictions)} "
                  f"(threshold={threshold})")

        # 保存当前预测
        current_path = DATA_DIR / "current_predictions.json"
        with open(current_path, "w") as f:
            json.dump(predictions, f, indent=2, ensure_ascii=False)

        # Step 3: 评估
        print(f"\n📊 Step 3: Evaluating (LLM judge={'ON' if use_llm_judge else 'OFF'})...")
        val_result = run_evaluation(predictions, "val",
                                    use_llm=use_llm_judge, model=model)
        train_result = run_evaluation(predictions, "train",
                                      use_llm=use_llm_judge, model=model)

        # 打印指标
        for label, r in [("Val", val_result), ("Train", train_result)]:
            print(f"\n  {label}: L_geo={r['L_geo']:.4f} | "
                  f"R_event={r['R_event']:.4f} R_causal={r['R_causal']:.4f} "
                  f"R_timing={r['R_timing']:.4f} | "
                  f"matches={r['n_matches']}/{r['n_ground_truth']}")

        # Step 4: 诊断 + 策略更新
        print("\n🔍 Step 4: Diagnosis + strategy update...")
        diagnosis = diagnose_and_update(val_result, train_result, state)
        for s in diagnosis["suggestions"]:
            print(f"  💡 {s}")
        for c in diagnosis.get("strategy_changes", []):
            print(f"  🔧 {c}")

        elapsed = time.time() - t0

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
            "llm": use_llm,
            "model": model,
            "elapsed_s": round(elapsed, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        write_loop_log(loop, val_result, train_result, diagnosis,
                       strategy, elapsed)

        if improved:
            state["best_L_geo_val"] = val_result["L_geo"]
            state["best_L_geo_train"] = train_result["L_geo"]
            shutil.copy(current_path, DATA_DIR / "best_predictions.json")
            no_improve_count = 0
            print(f"\n  ✅ IMPROVED! L_geo_val: {val_result['L_geo']:.4f}")
        else:
            no_improve_count += 1
            print(f"\n  ⚠️ No improvement ({no_improve_count}/{args.patience}). "
                  f"L_geo_val: {val_result['L_geo']:.4f} "
                  f"(best: {state['best_L_geo_val']:.4f})")

        save_state(state)

        # Early stop
        if no_improve_count >= args.patience:
            print(f"\n  🛑 Patience exhausted ({args.patience} loops). Stopping.")
            break

    # 最终总结
    print(f"\n{'='*60}")
    print(f"  TRAINING SUMMARY")
    print(f"{'='*60}")
    print(f"  Loops: {state['loop']}")
    print(f"  Best L_geo_val: {state['best_L_geo_val']:.4f}")
    print(f"  Best L_geo_train: {state['best_L_geo_train']:.4f}")
    for h in state["history"][-10:]:
        marker = "✅" if h["improved"] else "—"
        llm_tag = "🧠" if h.get("llm") else "📏"
        print(f"  Loop {h['loop']}: L_val={h['L_geo_val']:.4f} {marker} "
              f"{llm_tag} {h.get('model','?')} "
              f"weakest={h['weakest']} ({h.get('elapsed_s',0):.0f}s)")


if __name__ == "__main__":
    main()
