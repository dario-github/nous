"""Nous Geo LLM Synthesis Layer

在规则推理基础上，用 LLM 做两件事：
1. 精炼现有预测（调概率、补充因果链）
2. 补充规则覆盖不到的事件类型

输入: rule_predictions.json + KG context
输出: synthesized_predictions.json
"""
import json
import os
import sys
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data" / "geo"

# ── LLM Provider ──────────────────────────────────────────────────────────

def _get_llm_client():
    """获取 OpenAI 兼容客户端"""
    try:
        import openai
    except ImportError:
        raise ImportError("pip install openai")
    
    key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    if not key:
        raise ValueError("OPENAI_API_KEY not set")
    return openai.OpenAI(api_key=key, base_url=base_url)


def _call_llm(client, prompt: str, model: str = "qwen3-32b",
              max_tokens: int = 2000, temperature: float = 0.3) -> str:
    """调用 LLM，返回文本"""
    extra = {}
    # qwen3 系列需要显式关闭 thinking
    if "qwen3" in model.lower() or "kimi-k2-thinking" in model.lower():
        extra["extra_body"] = {"enable_thinking": False}
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=60.0,
        **extra,
    )
    return resp.choices[0].message.content or ""


def _parse_json_response(text: str) -> Optional[dict]:
    """从 LLM 响应中提取 JSON"""
    import re
    # 尝试直接解析
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试找第一个 JSON 块
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


# ── Synthesis Prompts ─────────────────────────────────────────────────────

REFINE_PROMPT = """你是一个地缘政治分析专家。以下是基于知识图谱和 Datalog 规则的推理预测。

## 当前规则预测
{predictions_json}

## 知识图谱背景（战前信号）
{signals_json}

## 任务
1. 审查每个预测的概率是否合理，给出修正后的概率
2. 识别规则可能遗漏的重要事件（最多补充 3 个）
3. 标记可能是幻觉的预测（置信度过高但证据不足）

输出严格 JSON：
{{
  "refined": [
    {{
      "id": "原预测id",
      "original_prob": 0.0,
      "refined_prob": 0.0,
      "reasoning": "调整原因",
      "hallucination_risk": "low/medium/high"
    }}
  ],
  "new_predictions": [
    {{
      "id": "llm_001",
      "event_type": "...",
      "description": "...",
      "predicted_day": 0,
      "probability": 0.0,
      "reasoning": "...",
      "causal_chain": ["sig_xxx", "..."]
    }}
  ],
  "removed_ids": ["过于投机的预测id"]
}}
"""


# ── Core Functions ────────────────────────────────────────────────────────

def synthesize(
    rule_predictions: list[dict],
    signals: list[dict],
    model: str = "DeepSeek-V3.2",
    max_new: int = 3,
    conservative: bool = False,
) -> list[dict]:
    """LLM 综合层：精炼规则预测 + 补充遗漏事件
    
    conservative=True: 只调概率，不新增/不移除（保守模式）
    Returns: synthesized predictions list
    """
    client = _get_llm_client()
    
    # 构建 prompt
    # 只传关键字段，减少 token
    pred_summary = [{
        "id": p["id"],
        "rule": p.get("rule", "?"),
        "event_type": p.get("event_type", p.get("prediction_type", "")),
        "description": p.get("description", ""),
        "predicted_day": p.get("predicted_day", 0),
        "probability": p.get("probability", 0.5),
        "causal_chain": p.get("causal_chain", []),
    } for p in rule_predictions]
    
    sig_summary = [{
        "id": s["id"],
        "type": s.get("type", ""),
        "description": s.get("description", ""),
        "strength": s.get("strength", 0),
    } for s in signals[:15]]  # 最多 15 个信号
    
    prompt = REFINE_PROMPT.format(
        predictions_json=json.dumps(pred_summary, ensure_ascii=False, indent=2),
        signals_json=json.dumps(sig_summary, ensure_ascii=False, indent=2),
    )
    
    raw = _call_llm(client, prompt, model=model)
    result = _parse_json_response(raw)
    
    if not result:
        print("⚠️ LLM 返回解析失败，使用原始规则预测")
        return rule_predictions
    
    # 应用精炼
    pred_map = {p["id"]: p for p in rule_predictions}
    removed = set(result.get("removed_ids", []))
    
    # 1. 精炼概率
    for ref in result.get("refined", []):
        pid = ref.get("id")
        if pid in pred_map and pid not in removed:
            pred_map[pid]["probability"] = ref["refined_prob"]
            pred_map[pid]["llm_reasoning"] = ref.get("reasoning", "")
            pred_map[pid]["hallucination_risk"] = ref.get("hallucination_risk", "unknown")
    
    # 2. 过滤掉标记为移除的（anti-regression: 不移除高概率预测）
    if conservative:
        # 保守模式：不移除任何预测
        synthesized = list(rule_predictions)
        removed = set()
    else:
        removed_safe = set()
        for rid in removed:
            p = pred_map.get(rid)
            if p and p.get("probability", 0) >= 0.75:
                print(f"  ⚠️ Anti-regression: keeping {rid} (prob={p['probability']})")
            else:
                removed_safe.add(rid)
        synthesized = [p for p in rule_predictions if p["id"] not in removed_safe]
    
    # 3. 添加 LLM 新预测（保守模式跳过）
    if conservative:
        new_preds = []
    else:
        new_preds = result.get("new_predictions", [])[:max_new]
    for np in new_preds:
        if not np.get("id"):
            continue
        np["source"] = "llm_synthesis"
        np.setdefault("predicted_day_range", [
            max(1, np.get("predicted_day", 5) - 2),
            np.get("predicted_day", 5) + 2,
        ])
        synthesized.append(np)
    
    # 4. 重排序
    synthesized.sort(key=lambda p: p.get("probability", 0), reverse=True)
    
    print(f"  LLM 综合层: {len(rule_predictions)} 规则 → "
          f"{len(synthesized)} 综合 "
          f"(移除 {len(removed)}, 新增 {len(new_preds)})")
    
    return synthesized


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Nous Geo LLM Synthesis")
    parser.add_argument("--input", default=str(DATA_DIR / "rule_predictions.json"))
    parser.add_argument("--output", default=str(DATA_DIR / "current_predictions.json"))
    parser.add_argument("--model", default="DeepSeek-V3.2")
    parser.add_argument("--max-new", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    with open(args.input) as f:
        rule_preds = json.load(f)
    
    signals_path = DATA_DIR / "pre_war_signals.json"
    with open(signals_path) as f:
        signals = json.load(f)
    
    if args.dry_run:
        print(f"[dry-run] {len(rule_preds)} predictions, {len(signals)} signals")
        return
    
    result = synthesize(rule_preds, signals, model=args.model, max_new=args.max_new)
    
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Synthesized {len(result)} predictions → {args.output}")


if __name__ == "__main__":
    main()
