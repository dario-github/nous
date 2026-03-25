# Nous 自动化管道设计 — 从手动到自动

> 2026-03-13 审计后重新设计。核心问题：手动导入+手动规则=表演，需要自动化。

## 管道 1：自动化知识构建（KG Auto-Build）

### 触发点
| 事件 | 触发 | 提取内容 |
|------|------|---------|
| tool call 完成 | after_tool_call hook | 操作结果 → 实体/关系 |
| 对话消息 | message:sent hook | 决策/偏好/事实声明 |
| memory/*.md 变更 | daily_sync cron | 文件内容 → 结构化实体 |
| 外部数据 | 定时 cron | 新闻/政策/行情 → 事件实体 |

### 提取流程
```python
# after_tool_call hook 中
async def auto_extract(tool_call, result, session_ctx):
    prompt = f"""从以下工具调用结果中提取实体和关系：
    工具: {tool_call['name']}
    结果: {result[:500]}
    
    输出 JSON: {{entities: [...], relations: [...]}}
    每个实体: {{id, type, name, props, confidence}}
    每个关系: {{from, to, type, props, confidence}}
    只提取有价值的新信息，不要重复已知内容。"""
    
    extracted = await llm_extract(prompt)  # 用 Flash/Kimi 低成本模型
    
    for entity in extracted['entities']:
        if entity['confidence'] >= 0.8:
            nous.upsert_entity(entity)  # 自动入库
        else:
            nous.propose_entity(entity)  # 提议队列
    
    for relation in extracted['relations']:
        if relation['confidence'] >= 0.8:
            nous.upsert_relation(relation)
        else:
            nous.propose_relation(relation)
```

### 关系类型化（修复 RELATED_TO 问题）
提取时强制指定关系类型：
```
WORKS_ON, KNOWS, DEPENDS_ON, CAUSED_BY, TARGETS,
IMPLEMENTS, SUPERSEDES, PARTNER_OF, CREATED_BY
```
LLM prompt 中给出类型列表，要求选择最匹配的。

## 管道 2：自动化决策图谱（Rule Auto-Gen）

### 触发
- 每日 cron 分析 decision_log
- 用户纠正（T9）立即触发

### 流程
```python
# 每日 cron
def analyze_decision_patterns():
    # 1. 从 decision_log 找 FP/FN 模式
    fps = query_decisions(outcome='fp', since=7_days_ago)
    fns = query_decisions(outcome='fn', since=7_days_ago)
    
    # 2. LLM 分析模式，生成候选规则
    for pattern in cluster_by_tool(fps + fns):
        prompt = f"""分析以下 {len(pattern)} 次误判：
        {pattern[:5]}  # 前5个样本
        
        生成一条 Datalog 约束规则修复此问题。
        格式: YAML (id, trigger, verdict, reason)"""
        
        candidate = await llm_generate_rule(prompt)
        nous.create_proposal(candidate)
    
    # 3. 高置信度（>0.9）自动生效，低置信度等审核
```

## 管道 3：混合推理（Hybrid Reasoning）

### 决策路由
```
gate(tool_call) →
  Step 1: Datalog 匹配（<5ms）
    → 命中确定性规则 → 直接返回 verdict + proof_trace
    → 未命中 →
  Step 2: KG 上下文增强
    → 查询相关实体/关系（如：这个股票的持仓/thesis/风险信号）
    → 构建 context snippet
  Step 3: LLM 判断（~500ms）
    → prompt = 规则集 + KG context + tool_call
    → LLM 输出 verdict + reasoning
    → 记录到 decision_log（标记为 llm_delegated）
  Step 4: 反馈闭环
    → 如果 LLM 判断被用户纠正 → 触发管道 2 生成新规则
    → 下次同类情况 → Datalog 直接匹配（不需要 LLM）
```

### 关键：越用越快
```
Day 1:  大量 delegate → LLM（慢但准）
Day 30: 常见模式 → Datalog 规则覆盖（快且准）
Day 90: 只有罕见/新情况 → LLM delegate
```
这就是 NeSy 范式三的实际工程实现：符号推理覆盖确定性场景，LLM 处理不确定性，反馈闭环让系统自我进化。

## 实现优先级

| # | 任务 | 依赖 | 预估 |
|---|------|------|------|
| P0 | after_tool_call hook → LLM 实体提取 | gateway plugin | 3天 |
| P0 | 关系类型化（修复 RELATED_TO） | LLM prompt 设计 | 1天 |
| P1 | decision_log FP/FN 分析 cron | 积累数据 | 2天 |
| P1 | LLM delegate 路径（Step 2-3） | KG 上下文查询 | 3天 |
| P2 | 外部数据自动提取（新闻/政策） | 数据源接入 | 1周 |
| P2 | 反馈闭环（纠正→新规则） | P1 | 2天 |
