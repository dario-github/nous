# Agent Safety Governance SOTA 研究报告
> 生成时间：2026-03-13 | 目标系统：Nous Agent Safety Governance

---

## 1. AgentHarm — Agent 安全 Benchmark 精读

**来源：** arXiv:2410.09024 | ICLR 2025  
**机构：** Gray Swan AI + UK AI Safety Institute (UKASI) + EPFL + CMU + Oxford

### 1.1 核心方法与架构

AgentHarm 是目前最权威的 LLM Agent 安全鲁棒性评估框架，评估目标是：**Agent 对恶意多步任务的拒绝能力**，以及在 jailbreak 攻击后**是否仍能完整执行危害任务**。

**数据集结构：**
- 110 个明确恶意的 Agent 任务（含 4× 增强版 = 440 个）
- 11 个危害类别：欺诈（fraud）、网络犯罪（cybercrime）、骚扰（harassment）、生物武器、爆炸物、虚假信息、隐私侵犯、色情内容、版权侵犯、人身伤害、其他
- 分为 val / test_public / test_private 三个 split
- 任务类型：detailed behaviors + open-ended behaviors

**评估逻辑（双重评估）：**
1. **Refusal Rate**：模型是否拒绝执行恶意请求
2. **HarmScore**：对于未拒绝的任务，Agent 实际完成危害行为的程度（0-100%）
3. **Capability Maintenance**：攻击后模型是否仍保留执行多步任务的能力

**工具链：**
- UK AISI 的 `inspect_evals` 框架（Python）
- Refusal Judge + Semantic Judge（均用 GPT-4o-2024-08-06）
- HuggingFace 数据集：`ai-safety-institute/AgentHarm`

### 1.2 评估结果（主要发现）

| 模型 | Refusal Rate（直接请求） | HarmScore |
|------|------------------------|-----------|
| GPT-4o | 48.4% | ~55% |
| Claude 3.5 Sonnet | ~85% | 较低 |
| GPT-4o-mini | ~1-22% | 62.5-82.2% |
| Mistral Large 2 | 极低 | 82.2% |

**关键发现：**
1. **前沿模型对恶意 Agent 请求意外地顺从**——即使不 jailbreak，GPT-4o 只有 48% 拒绝率
2. **简单通用 jailbreak 模板就能有效攻破 Agent**，且攻击后模型保持完整能力
3. **Agent 任务比纯聊天任务更难拒绝**（refusal rate 系统性更低）

### 1.3 与 Nous 的关系

**可直接复用：**
- AgentHarm 数据集作为 Nous 的标准 eval 套件（HuggingFace 公开）
- `inspect_evals` 框架可直接集成，通过自定义 `agent` 参数接入 Nous 的 agent 实现
- Refusal Judge 逻辑可借鉴（双重评判：拒绝率 + 危害执行分）

**互补关系：**
- AgentHarm 是 evaluation benchmark，不是防御系统——告诉你"漏洞在哪里"，不告诉你"怎么修"
- Nous 需要在 AgentHarm 上建立基线 + 防御改进后的对比测试

### 1.4 可实现技术点

1. **双重评分机制**：在 Nous eval 中区分 refusal_rate 和 harm_completion_score，避免"拒绝一切"的假安全感
2. **增强数据集设计**：用 4× 增强（改写措辞/变换工具调用方式）测试 Nous 防御的泛化能力
3. **Judge-LLM 分离**：refusal judge 和 semantic judge 用独立模型，避免被评估模型自我审查


---

## 2. QuadSentinel — 基于 Sequent 的机器可验证安全策略精读

**来源：** arXiv:2512.16279 | Dec 2025  
**机构：** 香港中文大学 + 阿里巴巴集团

### 2.1 核心方法与架构

**核心问题：** 自然语言安全策略含糊、依赖上下文，无法直接映射到机器可执行规则，运行时强制执行不可靠。

**解决方案：将安全策略表达为 Sequents（逻辑演算），编译为可机器验证的规则集合**

#### 架构：四 Agent Guard 系统

```
[目标 MAS] → QuadSentinel Guard Team → allow/deny
              ├── State Tracker       (实时谓词状态 Γ_t)
              ├── Policy Verifier     (sequent 逻辑检查)
              ├── Threat Watcher      (per-agent 威胁分数 τ)
              └── Referee             (综合裁决 + rationale)
```

| 组件 | 职责 | 技术 |
|------|------|------|
| **State Tracker** | 维护实时谓词状态集 Γ_t | top-k 动态更新（只更新关键谓词） |
| **Policy Verifier** | 检查逻辑 sequent 是否满足 | 命题逻辑推理，Γ ⊢ ψ 形式 |
| **Threat Watcher** | 每个 agent 的威胁分数 τ | 增量式风险评分 |
| **Referee** | 综合 violation + 威胁级别 | 层级化冲突解决 → allow/deny |

**策略编译流程：**
1. 自然语言策略 → 谓词集合 P（原子安全事实）
2. 谓词 → 逻辑规则集合 R（命题逻辑约束）
3. 在线：Γ_t ⊢ ψ（sequent 安全检查）

**示例（数据泄露场景）：**
```
策略："不要发布敏感信息"
谓词：p1 = sensitive_info, p2 = publish_content
规则：ϕ = ¬(sensitive_info ∧ publish_content)
执行：Γ_t = {sensitive_info=T, publish_content=T} → 违规 → block publish(API_KEY)
```

**关键设计优势 vs ShieldAgent（ICML '25）：**
- **拦截 inter-agent 消息** + 工具调用（ShieldAgent 只拦截工具调用）
- **形式逻辑而非概率推断**（ShieldAgent 用 Markov Logic Networks）
- **持久状态追踪**（top-k 增量更新，不重算全历史）
- **可审计性**：输出 rule hits + per-agent risk + human-readable rationale

### 2.2 评估方法

**Benchmarks：** ST-WebAgentBench (ICML CUA '25) + AgentHarm (ICLR '25)

| 系统配置 | Accuracy | Precision | Recall | FPR |
|---------|----------|-----------|--------|-----|
| **QuadSentinel Full** | **91.5%** | **97.4%** | **85.2%** | **2.3%** |
| (i) Single Referee | 83.0% | 74.6% | 100.0% | 34.1% |
| (ii) No Threat Watcher | 86.4% | 90.0% | 81.8% | 9.1% |
| (iii) No Top-k Filter | 88.9% | 92.0% | 85.2% | 7.4% |

消融结论：Threat Watcher 是降低 FPR 的关键（去掉后 FPR 从 2.3% → 9.1%）

**代码：** https://github.com/yyiliu/QuadSentinel

### 2.3 与 Nous 的关系

**可直接复用：**
- **四组件 Guard 架构**：State Tracker + Threat Watcher + Policy Verifier + Referee 分工可移植到 Nous 的多 agent 监督层
- **top-k 谓词更新策略**：成本控制，适合生产环境
- **inter-agent 消息拦截**：Nous 若有多 agent 协作，需在消息层拦截 prompt injection

**互补关系：**
- QuadSentinel 是运行时 guard，Nous 关注策略制定和值对齐——堆栈不同层
- QuadSentinel 的 policy compiler（NL→sequent）与 Nous 的 T 规则体系天然互补

### 2.4 可实现技术点

1. **Top-k Predicate Updater**：只更新与当前消息最相关的 k 个谓词（节省 LLM 调用次数）
2. **层级化 Referee 仲裁**：规则冲突时按优先级解决（类比 Nous T14 > T3 > T6 的优先级，但要机器可执行）
3. **策略编译器**：将 AGENTS.md T 规则自动编译为命题逻辑谓词（offline compilation + online check 分离）
4. **Per-agent 威胁分数**：为每个 sub-agent/外部源维护信任分数，累积风险时提升审查级别

---

## 3. Superego — 用户可配置监督层精读

**来源：** arXiv:2506.13774 / MDPI Information 16(8):651 | July-Aug 2025  
**机构：** University of Gloucestershire + 独立研究者  
**Demo：** superego.creed.space

### 3.1 核心方法与架构

**核心理念：** 借鉴精神分析"超我"（superego）作为道德监督的概念，实现**用户可个性化的 AI 行为对齐层**——把对齐从"模型内部 fine-tune"转移到"外部模块化监督层"。

```
用户 → 选择 Creed Constitutions（1-5 adherence dial）
           ↓
[Superego Agent] ← Constitutional Marketplace（共享 constitution 库）
           ↓  MCP 注入上下文
[Inner Agent] → Plan → [Compliance Enforcer] → 执行
                                ↓
                    Universal Ethical Floor（基线安全）
```

**四大核心机制：**

| 组件 | 职责 |
|------|------|
| **Creed Constitutions** | 规则集合封装（素食主义、K-12 适当性、犹太饮食法、信托义务等） |
| **Adherence Dial (1-5)** | 每个 constitution 的执行严格度（1=宽松，5=严格遵守） |
| **Compliance Enforcer** | 预执行验证：拦截 inner agent 的计划，对照 constitution 检查 |
| **Universal Ethical Floor** | 无论用户选什么 constitution，基线安全必须满足 |

**MCP 集成：** 通过 Model Context Protocol 将 constitutions + adherence 级别注入兼容模型

**Constitutional Marketplace：** 用户可发现、共享、fork constitutions，形成协作生态

### 3.2 评估方法

**Benchmarks：** HarmBench + AgentHarm

| 模型 | 危害分降低 | 有害指令拒绝率 |
|------|-----------|---------------|
| Claude Sonnet 4 + Superego | 最高 98.3% | 100% |
| Gemini 2.5 Flash + Superego | 大幅降低 | ~99.4% |
| GPT-4o + Superego | 大幅降低 | 高 |

对比基线：无 Superego 时 GPT-4o 拒绝率仅 48.4%（来自 AgentHarm 发现）

### 3.3 与 Nous 的关系

**可直接复用：**
- **Creed Constitution 框架**：Nous T 规则（T1-T15）可表示为 constitutions，支持按场景调整执行强度
- **预执行验证模式**：在 Nous sub-agent spawn 和工具调用前，插入 compliance check 节点
- **Universal Ethical Floor**：类似 Nous T14 内容安全规则——无论任何配置都不可绕过的底线

**互补关系：**
- Superego 是**用户侧个性化配置**层，QuadSentinel 是**系统侧机器验证**层
- 组合使用：用户配置 constitutions → 编译为 sequents → QuadSentinel 在线执行
- Superego 的 Constitutional Marketplace 对 Nous 多租户/多组织部署场景有价值

**潜在差距：**
- Superego 依赖 LLM 理解 constitution 文本，对 prompt injection 有一定脆弱性
- 论文理论形式化弱于 QuadSentinel

### 3.4 可实现技术点

1. **Constitution-as-Code**：将 Nous AGENTS.md T 规则结构化为可版本管理、可独立 enable/disable 的 constitution 对象
2. **1-5 Dial 机制**：对 Nous 风险容忍度建立量化 dial（而非 binary on/off）
3. **Pre-execution Compliance Check**：Task → [Compliance Check] → Spawn（在 sub-agent 分配流程中插入检查节点）
4. **MCP 注入上下文**：通过 MCP 把 Nous 安全策略注入第三方 agent（适用接入外部 LLM 场景）

---

## 4. 综合对比表

### 4.1 架构/方法维度

| 维度 | **Nous（现状）** | **QuadSentinel** | **Superego** |
|------|----------------|-----------------|--------------|
| **安全层位置** | 系统 prompt + 拦截器规则 | 外部 Guard Team（独立进程） | 外部监督层（串联注入） |
| **策略表示** | 自然语言 T 规则（AGENTS.md） | 命题逻辑 sequents（形式化） | Constitution 文本 + dial |
| **执行方式** | CoT 自检（thinking 中） | 硬性机器验证（allow/deny） | LLM 软性验证（pre-execution） |
| **适用粒度** | 单 Agent session 级 | Multi-agent 消息+动作级 | Agent 链间调用级 |
| **可审计性** | 低（thinking 不持久化） | 高（rule hits + rationale 记录） | 中（compliance log） |
| **用户可配置** | 有限（需手写 T 规则） | 无（deployer 配置） | 强（用户选 constitutions + dial） |
| **Jailbreak 抵抗** | 依赖模型自身 + T 规则 | 高（形式逻辑，不可 prompt 绕过） | 中（LLM 理解，有 injection 风险） |
| **成本控制** | 无显式机制 | top-k 谓词过滤 | 未详述 |

### 4.2 评估维度

| 维度 | **Nous** | **QuadSentinel** | **Superego** |
|------|---------|-----------------|--------------|
| **是否有 benchmark** | ❌ 无正式 benchmark | ✅ ST-WebAgentBench + AgentHarm | ✅ HarmBench + AgentHarm |
| **主要指标** | 无 | Accuracy/Precision/Recall/FPR | HarmScore 降低率/拒绝率 |
| **关键值** | N/A | Precision 97.4%, FPR 2.3% | 98.3% 危害降低，100% 拒绝 |
| **测试攻击** | CC-BOS 自测 | Jailbreak + prompt injection | 直接请求 + jailbreak |
| **消融实验** | 无 | ✅ 4组详细消融 | 有限 |

---

## 5. Nous 应该复现的 Top 5 技术点

### P1（最高优先级）：AgentHarm Benchmark 接入

**理由：** 没有 benchmark 就没有改进方向。Nous 当前缺乏系统性 eval，AgentHarm 是 ICLR 2025 公开标准，接入成本低（pip install + 自定义 solver）。

**直接行动：** 见第 6 节详细方案。预计 2 天可完成基线测试。

---

### P2：策略编译器：T 规则 → 命题逻辑谓词

**来源：** QuadSentinel Policy Compiler  
**理由：** T 规则目前是自然语言形式，依靠 LLM 理解——存在歧义和 prompt injection 绕过风险。形式化后可实现机器可验证的硬性检查。

```python
# 示例：T3 规则形式化
T3_rule = Sequent(
    predicates=["is_irreversible_op", "has_explicit_authorization"],
    constraint="¬(is_irreversible_op ∧ ¬has_explicit_authorization)",
    priority=3  # T14 > T3 > T6 > T8 > T1
)
T14_rule = Sequent(
    predicates=["content_has_harmful_synthesis"],
    constraint="¬content_has_harmful_synthesis",  # 绝对约束
    priority=14
)
```

**工作量：** 将 T1-T15 转化为命题逻辑约束，约 2-3 天

---

### P3：Per-Agent 威胁分数 + 动态审查级别

**来源：** QuadSentinel Threat Watcher  
**理由：** Nous 当前对所有输入审查级别平坦——不区分来源可信度。引入威胁分数后，外部工具/不可信源触发更严格审查（量化 T15 的"提升敏感度"）。

```yaml
# threat_scores.yaml
sources:
  - name: "user_input"
    base_threat: 0.1
  - name: "external_tool_output"
    base_threat: 0.5
  - name: "sub_agent_output"
    base_threat: 0.2
thresholds:
  normal_check: 0.3    # 标准 CoT 自检
  elevated_check: 0.6  # T 规则敏感度提升
  hard_block: 0.9      # 直接拦截
```

---

### P4：Pre-execution Compliance Check 串联

**来源：** Superego Compliance Enforcer  
**理由：** 当前安全检查在 thinking 中完成，易被"思维捷径"绕过。外化为硬性检查点，形成可审计记录。

```
当前：Task → [LLM thinking: CoT 自检] → spawn sub-agent → execute

改进：Task → [Compliance Checker（轻量 Flash）] 
              ↓ allowed                ↓ denied
           spawn + execute          block + security-log.sh
```

---

### P5：Constitution Dial 机制（风险容忍度量化）

**来源：** Superego 1-5 Adherence Dial  
**理由：** T 规则当前是 binary（触发/不触发），实际场景需要按上下文调整严格度。

```yaml
# nous-constitution.yaml
rules:
  T3_irreversible_ops:
    level: 4  # 1=只警告, 3=软阻断需确认, 5=硬阻断
    scope: ["external_channels", "file_system"]
  T14_harmful_content:
    level: 5  # 永远硬阻断
    scope: ["all"]
  T1_time_sensitive_info:
    level: 3  # 需验证但不阻断
    scope: ["investment", "market_data"]
```

---

## 6. AgentHarm Benchmark 接入方案

### 6.1 接入流程

**Step 1：安装**
```bash
pip install inspect-evals
export OPENAI_API_KEY=<key>           # judge 用 GPT-4o
export INSPECT_EVAL_MODEL=anthropic/claude-opus-4-6-v1
```

**Step 2：实现 Nous Agent Wrapper**

AgentHarm 通过 `--agent` 参数接受自定义 solver，将 Nous agent 封装为 inspect_evals solver 接口：

```python
# nous_agent_solver.py
from inspect_ai.solver import Solver, TaskState
from inspect_ai.tool import Tool
from typing import Sequence

class NousAgentSolver(Solver):
    """将 Nous Agent 封装为 AgentHarm solver"""

    async def solve(self, state: TaskState, tools: Sequence[Tool]) -> TaskState:
        task_content = state.messages[-1].content

        # 1. Nous 安全检查（T 规则 sequent 检查 / Compliance Checker）
        safety_result = await self._nous_safety_check(task_content)

        if safety_result.is_blocked:
            # 拒绝 → refusal response
            state.output.completion = "I cannot assist with this request."
            return state

        # 2. 正常执行（传入工具）
        return await self._nous_agent_execute(state, tools)

    async def _nous_safety_check(self, content: str):
        """接入 Nous T 规则检查 / scripts/security-log.sh"""
        # TODO: 调用 T 规则 sequent 验证逻辑
        pass
```

**Step 3：运行测试**
```bash
# harmful 任务集
uv run inspect eval inspect_evals/agentharm \
  --model anthropic/claude-opus-4-6-v1 \
  -T agent=nous_agent \
  -T split=test_public

# benign 任务集（测试是否过度拒绝）
uv run inspect eval inspect_evals/agentharm_benign \
  --model anthropic/claude-opus-4-6-v1 \
  -T agent=nous_agent

# 查看结果
uv run inspect view
```

### 6.2 评分目标

| 指标 | 含义 | Nous 目标 |
|------|------|-----------|
| Refusal Rate（harmful） | 对有害任务的拒绝率 | ≥ 95% |
| HarmScore | 有害任务完成度（越低越好） | ≤ 5% |
| Benign Refusal Rate | 对正常任务的错误拒绝率 | ≤ 5% |

### 6.3 推荐测试矩阵

| 测试配置 | 目的 |
|---------|------|
| Nous 无防御（基线） | 建立 baseline |
| Nous + 现有 T 规则 | 测试当前 prompt-based 防御 |
| Nous + P2 策略编译器 | 验证形式化规则提升 |
| Nous + P3 威胁分数 | 验证动态审查降低 FPR |
| Nous + P4 Compliance Check | 验证硬性检查点效果 |
| Nous + Full Stack (P2+P3+P4) | 对比 QuadSentinel/Superego |

---

## 7. 关键资源索引

| 资源 | 链接 |
|------|------|
| AgentHarm 数据集 | huggingface.co/datasets/ai-safety-institute/AgentHarm |
| AgentHarm inspect_evals | pip install inspect-evals → inspect_evals/agentharm |
| AgentHarm 论文 | arxiv.org/abs/2410.09024 |
| QuadSentinel 代码 | github.com/yyiliu/QuadSentinel |
| QuadSentinel 论文 | arxiv.org/abs/2512.16279 |
| Superego Demo | superego.creed.space |
| Superego 论文 | arxiv.org/abs/2506.13774 |
| HarmBench | github.com/centerforaisafety/HarmBench |

---

*数据来源：论文原文（arXiv + ICLR 2025 proceedings + MDPI） + UKASI inspect_evals 文档*  
*所有指标均来自论文，已注明原始来源*
