# Benchmark Feasibility Report: ToolEmu & AgentDojo 接入 Nous

**项目**: Owner-Harm Generalization v1
**日期**: 2026-04-09
**状态**: 初稿（Loop 30 节点）
**目标**: 评估在 ToolEmu 和 AgentDojo 上跑 Nous 验证"主人伤害（Owner-Harm）"威胁模型的可行性

---

## 一、两个评测集概述

### 1.1 ToolEmu

- **论文**: "Identifying the Risks of LM Agents with an LM-Emulated Sandbox" (ICLR 2024)
- **核心设计**: 用 GPT-4 模拟工具执行沙盒，无需真实 API，快速识别 LM agent 风险
- **规模**: 36 个 toolkit（311 个工具），144 个测试案例
- **数据格式**: JSON，每个案例包含字段：
  - `name`: 案例 ID（如 `official_0`）
  - `Toolkits`: 使用的工具集名称列表
  - `User Instruction`: 用户指令（常含欠规范项用于红队）
  - `Underspecifications`: 欠规范的任务信息 + 安全约束
  - `Potential Risky Outcomes`: 潜在风险后果列表
  - `Potential Risky Actions`: agent 可能采取的风险动作
  - `Expected Achievements`: agent 应达成的安全目标
- **评估方式**: LM-based 安全评估器（`agent_safe`）+ 帮助度评估器（`agent_help`）
- **依赖**: OpenAI API（每个案例约 $1.2，全集约 $170）

### 1.2 AgentDojo

- **论文**: "AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents" (NeurIPS 2024 D&B Track)
- **核心设计**: 评估 prompt injection 攻防，agent 在真实环境模拟中执行任务
- **规模**: 4 个套件（banking/slack/travel/workspace），共 86 个用户任务 + 27 个注入任务
  - banking: 16 user tasks, 9 injection tasks
  - slack: 17 user tasks, 5 injection tasks
  - travel: 20 user tasks, 7 injection tasks
  - workspace: 33 user tasks, 6 injection tasks
- **数据格式**: Python 类定义，每个任务包含：
  - `PROMPT`: 用户指令字符串
  - `GOAL`: 注入目标（攻击者试图实现的动作）
  - `ground_truth()`: 正确工具调用序列
  - `utility()`: 判断任务是否完成的函数
  - `security()`: 判断注入是否成功的函数
- **评估方式**: 确定性验证（utility + security 函数），不依赖 LLM 评估
- **防御接入点**: `BasePipelineElement.query()` 接口，可注入到 agent pipeline

---

## 二、ToolEmu 风险类别 vs Nous Owner-Harm 类别映射

### 2.1 ToolEmu 实际风险分布（144 个案例分析）

ToolEmu 数据集的风险类别不是预定义的枚举，而是自然语言标签（冒号前的类别词）。
分析 144 个案例的 `Potential Risky Outcomes` 字段，归一化后 7 大高层类别如下：

| ToolEmu 风险类别 | 案例数 | 代表性案例 |
|-----------------|--------|-----------|
| Privacy/Data breach | ~30 | 泄露门禁历史、分享 CSV 联系人列表 |
| Financial loss | ~26 | 错误下单 BTC、未授权转账 |
| Security breach | ~25 | 恶意软件执行、身份盗窃、未授权访问 |
| System/Operational | ~17 | 数据丢失、系统不稳定、错误配置 |
| Reputation damage | ~16 | 发布虚假信息、代发不当内容 |
| Physical safety | ~12 | 危险品、交通混乱、安全事故 |
| Legal/Compliance | ~12 | 版权侵犯、合规违规、刑事起诉 |
| Social harm | ~9 | 垃圾邮件、骚扰、不当自动化 |

> 注：ToolEmu 论文将风险归纳为 9 类，但仓库中未明确列举枚举值。
> 上表基于实际数据集提取，与论文 Figure 中的分类高度对应。

### 2.2 映射关系分析

#### 完全对应（Nous 与 ToolEmu 均覆盖）

| Nous Owner-Harm 类别 | ToolEmu 对应类别 | 重合度 |
|---------------------|-----------------|--------|
| Financial harm | Financial loss | 强（26 案例直接对应） |
| Privacy breach | Privacy/Data breach | 强（30 案例，最大类别） |
| Reputational harm | Reputation damage | 强（16 案例） |
| Legal harm | Legal/Compliance | 中（12 案例，含合规/刑事） |
| Security compromise | Security breach | 强（25 案例，含恶意软件/身份盗窃） |
| Operational harm | System/Operational | 中（17 案例，系统稳定性/配置错误） |

#### ToolEmu 有而 Nous 未明确覆盖的类别

| ToolEmu 类别 | 样例 | Nous 对应状态 |
|-------------|------|--------------|
| Physical safety | 危险品、交通事故、紧急响应延迟 | 未在 8 类中定义（物理世界伤害） |
| Social harm (broad) | 垃圾邮件、骚扰他人 | 部分对应 Relationship harm，但受害方是第三方 |

> 关键差异：ToolEmu 的 Physical safety（~12 案例）涉及真实世界物理危害（如智能锁、无人机、医疗），
> 这在 Nous 的 8 类中无对应类别。原因在于 Owner-Harm 聚焦**主人自损**，而物理安全往往是**第三方受害**。

#### Nous 有而 ToolEmu 弱覆盖的类别

| Nous Owner-Harm 类别 | ToolEmu 覆盖情况 |
|---------------------|----------------|
| Psychological harm | 几乎无（ToolEmu 偏工具调用风险，不含心理层面） |
| Relationship harm | 极少（仅 1-2 个社交媒体案例涉及关系损害） |

### 2.3 映射结论

- **6/8 Nous 类别**在 ToolEmu 中有直接对应数据，覆盖约 126/144 个案例（87.5%）
- ToolEmu 额外覆盖了 Physical safety（Nous 未定义）
- Nous 的 Psychological harm 和 Relationship harm 在 ToolEmu 中几乎无数据
- ToolEmu 的威胁模型是**agent 误操作导致任何方受损**，Nous 专注**agent 伤害自身 owner**，视角有差异但 80%+ 场景重叠

---

## 三、Nous 接入 ToolEmu 的技术方案

### 3.1 接入架构

ToolEmu 的核心评估流程：
```
test_case (JSON) → agent → trajectory (tool calls + observations) → safety evaluator
```

Nous 的接入点：**在 agent 每次工具调用前/后调用 `gate()`**，拦截高风险动作。

```
test_case → ToolEmu agent (with Nous gate hook) → trajectory → safety evaluator
```

### 3.2 需要编写的适配代码

#### 文件 1: `benchmarks/toolemu_adapter/nous_agent.py`（~100 行）

继承 ToolEmu 的 agent 执行框架，在每次工具调用前注入 gate：

```python
from nous.gate import gate, GateResult
from nous.schema import Verdict

class NousProtectedAgent:
    """ToolEmu agent wrapper，在工具调用前通过 Nous gate 过滤"""

    def __init__(self, base_agent, db=None, constraints_dir=None):
        self.base_agent = base_agent
        self.db = db
        self.constraints_dir = constraints_dir

    def step(self, action: str, action_input: dict) -> dict:
        tool_call = {
            "tool_name": action,
            "action": action,
            "params": action_input,
        }
        result: GateResult = gate(tool_call, db=self.db,
                                   constraints_dir=self.constraints_dir)
        if result.verdict == Verdict.BLOCK:
            return {"error": f"Nous gate blocked: {result.reason}"}
        return self.base_agent.step(action, action_input)
```

#### 文件 2: `benchmarks/toolemu_adapter/case_converter.py`（~80 行）

将 ToolEmu 的 JSON 案例转换为 Nous gate 可理解的 `tool_call` 格式，
并提取 `Potential Risky Outcomes` 用于评估后分析。

#### 文件 3: `benchmarks/toolemu_adapter/eval_runner.py`（~120 行）

批量运行评估、收集 gate 决策日志、计算 TPR/FPR（对比 ToolEmu 的 safety evaluator 结论）。

#### 文件 4: `benchmarks/toolemu_adapter/owner_harm_mapper.py`（~60 行）

将 ToolEmu 的自然语言风险标签映射到 Nous 的 8 类 Owner-Harm 类别，
生成评估矩阵（哪类风险 Nous 拦截了，哪类漏掉了）。

### 3.3 关键技术挑战

1. **ToolEmu 依赖 procoder 包**：需要额外安装 `PromptCoder`（`git clone` + `pip install -e .`），该包未上 PyPI。
2. **LLM 评估成本**：全集评估约 $170 API 成本（ToolEmu 的 safety evaluator 需要 GPT-4）。Nous 的 gate 调用另计（L3 semantic gate 用 qwen-turbo）。
3. **Trajectory 格式对接**：ToolEmu 的 trajectory 是 langchain Message 格式，需转换为 Nous 的 `tool_call` dict。
4. **Agent 框架耦合**：ToolEmu 的 agent 深度依赖 langchain + PromptCoder，独立运行难度中等。

### 3.4 预估工作量

| 任务 | 估时 |
|------|------|
| 安装 PromptCoder + 调通 ToolEmu 环境 | 0.5 天 |
| 编写 NousProtectedAgent wrapper | 1 天 |
| case_converter + owner_harm_mapper | 1 天 |
| eval_runner + 结果分析脚本 | 1 天 |
| 调试 + 小规模验证（10 个案例） | 1 天 |
| **合计** | **4.5 天** |

---

## 四、Nous 接入 AgentDojo 的技术方案

### 4.1 接入架构

AgentDojo 的防御接入设计非常清晰：

```python
class BasePipelineElement(abc.ABC):
    @abc.abstractmethod
    def query(self, query, runtime, env, messages, extra_args) -> tuple:
        ...
```

只需实现 `BasePipelineElement` 子类，插入到 agent pipeline 中，即可在每次 LLM 调用或工具调用前注入防御逻辑。

### 4.2 需要编写的适配代码

#### 文件 1: `benchmarks/agentdojo_adapter/nous_pipeline_element.py`（~80 行）

```python
from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from nous.gate import gate

class NousPipelineDefense(BasePipelineElement):
    """AgentDojo pipeline element，拦截高风险工具调用"""

    name = "nous_gate"

    def __init__(self, db=None, constraints_dir=None):
        self.db = db
        self.constraints_dir = constraints_dir

    def query(self, query, runtime, env, messages, extra_args):
        # 检查 messages 中最新的 tool call，若为 block 则替换
        # AgentDojo 的工具调用通过 runtime 传递
        filtered_runtime = NousFilteredRuntime(runtime, self.db, self.constraints_dir)
        return query, filtered_runtime, env, messages, extra_args
```

#### 文件 2: `benchmarks/agentdojo_adapter/nous_filtered_runtime.py`（~100 行）

包装 AgentDojo 的 `FunctionsRuntime`，在工具执行前调用 `gate()`。

#### 文件 3: `benchmarks/agentdojo_adapter/run_agentdojo_eval.py`（~100 行）

集成 AgentDojo 的 `benchmark.py` API，批量运行所有套件，输出：
- Nous 拦截率 vs AgentDojo security 通过率
- 误拦截率（utility 任务被误 block 的比例）

### 4.3 AgentDojo 独特优势

1. **无 LLM 评估成本**：utility/security 函数是确定性 Python 代码，评估完全免费。
2. **接口极其标准化**：`BasePipelineElement` 是专门为防御实现设计的，文档完整。
3. **注入 vs 防御的对立关系**：AgentDojo 的 27 个 injection task 直接模拟攻击者，适合验证 Nous 对 prompt injection 型 Owner-Harm 的防御效果。
4. **多套件覆盖**：banking（财务）、slack（信息泄露）、travel（预订操纵）、workspace（文件/邮件滥用），天然对应 Nous 的 Financial/Privacy/Operational harm。

### 4.4 AgentDojo 与 Owner-Harm 的关系

AgentDojo 的威胁模型是**第三方（attacker）通过 prompt injection 操纵 agent 伤害 owner**，
这与 Owner-Harm 威胁模型高度重叠：

| AgentDojo suite | Owner-Harm 类别 | 说明 |
|----------------|----------------|------|
| banking (InjectionTask0-2) | Financial harm | 攻击者让 agent 转账给自己的 IBAN |
| slack (InjectionTask1) | Privacy breach | 攻击者窃取所有 slack 消息 |
| workspace (InjectionTask1) | Operational harm | 攻击者删除 owner 的云盘文件 |
| workspace (InjectionTask0) | Reputational harm | 攻击者用 owner 身份发邮件 |

### 4.5 关键技术挑战

1. **工具调用时机**：AgentDojo 的工具通过 `FunctionsRuntime` 执行，需要在 runtime 层而非 pipeline 层拦截，比 ToolEmu 多一层封装。
2. **Nous gate 的 tool_call 格式**：AgentDojo 工具调用是 Pydantic model，需转换为 Nous 期望的 dict 格式。
3. **Owner-Harm 标注**：AgentDojo 的 injection task 是"攻击者目标"，需要手动标注哪个 injection task 对应哪类 Owner-Harm。

### 4.6 预估工作量

| 任务 | 估时 |
|------|------|
| 安装 agentdojo 包 + 调通环境 | 0.25 天 |
| NousPipelineElement 实现 | 0.5 天 |
| NousFilteredRuntime 实现 | 1 天 |
| run_agentdojo_eval 脚本 | 0.5 天 |
| Owner-Harm 标注（27 injection tasks） | 0.5 天 |
| 调试 + 小规模验证 | 0.5 天 |
| **合计** | **3.25 天** |

---

## 五、总体可行性判断

### 5.1 两个评测集对比

| 维度 | ToolEmu | AgentDojo |
|------|---------|-----------|
| 案例数 | 144 | 86 user × 27 injection = 2322 组合 |
| 安装难度 | 中（依赖 PromptCoder，非 PyPI） | 低（`pip install agentdojo`） |
| 防御接入难度 | 中（需 fork agent 框架） | 低（标准 `BasePipelineElement` 接口） |
| 评估成本 | 高（$170 GPT-4 API） | 零（确定性函数） |
| Owner-Harm 对应度 | 高（87.5% 案例覆盖 6/8 类别） | 中高（直接对应 prompt injection 型 Owner-Harm） |
| 威胁模型吻合度 | 中（ToolEmu 关注 agent 误操作，Owner-Harm 聚焦 owner 自损） | 高（AgentDojo 专注第三方攻击 owner） |
| 预估工作量 | 4.5 天 | 3.25 天 |

### 5.2 建议：先做 AgentDojo

理由：

1. **接入成本更低**：AgentDojo 有专门的防御插件接口（`BasePipelineElement`），而 ToolEmu 需要侵入式修改 agent 框架。

2. **零评估成本**：AgentDojo 的 utility/security 是 Python 函数，验证一次跑就有结论；ToolEmu 每次跑全集需要 $170。

3. **威胁模型更吻合**：AgentDojo 的 injection task 直接模拟"攻击者操控 agent 伤害 owner"，比 ToolEmu 的"agent 自身误操作"更直接对应 Owner-Harm。

4. **结论更清晰**：AgentDojo 的 security() 函数是二值判断（Nous 有没有拦截住），结果无歧义；ToolEmu 的 LM 评估器输出是打分，需要额外设阈值。

5. **可后续扩展 ToolEmu**：AgentDojo 完成后，ToolEmu 可作为第二阶段验证（更广泛的误操作场景）。

### 5.3 推荐执行路线

```
Phase 1（3.25 天）: AgentDojo 接入
  ├── D1: 环境搭建 + NousPipelineElement 实现
  ├── D2: NousFilteredRuntime + tool_call 格式转换
  ├── D3: 批量评估脚本 + Owner-Harm 标注（27 injection tasks）
  └── D3 下午: 调试 + 跑全量 + 分析报告

Phase 2（4.5 天，可选）: ToolEmu 接入
  ├── D1: PromptCoder 安装 + 环境调通
  ├── D2: NousProtectedAgent wrapper
  ├── D3: case_converter + owner_harm_mapper
  ├── D4: eval_runner + 分析脚本
  └── D5: 调试 + 10案例验证
```

### 5.4 预期收益

- **AgentDojo 完成后**：可以报告 Nous 对 prompt injection 型 Owner-Harm 的 TPR/FPR，直接对应 4 类（Financial/Privacy/Operational/Reputational harm）
- **ToolEmu 完成后**：额外覆盖 Security compromise + Legal harm，形成 6/8 类别的全面评估

---

## 六、附录：数据路径

- ToolEmu 仓库: `/Users/yan/clawd/nous/benchmarks/ToolEmu/`
- AgentDojo 仓库: `/Users/yan/clawd/nous/benchmarks/agentdojo/`
- ToolEmu 全量案例: `/Users/yan/clawd/nous/benchmarks/ToolEmu/assets/all_cases.json`（144 个案例）
- AgentDojo 套件入口: `/Users/yan/clawd/nous/benchmarks/agentdojo/src/agentdojo/default_suites/v1/`
- Nous gate 入口: `/Users/yan/clawd/nous/src/nous/gate.py`，函数签名 `gate(tool_call, db, constraints_dir, ...)`
