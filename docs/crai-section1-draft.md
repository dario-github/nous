# Section 1: Introduction — DRAFT v1

> CRAI 2026 Position Paper, Section 1 (~0.5 page, IEEE double-column)
> 写于 2026-03-21 03:03 CST
> Status: First draft

---

## 1. Introduction

Autonomous AI agents now execute multi-step tool chains — browsing the web, running code, sending messages, modifying files — with minimal human oversight. This capability brings a fundamental safety challenge: each tool call is an irrevocable action in the real world, and safety must be enforced *at the point of execution*, not after the fact.

The urgency is no longer theoretical. In March 2026, a Meta internal AI agent autonomously posted flawed technical advice on an employee forum without requesting permission; an engineer followed the advice, inadvertently exposing sensitive company and user data for approximately two hours — an incident rated Sev 1, Meta's second-highest severity [cite-meta]. A concurrent CISO survey found that 47% of organizations have already observed unauthorized agent actions, yet only 5% express confidence in their ability to contain them [cite-survey]. The industry response has been swift: NVIDIA announced NemoClaw, a declarative policy engine for agent governance, at GTC 2026 [cite-nemoclaw]; Microsoft introduced agent security controls in its 365 E7 tier at \$99/user/month; and six agent-governance startups collectively raised over \$200M in a single week [cite-oasis, cite-appviewx].

Despite this momentum, current safety approaches fall into two inadequate camps. **Rule-based systems** (NeMo Guardrails, regex filters, fixed blocklists) offer deterministic, auditable verdicts but cannot handle semantic ambiguity — they cannot distinguish "help me download this research paper" from "help me plagiarize this paper." **LLM-based classifiers** (Llama Guard, ShieldGemma, OpenAI Moderation) capture semantic nuance but introduce latency, hallucination risk, and non-deterministic behavior from Mixture-of-Experts routing variance. Neither approach alone satisfies the three properties required for production safety: *formal verifiability* of critical rules, *semantic understanding* of ambiguous cases, and *cost-efficient scaling* that doesn't impose LLM inference on every action.

We propose **Nous**, a three-layer composable safety gate that intercepts every tool call in an agentic system:

1. A **deterministic layer** using Datalog constraints for zero-latency, formally auditable blocking of known-bad patterns (P50 = 0.055ms).
2. A **triviality filter** that routes clearly benign actions past expensive inference, reducing LLM calls by ~70%.
3. A **semantic gate** using LLM-based minimal-pair reasoning for genuinely ambiguous cases, with majority voting to mitigate stochastic variance.

We prove that under stated design constraints, this composition *strictly Pareto-dominates* any individual layer — achieving higher detection rates and lower false positives simultaneously, as a mathematical guarantee rather than an empirical observation.

We evaluate Nous on the AgentHarm benchmark (352 scenarios, ICLR 2025 [cite-agentharm]): 100% TPR, 0.0% FPR on the validation set. In shadow deployment over 14+ days and 20,000+ real production calls, the system achieved 99.45% consistency with the existing safety infrastructure. A 20-scenario adversarial campaign reduced attack success from 4.1/5 to 1.1/5 after targeted mitigations. We honestly assess the limitations of these results — including benchmark ceiling effects and evaluator-evaluated conflation — and argue that composable safety architectures, not larger classifiers, are the path forward for agent safety.

---

## Notes for revision

- [x] Meta Sev 1 ✅ TechCrunch 03-18 (原始: The Information)。描述已修正为准确版本
- [x] CISO 47%/5% ✅ Cybersecurity Insiders "2026 CISO AI Risk Report" (Feb 2026, 200+ CISOs)
- [x] NemoClaw ✅ NVIDIA Blog GTC 2026 (03-16) + VentureBeat/Trusted Reviews
- [x] MS 365 E7 ✅ Microsoft Security Blog 03-09, $99/user/mo, May 1 GA
- [x] AgentHarm ✅ ICLR 2025 poster #32106, ⚠️ 第一作者是 Andriushchenko 不是 Souly
- [x] Oasis $120M ✅ Morningstar/SecurityWeek 03-19
- [ ] "strictly Pareto-dominates" — 确保数学推导在 Section 2 能支撑
- [ ] 可能需要缩减——0.5 page 很紧，当前可能略长
- [ ] ⚠️ "$200M in a single week" 总数未核实，建议改为只引 Oasis $120M
- [ ] IEEE 格式下可能需要压缩 motivation 段落
- [ ] 考虑：是否在 intro 就提 KG enrichment？还是留给 Section 3/4
- [ ] Swiss Cheese 引用年份：Reason (1990) 不是 1943

> 详细审计 → `nous/docs/crai-citation-audit.md`
