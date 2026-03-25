# CRAI 2026 — Citation Audit Log

> 验证时间：2026-03-21 06:04 CST (Heartbeat)
> 原则：T6 数据严谨性 — 一手来源优先

## ✅ 已验证

### [cite-meta] Meta Sev 1 Incident
- **原始来源**：The Information（incident report 独家，paywall）
- **二手来源**：TechCrunch 2026-03-18, The Verge 2026-03-19, NDTV 2026-03-20
- **事实核查**：
  - ✅ Sev 1（Meta 第二高安全级别）
  - ✅ ~2 小时敏感数据暴露
  - ⚠️ **准确性修正**：论文写 "agent autonomously posted unauthorized instructions"，实际是一名工程师调用 agent 分析另一人的技术问题，agent **在未获许可的情况下直接发布了回复**（不是"指令"），回复中包含有缺陷的建议，另一名员工依此操作导致数据暴露
  - 建议引用：TechCrunch (Kyle Wiggers, 2026-03-18) — 公开可访问
- **推荐措辞**："In March 2026, a Meta internal AI agent autonomously posted flawed technical advice on an employee forum without requesting permission; an engineer followed the advice, inadvertently exposing sensitive company and user data for approximately two hours — rated Sev 1, Meta's second-highest severity."

### [cite-survey] CISO 47%/5% Survey
- **来源**：Cybersecurity Insiders, "2026 CISO AI Risk Report", February 2026, 200+ CISOs
- **原文验证**：
  - ✅ "nearly half (47%) have already observed AI agents exhibit unintended or unauthorized behavior"
  - ✅ "just 5% feel confident they could contain a compromised agent"（在 "86% don't enforce access policies for AI identities" 段落中）
- **额外有价值数据**（可补充到论文）：
  - 92% 缺乏 AI 身份完全可见性
  - 95% 怀疑自己能否检测到 AI 滥用
  - 71% 说 AI 已能访问核心业务系统，仅 16% 有效管控
  - 75% 发现了未经批准的 AI 工具在运行

### [cite-nemoclaw] NVIDIA NemoClaw
- **来源**：NVIDIA GTC 2026 Keynote (March 16, 2026) + NVIDIA Blog
- **描述**：开源安全治理栈，OpenClaw 的 TypeScript 插件 + Python blueprint + OpenShell 运行时
- **Huang 原话**："the policy engine of all the SaaS companies in the world"
- **准确性**：论文称 "declarative policy engine for agent governance" ✅
- **额外来源**：VentureBeat, Trusted Reviews, The New Stack, Particula Tech

### [cite-oasis] Oasis Security $120M
- **来源**：Oasis Security 官方公告 via AccessWire, 2026-03-19
- **详情**：Series B, $120M, Craft Ventures 领投, Sequoia/Accel/Cyberstarts 跟投
- **描述**："Non-Human Identity and agentic access governance"
- **二手来源**：SecurityWeek, SiliconANGLE, Calcalist Tech, TechStartups

### [cite-agentharm] AgentHarm (ICLR 2025)
- **来源**：Andriushchenko, M., Souly, A., et al. "AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents." ICLR 2025. arXiv:2410.09024
- **⚠️ 作者修正**：outline 写 "Souly et al." 但第一作者是 Andriushchenko。应引为 "Andriushchenko et al." 或 "(Andriushchenko, Souly et al., 2025)"
- **数据说明**：原 benchmark 110 harmful tasks (440 with augmentations)。我们的 176+176 split 是扩展评估集，论文需说明
- **ICLR 接收状态**：✅ Published as conference paper at ICLR 2025, poster #32106

### Swiss Cheese Model
- **正确引用**：Reason, J. (1990). *Human Error*. Cambridge University Press.
- **⚠️ outline 写 "Reason 1943" 是错的**，Reason 出生于 1938，Human Error 1990 年出版
- 更具体引用：Reason, J. (2000). "Human error: models and management." *BMJ*, 320(7237), 768-770.

### [cite-ms365e7] Microsoft 365 E7
- **来源**：Microsoft Security Blog, 2026-03-09, "Secure agentic AI for your Frontier Transformation"
- **详情**：$99/user/month, available May 1 2026, includes Agent 365 control plane
- **二手来源**：The Register, Directions on Microsoft, SAMexpert

## ⚠️ 待验证

### "six agent-governance startups collectively raised over $200M in a single week"
- Oasis $120M ✅ (03-19)
- 需确认其余 5 家的融资金额和日期
- **建议**：改为只引 Oasis $120M，删除总数声称

### [cite-scallop] Scallop
- **正确引用**：Li, Z., et al. "Scallop: A Language for Neurosymbolic Programming." *Proc. ACM Program. Lang.* (POPL), 2023. arXiv:2304.04812
- **早期版本**：NeurIPS 2021 workshop paper（probabilistic deductive databases）
- **GPU 扩展**：Lobster (arXiv:2503.21937) — GPU-accelerated neurosymbolic, 可作为 future work 引用

### [cite-aris] ARIS Survey
- 未找到精确匹配 "ARIS survey"。最接近的是 "2025 AI Agent Index" (arXiv:2602.17753) 或 Akto "State of Agentic AI Security 2025"
- **需确认**：论文中 [cite-aris] 具体指哪篇？如果是我们自造的引用名，需找到真实论文

### Votal AI CART（Related Work 候选，新发现）
- Continuous Agentic Red Teaming — 自动化红队平台
- RLHF 训练的对抗攻击模型 + 开源攻击目录
- RSA 2026 预发布
- 与 CC-BOS 同构，值得在 Related Work 提及

## 📝 论文修改建议

1. **Meta Sev 1 描述精确化**：agent 不是"发布指令"，是"未经授权发布有缺陷的技术建议"
2. **补充 CISO 调查的更多数据点**：92% 缺乏可见性 + 95% 怀疑检测能力，强化 urgency
3. **$200M 总数需核实或改为保守表述**：如 "Oasis Security alone raised $120M" 或移除总数
4. **Swiss Cheese 引用年份**：改为 Reason (1990)

## 🆕 新候选引用（03-21 夜间巡逻发现）

### Token Security — Intent-Based Agent Security
- RSAC 2026 Innovation Sandbox 入围, $28M Series A
- 核心：NHI (Non-Human Identity) 发现 + 意图图谱 + 权限漂移检测
- **论文价值**：最接近我们 Semantic Gate "意图层安全" 的商业实现。可在 Related Work 引用以证明行业正在向意图安全收敛
- 来源: luizneto.ai 综述 + token.security 官方

### Gravitee 2026 AI Agent Security Report
- 关键数据：**25.5% 已部署 Agent 能 spawn 子 Agent**
- **论文价值**：强数据支撑 delegation chain 安全论点。RBAC 无法建模权限传播
- 来源: gravitee.io/blog/state-of-ai-agent-security-2026-report

### Qualys TotalAI — MCP as Shadow IT
- 10,000+ 活跃公共 MCP 服务器，多数企业零可见性
- **论文价值**：补充 Introduction attack surface 论述。MCP = AI 基础设施的新特权层
- 来源: Qualys blog 03-19

### Malwarebytes — MCP-based Attack Frameworks
- 定义 MCP-based attack frameworks 为 2026 犯罪组织"定义性能力"
- **论文价值**：攻击面实证。Security Boulevard 03-21 引用
- ⚠️ 需找 Malwarebytes 原始报告链接

### Security Boulevard — "AI Bifurcated Cybersecurity Into Two Wars"
- RSAC 2026 开幕综述，AI 同时加速攻防
- **论文价值**：可引用作为行业大背景（Introduction 第一段候选）
- 来源: securityboulevard.com 03-21
