"""Nous — Bayesian edge weight updates for KG relations.

When gate() produces a verdict, relations connected to involved entities
get their confidence updated via Beta distribution posterior:
  block   → alpha += 1.0  (KG correctly flagged danger)
  confirm → alpha += 0.3  (uncertain, leaning toward risk)
  allow   → beta  += 0.5  (relation less relevant to safety)
"""
import json
import logging

from nous.db import NousDB

logger = logging.getLogger("nous.edge_weight")

# Bayesian update increments: (d_alpha, d_beta) per verdict
_VERDICT_UPDATES: dict[str, tuple[float, float]] = {
    "block": (1.0, 0.0), "confirm": (0.3, 0.0), "allow": (0.0, 0.5),
}


def _extract_entity_ids(gate_result: dict) -> set[str]:
    """Extract entity IDs from kg_context and facts."""
    ids: set[str] = set()
    kg_ctx = gate_result.get("kg_context")
    if kg_ctx and isinstance(kg_ctx, dict):
        for key in ("entities", "policies"):
            for ent in kg_ctx.get(key, []):
                if isinstance(ent, dict) and ent.get("id"):
                    ids.add(ent["id"])
    facts = gate_result.get("facts") or {}
    for fact_key in ("tool_name", "name", "target", "recipient", "target_url"):
        val = facts.get(fact_key)
        if val and isinstance(val, str):
            ids.add(val)
            if ":" not in val:
                ids.add(f"tool:{val}")
    return ids


def _query_relations(db: NousDB, entity_id: str) -> list[dict]:
    """Query all relations where entity is from_id or to_id."""
    q_tpl = (
        "?[from_id, to_id, rtype, props, confidence, source, created_at] := "
        "*relation{{from_id, to_id, rtype, props, confidence, source, created_at}}, "
        "{col} = $eid"
    )
    out = db._query_with_params(q_tpl.format(col="from_id"), {"eid": entity_id})
    inc = db._query_with_params(q_tpl.format(col="to_id"), {"eid": entity_id})
    return out + inc


def update_edge_weights(db: NousDB, gate_result: dict) -> int:
    """Update confidence of KG edges connected to gate verdict entities.

    Args:
        db: NousDB instance with active connection.
        gate_result: Dict with keys: verdict (str), kg_context (dict|None),
                     facts (dict).

    Returns:
        Count of updated edges.
    """
    verdict = gate_result.get("verdict", "")
    if verdict not in _VERDICT_UPDATES:
        return 0

    entity_ids = _extract_entity_ids(gate_result)
    if not entity_ids:
        return 0

    d_alpha, d_beta = _VERDICT_UPDATES[verdict]
    seen: set[tuple[str, str, str]] = set()
    updated = 0

    for eid in entity_ids:
        for rel in _query_relations(db, eid):
            edge_key = (rel["from_id"], rel["to_id"], rel["rtype"])
            if edge_key in seen:
                continue
            seen.add(edge_key)

            props = rel.get("props") or {}
            if isinstance(props, str):
                props = json.loads(props)

            alpha = props.get("alpha", 1.0) + d_alpha
            beta = props.get("beta", 1.0) + d_beta
            new_props = {**props, "alpha": alpha, "beta": beta}

            db.db.run(
                "?[from_id, to_id, rtype, props, confidence, source, created_at] "
                "<- [[$fid, $tid, $rt, $props, $conf, $src, $cat]] "
                ":put relation {from_id, to_id, rtype => props, confidence, source, created_at}",
                {
                    "fid": rel["from_id"], "tid": rel["to_id"], "rt": rel["rtype"],
                    "props": new_props, "conf": alpha / (alpha + beta),
                    "src": rel.get("source", ""), "cat": rel.get("created_at", 0.0),
                },
            )
            updated += 1

    logger.debug("Updated %d edges (verdict=%s, entities=%d)", updated, verdict, len(entity_ids))
    return updated
