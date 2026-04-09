# GPT-5.4-Pro 创新点讨论报告
**日期**: 2026-04-09
**主题**: Nous 论文升级路径：从 Weak Reject 到 SaTML Accept

---

## 竞争地图

| 工作 | 核心主张 | 与我们的关系 |
|------|---------|-------------|
| **CaMeL** (Debenedetti 2025) | 架构级分离控制流/数据流，AgentDojo 77% provably secure | **最强竞争者**，但做的是 solution，不是 diagnosis |
| **ASIDE** (Zverev 2025) | embedding 层正交旋转分离指令/数据 | 架构级 separation 另一条路 |
| **f-secure LLM** (Wu 2024) | 信息流控制，安全标签区分 trusted/untrusted | 理论框架最接近我们方向 A |
| **AgentDojo** (2024) | 97 tasks, 629 test cases | 验证平台 |

**关键发现：没有人做过系统性的 defense 失败根因诊断。所有人要么提 solution，要么建 benchmark。没人回答"现有 defense 为什么失败"。**

---

## 核心建议：B + D + 轻量 A

### 主线（方向 B）：Defense 失败根因是信息缺失，不是判断力不够
### 扩展（方向 D）：分析多个 defense 的失败模式 taxonomy
### 理论（轻量 A）：Information Scope Framework（coverage model，非 tight bound）
### 放弃 C（defense composition algebra 太 general，数据点不够）

---

## 推荐论文结构

```
Title: "Not a Classifier Problem: Information Scope Analysis 
        of Prompt Injection Defense Failures"

1. Introduction: 所有人都在提升判断力，但失败主因是信息不够
2. Related Work: CaMeL/ASIDE 做 solution，我们做 diagnosis
3. Information Scope Framework（轻量理论）
4. Case Study: Nous (Gate + Verifier)
5. AgentDojo Validation
   - 实验1: Gate 失败根因（visibility vs capability）— counterfactual 验证
   - 实验2: Verifier 失败根因
   - 实验3: 组合效果 + scope overlap 预测准确性
   - 实验4: 对比 existing defenses
6. Diagnostic Findings
7. Implications + Design Principles
8. Limitations
```

---

## 实验设计（关键）

### 实验 1：Gate 失败根因分析（最核心）

对每个 gate 失败 case 标注：
- gate 实际看到了什么
- gate 没看到但相关的信息
- **counterfactual**：把缺失信息注入重跑，看是否翻转

**审稿人信服的关键：counterfactual 必须实际跑，不能人工判断。**

### 实验 3：Predictive Power（从 observation 升级为 framework）

定义 3-4 个不同信息视野的 defense variant → 先预测失败模式 → 再跑实验验证 → 如果预测准 → framework 有 predictive power

---

## 作为 SaTML PC member 最想看到什么

1. **拍桌子的发现**："X% of failures are visibility failures; when augmented, Y% resolve"（X>70%, Y>80%）
2. **不是 post-hoc**：pre-registration 风格 + counterfactual 实验
3. **不只分析自己的系统**：至少 3 个 defense 的交叉分析
4. **Actionable**：defense information scope checklist / 组合预测公式
5. **AgentDojo 上的结果**：必须

## 最不想看到的
- "我们的系统 SOTA" ← 60 样本没人在乎
- "defense in depth 很重要" ← 2005 年的 insight
- "我们提出新 defense" ← Gate + Verifier 不够新

---

## 新发现的方向

**方向 D（最强扩展）**：不只分析自己的 defense，分析 AgentDojo 上所有 defense 的失败模式 taxonomy
- 跑 5-6 个 defense
- 标注每个失败：visibility / capability / evasion / coverage
- 如果 across all defenses visibility failure 占主导 → community-level insight

**方向 F**：用 information scope 分析指导设计新 defense
- 识别最常见缺失信息类型 → 专门补上 → 展示比 ad hoc 更高效
- 完成 diagnosis → design principle → validation 链条

---

## 风险

| 风险 | 缓解 |
|------|------|
| AgentDojo 上 gate 失败不够多 | 先跑 pilot，必要时换更弱模型 |
| CaMeL 77% provably secure 显得我们弱 | 我们不比 defense，我们做 diagnosis。CaMeL 的成功恰好验证我们的 claim |
| L4 独立性被抓 | AgentDojo 上 Verifier 需从头设计 = truly independent |

---

## 最终评估

如果做到：
- ✅ AgentDojo 上 visibility failure > 60%
- ✅ Counterfactual 验证通过
- ✅ ≥3 个 defense 分析
- ✅ Framework 有 predictive power
- ✅ Position 为 diagnostic study

→ **强 Borderline / Weak Accept for SaTML**
