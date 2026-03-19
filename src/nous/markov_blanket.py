"""Nous — Markov Blanket 选择性 KG 注入 (E2)

从 seed entities 出发，沿 KG 关系图扩展 Markov Blanket：
  - Parents: 指向 seed 的实体
  - Children: seed 指向的实体
  - Co-parents: 与 children 共享 parent 的实体

结合 OWL 2 RL 推理结果（owl_inferred_type / owl_inferred_relation），
提供因果相关的精简 KG 上下文，替代全量注入以降低噪声。

设计约束：
  - 总实体数 ≤ max_entities（按 confidence 排序截断）
  - DB 查询预算 ≤ 5 次，延迟 <5ms（24 entities 量级 <1ms）
  - 失败时 graceful degradation → 返回空 blanket
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from nous.db import NousDB

logger = logging.getLogger("nous.markov_blanket")


def _extract_seed_entities(facts: dict) -> list[str]:
    """从 gate facts 提取 seed entities 用于 blanket 扩展。

    Seeds 来源：
    1. tool_name → "tool:{name}"
    2. args 中的可识别实体（URL、recipient、file_path、target）
    3. category/domain → "category:{value}"
    """
    seeds: list[str] = []

    # Tool entity
    tool_name = facts.get("tool_name") or facts.get("name")
    if tool_name:
        seeds.append(f"tool:{tool_name}")

    # Target entities from args
    for key in ("target_url", "url", "recipient", "file_path", "target"):
        val = facts.get(key)
        if val and isinstance(val, str) and val.strip():
            seeds.append(val.strip())

    # Category/domain
    category = facts.get("category") or facts.get("domain")
    if category:
        seeds.append(f"category:{category}")

    return seeds


def compute_blanket(
    db: "NousDB",
    seed_entities: list[str],
    max_depth: int = 2,
    max_entities: int = 15,
) -> dict:
    """计算 seed entities 的 Markov Blanket。

    Markov Blanket 定义（因果图语义）：
      MB(X) = Parents(X) ∪ Children(X) ∪ Co-Parents(Children(X))

    这里将 KG 关系映射为因果图：
      - relation(A → B) 表示 A 是 B 的 parent
      - Children(X) = {Y : X → Y}
      - Parents(X) = {Y : Y → X}
      - Co-Parents(C) = {Y : Y → C, Y ∉ Seeds} for C ∈ Children(X)

    Args:
        db:            NousDB 实例
        seed_entities: 起始实体 ID 列表
        max_depth:     扩展深度（1=仅直接邻居，2=含 co-parents）
        max_entities:  最大返回实体数（按 confidence 降序截断）

    Returns:
        {
            "entities": [{"id": ..., "etype": ..., "confidence": ..., "role": ...}, ...],
            "relations": [{"from_id": ..., "to_id": ..., "rtype": ..., "confidence": ...}, ...],
            "inferred_types": [{"entity_id": ..., "inferred_etype": ..., "rule": ..., "confidence": ...}, ...],
            "relevance_scores": {entity_id: float, ...}
        }
    """
    if not seed_entities or db is None:
        return _empty_blanket()

    try:
        t_start = time.perf_counter()

        # Phase 1: Resolve seeds — which ones exist in KG?
        seed_set = set(seed_entities)
        entity_map: dict[str, dict] = {}  # id → {etype, confidence, role}
        relation_list: list[dict] = []
        relevance: dict[str, float] = {}

        for sid in seed_entities:
            ent = db.find_entity(sid)
            if ent:
                entity_map[sid] = {
                    "id": sid,
                    "etype": ent.get("etype", ""),
                    "confidence": ent.get("confidence", 1.0),
                    "role": "seed",
                }
                relevance[sid] = 1.0  # seeds get max relevance

        if not entity_map:
            return _empty_blanket()

        # Phase 2: Children (seed → Y) and Parents (Y → seed)
        children_set: set[str] = set()

        for sid in list(entity_map.keys()):
            # Children: outgoing relations
            out_rels = db.related(sid, direction="out")
            for r in out_rels[:10]:  # budget cap per entity
                child_id = r.get("to_id", "")
                if not child_id or child_id in entity_map:
                    continue
                children_set.add(child_id)
                relation_list.append({
                    "from_id": sid,
                    "to_id": child_id,
                    "rtype": r.get("rtype", ""),
                    "confidence": r.get("confidence", 1.0),
                })
                if child_id not in entity_map:
                    _add_entity(db, child_id, "child", entity_map, relevance, 0.8)

            # Parents: incoming relations
            in_rels = db.related(sid, direction="in")
            for r in in_rels[:10]:
                parent_id = r.get("from_id", "")
                if not parent_id or parent_id in entity_map:
                    continue
                relation_list.append({
                    "from_id": parent_id,
                    "to_id": sid,
                    "rtype": r.get("rtype", ""),
                    "confidence": r.get("confidence", 1.0),
                })
                if parent_id not in entity_map:
                    _add_entity(db, parent_id, "parent", entity_map, relevance, 0.7)

        # Phase 3: Co-parents (depth 2) — entities that also point to our children
        if max_depth >= 2 and children_set:
            for child_id in list(children_set)[:5]:  # budget: top 5 children
                co_rels = db.related(child_id, direction="in")
                for r in co_rels[:5]:
                    cp_id = r.get("from_id", "")
                    if not cp_id or cp_id in seed_set or cp_id in entity_map:
                        continue
                    relation_list.append({
                        "from_id": cp_id,
                        "to_id": child_id,
                        "rtype": r.get("rtype", ""),
                        "confidence": r.get("confidence", 1.0),
                    })
                    _add_entity(db, cp_id, "co-parent", entity_map, relevance, 0.5)

        # Phase 4: OWL inferred types and relations for blanket entities
        inferred_types: list[dict] = []
        inferred_rels_from_owl: list[dict] = []

        for eid in list(entity_map.keys())[:max_entities]:
            try:
                itypes = db.inferred_type(eid)
                for it in itypes:
                    inferred_types.append({
                        "entity_id": eid,
                        "inferred_etype": it.get("inferred_etype", ""),
                        "rule": it.get("rule", ""),
                        "confidence": it.get("confidence", 1.0),
                    })
            except Exception:
                pass

            try:
                irels = db.inferred_relations(eid, direction="both")
                for ir in irels:
                    inferred_rels_from_owl.append(ir)
                    # Add the other end to entity_map if space allows
                    other_id = ir.get("to_id") or ir.get("from_id", "")
                    if other_id and other_id not in entity_map:
                        _add_entity(db, other_id, "owl-inferred", entity_map, relevance, 0.4)
            except Exception:
                pass

        # Add OWL-inferred relations to relation_list
        for ir in inferred_rels_from_owl:
            fid = ir.get("from_id", "")
            tid = ir.get("to_id", "")
            if fid and tid:
                relation_list.append({
                    "from_id": fid,
                    "to_id": tid,
                    "rtype": ir.get("rtype", ""),
                    "confidence": ir.get("confidence", 0.9),
                    "source": "owl_inferred",
                })

        # Phase 5: Truncate to max_entities by confidence × relevance
        if len(entity_map) > max_entities:
            scored = sorted(
                entity_map.values(),
                key=lambda e: e["confidence"] * relevance.get(e["id"], 0),
                reverse=True,
            )
            keep_ids = {e["id"] for e in scored[:max_entities]}
            entity_map = {k: v for k, v in entity_map.items() if k in keep_ids}
            # Filter relations to only include kept entities
            relation_list = [
                r for r in relation_list
                if r["from_id"] in keep_ids or r["to_id"] in keep_ids
            ]
            # Filter inferred types
            inferred_types = [
                it for it in inferred_types if it["entity_id"] in keep_ids
            ]

        elapsed_ms = (time.perf_counter() - t_start) * 1000
        if elapsed_ms > 5.0:
            logger.warning("Markov blanket computation took %.1fms (budget: 5ms)", elapsed_ms)

        return {
            "entities": list(entity_map.values()),
            "relations": relation_list,
            "inferred_types": inferred_types,
            "relevance_scores": {k: v for k, v in relevance.items() if k in entity_map},
        }

    except Exception as e:
        logger.warning("Markov blanket computation failed (non-fatal): %s", e)
        return _empty_blanket()


def _add_entity(
    db: "NousDB",
    entity_id: str,
    role: str,
    entity_map: dict,
    relevance: dict,
    rel_score: float,
) -> None:
    """尝试将实体加入 entity_map（如果存在于 KG 中）。"""
    if entity_id in entity_map:
        return
    ent = db.find_entity(entity_id)
    if ent:
        entity_map[entity_id] = {
            "id": entity_id,
            "etype": ent.get("etype", ""),
            "confidence": ent.get("confidence", 1.0),
            "role": role,
        }
    else:
        # Entity not in KG — still track as reference
        entity_map[entity_id] = {
            "id": entity_id,
            "etype": "unknown",
            "confidence": 0.5,
            "role": role,
        }
    relevance[entity_id] = rel_score


def _empty_blanket() -> dict:
    """返回空的 blanket 结构。"""
    return {
        "entities": [],
        "relations": [],
        "inferred_types": [],
        "relevance_scores": {},
    }


def format_blanket_for_prompt(blanket: dict) -> str:
    """将 Markov Blanket 格式化为简洁的 prompt 上下文。

    每个实体一行，包含类型+关键关系+推理来源标记。
    设计原则：信息密度高、噪声低、LLM 可读。
    """
    if not blanket or not blanket.get("entities"):
        return "No relevant KG context."

    lines: list[str] = []
    entities = blanket["entities"]
    relations = blanket["relations"]
    inferred = blanket["inferred_types"]

    # Build lookup maps
    inferred_map: dict[str, list[str]] = {}
    for it in inferred:
        eid = it["entity_id"]
        label = f"{it['inferred_etype']}[{it['rule']}]"
        inferred_map.setdefault(eid, []).append(label)

    rel_map: dict[str, list[str]] = {}
    for r in relations:
        fid, tid, rtype = r["from_id"], r["to_id"], r["rtype"]
        rel_map.setdefault(fid, []).append(f"→{rtype}→{tid}")
        rel_map.setdefault(tid, []).append(f"←{rtype}←{fid}")

    for ent in entities:
        eid = ent["id"]
        etype = ent.get("etype", "?")
        role = ent.get("role", "")
        conf = ent.get("confidence", 1.0)

        parts = [f"`{eid}` ({etype}"]
        if role and role != "seed":
            parts[0] += f", {role}"
        parts[0] += f", conf={conf:.2f})"

        # Add inferred types
        inf_labels = inferred_map.get(eid, [])
        if inf_labels:
            parts.append(f"  inferred: {', '.join(inf_labels[:3])}")

        # Add key relations (max 3)
        rels = rel_map.get(eid, [])
        if rels:
            parts.append(f"  rels: {'; '.join(rels[:3])}")

        # Props-based risk signals (from seed entities)
        props = ent.get("props", {})
        if isinstance(props, dict):
            risk = props.get("risk_level")
            if risk and risk in ("high", "critical"):
                parts.append(f"  ⚠️ RISK={risk.upper()}")
            evasion = props.get("evasion_patterns", [])
            if evasion:
                parts.append(f"  ⚠️ EVASION: {', '.join(str(e) for e in evasion[:2])}")

        lines.append(" | ".join(parts))

    return "KG Context (Markov Blanket):\n" + "\n".join(lines)
