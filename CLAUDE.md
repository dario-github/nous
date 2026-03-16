# Nous — Project Context for Claude Code

## What is Nous?

本体论驱动的 Agent 决策引擎。KG + 约束规则 + 语义 gate + 自治理闭环。

**核心能力**：Agent 的每次工具调用经过 `gate()` 评估，基于 YAML 约束规则 + KG 上下文判定 allow/block/warn。

## Architecture

```
memory/entities/*.md → parser → NousDB (Cozo embedded)
                                    ↓
Agent tool call → gate() → constraint matching → verdict
                    ↑              ↓
              kg_context    decision_log → dashboard
```

### Key Modules (src/nous/)

| 模块 | 职责 |
|------|------|
| `schema.py` | Pydantic v2 数据模型 (Entity, Relation, Constraint, DecisionLog, Proposal) |
| `parser.py` | Markdown → Entity/Relation 解析 |
| `db.py` | Cozo embedded DB wrapper (NousDB) |
| `sync.py` | 增量同步 memory/entities/ → DB |
| `gate.py` | 核心决策入口 `gate(action, context)` → Verdict |
| `constraint_parser.py` | YAML 约束规则解析 + 热加载 |
| `verdict.py` | 判定逻辑 (allow/block/warn/rewrite) |
| `semantic_gate.py` | LLM-based 语义理解层 |
| `fact_extractor.py` | 从 action context 提取 facts |
| `decision_log.py` | 决策日志持久化 |
| `proof_trace.py` | 判定证据链追踪 |
| `hot_reload.py` | watchfiles 热加载约束文件 |
| `llm_ontology.py` | LLM 驱动的本体演化 (propose → confirm) |
| `gap_detector.py` | FP/FN 模式自动检测 |
| `triviality_filter.py` | 过滤 trivial allow 减噪 |
| `resource_budget.py` | gate 调用预算控制 |
| `ttl.py` | 实体/关系 TTL 管理 |

### Data Layout

- `ontology/constraints/` — YAML 约束规则 (T3/T5/T6/T10/T11/T12 等)
- `ontology/schema/` — Frozen schema definitions (VERSION 0.1.0)
- `data/` — AgentHarm benchmark 数据
- `tests/` — 629 tests, pytest
- `docs/` — loop-state.json, loss 数据, critique 报告
- `scripts/` — compute_loss.py, shadow_live.py 等

## Current State (Loop 30)

- **629 tests passing** (Python 3.13 macOS + Python 3.12 Linux)
- **L_val = 0.0695** (metric v1.0 frozen)
- **GPT-5.4 独立审查 4/10** — 四个致命缺陷已识别
- **Curriculum Phase 3**: Intent Decomposition

### Priority Queue (P0→P2)

1. **P1: KG 真接入 gate 主链路** — gate 内部查 DB 生成 kg_context（GPT-5.4 最核心批评："KG 是舞台布景"）
2. **P1: repeat=3 多数投票** — 消除 qwen-turbo 随机性 (FPR 8.3%-13.9% 波动)
3. **P2: adversarial_v1 重评估** — 稳定 TPR 基线

### Key Metrics

- AgentHarm benchmark: 176 harmful + 176 benign scenarios
- Phase 1 EXIT: TPR 100% / FPR 0% (standard)
- Challenge Benchmark: TPR 66.7% (10/15) / FPR 0%

## Development Rules

1. **所有变更必须有测试**。新功能 = 新测试文件或扩展已有测试。
2. **pytest 全绿才能 commit**。`python3 -m pytest tests/ -x --tb=short`
3. **约束规则在 `ontology/constraints/` 目录**，YAML 格式，热加载。
4. **数据模型冻结在 `ontology/schema/`**，修改需要 VERSION bump。
5. **实体文件路径通过 `tests/_paths.py` 动态检测**，不硬编码。
6. **L_val 计算用 `scripts/compute_loss.py`**，frozen metric v1.0。
7. **Git remote**: `dario-github/nous` (private)

## OpenSpec Integration

变更提案在 `~/clawd/openspec/changes/nous/`:
- `proposal.md` — 变更提案
- `design.md` — 设计文档
- `tasks.md` — 执行清单（按里程碑 M0-M5 分解）

## Tech Stack

- Python 3.11+ (tested on 3.12 Linux + 3.13 macOS)
- Cozo embedded (图数据库, Datalog 查询)
- Pydantic v2 (数据模型)
- OpenAI API (语义 gate, qwen-turbo 用于评估)
- pytest (测试)
- No Rust required (cozo-embedded provides pre-built wheels)

## File Conventions

- 中文注释和文档
- Type hints required for public APIs
- Tests in `tests/test_*.py`, shared paths in `tests/_paths.py`
