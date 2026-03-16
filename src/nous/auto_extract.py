"""after_tool_call 自动实体/关系提取 (M7.1)

提供 Python API，用于从工具调用结果中自动提取实体和关系写入 KG。
接入方式：在 gateway_hook.py 的 after_tool_call 中调用此模块。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

# ── Prompt ──────────────────────────────────────────────────────────────────

EXTRACT_PROMPT = """从以下工具调用结果中提取新的实体和关系。
工具: {tool_name}
参数: {params}
结果: {result}

输出严格 JSON:
{{
  "entities": [
    {{"id": "entity:type:slug", "type": "person|project|concept|event|resource",
      "name": "名称", "props": {{}}, "confidence": 0.0-1.0}}
  ],
  "relations": [
    {{"from": "entity:...", "to": "entity:...", "type": "WORKS_ON|KNOWS|DEPENDS_ON|CAUSED_BY|TARGETS",
      "props": {{}}, "confidence": 0.0-1.0}}
  ]
}}

规则：
- 只提取有价值的新信息
- confidence < 0.5 的不要输出
- 日常操作（ls/cat/read）通常不产生新实体
"""

# ── 过滤配置 ─────────────────────────────────────────────────────────────────

# 不值得提取的工具（低信号、高频、无语义内容）
SKIP_TOOLS: frozenset[str] = frozenset({
    "read",
    "process",
    "session_status",
    "memory_search",
    "memory_get",
    "exec",
    "edit",
    "write",
})

# 最小实体/关系置信度阈值
ENTITY_CONFIDENCE_THRESHOLD = 0.8
RELATION_CONFIDENCE_THRESHOLD = 0.8

# 截断长度，防止 prompt 过大
MAX_PARAMS_LEN = 500
MAX_RESULT_LEN = 1000


# ── 核心函数 ─────────────────────────────────────────────────────────────────

async def extract_from_tool_call(
    tool_name: str,
    params: dict[str, Any],
    result: Any,
    db: Any,
    llm_fn: Callable[[str], Awaitable[dict]],
) -> dict[str, int]:
    """从 tool call 提取实体和关系，写入 KG。

    Args:
        tool_name: 工具名称（如 "web_search"）
        params:    工具参数 dict
        result:    工具返回值（任意类型）
        db:        NousDB 实例（需有 upsert_entities / upsert_relations 方法）
        llm_fn:    异步 LLM 调用函数，接受 prompt 字符串，返回解析后的 dict

    Returns:
        {"extracted": N}  其中 N 是写入 KG 的条目数
    """
    from nous.schema import Entity, Relation

    # 1. 过滤低信号工具
    if tool_name in SKIP_TOOLS:
        logger.debug("skip tool: %s", tool_name)
        return {"extracted": 0}

    # 2. 构建 prompt（截断防止过大）
    params_str = str(params)[:MAX_PARAMS_LEN]
    result_str = str(result)[:MAX_RESULT_LEN]

    prompt = EXTRACT_PROMPT.format(
        tool_name=tool_name,
        params=params_str,
        result=result_str,
    )

    # 3. 调用 LLM
    try:
        extracted = await llm_fn(prompt)
    except Exception as exc:
        logger.warning("llm_fn failed for tool %s: %s", tool_name, exc)
        return {"extracted": 0}

    # 4. 构建 Entity/Relation 对象并写入 KG
    now = time.time()
    entities_to_upsert = []
    relations_to_upsert = []

    for raw_entity in extracted.get("entities", []):
        if not isinstance(raw_entity, dict):
            continue
        if raw_entity.get("confidence", 0) < ENTITY_CONFIDENCE_THRESHOLD:
            continue
        try:
            entity = Entity(
                id=raw_entity["id"],
                etype=raw_entity.get("type", "concept"),
                labels=[raw_entity.get("name", "")],
                properties=raw_entity.get("props", {}),
                confidence=raw_entity.get("confidence", 0.8),
                source=f"auto_extract:{tool_name}",
                created_at=now,
                updated_at=now,
            )
            entities_to_upsert.append(entity)
        except Exception as exc:
            logger.warning("build entity failed: %s — %s", raw_entity.get("id"), exc)

    for raw_relation in extracted.get("relations", []):
        if not isinstance(raw_relation, dict):
            continue
        if raw_relation.get("confidence", 0) < RELATION_CONFIDENCE_THRESHOLD:
            continue
        try:
            relation = Relation(
                from_id=raw_relation["from"],
                to_id=raw_relation["to"],
                rtype=raw_relation.get("type", "RELATED_TO"),
                properties=raw_relation.get("props", {}),
                confidence=raw_relation.get("confidence", 0.8),
                source=f"auto_extract:{tool_name}",
                created_at=now,
            )
            relations_to_upsert.append(relation)
        except Exception as exc:
            logger.warning(
                "build relation failed: %s→%s — %s",
                raw_relation.get("from"),
                raw_relation.get("to"),
                exc,
            )

    # 5. 批量写入
    count = 0
    if entities_to_upsert:
        try:
            db.upsert_entities(entities_to_upsert)
            count += len(entities_to_upsert)
            logger.debug("upserted %d entities", len(entities_to_upsert))
        except Exception as exc:
            logger.warning("upsert_entities failed: %s", exc)

    if relations_to_upsert:
        try:
            db.upsert_relations(relations_to_upsert)
            count += len(relations_to_upsert)
            logger.debug("upserted %d relations", len(relations_to_upsert))
        except Exception as exc:
            logger.warning("upsert_relations failed: %s", exc)

    logger.info("tool=%s extracted=%d (entities=%d, relations=%d)",
                tool_name, count, len(entities_to_upsert), len(relations_to_upsert))
    return {"extracted": count}


def parse_llm_json(raw: str) -> dict:
    """解析 LLM 返回的 JSON 字符串（含 markdown 代码块剥离）。

    可在 llm_fn 中使用：
        async def my_llm(prompt):
            raw = await call_api(prompt)
            return parse_llm_json(raw)
    """
    # 剥离 markdown 代码块
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # 去掉首行（```json 或 ```）和末行（```）
        inner_lines = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner_lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("failed to parse LLM JSON: %s | raw=%r", exc, raw[:200])
        return {"entities": [], "relations": []}
