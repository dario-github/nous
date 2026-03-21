# Section 5: Related Work — DRAFT v1

> CRAI 2026 Position Paper, Section 5 (~0.5 page, IEEE double-column)
> 写于 2026-03-21 03:03 CST
> Status: First draft

---

## 5. Related Work

**Monolithic LLM classifiers.** Llama Guard [cite-llamaguard] and ShieldGemma [cite-shieldgemma] fine-tune LLMs as safety classifiers, achieving strong results on standard benchmarks. However, they inherit the non-determinism and latency of LLM inference for *every* input, including trivially benign ones. More critically, they offer no formal guarantees — a model update can silently change safety behavior. Our semantic gate is conceptually similar but is invoked only for genuinely ambiguous cases (~30% of inputs), and its failures are bounded by the upstream Datalog layer.

**Rule-based frameworks.** NeMo Guardrails [cite-nemoguardrails] provides a Colang-based framework for constraining LLM outputs. NVIDIA's NemoClaw (GTC 2026 [cite-nemoclaw]) extends this to enterprise agent governance with declarative policy engines — architecturally homologous to our Datalog layer. These systems handle pattern-matching well but have a fundamental expressivity ceiling: they cannot reason about semantic intent. Our architecture uses them *where they excel* (Layer 1) while routing ambiguous cases to a semantic reasoner (Layer 3).

**Hybrid and validation approaches.** Guardrails AI [cite-guardrailsai] provides output validation (format, schema, toxicity) but does not compose deterministic and semantic layers with formal guarantees. The ARIS survey [cite-aris] catalogs current safety approaches and identifies the gap between rule-based and classifier-based methods — the exact gap our architecture addresses.

**Agent safety benchmarks.** AgentHarm [cite-agentharm] (ICLR 2025) provides the most comprehensive agentic safety benchmark to date, with 352 scenarios across 11 harm categories. Prior work on agent safety (Agents of Chaos [cite-agentsofchaos]) identifies three structural gaps — fake completion, PII leakage, and process TTL — that single-layer defenses cannot address. Our compositional approach provides independent coverage for each gap class.

**Industry convergence.** The past week alone saw six agent governance products launch or receive major funding: NemoClaw (NVIDIA), AI Gateway (ServiceNow), Oasis Security (\$120M Series B), AppViewX-Eos acquisition, Teleport Beams, and Kore.ai guardrails. Microsoft's 365 E7 tier (\$99/user/month) bundles agent security controls into enterprise SaaS. This signals a market transition from "agents need safety" as a research question to "agents need safety" as a product requirement — validating the practical relevance of composable safety architectures.

**Neurosymbolic foundations.** The composition of symbolic reasoning (Datalog) with neural semantics (LLM) connects to a broader neurosymbolic AI research program. Scallop [cite-scallop] demonstrates differentiable Datalog for learning from structured and unstructured data simultaneously. While our current implementation uses the symbolic and neural layers sequentially rather than differentiably, the Scallop direction suggests future architectures where the Datalog rules themselves could be *learned* from safety incidents.

---

## Notes for revision

- [ ] 需要确认所有引用的准确性（Llama Guard 是 Meta 2023? ShieldGemma 是 Google 2024?）
- [ ] NemoClaw 只有 GTC keynote 信息，没有 paper — 引用方式需确认（conference talk/blog?）
- [ ] ARIS survey 需要完整引用
- [ ] Agents of Chaos paper 引用
- [ ] 行业融资数据引用来源（VentureBeat? TechCrunch?）
- [ ] Scallop 引用：Li et al., NeurIPS 2023?
- [ ] 0.5 page 可能需要压缩——砍 industry convergence 段？但这是 position paper 的核心价值
- [ ] 考虑加入：Swiss Cheese Model 引用（已在 S4 提到），OpenAI Moderation API 对比
