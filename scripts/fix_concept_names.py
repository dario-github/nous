#!/usr/bin/env python3
"""Fix concept entity names to be distinguishable from tool entities.

Problem: pattern:allow:write, latency:normal:write, cooccur:exec:write
all share name_zh="文件写入" with tool:write — looks like duplicates on graph.

Fix: give each concept a descriptive name based on its ID structure.
"""
import json
import sys
sys.path.insert(0, "src")

from nous.db import NousDB, Entity

db = NousDB()
rows = db.db.run('?[id, etype, labels, props, metadata, confidence, source, created_at, updated_at] := *entity{id, etype, labels, props, metadata, confidence, source, created_at, updated_at}, etype = "concept"')

TOOL_ZH = {}
tool_rows = db.db.run('?[id, props] := *entity{id, etype, props}, etype = "tool"')
for _, r in tool_rows.iterrows():
    p = json.loads(r['props']) if isinstance(r['props'], str) else (r['props'] or {})
    tool_name = r['id'].split(':')[-1]
    TOOL_ZH[tool_name] = p.get('name_zh', tool_name)

fixes = []
entities = []

for _, r in rows.iterrows():
    props = json.loads(r['props']) if isinstance(r['props'], str) else (r['props'] or {})
    eid = r['id']
    parts = eid.split(':')
    
    new_name = None
    if len(parts) >= 3:
        prefix = parts[0]
        if prefix == 'cooccur':
            t1, t2 = parts[1], parts[2]
            n1 = TOOL_ZH.get(t1, t1)
            n2 = TOOL_ZH.get(t2, t2)
            new_name = f'{n1} ↔ {n2}'
        elif prefix == 'latency':
            tier, tool = parts[1], parts[2]
            tn = TOOL_ZH.get(tool, tool)
            tier_zh = {'fast':'快','normal':'正常','slow':'慢','very_slow':'极慢'}.get(tier, tier)
            new_name = f'{tn} [{tier_zh}]'
        elif prefix == 'pattern':
            verdict, tool = parts[1], parts[2]
            tn = TOOL_ZH.get(tool, tool)
            vmap = {'allow':'✓','block':'✗','confirm':'?'}
            new_name = f'{tn} {vmap.get(verdict, verdict)}'
    
    if new_name and props.get('name_zh') != new_name:
        old = props.get('name_zh', '')
        props['name_zh'] = new_name
        fixes.append((eid, old, new_name))
        
        entities.append(Entity(
            id=eid,
            etype='concept',
            labels=json.loads(r['labels']) if isinstance(r['labels'], str) else (r['labels'] or []),
            properties=props,
            metadata=json.loads(r['metadata']) if isinstance(r['metadata'], str) else (r['metadata'] or {}),
            confidence=float(r['confidence']),
            source=r['source'] or 'kg_enrich',
            created_at=float(r['created_at']) if r['created_at'] else None,
            updated_at=float(r['updated_at']) if r['updated_at'] else None,
        ))

if entities:
    db.upsert_entities(entities)

print(f"Fixed {len(fixes)} concept display names")
for eid, old, new in fixes[:15]:
    print(f"  {old:16s} → {new}")
if len(fixes) > 15:
    print(f"  ... and {len(fixes)-15} more")

# Also fix category duplicate: Other vs other
cat_rows = db.db.run('?[id, props] := *entity{id, etype, props}, etype = "category"')
for _, r in cat_rows.iterrows():
    print(f"  category: {r['id']}")
