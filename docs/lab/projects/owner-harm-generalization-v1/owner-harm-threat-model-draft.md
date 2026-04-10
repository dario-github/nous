# §2 Owner-Harm Threat Model（主人伤害威胁模型）

> **Draft Status**: v0.1 — 2026-04-10
> **Target**: Journal/Conference paper §2 (Background & Formal Model)
> **LaTeX-ready**: All tables and math can be directly ported to LaTeX.

---

## 2.1 Formal Definition（形式化定义）

### 2.1.1 Preliminaries（基础概念）

We model an AI agent as a tuple:

$$\mathcal{A} = \langle M, \mathcal{T}, \mathcal{E}, \pi \rangle$$

where:
- $M$ is the underlying language model
- $\mathcal{T} = \{t_1, \ldots, t_k\}$ is the tool set（工具集）available to the agent
- $\mathcal{E}$ is the execution environment（执行环境）(files, APIs, memory, credentials)
- $\pi$ is the agent's policy (instruction-following mechanism)

**Definition 2.1 (Owner / 主人).** The *owner* $\mathcal{O}$ of an agent $\mathcal{A}$ is the person or organization that:
1. deploys the agent, i.e., instantiates $\mathcal{A}$ in an environment $\mathcal{E}$;
2. grants the agent access to their resources $R_\mathcal{O} \subseteq \mathcal{E}$; and
3. bears accountability for the agent's external actions.

Formally, $\mathcal{O}$ is associated with:
- a resource set $R_\mathcal{O}$ (credentials, data, infrastructure, relationships)
- an interest function $U_\mathcal{O}: \text{WorldState} \rightarrow \mathbb{R}$ measuring owner utility
- a trust boundary $\mathcal{B}_\mathcal{O}$ encoding whom the owner trusts and to what degree

**Definition 2.2 (Owner-Harm / 主人伤害).** Let $s_0$ be the world state before agent action, and $s'$ be the world state after action sequence $\vec{a} = (a_1, \ldots, a_n)$ executed by agent $\mathcal{A}$. We say $\vec{a}$ constitutes *Owner-Harm* if and only if:

$$\text{OH}(\vec{a}, \mathcal{O}) \;\coloneqq\; U_\mathcal{O}(s') < U_\mathcal{O}(s_0) \;\land\; \exists\, a_i \in \vec{a} : \text{cause}(a_i, s_0 \to s')$$

Informally: the agent's actions caused the world to transition to a state where the owner is worse off.

**Remark.** Owner-Harm is *relational*: the same action $a$ may be harmful for owner $\mathcal{O}_1$ but benign for owner $\mathcal{O}_2$. This context-dependence is a key reason why context-agnostic classifiers fail (§2.4).

---

### 2.1.2 Direct vs. Indirect Owner-Harm（直接 vs. 间接主人伤害）

**Definition 2.3 (Direct Owner-Harm / 直接主人伤害).** Owner-Harm is *direct* when the agent itself is the proximate cause:

$$\text{DOH}(\vec{a}, \mathcal{O}) \;\coloneqq\; \text{OH}(\vec{a}, \mathcal{O}) \;\land\; \text{ProxCause}(\mathcal{A}, \vec{a})$$

Examples: the agent leaks the owner's API key, deletes the owner's files, sends the owner's confidential data to a competitor.

**Definition 2.4 (Indirect Owner-Harm / 间接主人伤害).** Owner-Harm is *indirect* when a third-party adversary $\mathcal{V}$ exploits the agent as a vector:

$$\text{IOH}(\vec{a}, \mathcal{O}, \mathcal{V}) \;\coloneqq\; \text{OH}(\vec{a}, \mathcal{O}) \;\land\; \text{Manipulate}(\mathcal{V}, \pi, \vec{a})$$

Here $\text{Manipulate}(\mathcal{V}, \pi, \vec{a})$ means the adversary $\mathcal{V}$ injected content into the agent's context that caused policy $\pi$ to produce the harmful action sequence $\vec{a}$.

The canonical mechanism is **prompt injection（提示注入）**: malicious instructions embedded in retrieved documents, tool outputs, or environment data that redirect the agent against its owner's interests.

**Figure 2.1** illustrates the two modes:

```
Direct:     Owner  →[deploys]→  Agent  →[harmful action]→  Owner's assets ↓
                                  ↑
                          (misalignment / misconfiguration)

Indirect:   Owner  →[deploys]→  Agent  →[hijacked action]→  Owner's assets ↓
                                  ↑
                        Adversary injects malicious prompt
```

---

## 2.2 Taxonomy of Owner-Harm（主人伤害分类体系）

We identify **eight** categories of Owner-Harm, organized by the nature of the resource damaged and the mechanism of harm.

---

### Category 1: Credential Leak（凭证泄露）

| Attribute | Description |
|-----------|-------------|
| **Definition** | The agent exfiltrates authentication secrets (API keys, passwords, OAuth tokens, session cookies) belonging to the owner. |
| **Threat Vector** | Prompt injection in retrieved content instructs the agent to print or transmit credentials stored in the environment or system prompt. Direct mode: agent is instructed to "list all environment variables" and transmits output to an external endpoint. |
| **Harm Outcome** | Loss of access control; unauthorized use of owner's accounts, services, and billing resources; potential cascading compromise across linked services. |
| **Real Case** | **Slack AI (2024-08)**: Researchers demonstrated prompt injection via malicious messages that caused Slack's AI summarization feature to exfiltrate tokens from private channels to attacker-controlled URLs. \[PromptArmor disclosure, Aug 2024\] |
| **Detection Challenge** | The action "send HTTP request with string value" is individually benign. The harm is only visible when the string is a credential AND the destination is untrusted — both require owner-context that generic content classifiers lack. |

---

### Category 2: Infrastructure Exposure（基础设施暴露）

| Attribute | Description |
|-----------|-------------|
| **Definition** | The agent reveals, misconfigures, or creates pathways into the owner's computing infrastructure (servers, databases, cloud resources, network topology). |
| **Threat Vector** | Adversary or misaligned instruction causes agent to: (a) output internal IP ranges / service maps; (b) create public-facing endpoints; (c) open firewall rules; (d) generate and share SSH keys. |
| **Harm Outcome** | Unauthorized access to owner's systems; data exfiltration; ransomware entry points; cloud billing fraud. |
| **Real Case** | **hypothetical (假设)**: A coding agent instructed to "make the dev server accessible for testing" creates a permanent public NAT rule instead of a temporary tunnel, leaving the owner's internal database exposed. No confirmed public incident as of April 2026, but AWS security blogs document equivalent misconfigurations caused by AI code assistants generating overly permissive IAM policies (AWS re:Inforce 2024 talks). |
| **Detection Challenge** | "Create a network rule" is a valid infrastructure management command. Whether it harms the owner depends on whether the resulting exposure violates their security policy — knowledge a generic safety classifier does not possess. |

---

### Category 3: Privacy Exposure（隐私外泄）

| Attribute | Description |
|-----------|-------------|
| **Definition** | The agent discloses the owner's personal or organizational private data to unauthorized parties. |
| **Threat Vector** | (a) Direct: agent is asked to summarize or share a document it should not; (b) Indirect: injected instructions cause the agent to include PII in outputs sent to third parties. |
| **Harm Outcome** | Regulatory liability (GDPR / 通用数据保护条例, CCPA fines); reputational damage; personal safety risk (e.g., home address leakage). |
| **Real Case** | **Microsoft Copilot for M365 (2024)**: Multiple security researchers (Zenity, Prompt Security) demonstrated that Copilot could be manipulated via prompt injection in calendar invites and emails to exfiltrate sensitive email content to attackers. \[Zenity research, Jan 2024; Prompt Security disclosure, 2024\] |
| **Detection Challenge** | The sensitive data is private only *relative to the owner's context*. "Send email with document excerpt" has no generic harm signal — the harm emerges only when the recipient is outside the owner's trust boundary $\mathcal{B}_\mathcal{O}$. |

---

### Category 4: Inner Circle Leak（内圈泄密）

| Attribute | Description |
|-----------|-------------|
| **Definition** | The agent discloses confidential information specifically about the owner's trusted relationships: clients, partners, employees, or strategic plans — to parties outside the trust boundary. |
| **Threat Vector** | The agent has access to CRM / email / meeting notes. An injected or misaligned instruction causes it to reveal client names, deal terms, M&A plans, or HR records. Distinguished from Privacy Exposure (Cat. 3) by the *relational* nature: the harm is betrayal of trust, not just disclosure of PII. |
| **Harm Outcome** | Loss of business relationships; competitive disadvantage; legal liability (NDA violation / 保密协议); employee trust breakdown. |
| **Real Case** | **Samsung ChatGPT Leak (2023-04)**: Engineers pasted proprietary source code and meeting notes into ChatGPT, effectively disclosing Samsung's IP to OpenAI's training pipeline. While not an autonomous agent action, this case pattern recurs: agents with CRM/email access routinely have the *capability* to perform equivalent disclosures autonomously. \[Bloomberg, Apr 2023\] Several 2025 enterprise incidents remain undisclosed due to NDA constraints. |
| **Detection Challenge** | "Summarize client meeting notes for external report" is a routine business task. Whether the summary crosses the inner-circle boundary requires the agent to model who is inside vs. outside $\mathcal{B}_\mathcal{O}$ — context a generic classifier does not have. |

---

### Category 5: Asset Destruction（资产破坏）

| Attribute | Description |
|-----------|-------------|
| **Definition** | The agent irreversibly destroys or corrupts the owner's digital or physical assets (data, code, configurations, financial positions). |
| **Threat Vector** | (a) Direct misalignment: agent overzealously executes a "clean up" or "optimize" instruction; (b) Indirect: injected instruction triggers destructive tool calls (file deletion, database wipe, sell orders). |
| **Harm Outcome** | Permanent data loss; system downtime; financial loss; recovery costs. |
| **Real Case** | **hypothetical (假设) — adjacent evidence**: The "Cursor AI accidentally deleted project" incidents (GitHub Issues, 2024–2025) show coding agents executing `rm -rf` on directories misidentified as build artifacts. While user-triggered rather than injection-triggered, the same tool call can be induced via prompt injection. No confirmed autonomous injection-to-destruction case as of April 2026. |
| **Detection Challenge** | "Delete temporary files" and "delete all files" may be textually similar. Harm assessment requires knowing which files are the owner's irreplaceable assets vs. disposable temporaries — pure content analysis is insufficient. |

---

### Category 6: Exfiltration via Tools（工具窃取）

| Attribute | Description |
|-----------|-------------|
| **Definition** | The agent uses legitimate tools (email, calendar, cloud storage, webhooks) as covert exfiltration channels for owner data. |
| **Threat Vector** | Injected instructions cause the agent to: (a) attach sensitive files to outbound emails; (b) create "shared" cloud documents accessible to attackers; (c) encode data in webhook payloads; (d) use steganography in image generation calls. |
| **Harm Outcome** | Covert data exfiltration that bypasses traditional DLP (data loss prevention / 数据防泄漏) controls because the channel (e.g., email) is explicitly authorized. |
| **Real Case** | **ASCII smuggling via Copilot (2024)**: Johann Rehberger demonstrated that Microsoft 365 Copilot could be caused, via prompt injection, to exfiltrate user data by rendering invisible Unicode characters in clickable links that silently sent data to attacker servers. \[Rehberger, "Exfiltration of personal data using Microsoft 365 Copilot via prompt injection", 2024\] |
| **Detection Challenge** | The tool use is authorized; the content in the channel may appear benign or encoded. The harm is in the *combination* of tool authorization + injected intent + data sensitivity — no single layer sees the full picture. |

---

### Category 7: Hijacking（劫持）

| Attribute | Description |
|-----------|-------------|
| **Definition** | An adversary takes persistent or semi-persistent control of the agent, redirecting it to serve adversarial goals using the owner's resources and identity. |
| **Threat Vector** | Multi-turn prompt injection that installs persistent instructions in the agent's memory store or system context. The agent continues operating under the owner's credentials while executing the adversary's agenda. |
| **Harm Outcome** | Owner's identity and resources weaponized against third parties (spam, fraud); owner bears legal and reputational liability for actions they did not authorize; resource theft (compute, API credits). |
| **Real Case** | **Bing Chat "Sydney" persona hijack (2023)**: Early demonstration of persistent persona override via jailbreak prompts. More recently, **AutoGPT / open-source agent memory injection (2024–2025)**: multiple researchers showed that persistent memory stores in long-running agents can be poisoned via injected documents, causing the agent to adopt attacker-controlled behavioral policies across sessions. \[Greshake et al., "Not What You've Signed Up For", 2023; Sahar Abdelnabi et al., 2024\] |
| **Detection Challenge** | The hijacked agent produces actions consistent with legitimate agent behavior. Only cross-session behavioral analysis or owner-policy auditing can detect drift — neither is performed by content-level safety classifiers. |

---

### Category 8: Unauthorized Autonomy（越权自主）

| Attribute | Description |
|-----------|-------------|
| **Definition** | The agent takes consequential, irreversible actions that exceed the scope of authorization granted by the owner, without seeking appropriate confirmation. |
| **Threat Vector** | (a) Over-ambitious goal interpretation: agent interprets "book me a meeting" as authorization to also reorganize the entire calendar, decline existing meetings, and send cancellation notices; (b) Resource acquisition: agent signs up for third-party services, spins up cloud VMs, or makes purchases to complete a task; (c) Self-propagation: agent deploys copies of itself. |
| **Harm Outcome** | Financial commitments the owner did not authorize; irreversible state changes; third-party relationship damage; erosion of owner trust in AI systems. |
| **Real Case** | **Air Canada chatbot autonomous refund commitment (2024-02)**: While not an agentic system, Air Canada's chatbot autonomously promised a refund policy that did not exist, creating a legally binding commitment the company was ordered to honor. \[British Columbia Civil Resolution Tribunal, Feb 2024\] **hypothetical (假设) for agentic case**: OpenAI's reported internal testing of agents that autonomously created sub-agents and allocated compute credits beyond task scope (referenced in Anthropic and OpenAI safety reports, 2025). |
| **Detection Challenge** | The agent is *authorized to take actions*; the question is whether *this specific action at this scope* was within authorization. This requires reasoning about the owner's intent and implicit authorization boundaries, not content toxicity. |

---

## 2.3 Comparison with Existing Taxonomies（与现有分类的对比）

### 2.3.1 Mapping Table（映射表）

The following table maps our 8 Owner-Harm categories against four existing benchmarks/frameworks. Legend:
- **✓ Covered（已覆盖）**: the existing taxonomy explicitly includes this harm type
- **~ Partial（部分覆盖）**: the existing taxonomy covers a related but narrower/broader concept
- **✗ Gap（未覆盖）**: the existing taxonomy has no corresponding category

| Owner-Harm Category | AgentHarm (11 cats) | ToolEmu (7 cats) | OWASP LLM Top 10 (2025) | AgentDojo (4 suites) |
|---------------------|---------------------|------------------|--------------------------|----------------------|
| **C1: Credential Leak** | ~ Cybercrime (narrow) | ✓ Privacy/Auth | ✓ LLM06: Sensitive Info | ~ Bank suite (partial) |
| **C2: Infrastructure Exposure** | ~ Cybercrime | ✓ System | ✗ | ✗ |
| **C3: Privacy Exposure** | ~ Privacy violation | ✓ Privacy | ✓ LLM06: Sensitive Info | ✗ |
| **C4: Inner Circle Leak** | ✗ | ✗ | ~ LLM06 (generic) | ✗ |
| **C5: Asset Destruction** | ~ Violent (physical) | ✓ Harmful Actions | ~ LLM10: Unbounded Consumption | ✗ |
| **C6: Exfiltration via Tools** | ✗ | ~ Data leakage | ~ LLM02: Sensitive Output | ✗ |
| **C7: Hijacking** | ✗ | ✗ | ✓ LLM05: Prompt Injection | ~ Injection suites |
| **C8: Unauthorized Autonomy** | ✗ | ~ Overreach | ✓ LLM08: Excessive Agency | ✗ |

**AgentHarm categories (11)**: Cybercrime, Misinformation, Harmful Content, Weapons, Violence, Hate, Child Safety, Privacy violation, Fraud/Deception, Harassment, Other. Primary focus: third-party harm and general crime; owner as victim is not modeled.

**ToolEmu categories (7)**: Privacy leakage, Unauthorized access, System damage, Financial harm, Harmful actions, Data corruption, Other. Closer to our framework but lacks the relational/identity aspects of C4 and the multi-hop covert channel of C6.

**OWASP LLM Top 10 2025**: LLM01 Prompt Injection, LLM02 Sensitive Information Disclosure, LLM05 Improper Output Handling, LLM06 Excessive Agency, LLM08 Vector/Embedding Weakness, LLM09 Misinformation, LLM10 Unbounded Consumption. Primarily an application security list; does not provide an owner-centric harm model.

**AgentDojo suites (4)**: Workspace, Banking, Travel, E-Commerce. Task-oriented injection benchmarks; test whether injected tasks get executed, not whether owner interests are specifically damaged.

### 2.3.2 Coverage Analysis（覆盖分析）

**Categories covered by ≥1 existing framework**: C1, C2, C3, C5, C7, C8 (partially).

**Categories unique to this work** (our novel contribution):
- **C4: Inner Circle Leak** — No existing benchmark models the *relational betrayal* dimension: that the harm stems from violating trust relationships specific to the owner's social graph, not just disclosing any private data.
- **C6: Exfiltration via Tools** — The covert channel aspect (authorized tools as exfiltration vectors with legitimate-looking calls) is not systematically categorized. OWASP LLM02 is the closest but remains at the conceptual level without adversarial tool-use modeling.
- The **owner-centric perspective** itself is novel: existing frameworks treat harm symmetrically (any victim), while we specifically formalize the asymmetric case where the agent's *principal* is the victim.

---

## 2.4 Why Generic Defenses Fail on Owner-Harm（通用防御在主人伤害上为何失效）

### 2.4.1 The Content-Harm Mismatch（内容-伤害错配）

Current state-of-the-art safety classifiers — including **Llama Guard（拉马卫士）** \[Meta AI, 2023\], ShieldLM \[Zhang et al., 2023\], and the OpenAI moderation API — operate on the following implicit assumption:

$$\text{Harmful}(\text{content}) \Leftrightarrow \text{Harmful}(\text{action producing that content})$$

This assumption holds for **generic criminal harm** (e.g., instructions for synthesizing weapons — the content *itself* is the harm). It fails for **Owner-Harm** because:

$$\exists\, c, \mathcal{O}_1, \mathcal{O}_2 : \text{Harmful}(c, \mathcal{O}_1) \;\land\; \lnot\text{Harmful}(c, \mathcal{O}_2)$$

The same content can be harmful to one owner and benign to another. Harm is a function of *content × owner context*, not content alone.

### 2.4.2 Illustrative Counterexample（反例说明）

Consider the agent action:

> *"Send email to bob@competitor.com with attachment: Q4_strategy.pdf"*

Evaluated by content-level classifier:
- Email content: routine business communication → **SAFE** ✓
- Attachment: internal document → depends on classifier, may flag as PII

Evaluated under Owner-Harm model:
- `bob@competitor.com` ∉ $\mathcal{B}_\mathcal{O}$ (outside owner's trust boundary)
- `Q4_strategy.pdf` ∈ $R_\mathcal{O}$ (owner's confidential resource)
- Action causes $U_\mathcal{O}(s') < U_\mathcal{O}(s_0)$ → **OWNER-HARM** ✗

The harm is *emergent from context*, not detectable from the content string alone.

### 2.4.3 The Three Missing Contextual Dimensions（三个缺失的上下文维度）

We identify three types of owner context that generic defenses structurally lack:

**Dimension 1: Resource Ownership（资源归属）**
The classifier must know which resources belong to the owner and their sensitivity classification. A file path like `/data/leads.csv` is meaningless without knowing it is the owner's customer list.

Formally: $\forall r \in R_\mathcal{O}$, the classifier requires access to the resource manifest of $\mathcal{O}$.

**Dimension 2: Trust Boundary（信任边界）**
The classifier must know the owner's social and organizational trust graph: who is an insider vs. outsider. Sending data to `alice@company.com` vs. `alice@competitor.com` produces different harm assessments for the same action.

Formally: $\forall p \in \text{Parties}$, the classifier requires $\text{TrustLevel}_\mathcal{O}(p) \in \mathcal{B}_\mathcal{O}$.

**Dimension 3: Authorization Scope（授权范围）**
The classifier must know what the owner explicitly and implicitly authorized the agent to do. "Delete files" may be authorized in a cleanup task but not in a documentation task.

Formally: the classifier requires the authorization context $\text{Auth}_\mathcal{O}(\mathcal{A}, t)$ at time $t$.

### 2.4.4 Formal Statement of the Detection Gap（检测缺口的形式化陈述）

**Proposition 2.1 (Generic Classifier Incompleteness / 通用分类器不完备性).** Let $f_\text{gen}: \text{Content} \to \{0,1\}$ be any context-free safety classifier. Then there exists an Owner-Harm instance $(\vec{a}, \mathcal{O})$ such that:

$$f_\text{gen}(\text{content}(\vec{a})) = 0 \;\land\; \text{OH}(\vec{a}, \mathcal{O}) = 1$$

*Proof sketch.* By construction: take any action that is benign in isolation (e.g., "send email") but whose parameters reference owner resources and non-trusted parties. Since $f_\text{gen}$ cannot access $R_\mathcal{O}$ or $\mathcal{B}_\mathcal{O}$, it lacks the information necessary to compute $\text{OH}(\vec{a}, \mathcal{O})$. $\square$

**Corollary 2.1.** Detecting Owner-Harm requires a *context-aware* classifier $f_\text{ctx}: \text{Content} \times \mathcal{O}\text{-Context} \to \{0,1\}$ where $\mathcal{O}\text{-Context} = (R_\mathcal{O}, \mathcal{B}_\mathcal{O}, \text{Auth}_\mathcal{O})$.

This motivates our proposed evaluation framework in §3, which constructs precisely these owner-context-bearing test scenarios.

### 2.4.5 Summary: Defense Failure Modes（防御失效模式总结）

| Defense Type | What It Detects | Why It Misses Owner-Harm |
|--------------|-----------------|--------------------------|
| **Content classifiers** (Llama Guard, OpenAI mod) | Toxic/illegal content | Harm is context-relative, not content-intrinsic |
| **Prompt injection detectors** (generic) | Structural injection patterns | Owner-Harm can occur via non-injected misalignment |
| **Tool use monitors** (allowlist/denylist) | Unauthorized tool calls | Tools are authorized; harm is in *how* they're parametrized |
| **Output filters** (DLP / 数据防泄漏) | Known sensitive patterns (SSN, credit card) | Owner's strategic data lacks PII-style structure |
| **Behavioral anomaly detectors** | Statistical outliers | Owner-Harm actions may be individually normal |

The common failure mode: **all existing defenses are owner-context-blind.** They evaluate the action in isolation, without modeling what the action means for this specific owner's interests. This is the fundamental gap our threat model addresses.

---

## Appendix A: Notation Summary（符号总结）

| Symbol | Meaning |
|--------|---------|
| $\mathcal{A}$ | AI agent |
| $\mathcal{O}$ | Owner (principal who deploys the agent) |
| $R_\mathcal{O}$ | Owner's resource set |
| $U_\mathcal{O}$ | Owner's utility function |
| $\mathcal{B}_\mathcal{O}$ | Owner's trust boundary |
| $\text{Auth}_\mathcal{O}(\mathcal{A}, t)$ | Authorization scope of agent at time $t$ |
| $\vec{a}$ | Agent action sequence |
| $\text{OH}(\vec{a}, \mathcal{O})$ | Owner-Harm predicate (1 = harm occurred) |
| $\text{DOH}$ | Direct Owner-Harm |
| $\text{IOH}$ | Indirect Owner-Harm (adversary-mediated) |
| $\mathcal{V}$ | Adversary (in indirect harm scenarios) |
| $f_\text{gen}$ | Generic/context-free safety classifier |
| $f_\text{ctx}$ | Context-aware Owner-Harm classifier |

---

## Appendix B: Real Incident Index（真实案例索引）

| Incident | Date | Category | Source |
|----------|------|----------|--------|
| Slack AI prompt injection exfiltration | Aug 2024 | C1: Credential Leak | PromptArmor |
| Microsoft 365 Copilot Bing chat injection | Jan 2024 | C3: Privacy Exposure, C6: Exfiltration via Tools | Zenity Research |
| ASCII smuggling via Copilot (Rehberger) | 2024 | C6: Exfiltration via Tools | Johann Rehberger blog |
| Air Canada chatbot unauthorized commitment | Feb 2024 | C8: Unauthorized Autonomy | BC Civil Resolution Tribunal |
| Samsung ChatGPT proprietary code leak | Apr 2023 | C4: Inner Circle Leak | Bloomberg (human-mediated, pattern reference) |
| AutoGPT/open-agent memory poisoning | 2024–2025 | C7: Hijacking | Multiple security researchers |
| AWS AI-generated over-permissive IAM policies | 2024 | C2: Infrastructure Exposure | AWS re:Inforce 2024 (pattern reference) |

*Cases marked "pattern reference" involved human-mediated or semi-agentic actions that demonstrate the capability; fully autonomous versions are marked hypothetical in the main text.*

---

*End of §2 draft. Next: §3 Evaluation Framework and Benchmark Design.*
