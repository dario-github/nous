"""kg_enrich -- 从 shadow_live.jsonl 挖掘实体/关系注入 KG。"""
import json, math, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from nous.db import NousDB  # noqa: E402
from nous.schema import Entity, Relation  # noqa: E402

SHADOW = ROOT / "logs" / "shadow_live.jsonl"
CAT_MAP: dict[str, str] = {
    "exec": "system", "process": "system",
    "read": "fs", "write": "fs", "edit": "fs",
    "web_search": "net", "web_fetch": "net", "browser": "net",
    "memory_search": "mem", "memory_get": "mem",
    "message": "comm", "sessions_send": "comm",
    "sessions_spawn": "session", "sessions_list": "session",
    "sessions_yield": "session", "sessions_history": "session",
    "session_status": "session", "agents_list": "agent",
    "subagents": "agent", "nodes": "agent", "gateway": "agent",
    "image": "media", "pdf": "media", "cron": "sched",
    "lcm_describe": "lcm", "lcm_expand": "lcm",
    "lcm_expand_query": "lcm", "lcm_grep": "lcm",
}
LAT_TIERS = [(5000, "fast"), (15000, "normal"), (50000, "slow"), (1 << 60, "very_slow")]
SRC = "shadow_live"


def _c(n: int, t: int) -> float:
    return round(min(1.0, 0.3 + 0.7 * math.log1p(n / max(t, 1) * 100) / math.log1p(100)), 3)


def _e(eid: str, et: str, lb: list[str], cf: float, p: dict) -> dict:
    return dict(id=eid, etype=et, labels=lb, confidence=cf, source=SRC, properties=p)


def _r(f: str, t: str, rt: str, cf: float, p: dict | None = None) -> dict:
    return dict(from_id=f, to_id=t, rtype=rt, confidence=cf, source=SRC, properties=p or {})


def aggregate(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    tc: Counter[str] = Counter()
    vbt: dict[str, Counter[str]] = defaultdict(Counter)
    rc: Counter[str] = Counter()
    tr: dict[str, Counter[str]] = defaultdict(Counter)
    ht: dict[str, Counter[str]] = defaultdict(Counter)
    dt: dict[str, Counter[str]] = defaultdict(Counter)
    co: Counter[tuple[str, str]] = Counter()
    lt: dict[str, Counter[str]] = defaultdict(Counter)
    prev, N = "", len(entries)
    for e in entries:
        tool, v = e.get("tool", "unknown"), e.get("nous_verdict", "allow")
        tc[tool] += 1; vbt[tool][v] += 1
        rid = e.get("nous_rule_id", "")
        if rid: rc[rid] += 1; tr[tool][rid] += 1
        ts = e.get("ts", "")
        if len(ts) >= 13: ht[ts[11:13]][tool] += 1; dt[ts[:10]][tool] += 1
        if prev and prev != tool: co[tuple(sorted([prev, tool]))] += 1
        prev = tool
        lt[tool][next(n for c, n in LAT_TIERS if e.get("latency_us", 0) < c)] += 1
    ents: list[dict] = []; rels: list[dict] = []

    for tool, cnt in tc.items():
        cat = CAT_MAP.get(tool, "other")
        vs = {f"v_{k}": v for k, v in vbt[tool].items()}
        ls = {f"lat_{k}": v for k, v in lt[tool].items()}
        ents.append(_e(f"tool:{tool}", "tool", [tool], _c(cnt, N),
                       {"name": tool, "call_count": cnt, "category": cat, **vs, **ls}))
        rels.append(_r(f"tool:{tool}", f"category:{cat}", "belongs_to", _c(cnt, N)))
        for v, vc in vbt[tool].items():
            pid = f"pattern:{v}:{tool}"
            ents.append(_e(pid, "concept", [v, tool], _c(vc, cnt),
                           {"verdict": v, "tool": tool, "count": vc}))
            rels.append(_r(f"tool:{tool}", pid, "produces", _c(vc, cnt)))
        dtier = lt[tool].most_common(1)[0][0]
        lid = f"latency:{dtier}:{tool}"
        ents.append(_e(lid, "concept", [dtier, tool, "latency"], _c(cnt, N),
                       {"tier": dtier, "tool": tool}))
        rels.append(_r(f"tool:{tool}", lid, "has_latency", _c(cnt, N)))

    for cat in {CAT_MAP.get(t, "other") for t in tc}:
        ents.append(_e(f"category:{cat}", "category", [cat], 0.95, {"name": cat}))
    for rid, cnt in rc.items():
        ents.append(_e(f"rule:{rid}", "constraint", [rid], _c(cnt, N),
                       {"rule_id": rid, "trigger_count": cnt}))
    for tool, rules in tr.items():
        for rid, cnt in rules.items():
            rels.append(_r(f"tool:{tool}", f"rule:{rid}", "triggers", _c(cnt, N), {"count": cnt}))
    for hour, tools in ht.items():
        ht_n = sum(tools.values())
        ents.append(_e(f"temporal:hour:{hour}", "temporal", [f"h-{hour}"], _c(ht_n, N),
                       {"hour": hour, "count": ht_n,
                        "top": {t: c for t, c in tools.most_common(3)}}))
        for t, c in tools.most_common(3):
            rels.append(_r(f"tool:{t}", f"temporal:hour:{hour}", "active_during", _c(c, ht_n)))
    for day, tools in dt.items():
        dn = sum(tools.values())
        ents.append(_e(f"temporal:day:{day}", "temporal", [f"d-{day}"], _c(dn, N),
                       {"date": day, "count": dn, "tools": len(tools)}))
    for (t1, t2), cnt in co.most_common(40):
        pid = f"cooccur:{t1}:{t2}"
        ents.append(_e(pid, "concept", [t1, t2, "cooccurrence"], _c(cnt, N),
                       {"tool_a": t1, "tool_b": t2, "count": cnt}))
        rels.append(_r(f"tool:{t1}", pid, "co_occurs", _c(cnt, N)))
        rels.append(_r(f"tool:{t2}", pid, "co_occurs", _c(cnt, N)))
    return ents, rels


def main() -> None:
    if not SHADOW.exists():
        print(f"Shadow log not found: {SHADOW}"); sys.exit(1)
    entries = []
    with open(SHADOW) as f:
        for line in f:
            if line.strip():
                try: entries.append(json.loads(line))
                except json.JSONDecodeError: pass
    raw_e, raw_r = aggregate(entries)
    entities, relations = [Entity(**e) for e in raw_e], [Relation(**r) for r in raw_r]
    db = NousDB(str(ROOT / "nous.db"))
    db.upsert_entities(entities); db.upsert_relations(relations)
    print(f"Enriched KG: {len(entities)} entities, {len(relations)} relations "
          f"(from {len(entries)} shadow entries)")


if __name__ == "__main__":
    main()
