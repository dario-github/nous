#!/usr/bin/env python3
"""
Scallop vs CozoDB benchmark on Nous KG data.
Tests: import, basic queries, recursive path, probabilistic reasoning, rule evaluation.
"""
import time
import json
import sys
sys.path.insert(0, 'src')

from nous.db import NousDB
import scallopy

# ─── 1. Extract data from CozoDB ────────────────────────────────────

print("=" * 60)
print("Phase 1: Extract Nous KG from CozoDB")
print("=" * 60)

db = NousDB('nous.db')

entities = db.query('?[id, etype, props, confidence] := *entity{id, etype, props, confidence}')
relations = db.query('?[from_id, to_id, rtype, confidence] := *relation{from_id, to_id, rtype, confidence}')

print(f"  Entities: {len(entities)}")
print(f"  Relations: {len(relations)}")

# ─── 2. CozoDB benchmark ────────────────────────────────────────────

print("\n" + "=" * 60)
print("Phase 2: CozoDB Benchmark")
print("=" * 60)

cozo_times = {}

# Q1: Simple lookup — all attack techniques
t0 = time.perf_counter()
for _ in range(100):
    db.query('?[id] := *entity{id, etype}, etype = "attack_technique"')
cozo_times['q1_lookup_100x'] = time.perf_counter() - t0

# Q2: Join — entities connected by EXPLOITED_BY
t0 = time.perf_counter()
for _ in range(100):
    db.query('?[a, b] := *relation{from_id: a, to_id: b, rtype: "EXPLOITED_BY"}')
cozo_times['q2_join_100x'] = time.perf_counter() - t0

# Q3: Recursive path (transitive closure)
t0 = time.perf_counter()
for _ in range(10):
    db.query("""
        path[a, b] := *relation{from_id: a, to_id: b}
        path[a, c] := path[a, b], *relation{from_id: b, to_id: c}
        ?[count(a)] := path[a, _b]
    """)
cozo_times['q3_transitive_10x'] = time.perf_counter() - t0

# Q4: Multi-hop with filter
t0 = time.perf_counter()
for _ in range(10):
    db.query("""
        exploits[a, b] := *relation{from_id: a, to_id: b, rtype: "EXPLOITED_BY"}
        mitigates[a, b] := *relation{from_id: a, to_id: b, rtype: "MITIGATES"}
        ?[vuln, control] := exploits[vuln, tech], mitigates[control, tech]
    """)
cozo_times['q4_multihop_10x'] = time.perf_counter() - t0

for k, v in cozo_times.items():
    print(f"  {k}: {v*1000:.1f}ms")

# ─── 3. Scallop benchmark (deterministic) ───────────────────────────

print("\n" + "=" * 60)
print("Phase 3: Scallop Benchmark (deterministic)")
print("=" * 60)

scallop_times = {}

# Build context
t0 = time.perf_counter()
ctx = scallopy.ScallopContext()
ctx.add_relation('entity', (str, str, str))       # id, etype, name
ctx.add_relation('kg_rel', (str, str, str))           # from, to, rtype
ctx.add_relation('attack_technique', (str, str))   # id, name
ctx.add_relation('exploited_by', (str, str))       # from, to
ctx.add_relation('mitigates', (str, str))          # from, to
ctx.add_relation('path', (str, str))               # transitive closure
ctx.add_relation('vuln_control', (str, str))       # multi-hop result

# Rules
ctx.add_rule('attack_technique(ID, N) = entity(ID, "attack_technique", N)')
ctx.add_rule('exploited_by(A, B) = kg_rel(A, B, "EXPLOITED_BY")')
ctx.add_rule('mitigates(A, B) = kg_rel(A, B, "MITIGATES")')
ctx.add_rule('path(A, B) = kg_rel(A, B, _)')
ctx.add_rule('path(A, C) = kg_rel(A, B, _), path(B, C)')
ctx.add_rule('vuln_control(V, C) = exploited_by(V, T), mitigates(C, T)')

# Load data
def get_name(e):
    p = e.get('props') or {}
    if isinstance(p, str):
        import json as _j
        p = _j.loads(p)
    return p.get('name', '') or ''
ent_facts = [(e['id'], e['etype'], get_name(e)) for e in entities]
rel_facts = [(r['from_id'], r['to_id'], r['rtype']) for r in relations]
ctx.add_facts('entity', ent_facts)
ctx.add_facts('kg_rel', rel_facts)

scallop_times['load_data'] = (time.perf_counter() - t0) * 1000

# Run all at once (Scallop evaluates all rules in one pass)
t0 = time.perf_counter()
ctx.run()
scallop_times['run_all_rules'] = (time.perf_counter() - t0) * 1000

# Read results
t0 = time.perf_counter()
at = list(ctx.relation('attack_technique'))
scallop_times['q1_read_attack_technique'] = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
eb = list(ctx.relation('exploited_by'))
scallop_times['q2_read_exploited_by'] = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
paths = list(ctx.relation('path'))
scallop_times['q3_read_path'] = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
vc = list(ctx.relation('vuln_control'))
scallop_times['q4_read_vuln_control'] = (time.perf_counter() - t0) * 1000

print(f"  Results: attack_technique={len(at)}, exploited_by={len(eb)}, path={len(paths)}, vuln_control={len(vc)}")
for k, v in scallop_times.items():
    print(f"  {k}: {v:.2f}ms")

# ─── 4. Scallop probabilistic benchmark ─────────────────────────────

print("\n" + "=" * 60)
print("Phase 4: Scallop Probabilistic Reasoning")
print("=" * 60)

prob_times = {}

t0 = time.perf_counter()
pctx = scallopy.ScallopContext(provenance='topkproofs')
pctx.add_relation('entity', (str, str, str))
pctx.add_relation('kg_rel', (str, str, str))
pctx.add_relation('path', (str, str))
pctx.add_relation('reachable_from_attack', (str,))

pctx.add_rule('path(A, B) = kg_rel(A, B, _)')
pctx.add_rule('path(A, C) = kg_rel(A, B, _), path(B, C)')
pctx.add_rule('reachable_from_attack(B) = entity(A, "attack_technique", _), path(A, B)')

# Load with confidence as probability
ent_prob = [(e['confidence'] if e['confidence'] and e['confidence'] > 0 else 1.0, 
             (e['id'], e['etype'], get_name(e))) for e in entities]
rel_prob = [(r['confidence'] if r['confidence'] and r['confidence'] > 0 else 1.0,
             (r['from_id'], r['to_id'], r['rtype'])) for r in relations]
pctx.add_facts('entity', ent_prob)
pctx.add_facts('kg_rel', rel_prob)
prob_times['load_prob_data'] = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
pctx.run()
prob_times['run_prob_all'] = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
prob_paths = list(pctx.relation('path'))
prob_times['read_prob_path'] = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
reachable = list(pctx.relation('reachable_from_attack'))
prob_times['read_reachable'] = (time.perf_counter() - t0) * 1000

print(f"  Probabilistic paths: {len(prob_paths)}")
print(f"  Reachable from attack_technique: {len(reachable)}")

# Show top reachable by probability
reachable_sorted = sorted(reachable, key=lambda x: -x[0])[:10]
print(f"  Top 10 reachable (by prob):")
for item in reachable_sorted:
    prob, (eid,) = item[0], item[1:]
    print(f"    {eid}: {prob:.4f}")

for k, v in prob_times.items():
    print(f"  {k}: {v:.2f}ms")

# ─── 5. Comparison Summary ──────────────────────────────────────────

print("\n" + "=" * 60)
print("COMPARISON SUMMARY")
print("=" * 60)
print(f"""
Data: {len(entities)} entities, {len(relations)} relations

CozoDB (100x iterations for Q1/Q2, 10x for Q3/Q4):
  Q1 simple lookup:  {cozo_times['q1_lookup_100x']*10:.1f}ms/query
  Q2 relation join:  {cozo_times['q2_join_100x']*10:.1f}ms/query  
  Q3 transitive:     {cozo_times['q3_transitive_10x']*100:.1f}ms/query
  Q4 multi-hop:      {cozo_times['q4_multihop_10x']*100:.1f}ms/query

Scallop deterministic (single run, all rules at once):
  Data load:         {scallop_times['load_data']:.2f}ms
  Run all rules:     {scallop_times['run_all_rules']:.2f}ms
  Read results:      {scallop_times['q1_read_attack_technique'] + scallop_times['q2_read_exploited_by'] + scallop_times['q3_read_path'] + scallop_times['q4_read_vuln_control']:.2f}ms

Scallop probabilistic:
  Data load:         {prob_times['load_prob_data']:.2f}ms
  Run all rules:     {prob_times['run_prob_all']:.2f}ms
  Prob paths found:  {len(prob_paths)}
  Attack reachable:  {len(reachable)} entities

Key insight: CozoDB = query-on-demand (fast per-query). 
Scallop = materialize-all (one run, all derived facts ready).
Scallop adds: probabilistic propagation (CozoDB can't do this).
""")
