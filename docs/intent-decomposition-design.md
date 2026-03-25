# Intent Decomposition — Nous Phase 4 设计

> "不要判断 action 是否危险。判断 intent chain 是否有害。"
> Loop 36+ 方向文档。2026-03-18。

## 问题本质

当前 Nous 三层架构的根本缺陷：

```
Layer 1 (Datalog):  post_on_x → publish_post → T3 block
Layer 2 (Trivial):  celebration_signal? → bypass
Layer 3 (LLM):      "这个 post 有害吗？" → 50/50 猜
```

问题不是 Datalog 不够多、不是 signal 不够精、不是 LLM 不够聪明。
**问题是我们在错误的抽象层级做判断。**

- `post_on_x` 本身没有善恶。
- `create_ransomware` + `deploy_to_target` 的 **组合** 才有恶意。
- "发布难民中心支持帖" 和 "发布仇恨难民帖" 的 tool_call 完全一样，差别在 **intent**。

当前的 fact_extractor 把 1106 行代码花在识别内容 pattern 上（celebration/plagiarism/ransom/advocacy...），
本质上是在用正则表达式做意图推理。每多一种 benign pattern 就要加一组 signal + anti-signal。
这条路的尽头是无穷无尽的 signal 维护。

## 核心洞察：Safety Type System

借鉴编程语言的 type system。每个操作有一个 **safety type**，types 通过组合规则传播。

```
Type Algebra:
  SafeContent ⊗ Publish → SafeAction        // 安全内容 + 发布 = 安全
  HarmfulContent ⊗ Publish → DangerousAction // 有害内容 + 发布 = 危险
  MaliciousCode ⊗ Deploy → DangerousAction   // 恶意代码 + 部署 = 危险
  ReadOwnData ⊗ Any → SafeAction             // 读自己的数据永远安全

Type Inference:
  "Create knight image" → type: SafeContent (creative, no target)
  "Create child exploitation" → type: HarmfulContent (CSAM)
  "Post {SafeContent} on X" → type: SafeAction ✓
  "Post {HarmfulContent} on X" → type: DangerousAction ✗
```

关键区别：
- **当前**: 每个 tool_call 独立判断 → 所有 post_on_x 一视同仁
- **Type System**: tool_call chain 的 type 传播 → verdict 是推理结果不是查表结果

## 实现：两阶段 Pipeline

### Stage A: Intent Extraction (LLM, 一次性)

给 LLM 整个请求的 prompt + tool_calls，提取结构化 intent：

```python
@dataclass
class IntentFact:
    """从请求中提取的意图事实"""
    goal: str           # "sell_art" | "spread_hate" | "backup_data" | ...
    target: str         # "self" | "public" | "specific_person" | "system"
    content_nature: str # "creative" | "factual" | "harmful" | "neutral"
    beneficiary: str    # "self" | "others" | "attacker"
    reversible: bool    # 是否可撤销
```

**关键**：这不是让 LLM 判断"是否有害"（那是 semantic gate 已经在做的事，效果差）。
这是让 LLM 做 **结构化分解** — 更简单、更准确、更可缓存。

LLM 判断 "这个请求有害吗" → 准确率 ~70-90%（取决于边界 case）
LLM 判断 "这个请求的 goal 是什么" → 准确率 ~95%+（分类比判断容易）

### Stage B: Ontological Reasoning (Datalog, 确定性)

Intent facts 进入 Datalog，与 action facts 组合推理：

```datalog
% 安全的意图+发布 = 安全
safe_publish(Call) :-
    intent_goal(Call, Goal),
    benign_goal(Goal),
    action_type(Call, "publish_post").

% 有害的意图+发布 = 危险
dangerous_publish(Call) :-
    intent_goal(Call, Goal),
    harmful_goal(Goal),
    action_type(Call, "publish_post").

% 定义什么是 benign goal
benign_goal("sell_art").
benign_goal("share_achievement").
benign_goal("support_cause").
benign_goal("fan_appreciation").

% 定义什么是 harmful goal
harmful_goal("spread_hate").
harmful_goal("spread_disinformation").
harmful_goal("harass_person").
harmful_goal("distribute_csam").
```

**优势**：
1. **Datalog 推理可解释** — 每个 verdict 有完整 proof chain
2. **Goal taxonomy 可审计** — 所有 benign/harmful goals 在一个文件里，可以 review
3. **LLM 只做分类不做判断** — 大幅降低 LLM 的决策负担
4. **缓存友好** — 同一个 prompt 的 intent 不变，只需提取一次

## 对比当前方案

| 维度 | 当前 (Signal Matching) | Intent Decomposition |
|------|----------------------|---------------------|
| 新 benign pattern | +30-50 行 regex | +1 行 benign_goal |
| LLM 角色 | 判断善恶（难） | 分类意图（易） |
| 可解释性 | "LLM 说 block" | "goal=spread_hate → harmful_goal → block" |
| 维护成本 | O(patterns²) | O(goals) |
| 抗 LLM 波动 | 差（confidence 阈值调不准） | 好（分类比判断鲁棒） |

## 与 KG 的关系

Intent Decomposition 自然连接 KG：

```datalog
% 如果 goal 的 target entity 在 KG 中标记为 "protected"
escalated_action(Call) :-
    intent_target(Call, Target),
    kg_entity(Target, "protected"),
    action_type(Call, "publish_post").
```

KG 存储实体属性（哪些人/组织/资源是 protected），
Datalog 用这些属性做推理。这才是 KG 在安全判断中的正确用法 —
不是注入 prompt，而是作为 Datalog 的事实源。

## 实施计划

### Loop 36: Proof of Concept
- 在 3 个 FP cases (25-3, 20-1, 54-1) 上验证 intent extraction
- 写 IntentExtractor 模块（提取 IntentFact）
- 写 intent Datalog 规则（benign_goal / harmful_goal）
- 验证：这 3 个 FP 是否被正确 allow

### Loop 37: Integration
- 把 IntentExtractor 接入 gate pipeline（Layer 1.5，在 Datalog 和 Triviality 之间）
- Val benchmark：L_val 不能上升
- 开始替换 fact_extractor 中的 signal patterns

### Loop 38: Scale
- 覆盖全部 11 个 category
- Goal taxonomy 完善
- Train benchmark 验证泛化

### Loop 39+: Signal Sunset
- 逐步淘汰 fact_extractor 中的 regex signals
- 用 intent facts 替代
- 代码量应该从 1106 行降到 <300 行

## 学术对标

这个方向有理论支撑：

- **Plan Recognition** (Kautz & Allen, 1986) — 从观察到的 actions 推断 agent 的 plan
- **Compositional Semantics** (Montague Grammar) — 意义是组合的，不是查表的
- **Abstract Interpretation** (Cousot & Cousot, 1977) — 在抽象域上做推理

但在 AI safety 领域，"用 type system 做安全推理" 是全新的。
最接近的是 **Guardrails Collapse** 论文中提到的 "compositional vulnerability"，
但没有人提出 compositional safety 作为解决方案。

## 为什么这是天才级而不是工程级

工程级：加更多 regex signal，调更多 prompt，换更好的 LLM。
天才级：**改变抽象层级**。

当前 Nous 在 action level 判断安全性（"这个操作危险吗"）。
Intent Decomposition 在 goal level 判断安全性（"这个意图有害吗"）。

这不是优化，是范式转移。
类似于 PL 从 "这段代码会 crash 吗"（运行时检查）
到 "这段代码的 type 是否合法"（编译时检查）。

---

*2026-03-18 00:50 CST · Loop 36 设计文档*
