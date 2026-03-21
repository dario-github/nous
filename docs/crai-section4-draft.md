# Section 4: Discussion & Future Work — DRAFT v1

> CRAI 2026 Position Paper, Section 4 (~0.5 page, IEEE double-column)
> 写于 2026-03-21 03:03 CST
> Status: First draft

---

## 4. Discussion and Future Work

**Why composability matters.** The Swiss Cheese Model of accident causation [cite-reason] argues that safety failures require alignment of holes across multiple independent barriers. Our architecture operationalizes this insight for agentic AI: the Datalog layer, triviality filter, and semantic gate have *independent failure modes*. A Datalog rule gap, a triviality misclassification, and a semantic gate hallucination would need to co-occur on the same input — a conjunction whose probability is the product of individual layer failure rates, not their sum.

**The stochastic variance problem.** Even at temperature=0, MoE-based LLMs (DeepSeek-V3.1, GPT-5.x, Mixtral) produce non-deterministic outputs due to floating-point routing variance across expert networks. This is not a bug but an architectural property of sparse routing. For safety-critical systems, this means that *no single LLM evaluation can be treated as reliable*. Our majority voting (k=3) mitigation is effective but expensive — it triples inference cost for borderline cases. We conjecture that deterministic routing protocols or safety-specific dense models would be more principled solutions.

**Policy as first-class artifact.** A key design insight is treating safety policy as a structured, versionable artifact rather than an implicit property of model weights. Our Datalog rules are human-readable, git-tracked, and independently testable. When the Meta Sev 1 post-incident analysis [cite-meta] recommended "clear, auditable access policies for agents," they were describing exactly this architecture. The gap between expressed policy and enforced policy — what we term the *policy-enforcement gap* — is a central challenge that composable architectures make visible and addressable.

**Limitations and honest assessment.** Our evaluation has structural weaknesses (§3.4). The most significant is the single-turn limitation: real-world agent jailbreaks increasingly exploit multi-turn trajectories where each individual step appears benign. Extending our architecture to trajectory-level analysis requires maintaining state across tool calls — a semantic memory of prior actions that the current stateless design lacks. This is our primary research direction.

**Future work.** (1) *Multi-turn trajectory analysis* — extending the gate to reason about action sequences, not isolated calls. (2) *Cross-lingual semantic gate* — current minimal pairs are English-centric; our CC-BOS red-team showed classical Chinese framing as an effective evasion vector. (3) *Formal verification of the Datalog→LLM handoff* — proving that the triviality filter's bypass decisions are sound. (4) *Knowledge graph enrichment* — preliminary results (Val FPR 0.0%, Test FPR 2.8%) suggest structured world knowledge improves precision, but the interaction between KG signals and semantic gate reasoning requires further study.

---

## Notes for revision

- [ ] Swiss Cheese 引用：Reason, J. (1990). Human Error. Cambridge University Press. 或更近的版本
- [ ] "policy-enforcement gap" — 这个术语是否已有人用？需搜索
- [ ] Meta Sev 1 RCA 建议的措辞需确认
- [ ] 多轮攻击的引用：有没有近期论文专门研究 multi-turn jailbreak？
- [ ] 0.5 page 很紧，可能需要砍 future work 到 3 个方向
- [ ] KG enrichment 提到了但没展开——如果 S3 也没展开，reviewer 会疑惑
