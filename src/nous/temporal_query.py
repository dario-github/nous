"""Nous — 时序查询 API (M11.3)

提供 query_at(entity_id, timestamp) —— 返回实体在指定时间点的状态。

设计：
- 利用 entity.props.valid_from 和 relation.created_at 做时间过滤
- 实体层面：如果 valid_from > timestamp，该实体在该时间点"不存在"
- 关系层面：只返回 created_at <= timestamp 的关系
- 属性快照：如果 props 中有 history 列表，返回该时间点最近的版本

不修改 schema，纯查询层。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from nous.db import NousDB


@dataclass
class TemporalSnapshot:
    """实体在某时间点的状态快照"""
    entity_id: str
    timestamp: float
    exists: bool
    entity: Optional[dict] = None
    relations: list[dict] | None = None
    note: str = ""


def query_at(
    db: "NousDB",
    entity_id: str,
    timestamp: float | None = None,
    include_relations: bool = True,
) -> TemporalSnapshot:
    """查询实体在指定时间点的状态。

    Args:
        db: NousDB 实例
        entity_id: 实体 ID
        timestamp: 查询时间点（epoch seconds），None = 当前
        include_relations: 是否包含关系

    Returns:
        TemporalSnapshot
    """
    if timestamp is None:
        timestamp = time.time()

    entity = db.find_entity(entity_id)
    if not entity:
        return TemporalSnapshot(
            entity_id=entity_id,
            timestamp=timestamp,
            exists=False,
            note="entity not found in KG",
        )

    # 检查 valid_from
    props = entity.get("props", {})
    valid_from = props.get("valid_from", 0)
    created_at = entity.get("created_at", 0)
    effective_start = valid_from or created_at or 0

    if effective_start > timestamp:
        return TemporalSnapshot(
            entity_id=entity_id,
            timestamp=timestamp,
            exists=False,
            entity=entity,
            note=f"entity exists but valid_from ({effective_start}) > query time ({timestamp})",
        )

    # 实体在该时间点存在，构建快照
    snapshot_entity = dict(entity)

    # 如果 props 有 history，取最近的版本
    history = props.get("history", [])
    if history:
        # history 格式: [{"timestamp": epoch, "changes": {...}}, ...]
        applicable = [h for h in history if h.get("timestamp", 0) <= timestamp]
        if applicable:
            applicable.sort(key=lambda h: h["timestamp"])
            # 从原始 props 开始，逐步应用变更
            snapshot_props = {k: v for k, v in props.items() if k != "history"}
            for h in applicable:
                snapshot_props.update(h.get("changes", {}))
            snapshot_entity["props"] = snapshot_props
            snapshot_entity["_snapshot_source"] = f"history entry at {applicable[-1]['timestamp']}"

    relations = None
    if include_relations:
        # 获取所有关系，手动过滤 created_at <= timestamp
        all_rels = db.related(entity_id, direction="both")
        relations = [
            r for r in all_rels
            if r.get("created_at", 0) <= timestamp
        ]

    return TemporalSnapshot(
        entity_id=entity_id,
        timestamp=timestamp,
        exists=True,
        entity=snapshot_entity,
        relations=relations,
    )


def entity_timeline(
    db: "NousDB",
    entity_id: str,
) -> list[dict]:
    """获取实体的事件时间线。

    返回按时间排序的事件列表（创建、属性变更、关系建立）。
    """
    entity = db.find_entity(entity_id)
    if not entity:
        return []

    events = []
    props = entity.get("props", {})
    created_at = entity.get("created_at", 0)
    valid_from = props.get("valid_from", 0)

    # 实体创建
    events.append({
        "timestamp": valid_from or created_at or 0,
        "type": "entity_created",
        "detail": f"{entity_id} ({entity.get('etype', 'unknown')})",
    })

    # 属性变更历史
    for h in props.get("history", []):
        events.append({
            "timestamp": h.get("timestamp", 0),
            "type": "property_change",
            "detail": str(h.get("changes", {})),
        })

    # 关系建立时间
    all_rels = db.related(entity_id, direction="both")
    for r in all_rels:
        t = r.get("created_at", 0)
        direction = r.get("direction", "out")
        rtype = r.get("rtype", "?")
        other = r.get("to_id" if direction == "out" else "from_id", "?")
        events.append({
            "timestamp": t,
            "type": "relation_created",
            "detail": f"{'->' if direction == 'out' else '<-'} {rtype} {other}",
        })

    events.sort(key=lambda e: e["timestamp"])
    return events
