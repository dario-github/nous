#!/usr/bin/env python3
"""M7.2 + M11.1 迁移脚本

1. 把 RELATED_TO 关系用 LLM 重新分类为 9 种语义关系类型
2. 给现有实体加 valid_from/observed_at 时间维度（从 created_at 推断）
3. 增强 parser 的推断覆盖

用法: PYTHONPATH=src python3 scripts/migrate_relations.py [--dry-run]
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.db import NousDB

# ── 9 种关系类型定义 ─────────────────────────────────────────────────────

VALID_RTYPES = {
    "WORKS_ON",     # person → project/task
    "KNOWS",        # person ↔ person
    "DEPENDS_ON",   # project → project/tool
    "CAUSED_BY",    # event → event/action
    "TARGETS",      # action/policy → entity
    "PART_OF",      # sub → parent
    "GOVERNS",      # rule/policy → entity
    "CONTRADICTS",  # claim ↔ claim
    "SUPERSEDES",   # new_version → old_version
}

# ── 基于类型对的确定性映射（不需要 LLM）─────────────────────────────────

TYPE_PAIR_MAP = {
    ("person", "project"): "WORKS_ON",
    ("person", "person"): "KNOWS",
    ("project", "project"): "DEPENDS_ON",
    ("project", "tool"): "DEPENDS_ON",
    ("tool", "project"): "PART_OF",
    ("concept", "project"): "PART_OF",
    ("concept", "concept"): "PART_OF",
    ("category", "category"): "PART_OF",
    ("policy", "category"): "GOVERNS",
    ("policy", "person"): "TARGETS",
    ("policy", "project"): "TARGETS",
    ("event", "event"): "CAUSED_BY",
    # unknown 类型的兜底规则
    ("concept", "unknown"): "PART_OF",
    ("person", "unknown"): "WORKS_ON",
    ("project", "unknown"): "DEPENDS_ON",
    ("project", "person"): "WORKS_ON",  # evaluation-system → Alice
}

# 特殊 entity 名称 → 确定性映射
ENTITY_RTYPE_OVERRIDES = {
    # concept → 晏 = PART_OF (概念与晏相关)
    ("entity:concept:MMAcevedo", "entity:unknown:晏"): "PART_OF",
    ("entity:concept:Personal-Identity", "entity:unknown:晏"): "PART_OF",
    # person → org/field = WORKS_ON
    ("entity:person:Mrinank-Sharma", "entity:unknown:AI-Safety"): "WORKS_ON",
    ("entity:person:Mrinank-Sharma", "entity:unknown:Anthropic"): "WORKS_ON",
    # project → platform/tool = DEPENDS_ON
    ("entity:project:Context-Slim", "entity:unknown:OpenClaw"): "PART_OF",
    ("entity:project:interactive-movie-game", "entity:unknown:KOX-Agent"): "DEPENDS_ON",
    ("entity:project:interactive-movie-game", "entity:unknown:Ren'Py"): "DEPENDS_ON",
    ("entity:project:interactive-movie-game", "entity:unknown:Seedance"): "DEPENDS_ON",
    ("entity:project:interactive-movie-game", "entity:unknown:即梦"): "DEPENDS_ON",
    ("entity:project:portfolio-site", "entity:unknown:Vercel"): "DEPENDS_ON",
    ("entity:project:portfolio-site", "entity:unknown:example.com"): "PART_OF",
    ("entity:project:portfolio-site", "entity:unknown:framer-motion"): "DEPENDS_ON",
    # project → person = WORKS_ON (反向)
    ("entity:project:evaluation-system", "entity:person:Alice"): "WORKS_ON",
    ("entity:project:evaluation-system", "entity:unknown:投资系统"): "PART_OF",
    ("entity:project:portfolio-site", "entity:person:Alice"): "WORKS_ON",
    ("entity:project:portfolio-site", "entity:unknown:晏"): "WORKS_ON",
    ("entity:project:tsinghua-mem", "entity:person:Alice"): "WORKS_ON",
}


def get_etype(entity_id: str) -> str:
    """entity:type:slug → type"""
    parts = entity_id.split(":")
    return parts[1] if len(parts) >= 3 else "unknown"


def reclassify_deterministic(from_id: str, to_id: str, current_rtype: str) -> str | None:
    """尝试用确定性规则重新分类。返回 None 表示需要 LLM。"""
    if current_rtype != "RELATED_TO":
        return None  # 已有语义类型，不改

    # 先查特殊覆盖
    override = ENTITY_RTYPE_OVERRIDES.get((from_id, to_id))
    if override:
        return override

    from_type = get_etype(from_id)
    to_type = get_etype(to_id)
    return TYPE_PAIR_MAP.get((from_type, to_type))


def migrate_relations(db: NousDB, dry_run: bool = False):
    """重新分类 RELATED_TO 关系"""
    rels = db.query(
        "?[from_id, to_id, rtype, props, confidence, source, created_at] "
        ":= *relation{from_id, to_id, rtype, props, confidence, source, created_at}"
    )

    migrated = 0
    skipped = 0
    needs_llm = []

    for r in rels:
        from_id = r["from_id"]
        to_id = r["to_id"]
        rtype = r["rtype"]

        if rtype != "RELATED_TO":
            skipped += 1
            continue

        new_rtype = reclassify_deterministic(from_id, to_id, rtype)
        if new_rtype:
            if dry_run:
                print(f"  [DRY] {from_id} → {to_id}: {rtype} → {new_rtype}")
            else:
                # Cozo: 删旧关系，写新关系
                db.query(f"""
                    ?[from_id, to_id, rtype] <- [["{from_id}", "{to_id}", "{rtype}"]]
                    :rm relation {{from_id, to_id, rtype}}
                """)
                db.query(f"""
                    ?[from_id, to_id, rtype, props, confidence, source, created_at] <- [[
                        "{from_id}", "{to_id}", "{new_rtype}",
                        {json.dumps(r['props']) if isinstance(r['props'], str) else json.dumps(r['props'])},
                        {r['confidence']}, "{r['source']}", {r['created_at']}
                    ]]
                    :put relation {{from_id, to_id, rtype, props, confidence, source, created_at}}
                """)
                print(f"  ✅ {from_id} → {to_id}: {rtype} → {new_rtype}")
            migrated += 1
        else:
            needs_llm.append(r)

    print(f"\n=== 迁移结果 ===")
    print(f"  确定性重分类: {migrated}")
    print(f"  已有语义类型: {skipped}")
    print(f"  需要 LLM 分类: {len(needs_llm)}")

    if needs_llm:
        print(f"\n需要 LLM 的关系:")
        for r in needs_llm:
            print(f"  {r['from_id']} → {r['to_id']} ({r['rtype']})")

    return migrated, needs_llm


def add_time_dimensions(db: NousDB, dry_run: bool = False):
    """M11.1: 给实体的 props 加 valid_from/observed_at"""
    ents = db.query(
        "?[id, etype, props, created_at, updated_at] "
        ":= *entity{id, etype, props, created_at, updated_at}"
    )

    updated = 0
    for e in ents:
        props = e["props"] if isinstance(e["props"], dict) else json.loads(e["props"]) if e["props"] else {}
        if "valid_from" in props:
            continue  # 已有

        # 从 created_at 推断 valid_from
        props["valid_from"] = e["created_at"]
        props["observed_at"] = e.get("updated_at") or e["created_at"]

        if dry_run:
            print(f"  [DRY] {e['id']}: +valid_from={props['valid_from']:.0f}")
        else:
            eid = e['id']
            props_json = json.dumps(props)
            db.query(f"""
                ?[id, etype, labels, props, metadata, confidence, source, created_at, updated_at] := 
                    *entity{{id: id_v, etype, labels, metadata, confidence, source, created_at, updated_at}},
                    id_v = "{eid}",
                    id = id_v,
                    props = {props_json}
                :put entity {{id, etype, labels, props, metadata, confidence, source, created_at, updated_at}}
            """)
            updated += 1

    print(f"\n=== 时间维度 ===")
    print(f"  实体加 valid_from: {updated}")
    return updated


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN ===\n")

    db = NousDB("nous.db")

    print("--- Step 1: 关系类型重分类 (M7.2) ---")
    migrated, needs_llm = migrate_relations(db, dry_run)

    print("\n--- Step 2: 实体时间维度 (M11.1) ---")
    updated = add_time_dimensions(db, dry_run)

    # 验证
    if not dry_run:
        print("\n--- 验证 ---")
        rels = db.query("?[rtype, count(from_id)] := *relation{from_id, rtype}, :order rtype")
        print("关系类型分布:")
        for r in rels:
            print(f"  {r['rtype']}: {r['count(from_id)']}")


if __name__ == "__main__":
    main()
