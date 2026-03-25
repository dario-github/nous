# CRAI Paper — RSAC Week Related Work Additions (Draft)

> 03-21 夜间 heartbeat 准备。confirmed后再合入 main.tex。

## 新 BibTeX 条目

```bibtex
@misc{tokensecurity2026intent,
  title={Intent-Based Identity Security for Non-Human Identities},
  author={{Token Security}},
  year={2026},
  note={RSAC 2026 Innovation Sandbox Top 10 finalist. \url{https://www.token.security/}}
}

@report{gravitee2026agentsecurity,
  title={State of {AI} Agent Security 2026: When Adoption Outpaces Control},
  author={{Gravitee}},
  year={2026},
  url={https://www.gravitee.io/blog/state-of-ai-agent-security-2026-report-when-adoption-outpaces-control}
}

@misc{qualys2026mcpshadowit,
  title={{MCP} Servers Are the New Shadow {IT} for {AI}},
  author={{Qualys}},
  year={2026},
  url={https://blog.qualys.com/product-tech/2026/03/19/mcp-servers-shadow-it-ai-qualys-totalai-2026}
}
```

## Related Work 新增段落（建议插入 "Enterprise agent governance" 后）

```latex
\textbf{Runtime intent security.} The week of RSAC~2026 saw four fundamentally new
approaches to agent security ship simultaneously~\cite{tokensecurity2026intent},
marking a shift from role-based access control to intent-based authorization. A
key industry survey found that 25.5\% of deployed agents can spawn and instruct
sub-agents~\cite{gravitee2026agentsecurity}, rendering RBAC's static permission
model fundamentally inadequate for delegation chains. Meanwhile, MCP servers---the
emerging standard for agent-to-tool communication---have exceeded 10,000 active
public deployments with most enterprises having zero visibility into their
exposure~\cite{qualys2026mcpshadowit}. Our three-layer architecture addresses
these challenges through composable intent analysis (Layer~3 semantic gate) combined
with formal access control (Layer~1 Datalog rules), bridging the gap between static
policy and dynamic intent.
```

## 理由

1. **Token Security**: 最接近我们 Semantic Gate 的商业实现，引用它强化 "industry converging on intent-based security" 叙事
2. **Gravitee stat**: 硬数据支撑 "RBAC is dead for agents" 论点，25.5% delegation chain = 我们 Datalog 层的直接 use case
3. **Qualys MCP**: 攻击面量化（10k+ MCP servers），补充 Introduction 的 urgency 论述

## Discussion 可选新增（一句话）

在 "Multi-agent safety gaps" 段落末尾：
```
Industry data confirms the urgency: 25.5\% of deployed agents can spawn
sub-agents~\cite{gravitee2026agentsecurity}, creating delegation chains that
traditional access control cannot model.
```
