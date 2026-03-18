#!/usr/bin/env python3
"""Memory → KG 实体抽取：多模型 A/B 对比实验。

用 3 个模型跑同一批文件，对比：
- 抽取数量（实体/关系）
- 质量（是否有幻觉、是否符合 type_registry schema）
- 延迟和成本
- 结构化输出稳定性

模型：
A. Gemini 3 Flash   — 最便宜，有 responseSchema
B. Kimi K2.5        — 中等，强中文
C. Gemini 3.1 Pro   — 贵，最强理解力
"""
import json
import os
import sys
import time
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────────────

TEST_FILES = [
    ("人物档案", "memory/entities/people/东丞.md"),
    ("项目档案", "memory/entities/projects/evaluation-system.md"),
    ("经验记录", "memory/experiences/2026-03-18.md"),
    ("研究笔记", "memory/research/longmemeval-preference-analysis.md"),
    ("教训总结", "memory/lessons-learned.md"),
]

EXTRACT_PROMPT = """你是知识图谱实体抽取引擎。从以下文档中提取实体和关系。

## 输出格式（严格 JSON）

```json
{
  "entities": [
    {
      "id": "类型前缀:标识符",
      "etype": "person|project|concept|tool|event|decision|lesson|research",
      "name": "英文名或标识",
      "name_zh": "中文名",
      "properties": {"key": "value"},
      "confidence": 0.0-1.0
    }
  ],
  "relations": [
    {
      "from_id": "源实体ID",
      "to_id": "目标实体ID",
      "rtype": "关系类型（英文大写下划线）",
      "rtype_zh": "关系中文名",
      "properties": {},
      "confidence": 0.0-1.0
    }
  ]
}
```

## 规则
1. etype 必须是以上 8 种之一
2. id 格式：`etype:english-kebab-case`（如 `person:dongcheng`, `project:nous`）
3. 相同实体在不同文件中必须用相同 ID（人名→拼音，项目名→英文缩写）
4. confidence < 0.5 的不要输出
5. 关系要有明确证据支撑，不猜测
6. 只输出 JSON，不要其他文字

## 文档内容

文件路径：{path}

{content}
"""

# ── 模型调用 ──────────────────────────────────────────────────────────────

def call_gemini_flash(prompt: str) -> tuple[str, float]:
    """Gemini 3 Flash via CLI."""
    import subprocess
    t0 = time.time()
    result = subprocess.run(
        ["gemini", "-m", "gemini-3-flash-preview", "-p", prompt],
        capture_output=True, text=True, timeout=60
    )
    latency = time.time() - t0
    return result.stdout.strip(), latency


def call_gemini_pro(prompt: str) -> tuple[str, float]:
    """Gemini 3.1 Pro via CLI."""
    import subprocess
    t0 = time.time()
    result = subprocess.run(
        ["gemini", "-m", "gemini-3.1-pro-preview", "-p", prompt],
        capture_output=True, text=True, timeout=120
    )
    latency = time.time() - t0
    return result.stdout.strip(), latency


def call_kimi(prompt: str) -> tuple[str, float]:
    """Kimi K2.5 via OpenAI-compatible API."""
    import subprocess
    t0 = time.time()
    # Use curl to Moonshot API
    api_key = os.environ.get("MOONSHOT_API_KEY", "")
    if not api_key:
        # Try 1password
        result = subprocess.run(
            ["op", "read", "op://Agent/moonshot-api-key/credential"],
            capture_output=True, text=True, timeout=10
        )
        api_key = result.stdout.strip()
    
    payload = json.dumps({
        "model": "kimi-k2.5",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    })
    
    result = subprocess.run(
        ["curl", "-s", "-X", "POST", "https://api.moonshot.cn/v1/chat/completions",
         "-H", "Content-Type: application/json",
         "-H", f"Authorization: Bearer {api_key}",
         "-d", payload],
        capture_output=True, text=True, timeout=120
    )
    latency = time.time() - t0
    
    try:
        resp = json.loads(result.stdout)
        content = resp["choices"][0]["message"]["content"]
        return content, latency
    except (json.JSONDecodeError, KeyError, IndexError):
        return result.stdout, latency


MODELS = {
    "flash": ("Gemini 3 Flash", call_gemini_flash),
    "pro": ("Gemini 3.1 Pro", call_gemini_pro),
    "kimi": ("Kimi K2.5", call_kimi),
}


def parse_json_response(text: str) -> dict | None:
    """Extract JSON from model response (handles markdown code blocks)."""
    # Try direct parse
    text = text.strip()
    if text.startswith("```"):
        # Remove code block
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON in text
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def evaluate_extraction(data: dict, file_label: str) -> dict:
    """Evaluate extraction quality."""
    if not data:
        return {"valid_json": False, "entities": 0, "relations": 0}
    
    entities = data.get("entities", [])
    relations = data.get("relations", [])
    
    # Check schema compliance
    valid_etypes = {"person", "project", "concept", "tool", "event", "decision", "lesson", "research"}
    schema_ok = sum(1 for e in entities if e.get("etype") in valid_etypes)
    has_name_zh = sum(1 for e in entities if e.get("name_zh"))
    has_id = sum(1 for e in entities if e.get("id") and ":" in str(e.get("id", "")))
    avg_conf = sum(e.get("confidence", 0) for e in entities) / max(len(entities), 1)
    
    return {
        "valid_json": True,
        "entities": len(entities),
        "relations": len(relations),
        "schema_ok": schema_ok,
        "has_name_zh": has_name_zh,
        "has_proper_id": has_id,
        "avg_confidence": round(avg_conf, 2),
        "etypes": dict(__import__('collections').Counter(e.get("etype","?") for e in entities)),
    }


def main():
    model_key = sys.argv[1] if len(sys.argv) > 1 else "flash"
    
    if model_key == "all":
        models_to_test = ["flash", "kimi", "pro"]
    else:
        models_to_test = [model_key]
    
    results = {}
    
    for mk in models_to_test:
        model_name, call_fn = MODELS[mk]
        print(f"\n{'='*60}")
        print(f"  Model: {model_name}")
        print(f"{'='*60}")
        
        model_results = []
        
        for label, filepath in TEST_FILES:
            path = Path("/home/yan/clawd") / filepath
            if not path.exists():
                print(f"  ⚠ {label}: file not found, skipping")
                continue
            
            content = path.read_text()
            # Truncate lessons-learned to first 200 lines for fairness
            if len(content.split('\n')) > 200:
                content = '\n'.join(content.split('\n')[:200])
                content += '\n\n[... truncated for test ...]'
            
            prompt = EXTRACT_PROMPT.replace("{path}", filepath).replace("{content}", content)
            
            print(f"\n  📄 {label} ({filepath})")
            try:
                raw, latency = call_fn(prompt)
                data = parse_json_response(raw)
                eval_result = evaluate_extraction(data, label)
                eval_result["latency_s"] = round(latency, 1)
                eval_result["file"] = label
                model_results.append(eval_result)
                
                print(f"     ⏱ {latency:.1f}s | entities={eval_result['entities']} "
                      f"| relations={eval_result['relations']} "
                      f"| schema_ok={eval_result.get('schema_ok',0)}/{eval_result['entities']} "
                      f"| avg_conf={eval_result.get('avg_confidence',0)}")
                
                if data and data.get("entities"):
                    for e in data["entities"][:3]:
                        print(f"       → [{e.get('etype','?'):10s}] {e.get('name_zh','?')} "
                              f"({e.get('id','?')})")
                    if len(data["entities"]) > 3:
                        print(f"       ... +{len(data['entities'])-3} more")
                
                if not eval_result["valid_json"]:
                    print(f"     ❌ JSON parse failed")
                    print(f"     Raw[:200]: {raw[:200]}")
                    
            except Exception as ex:
                print(f"     ❌ Error: {ex}")
                model_results.append({"file": label, "error": str(ex)})
        
        results[mk] = model_results
    
    # Summary comparison
    if len(models_to_test) > 1:
        print(f"\n{'='*60}")
        print(f"  COMPARISON SUMMARY")
        print(f"{'='*60}")
        
        for mk in models_to_test:
            model_name = MODELS[mk][0]
            mrs = results[mk]
            total_e = sum(r.get("entities", 0) for r in mrs)
            total_r = sum(r.get("relations", 0) for r in mrs)
            avg_lat = sum(r.get("latency_s", 0) for r in mrs) / max(len(mrs), 1)
            json_ok = sum(1 for r in mrs if r.get("valid_json"))
            schema_pct = sum(r.get("schema_ok", 0) for r in mrs) / max(total_e, 1) * 100
            
            print(f"\n  {model_name}:")
            print(f"    Entities: {total_e} | Relations: {total_r}")
            print(f"    JSON success: {json_ok}/{len(mrs)}")
            print(f"    Schema compliance: {schema_pct:.0f}%")
            print(f"    Avg latency: {avg_lat:.1f}s")
    
    # Save results
    out = Path("/home/yan/clawd/nous/docs/extraction-ab-test.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n  Results saved to {out}")


if __name__ == "__main__":
    main()
