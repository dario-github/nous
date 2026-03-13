#!/bin/bash
cd ~/clawd/nous
# 导出最新 KG 数据
python3 -c "
import json, sys
sys.path.insert(0, 'src')
from nous.db import NousDB
db = NousDB('nous.db')
entities = db.query('?[id, etype, labels, props, confidence, source] := *entity{id, etype, labels, props, confidence, source}')
relations = db.query('?[from_id, to_id, rtype, props, confidence, source] := *relation{from_id, to_id, rtype, props, confidence, source}')
data = {
    'entities': [{'id':e['id'],'type':e['etype'],'labels':e.get('labels',[]),'props':e.get('props',{}),'confidence':e.get('confidence',1.0)} for e in entities],
    'relations': [{'from':r['from_id'],'to':r['to_id'],'type':r['rtype'],'props':r.get('props',{}),'confidence':r.get('confidence',1.0)} for r in relations],
}
with open('dashboard/data/kg.json', 'w') as f:
    json.dump(data, f, ensure_ascii=False)
print(f'KG: {len(data[\"entities\"])} entities, {len(data[\"relations\"])} relations')
" 2>&1
# 复制 shadow stats
cp logs/shadow_stats.json dashboard/data/stats.json 2>/dev/null
echo "Dashboard refreshed"
