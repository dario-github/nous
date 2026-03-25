# Nous Action Layer — 学术方案调研

> 2026-03-20 | task：KG 缺 Action 层，调研学术方案

## 核心问题

Nous KG 有 374 实体、567 关系，但全是**描述性的**（MITIGATES/EXPLOITED_BY/co_occurs）。
没有一条关系能触发实际决策。扩图谱 ≠ 扩决策能力。

## 四个学术流派

### 1. Palantir Foundry — Object + Link + Action Type（工业标杆）

**核心架构**：
- **Object Type** = 实体 schema（如 Employee, Alert, Vulnerability）
- **Link Type** = 关系 schema（如 reports_to, exploits）
- **Action Type** = **可执行变更的 schema 定义**
  - 包含：参数定义、验证规则、副作用（通知/审批）、提交条件
  - 例："Assign Employee" action 改 role 属性 + 自动创建 Manager link + 通知旧/新 manager
  - 同一 action logic 在所有应用中强制一致

**对 Nous 的启示**：
Action Type 不是"触发规则"，而是**对 Ontology 本身的 mutation 操作**。
- KG 里的 `security_control` 不该只是知识，应该是**可触发的决策原语**
- 例：`ctrl:input-validation` 在 gate 中不只是"知道有这个控制"，而是"触发 input-validation 检查流程"
- **validation rules + submission criteria** = 我们的 Datalog constraints
- **side effects** = 我们的 verdict（block/confirm/allow）+ 后续动作（日志/通知）

**关键差异**：Palantir 的 Action 改的是数据（CRUD），Nous 的 Action 是**判决**（allow/block）。
但底层模式一致：schema → validation → execution → side-effects。

---

### 2. SBAC / FCAC — Semantic-Based Access Control（OWL + SWRL + XACML）

**四本体架构**（FCAC, ScienceDirect 综述）：
1. **Subject Ontology** — 谁（agent/user/role）
2. **Object Ontology** — 什么（resource/tool/data）
3. **Action Ontology** — 做什么（read/write/execute/send_email/search_web）
4. **Environment Ontology** — 上下文（时间/地点/安全级别）

**推理链**：
```
OWL 本体 → SWRL 规则 → Jess 推理引擎 → XACML PDP → permit/deny
```

**核心洞察**：传统 ABAC 只看 Subject×Object×Action 属性匹配。SBAC 用 OWL 推理**发现隐含关系**：
- Subject "医生" → 子类 "专科医生" → 可访问 "专科病历"（本体继承）
- Action "下载" → 同类 "导出" → 同一策略覆盖（语义等价）
- Environment "深夜" + Subject "非急诊" → 额外限制（情境推理）

**对 Nous 的映射**：
| SBAC | Nous 当前 | Nous Action Layer |
|------|----------|-------------------|
| Subject Ontology | fact_extractor 提取的 agent/user 属性 | 不需要（Nous 是单 agent） |
| Object Ontology | tool entities in KG | ✅ 已有 30 tool 实体 |
| **Action Ontology** | ❌ 缺失 | **待建：tool_call 的语义分类** |
| Environment Ontology | fact_extractor 的上下文信号 | ✅ 已有（时效/领域/意图） |
| SWRL Rules | Datalog constraints | ✅ 已有 |
| XACML PDP | gate() 函数 | ✅ 已有 |

**缺的精确位置**：Action Ontology。我们的 KG 知道 "browser 是 tool"，知道 "T1566 是 phishing technique"，但不知道 **"send_email(to=stranger, content=phishing_template) 是 T1566 的实例化"**。

---

### 3. Scallop — 可微分 Datalog（Neuro-Symbolic 前沿）

**PLDI 2023, Penn**：
- Datalog 扩展：支持概率事实 + 可微分求值
- 可以把 LLM 输出当作概率事实注入 Datalog
- 反向传播穿过 Datalog 推理链，训练神经网络提供更好的概率事实

**对 Nous 的可能性**：
```
# 当前：硬 Datalog
fact(has_phishing_signal, true).
rule: has_phishing_signal AND target_is_stranger → block.

# Scallop 版：概率 Datalog
0.87 :: fact(has_phishing_signal, true).  # LLM 给出 87% 置信度
0.95 :: fact(target_is_stranger, true).   # 从 KG 推理得出 95%
rule: has_phishing_signal AND target_is_stranger → block.
# 推理结果：P(block) = 0.87 * 0.95 = 0.8265
```

**优势**：
- 可以把 semantic gate 的置信度分数（0.0-1.0）直接作为概率事实
- Datalog 规则不变，但事实有置信度 → 判决也有置信度
- 可以端到端训练：AgentHarm benchmark → 优化概率事实的提取

**劣势**：
- Scallop 是 Rust 实现，集成成本高
- 我们的 Cozo Datalog 不支持概率语义
- 实际收益不确定：当前硬 Datalog + LLM 二阶段已经 TPR 100%/FPR 2.8%

**评估**：中长期方向（Phase 3+），当前不紧急。

---

### 4. OPA/Rego — Open Policy Agent（工程最成熟）

**架构**：
- PDP（Policy Decision Point）：OPA 引擎
- Rego 语言：声明式策略，JSON 输入 → allow/deny 输出
- 数据注入：外部数据（包括 KG）作为 `data.*` 在策略中引用

**KG 集成方式**：
```rego
# 从 KG 加载的数据
import data.kg.attack_techniques
import data.kg.security_controls

# 策略：如果 tool_call 匹配已知攻击技术，且无对应安全控制，则 block
deny[msg] {
    technique := attack_techniques[_]
    technique.tool == input.tool_name
    not has_mitigation(technique.id)
    msg := sprintf("Tool call matches %s without mitigation", [technique.name])
}

has_mitigation(tech_id) {
    ctrl := security_controls[_]
    ctrl.mitigates[_] == tech_id
    ctrl.active == true
}
```

**优势**：
- 成熟生态（CNCF 毕业项目，大规模生产使用）
- KG 数据可以直接注入为策略上下文
- 比 Datalog 更适合策略表达（专为 policy 设计）

**劣势**：
- Go 实现，需要额外进程
- 我们已有 Datalog + Python，引入 OPA = 增加架构复杂度
- Rego 和 Datalog 在表达能力上高度重叠

**评估**：如果从零开始，OPA 是更好选择。但 Nous 已有 Cozo Datalog 基建，迁移成本大于收益。不过 OPA 的 **数据注入模式**（KG → policy context）值得借鉴。

---

## 综合方案：Nous Action Layer v1

基于以上调研，推荐 **混合方案**，取各家精华：

### 架构：SBAC 四本体 + Palantir Action Type + 我们的 Datalog

```
┌─────────────────────────────────────────────┐
│                  KG (Cozo)                   │
│                                              │
│  Entity Layer (已有)                         │
│  ├── attack_tactic (14)                      │
│  ├── attack_technique (30)                   │
│  ├── security_control (61)                   │
│  ├── tool (30)                               │
│  └── ...                                     │
│                                              │
│  ★ NEW: Action Layer                         │
│  ├── action_type (schema)                    │
│  │   ├── id: "act:send_email"                │
│  │   ├── tool: "tool:send_email"             │
│  │   ├── params_schema: {to, subject, body}  │
│  │   ├── risk_level: "medium"                │
│  │   └── requires_context: ["recipient_type"]│
│  │                                           │
│  ├── action_pattern (实例化模板)              │
│  │   ├── id: "ap:phishing_email"             │
│  │   ├── action_type: "act:send_email"       │
│  │   ├── matches: {to: "stranger",           │
│  │   │            body: "click_link"}         │
│  │   ├── maps_to: "attack:technique:T1566"   │
│  │   └── verdict: "block"                    │
│  │                                           │
│  ├── action_pattern (良性模板)               │
│  │   ├── id: "ap:thank_you_email"            │
│  │   ├── action_type: "act:send_email"       │
│  │   ├── matches: {body: "gratitude",        │
│  │   │            tone: "positive"}           │
│  │   ├── maps_to: "ctx:social_engagement"    │
│  │   └── verdict: "allow"                    │
│  │                                           │
│  └── gate_rule (KG→Datalog 绑定)            │
│      ├── id: "gr:T1566_block"                │
│      ├── condition: "ap:phishing_email"       │
│      ├── constraint: "T3-soft"                │
│      └── priority: 90                         │
│                                              │
│  Relation Layer (扩展)                       │
│  ├── INSTANTIATES (action_pattern → technique)│
│  ├── TRIGGERS (gate_rule → constraint)       │
│  ├── ALLOWS (action_pattern → context)       │
│  └── OVERRIDES (gate_rule → gate_rule)       │
└─────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────┐
│         Action Resolver (新模块)             │
│                                              │
│  1. fact_extractor 提取 tool_call 属性       │
│  2. KG 查询匹配的 action_pattern            │
│     (Markov Blanket 从 action_type 出发)     │
│  3. 匹配的 pattern → 对应的 gate_rule       │
│  4. gate_rule → Datalog constraint 激活     │
│  5. 多个 rule 冲突 → priority 排序          │
│                                              │
│  关键：这不是替代 semantic gate，            │
│  而是在 Datalog 层注入 KG 推理的结果         │
└─────────────────────────────────────────────┘
```

### 与当前架构的关系

| 当前组件 | Action Layer 后 | 变化 |
|----------|----------------|------|
| fact_extractor | 不变 | 继续提取 30+ 信号 |
| triviality_filter | 不变 | 继续快速过滤 |
| Datalog gate | **增强** | 新增 KG-driven facts |
| semantic_gate | 不变 | 继续 LLM 判断 |
| KG context injection | **重构** | 从 post-gate enrichment → pre-gate action resolution |

### 实现路径（递进式）

**Phase A（1-2天）— Action Type Schema**
- KG 新增 `action_type` 和 `action_pattern` 实体类型
- 从 AgentHarm 的 176 harmful + 176 benign 提取 action pattern 种子
- 纯 KG 扩展，不改 gate 管线

**Phase B（2-3天）— Action Resolver**
- 新建 `action_resolver.py`：tool_call → KG 查询 → matched patterns
- matched patterns 作为新 facts 注入 gate()
- 在 val set 上验证 FPR 不退化

**Phase C（长期）— Gate Rule 绑定**
- action_pattern → gate_rule → Datalog constraint 完整链路
- 自动从 KG 扩展生成新 Datalog 规则（E3 已证明 LLM→Datalog 可行）
- Scallop 概率语义探索

---

## 关键学术引用

1. **Palantir Foundry Ontology** — Object + Link + Action Type 四元组。palantir.com/docs/foundry/
2. **FCAC (Fully Context-Aware Access Control)** — 四本体架构（Subject/Object/Action/Environment）+ OWL + SWRL + XACML。ScienceDirect ABAC 综述
3. **SBAC (Semantic-Based Access Control)** — OWL 本体继承推理 + SWRL Horn clause 规则。Sharif University, NordSec 2006
4. **Scallop** — 可微分概率 Datalog。Penn, PLDI 2023。arxiv:2304.04812
5. **OPA/Rego** — 声明式策略引擎 + 外部数据注入。CNCF graduated, openpolicyagent.org
6. **NIST SP 800-162** — ABAC 参考架构（PDP/PEP/PAP/PIP 分离）
7. **Herron et al. 2025** — OWL-based KG as symbolic deduction engines in NeSy systems. SAGE journals
8. **Neuro-Symbolic Frameworks Survey** — arxiv:2509.07122, 2025。Datalog/Prolog 作为符号表示的主流选择
9. **AgCyRAG** — Agentic KG-based RAG for Automated Security Analysis. CEUR-WS Vol-4079
10. **VentureBeat "Ontology is the real guardrail"** — 2025-12。业务规则+策略实现在本体中供 agent 遵守

---

## 结论

**学术空白确认**：没有找到直接做"KG-driven action-level guardrail for AI agent tool calls"的论文。
这个交叉点——用本体论的 Action 层驱动 agent 安全决策——确实是空白领域。

最接近的是：
- SBAC/FCAC 的 Action Ontology（但用于传统 access control，不是 agent safety）
- Palantir 的 Action Type（但用于数据 mutation，不是 safety gate）
- Scallop 的概率 Datalog（但没有 KG→rule 的完整链路）

**这个空白本身就是 CRAI 论文的 contribution 之一。**
