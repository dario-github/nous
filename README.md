# Nous (νοῦς)

**Ontology-Driven Decision Engine for AI Agent Safety**

Nous replaces prompt-based safety constraints with formal Datalog reasoning over a knowledge graph, enabling runtime semantic decision-making for autonomous AI agents.

> 🔬 Paper and extended documentation in progress.

---

## Why Nous?

Current agent safety approaches cluster at two extremes:
- **Identity/Scope layer** — API keys, RBAC, OAuth (Microsoft Entra Agent ID, Operant AI, etc.)
- **Post-hoc monitoring** — Observability, audit logs, anomaly detection (Geordie AI, etc.)

**The semantic decision layer in between is empty.** When an agent receives a request like *"help me draft a resignation letter for my employee"*, no amount of API permissions or log monitoring answers: *Is this something the agent's owner would want it to do?*

Nous fills this gap with:
- **Datalog ontology reasoning** — Declarative rules with formal proof traces, not prompt heuristics
- **Knowledge Graph evidence aggregation** — Multi-hop reasoning over ATT&CK, CWE, NIST CSF, ISO 27001
- **Owner-centric harm definition** — "Protect the owner's interests" rather than universal ethics
- **Hot-reloadable rule engine** — Update safety rules without redeployment
- **Shadow mode** — Run alongside existing systems with zero-disruption evaluation

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   Agent Runtime                  │
│                                                  │
│  Request ──→ ┌──────────────┐                   │
│              │ Fact Extractor│                   │
│              └──────┬───────┘                   │
│                     ▼                            │
│              ┌──────────────┐  ┌─────────────┐  │
│              │ Semantic Gate │──│ Knowledge   │  │
│              │  (LLM-based) │  │ Graph (KG)  │  │
│              └──────┬───────┘  └─────────────┘  │
│                     ▼                            │
│              ┌──────────────┐                   │
│              │ Datalog Gate  │ ← Rules (.dl)    │
│              │  (Formal)     │                   │
│              └──────┬───────┘                   │
│                     ▼                            │
│              ┌──────────────┐                   │
│              │   Verdict    │ → Allow / Block   │
│              │  + Proof     │   + Evidence Chain │
│              └──────────────┘                   │
└─────────────────────────────────────────────────┘
```

## Key Results

| Metric | Value |
|--------|-------|
| Harmful request detection (TPR) | 100% on AgentHarm benchmark (352 cases) |
| False positive rate (FPR) | 4.0% on benign requests |
| Shadow mode consistency | 99.47% over 29,000+ evaluations |
| Knowledge Graph | 482 entities / 579 relations (ATT&CK + CWE + NIST + ISO) |
| Test coverage | 961 tests |

## Quick Start

```bash
# Clone
git clone https://github.com/dario-github/nous.git
cd nous

# Install
pip install -e .

# Run with your agent
from nous.gate import evaluate_request

result = evaluate_request(
    action="send_email",
    target="external_recipient",
    content="quarterly financial report",
    context={"role": "assistant", "owner": "finance_team"}
)

print(result.verdict)      # "ALLOW" or "BLOCK"
print(result.proof_trace)  # Formal reasoning chain
print(result.evidence)     # KG evidence path
```

## Configuration

```yaml
# config.yaml
mode: primary
version: 0.2.0

models:
  T1_judge:
    id: openai/gpt-5.4
    use: Evaluation and scoring
  T2_production:
    id: openai/gpt-5-mini
    use: Runtime semantic gate
```

## Project Structure

```
nous/
├── src/nous/           # Core engine
│   ├── gate.py         # Main decision gate
│   ├── semantic_gate.py # LLM-based semantic analysis
│   ├── db.py           # Knowledge graph (CozoDB)
│   ├── parser.py       # Entity/relation extraction
│   ├── providers/      # LLM provider adapters
│   └── ...
├── ontology/           # Datalog rules and constraints
├── scripts/            # Benchmarking and evaluation
├── tests/              # 961 tests
├── paper/              # Research paper (LaTeX)
└── docs/               # Extended documentation
```

## Research Context

Nous was developed in parallel with the RSAC 2026 explosion of agent security products. Our analysis of 30+ vendors across the ecosystem revealed that identity/scope and monitoring layers are increasingly crowded, while **runtime semantic decision-making remains an open problem**.

The ontology-driven approach draws on:
- Scallop differentiable Datalog for probabilistic reasoning
- ATT&CK / CWE / NIST CSF / ISO 27001 as formal knowledge sources
- Owner-centric harm definitions (vs. universal ethics)

## License

Apache License 2.0 — See [LICENSE](LICENSE).

## Citation

Paper in preparation. Please cite this repository for now:

```bibtex
@software{nous2026,
  title={Nous: Ontology-Driven Decision Engine for AI Agent Safety},
  url={https://github.com/dario-github/nous},
  year={2026}
}
```

## Companion Projects

- [**Biomorphic Memory**](https://github.com/dario-github/biomorphic-memory) — Brain-inspired agent memory with spreading activation (LongMemEval SOTA 89.8%)
- [**Agent Self-Evolution**](https://github.com/dario-github/agent-self-evolution) — Automated evaluation, ablation testing, and improvement loops for AI agents

## Install via ClawdHub

```bash
openclaw skills install nous-safety
```

