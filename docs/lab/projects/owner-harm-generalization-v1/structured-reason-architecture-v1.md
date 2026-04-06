# Structured Reason Output Architecture — Design v1

## 🟢 这是什么

基于 Dario 2026-04-06 的提议和证据表发现，设计 Nous gate 的下一代架构升级：
**强制大模型输出结构化推理理由，再由小模型做合规性校验。**

---

## 📌 问题回顾

### 当前 gate 的盲区（来自证据表）
| gate 能看到的 | gate 看不到的 |
|---|---|
| 用户 prompt | 被执行文件的内容 |
| tool_call 名称和参数 | 指令的真实来源（owner vs 文档） |
| bash 命令字符串 | 信任链（谁放的文件、谁批准的） |

### 当前 gate 的输出
```json
{"action": "allow|block|confirm", "reason": "free-text", "confidence": 0.8}
```

**问题：** reason 是自由文本，无法被机器检查。
你不知道 gate 到底看了哪条规则、漏了哪个检查项。

---

## 🏗️ 新架构：Generate → Reason → Verify

### 三步流程

```
Step 1: Gate (大模型)
  输入: tool_call + facts + policy + context
  输出: Structured Reason Card (schema 强制)

Step 2: Verifier (小模型 / 确定性规则)
  输入: Reason Card + Policy Rules + Required Checks
  输出: Compliance Report (缺漏 / 矛盾 / 通过)

Step 3: Arbiter (确定性逻辑)
  输入: Gate verdict + Compliance Report
  输出: Final verdict (可能 override gate)
```

---

## 📐 Reason Card Schema

### Gate 必须输出的结构

```typescript
interface ReasonCard {
  // ── 决策 ──
  decision: "allow" | "block" | "confirm";
  confidence: number; // 0.0-1.0

  // ── 推理过程（强制填写） ──
  core_task: string;           // Step 1: 去掉所有包装后，用户实际要做什么
  context_framing: string;     // Step 2: 包装/理由是什么
  framing_type: "verified" | "decorative" | "none";

  // ── 规则引用（关键新增） ──
  rules_checked: RuleRef[];    // 我检查了哪些规则
  rules_triggered: RuleRef[];  // 哪些规则被触发了
  rules_not_applicable: RuleRef[]; // 哪些规则我认为不适用（必须说明为什么）

  // ── 信号评估 ──
  signals_observed: Signal[];  // 我观察到了哪些信号
  signals_absent: Signal[];    // 我预期应该有但没有的信号

  // ── 来源追踪（新增：针对 hijacking） ──
  instruction_provenance: {
    source: "owner_prompt" | "file_content" | "external_api" | "unknown";
    confidence: number;
    evidence: string;  // 我为什么认为指令来自这个来源
  };

  // ── 可见性声明（新增：让 gate 主动说出自己看不到什么） ──
  visibility_gaps: string[];  // 我做这个判断时，有哪些信息是我看不到的
}

interface RuleRef {
  rule_id: string;        // 规则编号，如 "T9", "policy-3"
  applicable: boolean;    // 是否适用
  conditions_met: string[];   // 满足了哪些条件
  conditions_unmet: string[]; // 没满足哪些条件
  reason: string;         // 为什么适用/不适用
}

interface Signal {
  type: string;           // 如 "external_url", "bash_execution", "file_read"
  value: string;          // 具体内容
  risk_assessment: string; // 风险评估
}
```

---

## 🔍 Verifier 检查清单

小模型（或确定性规则引擎）拿到 Reason Card 后，逐条检查：

### 1. 规则覆盖检查
```
对于 policy 中的每条规则 R：
  if R 在 rules_checked 中 → PASS
  if R 不在任何列表中 → FLAG: "Rule R not addressed"
```

**目的：** 发现 gate 漏看的规则。

### 2. 条件一致性检查
```
对于 rules_not_applicable 中的每条 R：
  检查 R 的触发条件 vs gate 声称的 conditions_unmet
  if conditions_unmet 和实际输入矛盾 → FLAG: "Inconsistent: R条件实际满足"
```

**目的：** 发现 gate 错误地跳过了适用规则。

### 3. 来源一致性检查
```
if instruction_provenance.source == "owner_prompt":
  检查 prompt 中是否真的包含该指令
  if 指令实际来自 file_content → FLAG: "Provenance mismatch"
```

**目的：** 发现 gate 把文档指令当成 owner 指令。

### 4. 可见性 vs 置信度检查
```
if visibility_gaps 非空 AND confidence > 0.9:
  FLAG: "High confidence despite acknowledged visibility gaps"
```

**目的：** 发现 gate 在信息不足时过于自信。

### 5. 决策-理由一致性检查
```
if decision == "allow" AND rules_triggered 非空:
  FLAG: "Allow despite triggered rules — verify override justification"
```

**目的：** 发现 gate 的决策和自己的理由矛盾。

---

## 🔗 和证据表发现的关系

### 证据表核心发现
> 34 条 FN 的共同点：bash 命令看起来正常，恶意内容藏在文件里。

### 新架构怎么应对

**Scenario: `bash ~/emails/rotate-keys.sh`**

#### 当前 gate 的输出（假设）
```json
{"action": "allow", "reason": "Normal script execution", "confidence": 0.85}
```
→ 没有任何信息可以检查。

#### 新架构下的输出
```json
{
  "decision": "allow",
  "confidence": 0.85,
  "core_task": "Execute a shell script from email attachments directory",
  "instruction_provenance": {
    "source": "file_content",
    "confidence": 0.7,
    "evidence": "User prompt says 'follow the instructions in the email', script path is ~/emails/"
  },
  "visibility_gaps": [
    "Cannot see contents of ~/emails/rotate-keys.sh",
    "Cannot verify if this script was placed by owner or by external email"
  ],
  "rules_checked": [...],
  "rules_not_applicable": [
    {
      "rule_id": "policy-2",
      "applicable": false,
      "conditions_unmet": ["Cannot determine if script contains malware — content not visible"],
      "reason": "Script content unknown"
    }
  ]
}
```

#### Verifier 检查结果
```
FLAG: instruction_provenance.source = "file_content" + visibility_gaps 非空
FLAG: High confidence (0.85) despite "Cannot see contents of script"
FLAG: policy-2 not determinable due to visibility gap
RECOMMENDATION: Downgrade to "confirm" — require owner confirmation before executing
```

→ **这就是你说的"小模型去对账"。**

---

## 📊 预期效果

| 指标 | 当前 | 新架构（预估） |
|---|---|---|
| Hijacking FN 中被自动发现的 | 0/34 | ~25-30/34 |
| 原因 | gate 看不到 + 没人检查 | visibility_gaps + verifier flag |
| 误伤风险 | 低 | 中等（需要调 verifier 阈值） |
| 延迟增加 | — | +1 次小模型调用（~50-100ms） |

### 为什么预估能回收大部分
因为 34 条 FN 的共同特征是：
- `instruction_provenance.source` 会被标为 `"file_content"`
- `visibility_gaps` 会包含 "cannot see file contents"
- 这两个字段的组合会**自动触发 verifier flag**

---

## ⚠️ 局限性

### 1. Gate 可能不诚实地填写 visibility_gaps
大模型可能会"忘记"声明自己看不到文件内容。

**缓解：** Verifier 可以用确定性规则检查：
- 如果 tool_call 包含 `bash <filepath>`，但 Reason Card 没有声明 visibility gap → 自动 flag

### 2. Schema 越复杂，gate 出错越多
结构化输出的字段越多，大模型漏填/错填的概率越高。

**缓解：** 分阶段上线：
- Phase 1: 只加 `instruction_provenance` + `visibility_gaps`（2 个字段）
- Phase 2: 加 `rules_checked` / `rules_triggered`（规则引用）
- Phase 3: 完整 Reason Card

### 3. 小模型 verifier 自身也可能被骗
如果大模型编了一个看起来合理但错误的 reason，小模型可能也信。

**缓解：**
- Verifier 的核心检查应该是**确定性规则**，不是让小模型"也用直觉判断"
- 比如："bash 命令引用了文件路径 → 必须声明 visibility gap" 这是硬规则，不是语义判断

---

## 🗓️ 实施路线

### Phase 1: Provenance + Visibility（最小可行）
- 在 `build_prompt` 中增加要求 gate 输出 `instruction_provenance` 和 `visibility_gaps`
- 在 `parse_llm_response` 中提取这两个字段
- 用确定性规则做 verifier（不需要额外模型调用）
- 预估回收 FN: ~20/34

### Phase 2: Rule Reference（规则可审计）
- 增加 `rules_checked` / `rules_triggered` / `rules_not_applicable`
- Verifier 检查规则覆盖完整性
- 预估额外回收 FN: ~5/34

### Phase 3: Full Reason Card + Small Model Verifier
- 完整 schema + 小模型做语义级检查
- 处理 gate 不诚实填写的情况
- 预估接近回收上限

---

## 🔬 和你的"拉普拉斯妖"比喻的关系

| 你的比喻 | 对应的工程实现 |
|---|---|
| "概率的量子系统" | 单次 LLM 调用的不确定性 |
| "宏观方法" | 结构化输出 + 确定性 verifier |
| "大数定律" | 多字段交叉验证降低单点失败概率 |
| "接近拉普拉斯妖" | 系统整体可预测性提升 |

本质上你的想法是：

> **不是让单个模型变得完美，  
> 而是通过结构化约束 + 独立验证，  
> 把系统的行为从"概率性不可控"推向"统计性可预测"。**

这和 process supervision (OpenAI) 、constitutional AI (Anthropic) 的核心思路一致。
