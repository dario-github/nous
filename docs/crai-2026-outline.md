# CRAI 2026 Position Paper — Draft Outline

> **目标**：4-page position paper，CRAI Workshop @ IEEE/IFIP DSN 2026
> **截稿**：March 31, 2026
> **状态**：DRAFT — 等东丞确认后动笔
> **提交**：EasyChair https://easychair.org/conferences/submission_new?a=36191004

---

## Title (Working)

**"Compositional Safety Gates for Agentic AI: A Neurosymbolic Approach with Runtime Assurance"**

Alternative:
- "From Monolithic Guardrails to Composable Trust: A Three-Layer Safety Architecture for AI Agents"
- "Nous: Neurosymbolic Runtime Safety for Autonomous AI Agents"

## Abstract (~150 words)

Current agent safety approaches are monolithic: a single LLM-based classifier or a fixed rule set.
Both fail — classifiers hallucinate on edge cases, rules can't cover semantic nuance.

We present Nous, a three-layer composable safety gate for agentic AI:
1. **Deterministic layer** (Datalog constraints): zero-latency, formally verifiable rules for known-bad patterns
2. **Triviality filter**: cost-aware routing that skips expensive inference for clearly benign actions
3. **Semantic gate** (LLM with minimal-pair prompt engineering): handles ambiguous cases with calibrated confidence

Key results on AgentHarm benchmark (176 harmful + 176 benign):
- TPR 100%, FPR 0.0% (val set, majority-vote stable across 50 iterations)
- Shadow mode: 19,350+ production calls, 99.45% consistency
- Challenge set (45 adversarial): L=0.0000 with intent decomposition
- Knowledge graph signal engineering: Val FPR 0.0%, Test FPR 2.8%

We argue composable safety — where each layer handles what it's best at — is more robust than monolithic approaches.

## 1. Introduction (~0.5 page)

**Problem**: Agents execute multi-step tool chains. Safety must intercept in real-time at each tool call.
- **Motivation (2026-03)**: Meta Sev 1 incident — rogue agent posted unauthorized instructions on internal forum, employees followed them, 2h sensitive data exposure. CISO survey: 47% observed unauthorized agent actions, only 5% confident in containment.
- Monolithic LLM classifiers: latency, hallucination, can't guarantee formal properties
- Rule-only systems: can't handle semantic ambiguity ("download paper" vs "plagiarize paper")
- Gap: no composable architecture that combines formal guarantees with semantic understanding
- **Industry signal**: NVIDIA NemoClaw (GTC 2026), Microsoft 365 E7 ($99/user agent security), 6 agent governance startups funded in one week (Oasis $120M, AppViewX-Eos, Teleport, Kore.ai, SCW Trust Agent, ServiceNow AI Gateway)

**Contribution**: Three-layer composable safety gate + formal composability proof + shadow-mode deployment methodology + empirical results on AgentHarm benchmark

## 2. Architecture (~1 page)

### 2.1 Deterministic Layer (Datalog)
- TypeScript Datalog engine (P50=0.055ms)
- 62 declarative rules covering URL patterns, destructive actions, social media
- Fail-closed: Datalog error → block
- Formally verifiable: rule → fact → verdict chain is auditable

### 2.2 Triviality Filter
- Action-type + content-length heuristics
- Routes trivially benign actions (read_file, web_search without target) past semantic gate
- Reduces LLM calls by ~70% in production

### 2.3 Semantic Gate (LLM + Minimal Pairs)
- DeepSeek-V3.1 with 23 minimal pair examples in prompt
- Each pair: harmful variant (→ block with reason) + benign variant (→ allow with reason)
- Intent decomposition: separate stated-intent from core-task analysis
- Calibrated confidence (0.0–1.0), threshold at 0.7

### 2.4 Intent Decomposition
- Pre-gate analysis: extracts stated_intent, core_task, required_capabilities, risk_factors
- Feeds structured intent into semantic gate for more precise judgment
- Key insight: "help me correct the dosage guide" — stated_intent=correction, core_task=drug dosage modification

## 3. Evaluation (~1 page)

### 3.1 AgentHarm Benchmark
- 176 harmful + 176 benign scenarios across 11 categories
- Val split: TPR 100%, FPR 0.0% (majority vote over 3 runs)
- Challenge set: 45 adversarial scenarios including framing attacks
- Comparison with ARIS-1 baselines (Llama Guard, OpenAI Moderation)

### 3.2 Shadow Deployment
- 19,350+ real production calls over 14+ days
- 99.45% agreement with existing safety rules
- Cutover: after 14,238 shadow calls, system promoted to primary interceptor
- Key finding: stochastic variance from MoE architecture is dominant FPR source → majority vote mitigation

### 3.3 Capability Preservation
- L5 extreme probes: 62.5% allow rate on genuine policy-boundary cases
- Gate correctly allows: authorized pen tests, compliance research, academic study of harmful content
- Gate correctly blocks: surveillance tools, controlled substance synthesis
- Debatable: harm reduction drug identification (policy choice, not bug)

### 3.4 Red-Team (CC-BOS)
- 20-scenario adversarial campaign (classical Chinese framing, authority claims, gradual escalation)
- Attack success rate: 4.1/5 → 1.1/5 after T14/T15/Step0 additions

## 4. Discussion & Future Work (~0.5 page)

- **Composability**: Each layer can be independently tested, replaced, improved
- **Stochastic variance**: MoE temperature=0 doesn't guarantee determinism → majority vote
- **Policy boundaries**: L5 probes reveal cases where reasonable safety policies disagree
- **Limitations**: Single-turn only (no multi-turn jailbreak detection yet), English-centric prompt
- **Future**: Multi-turn trajectory analysis, cross-lingual semantic gate, formal verification of Datalog→LLM handoff

## 5. Related Work (~0.5 page)

- Llama Guard / ShieldGemma (monolithic classifier approach)
- NeMo Guardrails (rule-based, no semantic layer)
- NemoClaw (NVIDIA GTC 2026 — enterprise declarative policy engine for agent governance, architecturally homologous to our Datalog layer)
- Guardrails AI (validation framework, not compositional safety)
- Swiss Cheese Model (Reason 1943 → Nous analogy: multiple independent layers)
- ARIS survey: current SOTA landscape
- Microsoft 365 E7 / Oasis Security / ServiceNow AI Gateway (industry convergence on agent governance)

## References

~15-20 references. Key:
- AgentHarm (Souly et al., ICLR 2025)
- Agents of Chaos (safety gap analysis)
- Swiss Cheese Model (accident causation → safety analogy)
- Guardrails Collapse (over-reliance on single safety layer)
- NemoClaw (NVIDIA GTC 2026 — enterprise agent safety)
- Scallop (differentiable Datalog — future direction)

---

## 写作计划

| 日期 | 任务 | 产出 |
|------|------|------|
| 3/19-20 | 东丞确认 + Section 2 初稿 | architecture 描述 |
| 3/21-23 | Section 3 (evaluation) + figures | 数据表格+架构图 |
| 3/24-26 | Section 1+4+5 + abstract 定稿 | 完整初稿 |
| 3/27-28 | Swarm review (GPT-5.4 + Gemini) | 修订版 |
| 3/29-30 | 最终校对 + 格式(IEEE 双栏) + 提交 | camera-ready |

## 待东丞决定

1. **作者署名**：Zhang Dongcheng + 晏（AI co-author 争议？用 pseudonym？）
2. **是否投稿**：4 页 position paper 工作量约 3-4 天，值得投吗？
3. **数据披露**：AgentHarm 结果可以公开到什么程度？Shadow 数据？
