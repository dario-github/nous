# KG 真接入 Gate 主链路 — 设计文档

> P1 priority from GPT-5.4 critique (4/10): "KG 是舞台布景不是发动机"
> 目标：gate() 内部主动查 KG，生成 kg_context，注入 semantic gate

## 问题

当前 `gateway_hook.before_tool_call()` 调用 `gate()` 时**从不传 kg_context**。
`gate.py` 接受 `kg_context: Optional[dict] = None`，但实际调用链中始终为 None。
结果：semantic_gate.py 的 prompt 里写的是 "No additional context available."

KG 有 24 entities、26 relations（每日同步），有丰富的查询 API：
- `find_entity(id)` / `find_by_type(etype)`
- `related(entity_id, rtype, direction)`
- `path(from_id, to_id, max_hops)`
- `query(datalog)` — 原始 Datalog

但这些 API 从未在 gate pipeline 中被调用。

## 设计

### 核心改动：gate() 内部自动生成 kg_context

**位置**：在 `gate.py` 的 Step 2（加载约束）和 Step 4（verdict 路由）之间。

**逻辑**：
```python
# Step 2.5: KG Context Lookup（新增）
kg_context = None
if db is not None and semantic_config is not None:
    kg_context = _build_kg_context(facts, db)
```

### _build_kg_context(facts, db) 实现

```python
def _build_kg_context(facts: dict, db: NousDB) -> Optional[dict]:
    """
    从 facts 中提取关键实体标识，查询 KG 获取相关上下文。
    
    策略：
    1. 从 facts 提取 tool_name → 查 KG 中对应的 tool entity
    2. 从 facts 提取 target/url/recipient 等 → 查 KG 中对应实体
    3. 查询相关关系（1-hop neighbors）
    4. 组装为结构化 dict 供 semantic gate 使用
    
    预算：最多查询 3 次 DB，总耗时 < 5ms。
    """
    context = {"entities": [], "relations": [], "policies": []}
    
    # 1. Tool entity lookup
    tool_name = facts.get("tool_name")
    if tool_name:
        tool_entity = db.find_entity(f"tool:{tool_name}")
        if tool_entity:
            context["entities"].append(tool_entity)
            # 查该 tool 的策略关系
            rels = db.related(f"tool:{tool_name}", rtype="governed_by", direction="out")
            context["relations"].extend(rels)
    
    # 2. Target entity lookup (URL, recipient, file path)
    target_candidates = [
        facts.get("target_url"),
        facts.get("recipient"),
        facts.get("file_path"),
    ]
    for candidate in target_candidates:
        if candidate:
            # 尝试精确匹配
            entity = db.find_entity(candidate)
            if entity:
                context["entities"].append(entity)
                rels = db.related(candidate, direction="both")
                context["relations"].extend(rels[:5])  # 限制
    
    # 3. Category/domain context
    category = facts.get("category") or facts.get("domain")
    if category:
        cat_entities = db.find_by_type(f"category:{category}")
        context["policies"].extend(cat_entities[:3])
    
    return context if any(context.values()) else None
```

### semantic_gate.py prompt 注入

当前：
```
if kg_context:
    json.dumps(kg_context, ...)
else:
    "No additional context available."
```

改为：
```
## Knowledge Graph Context
{formatted_kg_context}

Use this context to:
- Understand the relationships between tools, targets, and policies
- Identify if the target entity has special governance rules
- Check if the tool is known to be high-risk or benign for this context
```

### gateway_hook.py 改动

`before_tool_call` 传 `db` 给 `gate()` — **已经在做**（`self.db`）。
只需确保 `NousGatewayHook` 初始化时传入 `db` 实例。

当前代码：
```python
result: GateResult = gate(
    tool_call=tool_call,
    db=self.db,
    constraints_dir=self.constraints_dir,
    session_key=sk,
)
```

`gate()` 签名已经接受 `db`，但内部从未用 db 查 KG。改动在 `gate.py` 内部，gateway_hook 无需改。

## 验证计划

### 测试矩阵

| 场景 | 预期 |
|------|------|
| db=None（无 KG） | 行为不变，kg_context=None |
| db 有实体但 facts 无匹配 | kg_context=None，不影响判决 |
| db 有匹配实体 | kg_context 注入 semantic gate prompt |
| KG 查询异常 | 捕获异常，kg_context=None，不影响 gate |
| 延迟测试 | _build_kg_context < 5ms（24 entities 量级） |

### 消融实验

1. **Baseline**：当前 L_val（无 KG，0.0695）
2. **+KG context**：重跑 val set，对比 L_val 变化
3. **KG-only FPs**：检查 KG context 是否减少 FPs（特别是 Cybercrime/Copyright 类别）

## 风险

| 风险 | 缓解 |
|------|------|
| KG 实体稀疏（仅 24 个），context 几乎总是 None | 先接入管线，再丰富实体。管线 > 数据 |
| DB 查询延迟影响 gate P50 | 预算 5ms，Cozo in-process 查 24 行 < 1ms |
| KG context 注入增加 prompt token 数 | 限制 entities ≤ 5，relations ≤ 10 |
| Semantic gate 对 KG context 的理解不准确 | 格式化为人类可读文本，加使用说明 |

## 实施步骤

1. [x] `gate.py` 新增 `_build_kg_context()` + Step 4.5 调用 — ae85838
2. [x] `semantic_gate.py` kg_context prompt 模板（已有，不需改）
3. [x] 新增测试：`test_gate_kg_integration.py`（11 tests, 629 total pass）— ae85838
4. [ ] 跑 val set + challenge set 消融实验
5. [ ] 更新 loop-state.json + 提交
