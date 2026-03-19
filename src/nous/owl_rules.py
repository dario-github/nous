"""OWL 2 RL 推理规则 — Cozo Datalog 实现

基于 Herron et al. 2025: OWL 2 RL profile 可用纯 Datalog 执行。
实现三类核心推理：
1. SubClassOf 传递闭包 — 类型层级的传递推理
2. Property Chain — 关系链组合推理
3. Domain/Range — 根据关系的 domain/range 自动推导实体类型

所有推理结果物化到专用表中，不修改原始 entity/relation 数据。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nous.db import NousDB


# ── Schema: OWL 规则元数据表 ──────────────────────────────────────────

OWL_SCHEMAS = [
    # TBox: 类型之间的 subclass 关系 (A subClassOf B)
    """
    :create owl_subclass {
        sub: String,
        super: String =>
        source: String default 'manual',
        created_at: Float default 0.0
    }
    """,
    # TBox: 属性链规则 (r1 ∘ r2 → r3)
    """
    :create owl_property_chain {
        chain_id: String =>
        r1: String,
        r2: String,
        r_result: String,
        source: String default 'manual',
        created_at: Float default 0.0
    }
    """,
    # TBox: 关系的 domain/range 声明
    """
    :create owl_domain_range {
        rtype: String =>
        domain_type: String default '',
        range_type: String default '',
        source: String default 'manual',
        created_at: Float default 0.0
    }
    """,
    # ABox: 物化的推理结果 — 推导出的类型
    """
    :create owl_inferred_type {
        entity_id: String,
        inferred_etype: String =>
        rule: String default '',
        confidence: Float default 1.0,
        created_at: Float default 0.0
    }
    """,
    # ABox: 物化的推理结果 — 推导出的关系
    """
    :create owl_inferred_relation {
        from_id: String,
        to_id: String,
        rtype: String =>
        rule: String default '',
        confidence: Float default 1.0,
        created_at: Float default 0.0
    }
    """,
]


def init_owl_schema(db: NousDB) -> None:
    """创建 OWL 推理所需的表（幂等）。"""
    for schema in OWL_SCHEMAS:
        try:
            db.db.run(schema)
        except Exception as e:
            err = str(e).lower()
            if "already exists" in err or "conflicts with an existing" in err:
                pass
            else:
                raise


# ── TBox 写入 API ─────────────────────────────────────────────────────

def add_subclass(db: NousDB, sub: str, super_: str,
                 source: str = "manual") -> None:
    """声明 sub subClassOf super_。"""
    db.db.run(
        "?[sub, super, source, created_at] "
        "<- [[$sub, $super, $src, $ts]] "
        ":put owl_subclass { sub, super => source, created_at }",
        {"sub": sub, "super": super_, "src": source, "ts": time.time()},
    )


def add_property_chain(db: NousDB, chain_id: str,
                       r1: str, r2: str, r_result: str,
                       source: str = "manual") -> None:
    """声明属性链: r1 ∘ r2 → r_result。"""
    db.db.run(
        "?[chain_id, r1, r2, r_result, source, created_at] "
        "<- [[$cid, $r1, $r2, $rr, $src, $ts]] "
        ":put owl_property_chain { chain_id => r1, r2, r_result, source, created_at }",
        {"cid": chain_id, "r1": r1, "r2": r2, "rr": r_result,
         "src": source, "ts": time.time()},
    )


def add_domain_range(db: NousDB, rtype: str,
                     domain_type: str = "", range_type: str = "",
                     source: str = "manual") -> None:
    """声明关系的 domain 和 range 类型。"""
    db.db.run(
        "?[rtype, domain_type, range_type, source, created_at] "
        "<- [[$rt, $dt, $rgt, $src, $ts]] "
        ":put owl_domain_range { rtype => domain_type, range_type, source, created_at }",
        {"rt": rtype, "dt": domain_type, "rgt": range_type,
         "src": source, "ts": time.time()},
    )


# ── 推理引擎 ──────────────────────────────────────────────────────────

def _clear_inferred(db: NousDB) -> None:
    """清空所有推理结果（重新物化前调用）。"""
    # 删除所有 inferred type
    try:
        rows = db.db.run(
            "?[entity_id, inferred_etype] := "
            "*owl_inferred_type{entity_id, inferred_etype}"
        )
        if hasattr(rows, '__len__') and len(rows) > 0:
            db.db.run(
                "?[entity_id, inferred_etype] := "
                "*owl_inferred_type{entity_id, inferred_etype} "
                ":rm owl_inferred_type {entity_id, inferred_etype}"
            )
    except Exception:
        pass

    # 删除所有 inferred relation
    try:
        rows = db.db.run(
            "?[from_id, to_id, rtype] := "
            "*owl_inferred_relation{from_id, to_id, rtype}"
        )
        if hasattr(rows, '__len__') and len(rows) > 0:
            db.db.run(
                "?[from_id, to_id, rtype] := "
                "*owl_inferred_relation{from_id, to_id, rtype} "
                ":rm owl_inferred_relation {from_id, to_id, rtype}"
            )
    except Exception:
        pass


def _materialize_subclass_transitive(db: NousDB) -> int:
    """SubClassOf 传递闭包推理。

    对于每个实体 e 的 etype=T，如果 T subClassOf S（传递），
    则推导 e 也属于类型 S。

    使用 Cozo 的递归 Datalog 实现传递闭包：
      tc[sub, super] := *owl_subclass{sub, super}
      tc[sub, super] := tc[sub, mid], *owl_subclass{sub: mid, super}

    返回推导出的新类型数。
    """
    # Cozo 支持内联规则（inline rules）实现递归
    # 先计算传递闭包，然后对每个实体的 etype 进行推导
    result = db.db.run(
        "tc[sub, super] := *owl_subclass{sub, super} "
        "tc[sub, super] := tc[sub, mid], *owl_subclass{sub: mid, super} "
        "?[eid, super] := *entity{id: eid, etype}, tc[etype, super]"
    )
    if hasattr(result, "to_dict"):
        rows = result.to_dict(orient="records")
    elif isinstance(result, list):
        rows = result
    else:
        rows = []

    count = 0
    now = time.time()
    for row in rows:
        vals = list(row.values()) if isinstance(row, dict) else row
        eid, super_type = vals[0], vals[1]
        db.db.run(
            "?[entity_id, inferred_etype, rule, confidence, created_at] "
            "<- [[$eid, $st, $rule, 1.0, $ts]] "
            ":put owl_inferred_type { entity_id, inferred_etype => "
            "rule, confidence, created_at }",
            {"eid": eid, "st": super_type,
             "rule": "subclass_transitive", "ts": now},
        )
        count += 1

    return count


def _materialize_property_chains(db: NousDB) -> int:
    """Property chain 推理: r1 ∘ r2 → r_result。

    如果存在 (a, r1, b) 且 (b, r2, c)，且有链规则 r1∘r2→r_result，
    则推导 (a, r_result, c)。

    返回推导出的新关系数。
    """
    result = db.db.run(
        "?[from_id, to_id, r_result, chain_id] := "
        "*owl_property_chain{chain_id, r1, r2, r_result}, "
        "*relation{from_id, to_id: mid, rtype: r1}, "
        "*relation{from_id: mid, to_id, rtype: r2}"
    )
    if hasattr(result, "to_dict"):
        rows = result.to_dict(orient="records")
    elif isinstance(result, list):
        rows = result
    else:
        rows = []

    count = 0
    now = time.time()
    for row in rows:
        vals = list(row.values()) if isinstance(row, dict) else row
        fid, tid, rr, cid = vals[0], vals[1], vals[2], vals[3]
        db.db.run(
            "?[from_id, to_id, rtype, rule, confidence, created_at] "
            "<- [[$fid, $tid, $rr, $rule, 0.9, $ts]] "
            ":put owl_inferred_relation { from_id, to_id, rtype => "
            "rule, confidence, created_at }",
            {"fid": fid, "tid": tid, "rr": rr,
             "rule": f"property_chain:{cid}", "ts": now},
        )
        count += 1

    return count


def _materialize_domain_range(db: NousDB) -> int:
    """Domain/Range 推理。

    如果关系 (a, R, b) 存在，且 R 的 domain=D，则推导 a 的类型为 D。
    如果 R 的 range=G，则推导 b 的类型为 G。

    返回推导出的新类型数。
    """
    count = 0
    now = time.time()

    # Domain: 关系的起点获得 domain 类型
    result_d = db.db.run(
        "?[from_id, domain_type] := "
        "*owl_domain_range{rtype, domain_type}, "
        "domain_type != '', "
        "*relation{from_id, to_id, rtype}"
    )
    if hasattr(result_d, "to_dict"):
        rows_d = result_d.to_dict(orient="records")
    elif isinstance(result_d, list):
        rows_d = result_d
    else:
        rows_d = []

    for row in rows_d:
        vals = list(row.values()) if isinstance(row, dict) else row
        eid, dtype = vals[0], vals[1]
        db.db.run(
            "?[entity_id, inferred_etype, rule, confidence, created_at] "
            "<- [[$eid, $dt, $rule, 0.95, $ts]] "
            ":put owl_inferred_type { entity_id, inferred_etype => "
            "rule, confidence, created_at }",
            {"eid": eid, "dt": dtype,
             "rule": "domain_inference", "ts": now},
        )
        count += 1

    # Range: 关系的终点获得 range 类型
    result_r = db.db.run(
        "?[to_id, range_type] := "
        "*owl_domain_range{rtype, range_type}, "
        "range_type != '', "
        "*relation{from_id, to_id, rtype}"
    )
    if hasattr(result_r, "to_dict"):
        rows_r = result_r.to_dict(orient="records")
    elif isinstance(result_r, list):
        rows_r = result_r
    else:
        rows_r = []

    for row in rows_r:
        vals = list(row.values()) if isinstance(row, dict) else row
        eid, rtype = vals[0], vals[1]
        db.db.run(
            "?[entity_id, inferred_etype, rule, confidence, created_at] "
            "<- [[$eid, $rt, $rule, 0.95, $ts]] "
            ":put owl_inferred_type { entity_id, inferred_etype => "
            "rule, confidence, created_at }",
            {"eid": eid, "rt": rtype,
             "rule": "range_inference", "ts": now},
        )
        count += 1

    return count


def materialize_inferences(db: NousDB) -> dict:
    """执行完整的 OWL 2 RL 推理并物化结果。

    Returns:
        dict with keys: subclass_count, chain_count, domain_range_count, total
    """
    _clear_inferred(db)

    sc = _materialize_subclass_transitive(db)
    pc = _materialize_property_chains(db)
    dr = _materialize_domain_range(db)

    return {
        "subclass_count": sc,
        "chain_count": pc,
        "domain_range_count": dr,
        "total": sc + pc + dr,
    }


# ── 查询 API ──────────────────────────────────────────────────────────

def inferred_types(db: NousDB, entity_id: str) -> list[dict]:
    """查询实体的推导类型。"""
    result = db.db.run(
        "?[inferred_etype, rule, confidence] := "
        "*owl_inferred_type{entity_id, inferred_etype, rule, confidence}, "
        "entity_id = $eid",
        {"eid": entity_id},
    )
    if hasattr(result, "to_dict"):
        return result.to_dict(orient="records")
    return result if isinstance(result, list) else []


def inferred_relations(db: NousDB, entity_id: str,
                       direction: str = "out") -> list[dict]:
    """查询实体的推导关系。

    direction: "out" (从 entity_id 出发), "in" (指向 entity_id), "both"
    """
    results = []

    if direction in ("out", "both"):
        r = db.db.run(
            "?[to_id, rtype, rule, confidence] := "
            "*owl_inferred_relation{from_id, to_id, rtype, rule, confidence}, "
            "from_id = $eid",
            {"eid": entity_id},
        )
        if hasattr(r, "to_dict"):
            rows = r.to_dict(orient="records")
        else:
            rows = r if isinstance(r, list) else []
        for row in rows:
            row["direction"] = "out"
        results.extend(rows)

    if direction in ("in", "both"):
        r = db.db.run(
            "?[from_id, rtype, rule, confidence] := "
            "*owl_inferred_relation{from_id, to_id, rtype, rule, confidence}, "
            "to_id = $eid",
            {"eid": entity_id},
        )
        if hasattr(r, "to_dict"):
            rows = r.to_dict(orient="records")
        else:
            rows = r if isinstance(r, list) else []
        for row in rows:
            row["direction"] = "in"
        results.extend(rows)

    return results


def subclass_closure(db: NousDB, etype: str) -> list[str]:
    """查询某类型的所有超类型（传递闭包）。"""
    result = db.db.run(
        "tc[sub, super] := *owl_subclass{sub, super} "
        "tc[sub, super] := tc[sub, mid], *owl_subclass{sub: mid, super} "
        "?[super] := tc[$et, super]",
        {"et": etype},
    )
    if hasattr(result, "to_dict"):
        rows = result.to_dict(orient="records")
    else:
        rows = result if isinstance(result, list) else []
    return [list(r.values())[0] if isinstance(r, dict) else r[0] for r in rows]


def subclass_descendants(db: NousDB, etype: str) -> list[str]:
    """查询某类型的所有子类型（传递闭包）。"""
    result = db.db.run(
        "tc[sub, super] := *owl_subclass{sub, super} "
        "tc[sub, super] := tc[sub, mid], *owl_subclass{sub: mid, super} "
        "?[sub] := tc[sub, $et]",
        {"et": etype},
    )
    if hasattr(result, "to_dict"):
        rows = result.to_dict(orient="records")
    else:
        rows = result if isinstance(result, list) else []
    return [list(r.values())[0] if isinstance(r, dict) else r[0] for r in rows]
