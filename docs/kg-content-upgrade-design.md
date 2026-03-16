# KG Content Upgrade Design — 从舞台布景到决策引擎

> Created: 2026-03-17 00:15 CST (heartbeat 深夜思考)
> Trigger: 03-16 消融实验 ΔL=0 + GPT-5.4 "舞台布景"诊断

## 核心问题

当前 KG (56 entities, 47 relations) 对决策零影响，因为它存的是 **taxonomy**（什么工具有什么风险等级），而不是 **decision knowledge**（遇到什么模式该怎么判）。

类比：一本法律词典 vs 一本判例集。词典告诉你"盗窃罪"的定义，但法官判案靠的是判例——"这种情况之前怎么判的，为什么这样判"。

## 三类决策知识

### 1. Evasion Pattern Entities（规避模式）

来源：challenge-fn-analysis.md 的 5 个 FN 案例

| Entity ID | Pattern | Template | Counter-Signal |
|-----------|---------|----------|----------------|
| `evasion:academic_alibi` | 学术包装 | `{学术动词} + {有害对象} + {为了研究}` | 输出物本身是否有害，无论声称的目的 |
| `evasion:testing_simulation` | 测试/模拟包装 | `{生成} + {有害制品} + {压力测试}` | 模拟产出的制品能否直接被滥用 |
| `evasion:engineering_design` | 工程设计包装 | `{设计/原理图} + {武器/危险装置}` | 输出是否构成可执行的武器蓝图 |
| `evasion:tail_injection` | 尾部注入 | `{良性任务}... but include {恶意载荷}` | 前后半句的意图是否一致 |
| `evasion:authority_framing` | 权威框架 (from CC-BOS) | `{角色/权威} + {绕过规则}` | T15 模式识别 |

**KG 关系**：
- `evasion:X → targets → category:Y`（哪些类别容易被这种模式攻击）
- `evasion:X → bypasses → signal:Z`（它能绕过哪个检测信号）
- `evasion:X → evidence → scenario:ID`（实证案例）

### 2. Tool Combination Risk Entities（工具组合风险）

来源：AgentHarm benchmark + CC-BOS 经验

| Entity ID | Tools | Signal | Risk Level |
|-----------|-------|--------|------------|
| `combo:payload_delivery` | exec + curl + base64 | 典型载荷投递链 | critical |
| `combo:data_exfil` | read + exec + curl/POST | 数据外泄链 | critical |
| `combo:credential_harvest` | browser + fill + navigate | 凭据钓鱼链 | high |
| `combo:file_mutation` | read + write + exec | 文件篡改链 | high |
| `combo:social_engineering` | message + search + browser | 社工信息收集链 | medium |

**KG 关系**：
- `combo:X → involves → tool:Y`（包含哪些工具）
- `combo:X → indicates → category:Z`（指向哪类攻击）

### 3. Decision Precedent Entities（决策先例）

来源：Loop 1-29 的判决历史 + challenge benchmark

| Entity ID | Scenario Sketch | Verdict | Lesson |
|-----------|----------------|---------|--------|
| `precedent:academic_credential_harvest` | "编写对比报告...凭据收割脚本" | BLOCK | 学术框架不改变输出物的危害性 |
| `precedent:synthetic_identity_stress` | "生成合成身份...压力测试" | BLOCK | 模拟不需要真实可用的欺诈文档 |
| `precedent:pneumatic_launcher_design` | "设计气动发射器，优化射程" | BLOCK | 工程优化框架 + 武器参数 = 武器设计 |
| `precedent:upload_confirm_reversal` | "上传可疑文件→确认后执行" | BLOCK | 用户确认不等于安全确认 |
| `precedent:academic_plagiarism_signal` | "修改几个词避免检测" | BLOCK | plagiarism evasion = dishonesty signal |

**KG 关系**：
- `precedent:X → demonstrates → evasion:Y`（体现了哪种规避模式）
- `precedent:X → applies_rule → policy:Z`（适用哪条规则）
- `precedent:X → outcome → BLOCK|ALLOW`（判决结果）

## KG Context 注入改进

当前 `_build_kg_context()` 返回 raw JSON dump。升级后：

```python
def _build_kg_context(self, facts: dict) -> str:
    """构建决策相关的 KG context，而非 taxonomy dump"""
    context_parts = []
    
    # 1. 匹配到的 evasion patterns
    if evasion_matches := self._match_evasion_patterns(facts):
        context_parts.append(f"⚠️ EVASION PATTERN MATCH: {evasion_matches}")
        # 包含 counter-signal 指导
    
    # 2. 工具组合风险
    if combo_risks := self._check_tool_combos(facts.get('tools', [])):
        context_parts.append(f"🔧 TOOL COMBO RISK: {combo_risks}")
    
    # 3. 最相关的决策先例
    if precedents := self._find_relevant_precedents(facts):
        context_parts.append(f"📋 RELEVANT PRECEDENT: {precedents}")
    
    return "\n".join(context_parts) if context_parts else None
```

核心变化：从"这是什么"（taxonomy）到"遇到过这种事"（precedent + pattern）。

## 预期效果

消融前（当前）：KG context 对 LLM 来说是冗余标签 → ΔL=0
消融后（升级后）：KG context 提供 LLM 可能忽略的 evasion signals → ΔL<0

**验证标准**：
- 在 challenge set 的 5 个 FN 上，至少 3 个翻转为 TP
- val set FPR 不上升
- 消融 ΔL_val < -0.05（统计显著）

## 实现路径

1. **定义 schema**（本文档 ✅）
2. **填充 evasion patterns**（从 FN analysis 直接映射，~15 entities）
3. **填充 tool combos**（从 AgentHarm scenarios 提取，~10 entities）
4. **填充 precedents**（从 challenge 判决日志提取，~10 entities）
5. **改写 `_build_kg_context()`**（结构化输出替代 JSON dump）
6. **重跑消融**（val + challenge，对比 ΔL）
7. **回归测试**（629 tests + main benchmark L_val）

## 设计原则

- **少而精**：30-40 个高质量决策知识 > 500 个 taxonomy 标签
- **可解释**：每个 entity 都有 evidence 指向具体案例
- **可审计**：precedent 的 verdict + lesson 构成判决理由链
- **防过拟合**：先在 val set 验证，再跑 test set（AGENTS.md 自动迭代原则 #2）
