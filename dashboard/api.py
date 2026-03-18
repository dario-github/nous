#!/usr/bin/env python3
"""νοῦς Dashboard — Live API Server

FastAPI 后端，提供：
1. GET /api/kg          — 实时 KG 数据（含 effective_confidence）
2. GET /api/stats       — Shadow 统计 + 延迟分布
3. GET /api/events      — SSE 事件流（KG 变更 / gate 决策）
4. POST /api/reason     — 交互式推理（问题 → gate proof_trace）
5. GET /api/timeline    — 实体时间线（M11.3）
6. GET /api/diff        — KG diff（自上次请求以来的变更）
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Add nous src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from nous.db import NousDB
from nous.edge_weight import effective_confidence, rank_edges

app = FastAPI(title="νοῦς Dashboard API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_PATH = Path(__file__).parent.parent / "nous.db"
SHADOW_LOG = Path(__file__).parent.parent / "logs" / "shadow_live.jsonl"
SHADOW_STATS = Path(__file__).parent.parent / "logs" / "shadow_stats.json"
DECISION_LOG = Path(__file__).parent.parent / "logs" / "decisions.jsonl"

# ── KG snapshot cache ────────────────────────────────────────────────────
_kg_cache = {"hash": None, "data": None, "ts": 0}


def _get_db():
    return NousDB(str(DB_PATH))


def _build_kg_snapshot(db: NousDB) -> dict:
    """Build full KG snapshot with effective confidence."""
    now = time.time()
    entities = db.query(
        "?[id, etype, labels, props, confidence, source, created_at, updated_at] := "
        "*entity{id, etype, labels, props, confidence, source, created_at, updated_at}"
    )
    relations = db.query(
        "?[from_id, to_id, rtype, props, confidence, source, created_at] := "
        "*relation{from_id, to_id, rtype, props, confidence, source, created_at}"
    )

    ent_list = []
    for e in entities:
        ent_list.append({
            "id": e["id"],
            "type": e["etype"],
            "labels": e.get("labels", []),
            "props": e.get("props", {}),
            "confidence": e.get("confidence", 1.0),
            "source": e.get("source", ""),
            "created_at": e.get("created_at", 0),
            "updated_at": e.get("updated_at", 0),
            "age_hours": round((now - e.get("created_at", now)) / 3600, 1),
        })

    rel_list = []
    for r in relations:
        props = r.get("props", {}) or {}
        eff_conf = effective_confidence(
            base=r.get("confidence", 1.0),
            created_at=r.get("created_at", now),
            now=now,
            props=props,
        )
        rel_list.append({
            "from": r["from_id"],
            "to": r["to_id"],
            "type": r["rtype"],
            "props": props,
            "confidence": r.get("confidence", 1.0),
            "effective_confidence": round(eff_conf, 4),
            "created_at": r.get("created_at", 0),
            "age_hours": round((now - r.get("created_at", now)) / 3600, 1),
        })

    return {"entities": ent_list, "relations": rel_list, "ts": now}


@app.get("/api/kg")
def get_kg():
    db = _get_db()
    return _build_kg_snapshot(db)


@app.get("/api/stats")
def get_stats():
    """Shadow stats + enriched data."""
    stats = {}
    if SHADOW_STATS.exists():
        stats = json.loads(SHADOW_STATS.read_text())

    # Enrich with recent decisions
    recent_decisions = []
    if DECISION_LOG.exists():
        lines = DECISION_LOG.read_text().strip().split("\n")
        for line in lines[-50:]:  # last 50
            try:
                recent_decisions.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    stats["recent_decisions"] = recent_decisions
    return stats


class ReasonRequest(BaseModel):
    question: str
    tool_call: Optional[dict] = None


@app.post("/api/reason")
def reason(req: ReasonRequest):
    """Interactive reasoning — simulate gate() and return proof trace.

    If tool_call is provided, run it through gate() directly.
    If only question is provided, parse it into a synthetic tool_call.
    """
    from nous.gate import gate, GateResult
    from nous.fact_extractor import extract_facts

    db = _get_db()

    if req.tool_call:
        tc = req.tool_call
    else:
        # Parse question into synthetic tool_call for exploration
        tc = _question_to_tool_call(req.question)

    # Run through gate
    result: GateResult = gate(
        tc,
        constraints_dir=str(Path(__file__).parent.parent / "ontology" / "constraints"),
        db=db,
    )

    # Build KG context for the entities involved
    kg_context = _get_related_kg_context(db, tc)

    return {
        "question": req.question,
        "tool_call": tc,
        "verdict": {
            "action": result.verdict.action,
            "reason": result.verdict.reason,
        },
        "proof_trace": result.proof_trace.to_dict(),
        "facts_extracted": result.facts if hasattr(result, "facts") else {},
        "layer_path": result.layer_path if hasattr(result, "layer_path") else "",
        "semantic_verdict": result.semantic_verdict if hasattr(result, "semantic_verdict") else None,
        "kg_context": kg_context,
        "latency_ms": result.proof_trace.total_ms,
    }


def _question_to_tool_call(question: str) -> dict:
    """Convert a natural language question to a synthetic tool_call."""
    q = question.lower()

    # Simple pattern matching for common queries
    if any(w in q for w in ["删除", "delete", "rm", "remove"]):
        target = question.split("删除")[-1].strip() if "删除" in question else question
        return {"tool_name": "exec", "action_type": "delete_file",
                "params": {"command": f"rm {target}"}, "_synthetic": True, "_question": question}
    elif any(w in q for w in ["发布", "发帖", "post", "tweet", "publish"]):
        return {"tool_name": "message", "action_type": "publish_post",
                "params": {"content": question}, "_synthetic": True, "_question": question}
    elif any(w in q for w in ["执行", "run", "exec"]):
        return {"tool_name": "exec", "action_type": "exec_command",
                "params": {"command": question}, "_synthetic": True, "_question": question}
    elif any(w in q for w in ["读", "read", "查看", "cat"]):
        return {"tool_name": "read", "action_type": "read_file",
                "params": {"path": question}, "_synthetic": True, "_question": question}
    else:
        return {"tool_name": "unknown", "action_type": "unknown",
                "params": {"raw": question}, "_synthetic": True, "_question": question}


def _get_related_kg_context(db: NousDB, tool_call: dict) -> list:
    """Find KG entities related to the tool_call."""
    context = []
    # Extract keywords from tool_call
    keywords = set()
    for v in tool_call.values():
        if isinstance(v, str):
            keywords.update(v.lower().split())
        elif isinstance(v, dict):
            for vv in v.values():
                if isinstance(vv, str):
                    keywords.update(vv.lower().split())

    # Search entities by label match
    try:
        entities = db.query(
            "?[id, etype, labels, props] := *entity{id, etype, labels, props}"
        )
        for e in entities:
            labels = e.get("labels", [])
            name = (e.get("props", {}) or {}).get("name", "")
            eid = e["id"]
            # Check if any keyword matches
            searchable = " ".join([eid, name] + (labels or [])).lower()
            if any(kw in searchable for kw in keywords if len(kw) > 2):
                context.append({
                    "id": eid, "type": e["etype"],
                    "name": name or eid.split(":")[-1],
                })
    except Exception:
        pass

    return context[:10]


@app.get("/api/timeline/{entity_id:path}")
def get_timeline(entity_id: str):
    """Get temporal history of an entity."""
    db = _get_db()
    try:
        # Get entity
        entity = db.find_entity(entity_id)
        if not entity:
            return {"error": f"Entity {entity_id} not found"}

        # Get all relations involving this entity
        relations = db.query(
            "?[from_id, to_id, rtype, props, confidence, created_at] := "
            "*relation{from_id, to_id, rtype, props, confidence, created_at}, "
            f"(from_id = $eid or to_id = $eid)",
            # Note: pycozo parameter binding
        )
    except Exception:
        relations = []

    return {
        "entity": entity,
        "relations": relations,
    }


@app.get("/api/events")
async def event_stream():
    """SSE stream — push KG changes and gate decisions in real-time."""
    async def generate():
        last_shadow_size = SHADOW_LOG.stat().st_size if SHADOW_LOG.exists() else 0
        last_kg_hash = None

        while True:
            events = []

            # Check shadow log for new entries
            if SHADOW_LOG.exists():
                current_size = SHADOW_LOG.stat().st_size
                if current_size > last_shadow_size:
                    with open(SHADOW_LOG) as f:
                        f.seek(last_shadow_size)
                        new_lines = f.readlines()
                    for line in new_lines[-5:]:  # max 5 per tick
                        try:
                            entry = json.loads(line.strip())
                            events.append({
                                "type": "gate_decision",
                                "data": {
                                    "tool": entry.get("tool_name", "?"),
                                    "verdict": entry.get("verdict", "?"),
                                    "ts": entry.get("timestamp", 0),
                                }
                            })
                        except json.JSONDecodeError:
                            pass
                    last_shadow_size = current_size

            # Check KG changes
            try:
                db = _get_db()
                count = db.count_entities() + db.count_relations()
                kg_hash = f"{count}"
                if last_kg_hash and kg_hash != last_kg_hash:
                    events.append({"type": "kg_changed", "data": {"count": count}})
                last_kg_hash = kg_hash
            except Exception:
                pass

            for evt in events:
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

            if not events:
                yield f"data: {json.dumps({'type': 'heartbeat', 'ts': time.time()})}\n\n"

            await asyncio.sleep(3)

    return StreamingResponse(generate(), media_type="text/event-stream")


# Serve static files (the dashboard frontend)
app.mount("/", StaticFiles(directory=str(Path(__file__).parent), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
