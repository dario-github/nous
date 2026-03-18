#!/usr/bin/env python3
"""νοῦς Dashboard — Live API Server

FastAPI 后端，提供：
1. GET /api/kg          — 实时 KG 数据（含 effective_confidence）
2. GET /api/stats       — Shadow 统计 + 延迟分布 + 图谱统计
3. GET /api/events      — SSE 事件流（KG 变更 / gate 决策）
4. POST /api/reason     — 交互式推理（问题 → gate proof_trace）
5. GET /api/timeline    — 实体时间线
6. GET /api/graph-stats — 图谱统计面板数据
"""
import asyncio
import json
import math
import sys
import time
from pathlib import Path
from typing import Optional

# Add nous src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from nous.db import NousDB

app = FastAPI(title="νοῦς Dashboard API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

DB_PATH = Path(__file__).parent.parent / "nous.db"
SHADOW_LOG = Path(__file__).parent.parent / "logs" / "shadow_live.jsonl"
SHADOW_STATS = Path(__file__).parent.parent / "logs" / "shadow_stats.json"
DECISION_LOG = Path(__file__).parent.parent / "logs" / "decisions.jsonl"


# ── Inline effective_confidence (edge_weight module doesn't exist) ──────
def _effective_confidence(
    base_confidence: float,
    created_at: float,
    now: float,
    props: dict,
) -> float:
    """Compute time-decayed effective confidence for a relation edge.

    Uses exponential decay: eff = base * exp(-lambda * age_days)
    Half-life defaults to 30 days (configurable via props.half_life_days).
    """
    half_life = props.get("half_life_days", 30)
    if half_life <= 0:
        half_life = 30
    decay_lambda = math.log(2) / half_life
    age_days = max(0, (now - created_at)) / 86400
    decay = math.exp(-decay_lambda * age_days)
    return max(0.01, base_confidence * decay)


# ── DB helper ───────────────────────────────────────────────────────────
def _get_db():
    return NousDB(str(DB_PATH))


# ── KG snapshot ─────────────────────────────────────────────────────────
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
        eff_conf = _effective_confidence(
            base_confidence=r.get("confidence", 1.0),
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


# ── Stats ───────────────────────────────────────────────────────────────
@app.get("/api/stats")
def get_stats():
    """Shadow stats + enriched data."""
    stats = {}
    if SHADOW_STATS.exists():
        stats = json.loads(SHADOW_STATS.read_text())

    recent_decisions = []
    if DECISION_LOG.exists():
        text = DECISION_LOG.read_text().strip()
        if text:
            lines = text.split("\n")
            for line in lines[-50:]:
                try:
                    recent_decisions.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    stats["recent_decisions"] = recent_decisions
    return stats


# ── Graph Stats (new panel) ─────────────────────────────────────────────
@app.get("/api/graph-stats")
def get_graph_stats():
    """图谱统计: 类型分布, TOP 连接度, 最新变更, confidence 分布."""
    db = _get_db()
    now = time.time()

    # Type distribution
    entities = db.query(
        "?[id, etype, props, confidence, updated_at] := "
        "*entity{id, etype, props, confidence, updated_at}"
    )
    type_counts: dict[str, int] = {}
    for e in entities:
        t = e.get("etype", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Degree calculation
    relations = db.query(
        "?[from_id, to_id, rtype, confidence, created_at] := "
        "*relation{from_id, to_id, rtype, confidence, created_at}"
    )
    degree: dict[str, int] = {}
    eff_confs = []
    for r in relations:
        f, t = r["from_id"], r["to_id"]
        degree[f] = degree.get(f, 0) + 1
        degree[t] = degree.get(t, 0) + 1
        base_c = r.get("confidence", 1.0)
        cat = r.get("created_at", now)
        eff_confs.append(round(_effective_confidence(base_c, cat, now, {}), 2))

    # Top 5 by degree
    top5 = sorted(degree.items(), key=lambda x: -x[1])[:5]
    top5_list = []
    for eid, deg in top5:
        name = eid.split(":")[-1] if ":" in eid else eid
        # Try to get friendly name from entities
        for e in entities:
            if e["id"] == eid:
                name = (e.get("props", {}) or {}).get("name", name)
                break
        top5_list.append({"id": eid, "name": name, "degree": deg})

    # Recently changed (top 5 by updated_at)
    sorted_ents = sorted(entities, key=lambda e: e.get("updated_at", 0), reverse=True)
    recent = []
    for e in sorted_ents[:5]:
        name = (e.get("props", {}) or {}).get("name", e["id"].split(":")[-1])
        age_h = round((now - e.get("updated_at", now)) / 3600, 1)
        recent.append({
            "id": e["id"], "type": e.get("etype", "?"),
            "name": name, "age_hours": age_h,
        })

    # Confidence distribution buckets
    conf_buckets = {"0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
    for c in eff_confs:
        if c < 0.2:
            conf_buckets["0-0.2"] += 1
        elif c < 0.4:
            conf_buckets["0.2-0.4"] += 1
        elif c < 0.6:
            conf_buckets["0.4-0.6"] += 1
        elif c < 0.8:
            conf_buckets["0.6-0.8"] += 1
        else:
            conf_buckets["0.8-1.0"] += 1

    return {
        "type_distribution": type_counts,
        "top_connected": top5_list,
        "recent_changes": recent,
        "confidence_distribution": conf_buckets,
        "total_entities": len(entities),
        "total_relations": len(relations),
    }


# ── Reasoning ───────────────────────────────────────────────────────────
class ReasonRequest(BaseModel):
    question: str
    tool_call: Optional[dict] = None


@app.post("/api/reason")
def reason(req: ReasonRequest):
    """Interactive reasoning — simulate gate() and return proof trace."""
    from nous.gate import gate, GateResult

    db = _get_db()

    if req.tool_call:
        tc = req.tool_call
    else:
        tc = _question_to_tool_call(req.question)

    result: GateResult = gate(
        tc,
        constraints_dir=Path(__file__).parent.parent / "ontology" / "constraints",
        db=db,
    )

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


# ── NLP parsing (enhanced) ─────────────────────────────────────────────
_INTENT_PATTERNS = [
    # (keywords, tool_name, action_type)
    (["删除", "delete", "rm", "remove", "清除", "drop"], "exec", "delete_file"),
    (["发布", "发帖", "post", "tweet", "publish", "推送", "send", "发送"], "message", "publish_post"),
    (["执行", "run", "exec", "运行", "启动", "start"], "exec", "exec_command"),
    (["读", "read", "查看", "cat", "打开", "open", "看"], "read", "read_file"),
    (["写", "write", "编辑", "edit", "修改", "modify", "update", "更新"], "write", "write_file"),
    (["安装", "install", "pip", "npm", "apt"], "exec", "install_package"),
    (["下载", "download", "fetch", "curl", "wget"], "exec", "download"),
    (["上传", "upload", "deploy", "部署"], "exec", "upload"),
    (["搜索", "search", "find", "grep", "查找"], "read", "search"),
    (["连接", "connect", "ssh", "登录", "login"], "exec", "connect"),
]


def _question_to_tool_call(question: str) -> dict:
    """Convert a natural language question to a synthetic tool_call (enhanced NLP)."""
    q = question.lower()

    for keywords, tool_name, action_type in _INTENT_PATTERNS:
        if any(kw in q for kw in keywords):
            # Extract target (text after the keyword)
            target = question
            for kw in keywords:
                if kw in q:
                    parts = question.lower().split(kw, 1)
                    if len(parts) > 1 and parts[1].strip():
                        target = parts[1].strip()
                    break
            return {
                "tool_name": tool_name,
                "action_type": action_type,
                "params": {"command": target, "raw": question},
                "_synthetic": True,
                "_question": question,
            }

    return {
        "tool_name": "unknown", "action_type": "unknown",
        "params": {"raw": question}, "_synthetic": True, "_question": question,
    }


def _get_related_kg_context(db: NousDB, tool_call: dict) -> list:
    """Find KG entities related to the tool_call."""
    context = []
    keywords = set()
    for v in tool_call.values():
        if isinstance(v, str):
            keywords.update(w for w in v.lower().split() if len(w) > 2)
        elif isinstance(v, dict):
            for vv in v.values():
                if isinstance(vv, str):
                    keywords.update(w for w in vv.lower().split() if len(w) > 2)

    if not keywords:
        return []

    try:
        entities = db.query(
            "?[id, etype, labels, props] := *entity{id, etype, labels, props}"
        )
        for e in entities:
            labels = e.get("labels", [])
            name = (e.get("props", {}) or {}).get("name", "")
            eid = e["id"]
            searchable = " ".join([eid, name] + (labels or [])).lower()
            if any(kw in searchable for kw in keywords):
                context.append({
                    "id": eid, "type": e["etype"],
                    "name": name or eid.split(":")[-1],
                })
    except Exception:
        pass

    return context[:10]


# ── Timeline (fixed: use _query_with_params) ────────────────────────────
@app.get("/api/timeline/{entity_id:path}")
def get_timeline(entity_id: str):
    """Get temporal history of an entity."""
    db = _get_db()
    try:
        entity = db.find_entity(entity_id)
        if not entity:
            return {"error": f"Entity {entity_id} not found"}

        # Use db.related() which properly binds parameters
        rels = db.related(entity_id, direction="both")
        return {"entity": entity, "relations": rels}
    except Exception as exc:
        return {"entity": None, "relations": [], "error": str(exc)}


# ── SSE Event Stream ────────────────────────────────────────────────────
@app.get("/api/events")
async def event_stream():
    """SSE stream — push KG changes and gate decisions in real-time."""
    async def generate():
        last_shadow_size = SHADOW_LOG.stat().st_size if SHADOW_LOG.exists() else 0
        last_kg_hash = None

        while True:
            events = []

            if SHADOW_LOG.exists():
                current_size = SHADOW_LOG.stat().st_size
                if current_size > last_shadow_size:
                    with open(SHADOW_LOG) as f:
                        f.seek(last_shadow_size)
                        new_lines = f.readlines()
                    for line in new_lines[-5:]:
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


# ── Static files ────────────────────────────────────────────────────────
app.mount("/", StaticFiles(directory=str(Path(__file__).parent), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
