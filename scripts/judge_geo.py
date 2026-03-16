"""Nous 地缘推理评估器 (judge_geo.py)

评估推理预测 vs 实际事件的 reward。
用 GPT-5.4 作为 judge，计算 5 维 reward → L_geo。

R = 0.30·R_event + 0.25·R_causal + 0.15·R_timing + 0.20·R_calibration - 0.10·R_hallucination
L_geo = 1 - R
"""
import json
import os
import sys
from pathlib import Path

# 尝试导入 openai，不可用时可 dry-run
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

DATA_DIR = Path(__file__).parent.parent / "data" / "geo"
DOCS_DIR = Path(__file__).parent.parent / "docs"


def load_ground_truth(split: str = "val") -> list[dict]:
    """加载 ground truth 事件"""
    path = DATA_DIR / f"{split}_events.json"
    with open(path) as f:
        return json.load(f)


def load_predictions(path: str) -> list[dict]:
    """加载模型预测"""
    with open(path) as f:
        return json.load(f)


# ── Judge Prompts ─────────────────────────────────────────────────────────

EVENT_MATCH_PROMPT = """你是一个地缘政治事件匹配评估器。

判断以下预测事件是否与实际事件"实质匹配"。
实质匹配 = 核心事件类型相同 + 关键行为者匹配 + 主要后果方向一致。
不要求完全一致，但方向必须对。

预测事件：
{prediction}

实际事件：
{ground_truth}

输出严格 JSON：
{{"match": true/false, "confidence": 0.0-1.0, "reasoning": "..."}}
"""

CAUSAL_JUDGE_PROMPT = """你是一个因果推理质量评估器。

评估以下预测的因果推理链质量。

预测：
{prediction}

实际事件：
{ground_truth}

评分标准（0-5）：
5: 因果链逻辑严密，引用了正确的前因后果
4: 主要因果关系正确，细节有小偏差
3: 方向对但逻辑链不完整
2: 部分因果关系正确，但有重要遗漏
1: 因果关系基本错误
0: 无因果链或纯猜测

输出严格 JSON：
{{"score": 0-5, "reasoning": "..."}}
"""


def _semantic_type_similarity(pred_type: str, gt_type: str) -> float:
    """事件类型的语义相似度（不要求精确匹配）"""
    if pred_type == gt_type:
        return 1.0

    # 相近类型组（同组内 0.7 分）
    TYPE_GROUPS = [
        {"military_strike", "escalation", "military_escalation"},
        {"diplomatic", "de_escalation_signal", "de_escalation", "political", "political_transition", "political_dynamics"},
        {"economic", "economic_shock", "economic_intervention"},
        {"humanitarian", "regional_spillover", "regional_war", "spillover"},
    ]

    for group in TYPE_GROUPS:
        if pred_type in group and gt_type in group:
            return 0.7

    return 0.0


def _keyword_overlap(pred: dict, gt: dict) -> float:
    """描述关键词重叠度"""
    pred_words = set(pred.get("description", "").lower().split())
    gt_words = set(gt.get("description", "").lower().split())

    # 加入实体/行为者关键词
    for key in ("actors", "targets", "consequences"):
        for item in gt.get(key, []):
            gt_words.update(item.lower().replace("_", " ").split())

    if not pred_words or not gt_words:
        return 0.0

    overlap = pred_words & gt_words
    return len(overlap) / min(len(pred_words), len(gt_words))


def _llm_match_score(pred: dict, gt: dict, client, model: str) -> float:
    """用 LLM 判断预测与事实是否匹配，返回 0-1 分数"""
    prompt = EVENT_MATCH_PROMPT.format(
        prediction=json.dumps({
            "event_type": pred.get("event_type", pred.get("prediction_type", "")),
            "description": pred.get("description", ""),
            "predicted_day": pred.get("predicted_day", 0),
            "probability": pred.get("probability", 0.5),
        }, ensure_ascii=False),
        ground_truth=json.dumps({
            "event_type": gt.get("event_type", ""),
            "description": gt.get("description", ""),
            "day": gt.get("day", 0),
            "actors": gt.get("actors", []),
        }, ensure_ascii=False),
    )
    try:
        extra = {}
        if "qwen3" in model.lower() or "kimi-k2-thinking" in model.lower():
            extra["extra_body"] = {"enable_thinking": False}
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200, temperature=0.0, timeout=30.0,
            **extra,
        )
        text = resp.choices[0].message.content or ""
        import re
        text = re.sub(r"^```(?:json)?\n?", "", text.strip())
        text = re.sub(r"\n?```$", "", text)
        result = json.loads(text)
        if result.get("match"):
            return result.get("confidence", 0.8)
        return 0.0
    except Exception as e:
        return -1.0  # 标记 LLM 失败，回退到启发式


def compute_r_event(predictions: list, ground_truth: list,
                    use_llm: bool = False, llm_model: str = "DeepSeek-V3.2") -> dict:
    """计算事件预测准确率 (R_event)

    多维匹配：类型相似度 + 时间窗口 + 关键词重叠。
    use_llm=True 时用 LLM 做语义精排（更准但更慢）。
    """
    if not predictions:
        return {"precision": 0, "recall": 0, "f1": 0, "matches": []}

    # 可选 LLM client
    llm_client = None
    if use_llm:
        try:
            import openai
            key = os.environ.get("OPENAI_API_KEY")
            base_url = os.environ.get("OPENAI_BASE_URL")
            if key:
                llm_client = openai.OpenAI(api_key=key, base_url=base_url)
        except Exception:
            pass

    matches = []
    matched_gt = set()

    for pred in predictions:
        best_match = None
        best_score = 0

        for gt in ground_truth:
            if gt["id"] in matched_gt:
                continue

            # 启发式打分
            type_sim = _semantic_type_similarity(
                pred.get("event_type", ""), gt.get("event_type", ""))
            day_diff = abs(pred.get("predicted_day", 0) - gt.get("day", 0))
            time_score = max(0, 1.0 - day_diff * 0.1) if day_diff <= 5 else 0
            kw_score = _keyword_overlap(pred, gt)
            heuristic_score = 0.4 * type_sim + 0.3 * time_score + 0.3 * kw_score

            # LLM 精排：对启发式 > 0.15 的候选对做 LLM 判断
            score = heuristic_score
            if llm_client and heuristic_score > 0.15:
                llm_score = _llm_match_score(pred, gt, llm_client, llm_model)
                if llm_score >= 0:  # LLM 成功
                    # 混合：60% LLM + 40% 启发式
                    score = 0.6 * llm_score + 0.4 * heuristic_score

            if score > best_score:
                best_score = score
                best_match = gt

        if best_match and best_score > 0.25:
            matches.append({
                "pred": pred["id"],
                "gt": best_match["id"],
                "score": round(best_score, 4),
            })
            matched_gt.add(best_match["id"])

    precision = len(matches) / len(predictions) if predictions else 0
    recall = len(matches) / len(ground_truth) if ground_truth else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {"precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4), "matches": matches}


def compute_r_causal(predictions: list, ground_truth: list) -> float:
    """计算因果链质量 (R_causal) — 需要 LLM judge

    暂用启发式：有 causal_chain 字段 → 基础分 0.3，
    引用了已知 signal → +0.2/个（最多 +0.4）
    """
    if not predictions:
        return 0.0

    scores = []
    for pred in predictions:
        chain = pred.get("causal_chain", [])
        if not chain:
            scores.append(0.0)
            continue

        base = 0.3
        signal_refs = sum(1 for c in chain if c.startswith("sig_"))
        bonus = min(signal_refs * 0.2, 0.4)
        scores.append(min(base + bonus, 1.0))

    return round(sum(scores) / len(scores), 4)


def compute_r_timing(predictions: list, ground_truth: list,
                     matches: list) -> float:
    """计算时间窗口准确度 (R_timing)"""
    if not matches:
        return 0.0

    errors = []
    gt_map = {e["id"]: e for e in ground_truth}
    pred_map = {p["id"]: p for p in predictions}

    for m in matches:
        pred = pred_map.get(m["pred"], {})
        gt = gt_map.get(m["gt"], {})

        pred_day = pred.get("predicted_day", 0)
        actual_day = gt.get("day", 0)

        if actual_day > 0:
            error = abs(pred_day - actual_day) / max(actual_day, 1)
            errors.append(min(error, 1.0))

    if not errors:
        return 0.0
    return round(1 - sum(errors) / len(errors), 4)


def compute_r_calibration(predictions: list, ground_truth: list,
                          matches: list) -> float:
    """计算概率校准度 (R_calibration) — Brier Score"""
    if not predictions:
        return 0.0

    matched_pred_ids = {m["pred"] for m in matches}
    brier_scores = []

    for pred in predictions:
        prob = pred.get("probability", 0.5)
        actual = 1.0 if pred["id"] in matched_pred_ids else 0.0
        brier_scores.append((prob - actual) ** 2)

    brier = sum(brier_scores) / len(brier_scores)
    return round(1 - brier, 4)


def compute_r_hallucination(predictions: list, matches: list) -> float:
    """计算幻觉惩罚 (R_hallucination)"""
    if not predictions:
        return 0.0

    matched_pred_ids = {m["pred"] for m in matches}
    hallucinated = sum(1 for p in predictions if p["id"] not in matched_pred_ids)
    return round(hallucinated / len(predictions), 4)


def compute_reward(predictions: list, ground_truth: list,
                   use_llm: bool = False, llm_model: str = "DeepSeek-V3.2") -> dict:
    """计算完整 reward 和 L_geo"""
    event_result = compute_r_event(predictions, ground_truth,
                                   use_llm=use_llm, llm_model=llm_model)
    r_event = event_result["f1"]
    r_causal = compute_r_causal(predictions, ground_truth)
    r_timing = compute_r_timing(predictions, ground_truth, event_result["matches"])
    r_calibration = compute_r_calibration(predictions, ground_truth, event_result["matches"])
    r_hallucination = compute_r_hallucination(predictions, event_result["matches"])

    R = (0.30 * r_event
         + 0.25 * r_causal
         + 0.15 * r_timing
         + 0.20 * r_calibration
         - 0.10 * r_hallucination)

    L_geo = round(1 - R, 4)

    return {
        "R_event": r_event,
        "R_causal": r_causal,
        "R_timing": r_timing,
        "R_calibration": r_calibration,
        "R_hallucination": r_hallucination,
        "R_total": round(R, 4),
        "L_geo": L_geo,
        "event_detail": event_result,
        "n_predictions": len(predictions),
        "n_ground_truth": len(ground_truth),
        "n_matches": len(event_result["matches"]),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Nous 地缘推理评估器")
    parser.add_argument("predictions", help="预测 JSON 文件路径")
    parser.add_argument("--split", default="val", choices=["train", "val", "test"])
    parser.add_argument("--output", help="输出结果 JSON 路径")
    parser.add_argument("--use-llm", action="store_true", help="用 LLM 做语义匹配")
    parser.add_argument("--llm-model", default="DeepSeek-V3.2", help="LLM 模型")
    args = parser.parse_args()

    gt = load_ground_truth(args.split)
    preds = load_predictions(args.predictions)

    result = compute_reward(preds, gt, use_llm=args.use_llm,
                            llm_model=args.llm_model)

    print(f"\n{'='*60}")
    print(f"Nous Geo Reasoning Evaluation — {args.split} set")
    print(f"{'='*60}")
    print(f"Predictions: {result['n_predictions']} | Ground Truth: {result['n_ground_truth']} | Matches: {result['n_matches']}")
    print(f"")
    print(f"  R_event (F1):        {result['R_event']:.4f}")
    print(f"  R_causal:            {result['R_causal']:.4f}")
    print(f"  R_timing:            {result['R_timing']:.4f}")
    print(f"  R_calibration:       {result['R_calibration']:.4f}")
    print(f"  R_hallucination:     {result['R_hallucination']:.4f}")
    print(f"  ─────────────────────────")
    print(f"  R_total:             {result['R_total']:.4f}")
    print(f"  L_geo:               {result['L_geo']:.4f}")
    print(f"{'='*60}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
