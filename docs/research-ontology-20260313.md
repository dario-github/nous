# Nous 本体论 + LLM 驱动决策 — 学术 SOTA 研究报告

> 生成时间: 2026-03-13 | 研究方向: 本体论/KG + LLM + Agent 行为治理
> 覆盖五大方向: Ontology-driven Decision Making / NeSy Governance / KG+LLM Hybrid / LLM-Modulo / Ontology Policy Enforcement

---

## 一、精读论文摘要（10 篇）

---

### P1. ATA: Autonomous Trustworthy Agents
**arXiv:** 2510.16381 | **时间:** Oct 2025 | **方向:** NeSy Agent 架构

#### 核心创新
LLM 不直接做决策，只在离线阶段将问题规范翻译成**形式化符号知识库**（formal KB）。运行时，新输入被编码为同一形式语言，由**符号决策引擎**（symbolic decision engine）纯推理产出结果。

**两阶段解耦：**
- **Offline**: LLM → 形式化 KB（可由人类专家审验、修正）
- **Online**: 符号引擎用 KB 推理，LLM 不参与

#### 架构
```
用户输入 → LLM（Offline，仅一次）→ Formal KB
运行时输入 → Encoder → Symbolic Engine ← Formal KB → 输出
```
人类专家可在中间审核/修正 KB，之后所有在线决策**完全确定性**（perfect determinism）。

#### 关键结果
- 与 SOTA 端到端推理模型竞争（全自动设置）
- 人工验证 KB 后：大幅超越更大模型
- **对 prompt injection 天然免疫**（决策不经 LLM）

#### 与 Nous 对比
| 维度 | ATA | Nous |
|------|-----|------|
| LLM 角色 | 离线 KB 翻译器 | 主 Agent + 实时执行者 |
| 本体论 | 隐含（formal KB 结构） | 显式 OWL/Datalog 本体 |
| 拦截时机 | 无（决策前置于符号层） | **运行时动作拦截** |
| 会话状态 | 无（无状态符号系统） | **会话本体实例更新** |
| 策略优先级 | 无 | **T 规则优先级体系** |

**ATA 没做的，Nous 做了：** 会话上下文（谁说了什么、授权了什么）作为本体实例参与推理

---

### P2. GaaS: Governance-as-a-Service
**arXiv:** 2508.18765 | **时间:** Aug 2025 | **方向:** 运行时策略执行

#### 核心创新
把 AI 治理从"嵌入 agent 架构"变成**独立的运行时基础设施**（runtime infrastructure）。GaaS 截获 agent 输出，按声明式规则评估，调整 Trust Factor 分数。

**三种干预模式：**
1. **强制（Coercive）**: 直接修改/拦截输出
2. **规范（Normative）**: 向 agent 反馈违规
3. **自适应（Adaptive）**: 动态调整信任分

#### 架构
```
Agent 输出 → GaaS 拦截层 → Policy Evaluator
                           → Trust Factor 更新
                           → 干预决策 → 放行/修改/阻断
```

#### 与 Nous 对比
| 维度 | GaaS | Nous |
|------|------|------|
| 规则语言 | 声明式规则（无 OWL/Datalog） | **Datalog + 本体语义** |
| 知识层 | 无（纯规则检查） | **本体类层级 + 属性推理** |
| 语义推理 | 无 | **entailment（ontological reasoning）** |
| 状态跟踪 | Trust Factor（数值） | **本体实例（关系性状态）** |

---

### P3. LLM-Modulo Framework
**arXiv:** 2402.01817 | **时间:** Feb 2024 | **发表:** ICML 2024 | **作者:** Kambhampati et al., ASU

#### 核心创新
Position Paper：LLM 不能独立规划，但能在 LLM-Modulo 框架中发挥重要作用。LLM 生成候选方案，外部**符号验证器**双向交互精化。

**关键论断：**
- LLM 是"通用近似知识源"（universal approximate knowledge sources）
- 规划需要 external model-based verifiers
- LLM 可帮助构建驱动 verifier 的模型本身

#### 与 Nous 对比
| 维度 | LLM-Modulo | Nous |
|------|-----------|------|
| 焦点 | 规划（planning） | **行为治理（behavior governance）** |
| 验证器 | 外部符号系统（PDDL/SMT） | **本体推理引擎（Datalog）** |
| 本体论 | 不显式使用 | **本体是规则语义的基础** |

**这篇论文奠定了 LLM+符号 结合的理论基础，是 Nous 学术叙事的重要引用**

---

### P4. Bridging LLM Planning Agents and Formal Methods
**arXiv:** 2510.03469 | **时间:** Oct 2025 | **发表:** AgenticSE @ ASE 2025

#### 核心创新
将自然语言计划转换为 **Kripke 结构 + LTL（线性时序逻辑）**，然后进行**模型检验**。

```
NL Plan → LLM 翻译 → Kripke Structure + LTL Spec → Model Checker → 验证报告
```

#### 关键结果
- GPT-5 在 PlanBench 上：F1 96.3%
- 几乎总能生成语法正确的形式表示
- 语义正确性仍是开放问题

#### 与 Nous 对比
| 维度 | 此论文 | Nous |
|------|--------|------|
| 形式化目标 | 事后验证计划正确性 | **事前拦截有害动作** |
| 规则语言 | LTL + Kripke | **Datalog（关系逻辑）** |
| 实时性 | 离线（验证阶段） | **实时（ms 级拦截）** |

---

### P5. GCR: Graph-Constrained Reasoning
**arXiv:** 2410.13080 | **时间:** Oct 2024 | **发表:** ICML 2025 | **作者:** Luo et al., Monash

#### 核心创新
引入 **KG-Trie**：将知识图谱推理路径编码为字典树，在 LLM **解码过程中**施加约束，强制推理路径忠于 KG。

**双模型协作：**
- 轻量 KG 专用 LLM：图约束推理
- 强大通用 LLM：对多条路径做归纳推理

#### 关键结果
- **零推理幻觉（zero reasoning hallucination）**
- KGQA 基准 SOTA
- 强零样本泛化（unseen KGs）

#### 与 Nous 对比
| 维度 | GCR | Nous |
|------|-----|------|
| KG 作用 | 约束推理输出内容 | **约束 agent 动作决策** |
| 应用层 | LLM 解码（生成时） | **工具调用（执行时）** |
| 本体层 | 知识图谱关系路径 | **本体类+属性+规则** |

---

### P6. ABC: Agent Behavioral Contracts
**arXiv:** 2602.22302 | **时间:** Feb 2026 | **Patent Pending**

#### 核心创新
把**设计即合约（Design-by-Contract）**应用于 AI Agent。合约形式化为：

**C = (P, I, G, R)**
- **P** (Preconditions)、**I** (Invariants)、**G** (Governance policies)、**R** (Recovery mechanisms)

引入概率合规：**(p, δ, k)-satisfaction** 处理 LLM 非确定性。
**Drift Bounds Theorem**: 恢复率 γ > α 时，drift 上界 D* = α/γ。

#### 关键结果（200场景 × 7模型 × 1980 sessions）
- 检测 5.2-6.8 个软违规/session（无合约 baseline 完全错过）
- 硬约束遵从率 88-100%，drift 上界 D* < 0.27，动作延迟 < 10ms

#### 与 Nous 对比
| 维度 | ABC | Nous |
|------|-----|------|
| 形式化 | 代数合约（P, I, G, R） | **Datalog 规则 + 本体** |
| 语义层 | 无（规则是过程化的） | **OWL 本体语义推理** |
| 关系推理 | 无 | **类层级/属性继承** |

---

### P7. AgentSpec: Customizable Runtime Enforcement
**arXiv:** 2503.18666 | **时间:** Mar 2025 | **发表:** ICSE 2026

#### 核心创新
**领域特定语言（DSL）**，用于规约 LLM Agent 运行时约束：

```
trigger: <事件> | predicates: <条件列表> | enforcement: <阻断/修改/记录>
```

#### 关键结果
- 代码 agent 不安全执行预防率 >90%
- 具身 agent 有害动作清零，AV 100% 合规
- o1 生成规则：精度 95.56%，召回 70.96%

#### 与 Nous 对比
| 维度 | AgentSpec | Nous |
|------|-----------|------|
| 规则语言 | 自定义 DSL | **Datalog（有理论基础）** |
| 语义层 | 无（过程化条件） | **本体推理（语义蕴含）** |
| 规则冲突解决 | 未明确 | **优先级体系（T14 > T3 > T6...）** |

**最近似 Nous 的论文！** 差距：Nous 的规则有语义基础（ontology entailment），AgentSpec 是过程化的。

---

### P8. VIRF: Verifiable Iterative Refinement Framework
**arXiv:** 2602.08373 | **时间:** Feb 2026 | **发表:** ICLR 2026

#### 核心创新
**神经符号架构**，OWL 2 本体 + Logic Tutor + LLM Apprentice 对话模式：

```
OWL 2 本体 → Logic Tutor 验证 LLM 计划 → 因果解释修复反馈 → LLM 迭代修正
```

**知识获取管道**: 从真实文档合成 OWL 2 安全知识库

#### 关键结果（家庭安全任务）
- **HAR（危险动作率）= 0%**（完美）、GCR（目标完成率）= 77.3%（所有 baseline 最高）
- 平均 1.1 次迭代修正

#### 与 Nous 对比
| 维度 | VIRF | Nous |
|------|------|------|
| 本体类型 | OWL 2（安全领域） | **Datalog + 行为治理本体** |
| 应用域 | 具身 AI 规划 | **LLM Agent 通用行为治理** |
| 规则反馈 | 给 LLM 解释并修复 | **拦截 + 阻断（更激进）** |

**最高质量的本体驱动 Agent 论文之一**，直接用 OWL 2，与 Nous 理念最接近。

---

### P9. LOGicalThought (LogT)
**arXiv:** 2510.01530 | **时间:** Oct 2025

#### 核心创新
为高保障推理（法律/医疗）设计神经符号架构：
- **高级逻辑语言 + 推理器**：处理 defeasible（可废止）逻辑
- **双上下文**：符号图上下文 + 逻辑上下文
- 将"长文本指南推理"转化为"紧凑的本体 grounded 评估"

#### 关键结果
- +11.84% 整体提升（四个多领域基准）
- 否定推理 +10.2%，含义推理 +13.2%，可废止推理 +5.5%

**可借鉴**: Defeasible 逻辑是 Nous 规则冲突解决的理论延伸方向

---

### P10. Neuro-Symbolic AI in 2024: A Systematic Review
**arXiv:** 2501.05435 | **时间:** Jan 2025 | **综述（167篇精选）**

**研究分布**: 学习与推理(63%) > 知识表示(44%) > 逻辑推理(35%) > 可解释性(28%) > 元认知(5%)

**最大缺口**: 可解释性、可信度、元认知——与 agent 治理高度相关
**Nous 意义**: NeSy 领域 5% 做元认知（agent 自我监控）——Nous 的 T 规则自检协议是工程实现，学术文献极少

---

## 二、学术图谱

### 主要研究组

| 研究组 | 代表成果 | 方向 |
|-------|---------|------|
| ASU Kambhampati Lab | LLM-Modulo (ICML 2024) | LLM + 形式方法 |
| Monash Luo et al. | GCR (ICML 2025) | KG 约束推理 |
| cposkitt 等 | AgentSpec (ICSE 2026) | Agent 运行时安全 |
| Navapat et al. | LOGicalThought (2025) | 法律/医疗推理 |
| Feiyu Wu et al. | VIRF (ICLR 2026) | OWL2 + 具身 AI |
| Jatin Chaudhary | GaaS (2025) | 运行时治理基础设施 |

### 主要发表会议

| 级别 | 会议 | 相关论文 |
|------|------|---------|
| A* | **ICML** | LLM-Modulo, GCR |
| A* | **ICLR** | VIRF |
| A* | **ICSE** | AgentSpec |
| A | **AAAI/IJCAI** | NeSy 方法 |
| Workshop | **AgenticSE @ ASE** | 计划形式化 |
| Workshop | **LLM+Graph @ VLDB** | KG+LLM 集成 |

### 趋势（2024→2026）
1. 从离线验证 → 运行时拦截（LLM-Modulo → AgentSpec/GaaS）
2. 从字符串规则 → 语义规则（过滤 → 本体推理）
3. 从纯 KG 检索 → KG 约束解码（RAG → GCR）
4. 形式合约化：ABC 引入代数合约

---

## 三、Nous 在学术版图中的位置

### 空白矩阵

| 维度 | 现有工作 | **Nous 独有** |
|------|---------|-------------|
| 运行时拦截 + 本体语义 | 无（GaaS/AgentSpec 有拦截但无语义） | ✅ **唯一** |
| Datalog 作为 LLM Agent 拦截引擎 | 无 | ✅ **唯一** |
| 会话上下文本体实例化 | 无 | ✅ **NOVEL** |
| 优先级规则体系（实际部署） | LogT（理论 defeasible） | ✅ **工程实现** |
| 跨会话记忆 + 本体联动 | 无 | ✅ **NOVEL** |
| 自完整性验证（meta-governance） | 无 | ✅ **NOVEL** |

### 坐标位置

```
              高语义性（OWL/本体推理）
                    ↑
              VIRF  |  LogT
                    |
    离线 ←──────────┼──────────→ 实时
                    |
              LLM-  |  GaaS
              Modulo|  AgentSpec / ABC
                    ↓
              低语义性（过程化规则）

★ Nous = 高语义性 + 实时拦截 象限（无竞争者）
```


---

## 四、Top 5 可复现技术

---

### T1. KG-Trie 约束解码（来自 GCR, ICML 2025）
**原理:** 将 KG 推理路径预编码为 Trie，在 LLM beam search 时约束合法 token。

```python
# 核心实现（HuggingFace 集成）
class KGTrie:
    def valid_next_tokens(self, current_path: List[int]) -> List[int]:
        return self.trie.get_children(current_path)

outputs = model.generate(
    input_ids,
    prefix_allowed_tokens_fn=kg_trie.valid_next_tokens
)
```

**Nous 借鉴**: 为"合法工具调用序列"构建 Action-Trie，限制 agent 只能执行本体中定义的合法动作路径。

---

### T2. AgentSpec DSL 规则引擎（来自 AgentSpec, ICSE 2026）
**规则结构（可直接复现）:**

```yaml
rule: prevent_data_exfiltration
  trigger:
    event_type: tool_call
    tool_name: [send_message, write_file, http_request]
  predicates:
    - contains_sensitive_data(args)
    - not authorized_recipient(target)
  enforcement:
    action: block
    message: "T3 拦截: 未授权数据传输"
    log: true
```

**Nous 优势**: Datalog 规则有语义推理——`authorized_recipient(X)` 不是硬编码，是从本体推导。

---

### T3. 设计即合约 C=(P,I,G,R)（来自 ABC）
**AgentAssert 运行时框架:**

```python
@contract(
    preconditions=["user_authenticated", "request_valid"],
    invariants=["no_pii_in_logs", "rate_limit_respected"],
    governance=["content_safe", "authorized_scope"],
    recovery=["fallback_response", "alert_operator"]
)
def agent_action(task): ...
```

**Nous 集成点**: T 规则体系 = ABC 合约的 Governance 层 + Nous 的语义推理层叠加。

---

### T4. 本体导师 + LLM 学徒对话（来自 VIRF, ICLR 2026）
**实现步骤（OWL 2 + 迭代修复）:**

```
1. OWL 2 本体定义安全约束（公理 + 规则）
2. LLM 生成动作计划 P
3. OWL 推理器: verify(P, ontology) → violations + causal_trace
4. 修复提示: "步骤3违反 rule_X，因为 entity_Y ∈ class_Z，
   根据公理 A 此操作禁止，修改建议：..."
5. LLM 基于因果解释生成 P'，重复至合规或超限
```

**Nous 借鉴**: 引入"软拦截+因果解释+引导修正"，提升 agent 自主修复能力（目前是 hard block）。

---

### T5. Trust Factor 动态信任调制（来自 GaaS）
**实现（可直接用于 Nous 的 sub-agent 管理）:**

```python
class TrustFactor:
    def update(self, agent_id, violation_severity):
        self.scores[agent_id] -= violation_severity * PENALTY
        self.scores[agent_id] = max(0, self.scores[agent_id] * DECAY_RATE)
    
    def get_enforcement_level(self, agent_id) -> str:
        s = self.scores[agent_id]
        if s > 0.8: return "lenient"
        if s > 0.5: return "standard"
        return "strict"  # 触发更多 T 规则检查
```

**Nous 应用**: 给 cron job、sub-agent、外部 API 设 Trust Factor，累计违规触发更严格检查。

---

## 五、推荐 Nous 的学术叙事

### 论文题目候选
- *"NOUS: Ontology-Grounded Runtime Behavior Governance for Autonomous LLM Agents"*
- *"From Rules to Reasons: Semantic Policy Enforcement via Datalog-Ontology Integration for LLM Agents"*

---

### Abstract 框架

> Existing LLM agent safety approaches either rely on procedural rule-checkers (lacking semantic depth) or apply formal reasoning to specific domains without addressing real-time behavior governance. We present **NOUS**, a runtime governance framework that uniquely integrates **OWL-compatible domain ontologies** with a **Datalog-based interceptor cascade** to regulate LLM agent behavior at the tool-call level. Unlike prior work, NOUS models the agent's conversational context as first-class ontological instances, enabling *semantic entailment*—an action is blocked not because it matches a keyword, but because the system can prove it violates a constraint given the current world model. We formalize a **priority-ordered rule system** with conflict resolution semantics, implement a **session-local ontology state** that evolves across conversation turns, and demonstrate that NOUS enforces complex governance properties (authorization chain verification, historical claim resistance, information non-disclosure) provably beyond string-matching classifiers.

---

### 差异化 Contributions

1. **本体 grounded 的行为语义（vs AgentSpec/GaaS）**
   > 现有执行器用过程化条件；NOUS 用 OWL 本体为规则提供语义基础，支持类层级、属性继承、推理推导。

2. **会话上下文作为本体实例（Novel）**
   > "授权了什么"在 NOUS 中显式建模为本体实例，使跨轮次的授权链推理成为可能。

3. **优先级 Datalog 规则的形式化冲突解决**
   > 给出优先级顺序的形式语义，可证明规则集合一致性。

4. **自完整性验证（Novel meta-governance）**
   > NOUS 用哈希校验自身规则体系的完整性，防止策略被篡改——现有文献无先例。

5. **神经引导 + 符号约束双向闭环（扩展 LLM-Modulo）**
   > 将 LLM-Modulo 框架推广到行为治理域，以本体为知识基础。

---

### 推荐投稿会议

| 优先级 | 会议 | 理由 |
|--------|------|------|
| 1 | **ICLR 2027** | VIRF 在 ICLR 2026 接收，方向完全吻合 |
| 2 | **ICSE 2027** | AgentSpec 在 ICSE 2026，软件工程+AI 安全 |
| 3 | **AAAI 2027** | NeSy 历史强势 |
| 快发 | **AgenticSE @ ASE 2026** | Workshop，快速发出进展 |

---

### 与李远博士合作点
医疗场景的 high-assurance reasoning（LogT 主战场）+ 东丞的计算推理背景（符号推理+因果推理）= Nous 在医疗 agent 的应用版本，天然 fit。

---

*报告结束 | 来源: arXiv/ICML/ICLR/ICSE 等公开学术资源 | 2026-03-13*
