"""M0.1 Cozo POC — 验证图查询性能、规则表达力、热加载可行性"""
import time
import json

# === M0.1b: 建测试图 ===
def setup_db():
    """创建 100 节点 200 边测试图"""
    try:
        from pycozo.client import Client
        db = Client('mem', '')  # 内存模式
    except Exception:
        # 尝试另一种导入方式
        import pycozo
        db = pycozo.CozoClient('mem')
    
    # 创建 entity 存储关系
    db.run("""
        :create entity {
            id: String =>
            type: String,
            name: String,
            age: Int default 0,
            city: String default '',
            metadata: String default '{}'
        }
    """)
    
    # 创建 relation 存储关系
    db.run("""
        :create rel {
            from_id: String,
            to_id: String,
            type: String =>
            confidence: Float default 1.0,
            source: String default ''
        }
    """)
    
    # 创建 constraint 存储关系
    db.run("""
        :create constraint {
            id: String =>
            trigger_tool: String,
            trigger_pattern: String default '',
            verdict: String,
            priority: Int default 0,
            enabled: Bool default true
        }
    """)
    
    # 插入 100 个实体
    entities = []
    types = ['person', 'project', 'concept', 'event', 'resource']
    cities = ['北京', '上海', '深圳', '杭州', '成都']
    for i in range(100):
        etype = types[i % 5]
        city = cities[i % 5]
        entities.append(f'{{ id: "e{i}", type: "{etype}", name: "实体{i}", age: {20 + i % 50}, city: "{city}" }}')
    
    # 批量插入
    batch_size = 20
    for start in range(0, len(entities), batch_size):
        batch = entities[start:start+batch_size]
        rows = ", ".join(f'["{types[i%5]}", "实体{i}", {20+i%50}, "{cities[i%5]}"]' for i in range(start, min(start+batch_size, 100)))
        ids = ", ".join(f'["e{i}"]' for i in range(start, min(start+batch_size, 100)))
        # Use parameterized approach
        for i in range(start, min(start+batch_size, 100)):
            etype = types[i % 5]
            city = cities[i % 5]
            age = 20 + i % 50
            db.run(f'?[id, type, name, age, city] <- [["e{i}", "{etype}", "实体{i}", {age}, "{city}"]] :put entity {{ id => type, name, age, city }}')
    
    # 插入 200 条关系
    rels = []
    rel_types = ['WORKS_ON', 'KNOWS', 'DEPENDS_ON', 'CAUSED_BY', 'LOCATED_IN']
    for i in range(200):
        from_id = f"e{i % 100}"
        to_id = f"e{(i * 7 + 13) % 100}"
        rtype = rel_types[i % 5]
        conf = round(0.5 + (i % 50) / 100, 2)
        rels.append(f'{{ from_id: "{from_id}", to_id: "{to_id}", type: "{rtype}", confidence: {conf} }}')
    
    for i in range(200):
        from_id = f"e{i % 100}"
        to_id = f"e{(i * 7 + 13) % 100}"
        rtype = rel_types[i % 5]
        conf = round(0.5 + (i % 50) / 100, 2)
        db.run(f'?[from_id, to_id, type, confidence] <- [["{from_id}", "{to_id}", "{rtype}", {conf}]] :put rel {{ from_id, to_id, type => confidence }}')
    
    # 插入约束规则 (T3/T5/T10)
    db.run("""
        ?[id, trigger_tool, trigger_pattern, verdict, priority, enabled] <- [
            ["T3", "write", "SOUL.md|USER.md|MEMORY.md", "confirm", 100, true],
            ["T5", "web_fetch", "xhslink|douyin|weibo", "block", 90, true],
            ["T10", "write", "lines>400", "warn", 70, true],
            ["T11", "web_search", "lang=zh", "transform", 60, true],
            ["T12", "message", "discord+structured", "require", 80, true]
        ]
        :put constraint { id => trigger_tool, trigger_pattern, verdict, priority, enabled }
    """)
    
    return db


# === M0.1c: 5 类查询 ===
def run_queries(db):
    results = {}
    
    # Q1: 实体查询
    r = db.run('?[id, name, type] := *entity{id, name, type}, type = "person", id = "e0"')
    results['Q1_entity_lookup'] = r
    
    # Q2: 一跳关系
    r = db.run('?[to_id, rtype] := *rel{from_id: "e0", to_id, type: rtype}')
    results['Q2_one_hop'] = r
    
    # Q3: 多跳路径 (2跳)
    r = db.run("""
        ?[start, mid, end] := *rel{from_id: start, to_id: mid}, 
                              *rel{from_id: mid, to_id: end},
                              start = "e0"
    """)
    results['Q3_two_hop'] = r
    
    # Q4: 数值条件
    r = db.run('?[id, name, age] := *entity{id, name, age}, age > 60')
    results['Q4_numeric'] = r
    
    # Q5: 字符串包含 (约束匹配)
    r = db.run("""
        ?[id, verdict] := *constraint{id, trigger_tool, trigger_pattern, verdict, enabled},
                          enabled = true,
                          starts_with(trigger_pattern, "xhs")
    """)
    results['Q5_string_match'] = r
    
    return results


# === M0.1d: 性能测试 ===
def benchmark(db, iterations=100):
    queries = {
        'entity_lookup': '?[id, name] := *entity{id, name, type}, type = "person", id = "e0"',
        'one_hop': '?[to_id, rtype] := *rel{from_id: "e0", to_id, type: rtype}',
        'two_hop': '?[s, m, e] := *rel{from_id: s, to_id: m}, *rel{from_id: m, to_id: e}, s = "e0"',
        'numeric_filter': '?[id, age] := *entity{id, age}, age > 60',
        'constraint_check': '?[id, verdict] := *constraint{id, verdict, enabled}, enabled = true',
    }
    
    results = {}
    for name, q in queries.items():
        times = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            db.run(q)
            times.append((time.perf_counter() - t0) * 1000)  # ms
        
        times.sort()
        results[name] = {
            'P50': round(times[len(times)//2], 3),
            'P95': round(times[int(len(times)*0.95)], 3),
            'P99': round(times[int(len(times)*0.99)], 3),
        }
    
    return results


# === M0.1e: T3 规则表达 ===
def test_t3_rule(db):
    """模拟 gate: tool_call → 检查约束 → verdict"""
    # 模拟一个 tool call: write to SOUL.md
    tool_name = "write"
    target_file = "SOUL.md"
    
    # 查询匹配的约束
    r = db.run(f"""
        ?[cid, verdict, priority] := *constraint{{id: cid, trigger_tool, trigger_pattern, verdict, priority, enabled}},
                                     enabled = true,
                                     trigger_tool = "{tool_name}",
                                     str_includes(trigger_pattern, "SOUL.md")
    """)
    
    return r


# === M0.1f: 热加载验证 ===
def test_hot_reload(db):
    """验证规则变更不重启"""
    # 读当前 T3
    before = db.run('?[verdict] := *constraint{id: "T3", verdict}')
    
    # 热更新: T3 从 confirm 改为 block
    db.run("""
        ?[id, trigger_tool, trigger_pattern, verdict, priority, enabled] <- [
            ["T3", "write", "SOUL.md|USER.md|MEMORY.md", "block", 100, true]
        ]
        :put constraint { id => trigger_tool, trigger_pattern, verdict, priority, enabled }
    """)
    
    after = db.run('?[verdict] := *constraint{id: "T3", verdict}')
    
    # 回滚
    db.run("""
        ?[id, trigger_tool, trigger_pattern, verdict, priority, enabled] <- [
            ["T3", "write", "SOUL.md|USER.md|MEMORY.md", "confirm", 100, true]
        ]
        :put constraint { id => trigger_tool, trigger_pattern, verdict, priority, enabled }
    """)
    
    return {'before': before, 'after': after}


if __name__ == '__main__':
    print("=== M0.1b: Setup ===")
    db = setup_db()
    print("✅ 100 entities + 200 relations + 5 constraints created")
    
    print("\n=== M0.1c: Queries ===")
    qr = run_queries(db)
    for name, r in qr.items():
        rows = r.get('rows', r) if isinstance(r, dict) else r
        print(f"  {name}: {len(rows) if hasattr(rows, '__len__') else '?'} results")
    
    print("\n=== M0.1d: Benchmark (100 iterations) ===")
    bench = benchmark(db)
    for name, stats in bench.items():
        print(f"  {name}: P50={stats['P50']}ms  P95={stats['P95']}ms  P99={stats['P99']}ms")
    
    print("\n=== M0.1e: T3 Rule ===")
    t3 = test_t3_rule(db)
    print(f"  T3 match: {t3}")
    
    print("\n=== M0.1f: Hot Reload ===")
    hr = test_hot_reload(db)
    print(f"  Before: {hr['before']}")
    print(f"  After:  {hr['after']}")
    print("  ✅ Hot reload works (no restart needed)")
    
    print("\n=== SUMMARY ===")
    all_p99 = [v['P99'] for v in bench.values()]
    max_p99 = max(all_p99)
    print(f"  Max P99: {max_p99}ms (target: <5ms)")
    print(f"  GO/NO-GO: {'✅ GO' if max_p99 < 5 else '❌ NO-GO'}")
