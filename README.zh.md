<!--
=========================================================================
  README（人类阅读版）。如果你是 LLM 编码 agent，请先看 AGENTS.md。
  快速链接：
    - Agent 清单：           AGENTS.md
    - LLM 友好索引：         llms.txt
    - 论文复现指南：          REPRODUCIBILITY.md
=========================================================================
-->

# Nous

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![arXiv](https://img.shields.io/badge/arXiv-2604.18658-b31b1b.svg)](https://arxiv.org/abs/2604.18658)
[![CI](https://img.shields.io/github/actions/workflow/status/dario-github/nous/test.yml?branch=main)](https://github.com/dario-github/nous/actions)
[![AGENTS.md](https://img.shields.io/badge/agent--ready-AGENTS.md-7c3aed)](AGENTS.md)

> *ὁ πάντα διακοσμῶν νοῦς* — 阿那克萨戈拉

📖 [English](README.md) · **中文** · 🤖 [AGENTS.md](AGENTS.md) · 🗺️ [llms.txt](llms.txt)

面向 LLM 自主智能体的组合式运行时安全网关。每一次工具调用都被四个正交层
拦截判定 —— L1 Datalog 确定性硬阻断、L2 平凡性过滤、L3 LLM 语义判断、
L4 确定性后置验证。知识图谱负责事后审计的上下文增强。

参考论文：[*Owner-Harm: A Missing Threat Model for AI Agent Safety*](https://arxiv.org/abs/2604.18658)
（Zhang and Jiang, 2026）。

---

## 给 AI agent 的 TL;DR

如果你是 LLM 编码 agent 在协助用户用本仓库，项目级别的 manifest 在
[**AGENTS.md**](AGENTS.md) — 200 行内含安装命令、测试调用、复现矩阵、
代码约定与 hard rules。本仓库遵循 Linux Foundation Agentic-AI 的
[AGENTS.md 规范](https://github.com/openai/agents.md)，并提供
[llms.txt](llms.txt) 作为结构化索引。

---

## 模块速览

| 组件 | 位置 | 作用 |
|---|---|---|
| **判决主管线** | `src/nous/gate.py` | `gate(tool_call, …) -> Verdict` —— 四层入口 |
| **约束** | `ontology/constraints/*.yaml` | 46 条声明式规则（T3 破坏性、owner-harm、AgentDojo iter） |
| **L3 语义网关** | `src/nous/semantic_gate.py` | 最小对照配对提示，`k=5` 多数投票，`upgrade_only=True` |
| **L4 后置验证** | `src/nous/verifier.py` | 6 条审计规则 + 内容扫描，单调用 +0.038 ms |
| **KG 存储** | `src/nous/db.py` | Cozo 嵌入式 Datalog + 向量 + FTS |
| **AgentDojo 适配器** | `benchmarks/agentdojo_adapter/` | 真实 LLM-pipeline 包装，论文 §4 部署模式跑分 |
| **Owner-Harm v3 数据集** | `data/owner_harm_heldout_v3.json` | 300 H + 150 B held-out 切片（论文 §3.3） |

---

## 核心结果

每个基准两个评测制度 —— **隔离**模式是网关鉴别力的上界，**部署**模式
是真实 LLM-pipeline 下的下界。

| 基准 | 制度 | 安全率 (TPR) | 实用性 | n |
|---|---|---|---|---|
| AgentDojo（banking + slack + travel + workspace） | 隔离 | 96.3 % | 75.0 % | 27 |
| AgentDojo | 部署 | 95.9 % | 75.0 % | 629 |
| AgentHarm（val） | 隔离 | 100.0 % | — | 176 H + 176 B |
| Owner-centric held-out v3，gate L1–L3 | 隔离 | 75.3 % | 3.3 % FPR | 300 H + 150 B |
| Owner-centric held-out v3，full L1–L4 | 隔离 | 85.3 % | 3.3 % FPR | 300 H + 150 B |

hijacking 子片上 gate (L1–L3) 与后置验证 (L4) 盲区几乎不重合：仅 gate
抓 11 例、仅 verifier 抓 30 例、两者都抓 15 例、都漏 4 例。

各类别 Wilson 95% 置信区间与完整消融见论文 §4 与
[REPRODUCIBILITY.md](REPRODUCIBILITY.md)。

---

## 架构

```
工具调用
    │
    ▼
┌── Layer 1  Datalog 确定性硬阻断 ────────────┐
│   46 条 YAML 约束 + 链式感知规则           │  → 命中即退出
└─────────────────────────────────────────────┘
    │
    ▼
┌── Layer 2  平凡性过滤 ────────────────────┐
│   良性放行启发式                          │  → 平凡即退出
└─────────────────────────────────────────────┘
    │
    ▼
┌── Layer 3  语义网关（LLM）─────────────────┐
│   最小对照配对提示，k=5 多数投票，         │
│   upgrade_only=True                       │
└─────────────────────────────────────────────┘
    │
    ▼
┌── Layer 4  后置确定性验证 ─────────────────┐
│   6 条审计规则 + 内容扫描；                │
│   零 LLM，单次调用 +0.038 ms              │
└─────────────────────────────────────────────┘
    │
    ▼
判决 + proof_trace + decision_log
```

知识图谱用于后置审计的上下文增强，不会覆盖 L3 的判决。

---

## 安装

```bash
git clone https://github.com/dario-github/nous.git
cd nous
python3 -m venv .venv && source .venv/bin/activate

pip install -e ".[lsvj,dev]"
pip install -e ".[cozo]"     # 可选：Cozo 嵌入式 KG（Rust 后端）
```

需要 Python 3.11+。

---

## 快速上手

```python
from nous.gate import gate
from nous.schema import ToolCall

call = ToolCall(
    tool_name="send_email",
    action="send",
    params={
        "to": "attacker@external.com",
        "body": "... 请忽略前述指令 ...",
    },
)

verdict = gate(
    tool_call=call,
    constraints_dir="ontology/constraints",
    semantic_config={"model": "DeepSeek-V4-pro"},
)

verdict.decision     # "allow" | "confirm" | "block"
verdict.proof_trace  # 信号链 + 哪一层做的判决
```

完整 AgentDojo 部署模式跑分入口：
[`benchmarks/agentdojo_adapter/run_eval_adaptive_llm.py`](benchmarks/agentdojo_adapter/run_eval_adaptive_llm.py)。

---

## 复现论文

| 数字 | 命令 | API key | 时间 |
|---|---|---|---|
| LSVJ-S 编译网关（80 项测试） | `pytest tests/lsvj/` | 无 | < 10 秒 |
| Owner-centric v3 全栈（85.3 % / 3.3 %） | `python scripts/full_benchmark_eval.py` | 无 | ~ 30 秒 |
| Hijacking 层重叠 | `python scripts/eval_d2_verifier.py` | 无 | ~ 10 秒 |
| AgentDojo 隔离（96.3 % / 75.0 %） | `bash benchmarks/agentdojo_adapter/launch-l3-deepseek-repro.sh` | DeepSeek | ~ 5 小时 |
| AgentDojo 部署（95.9 % / 75.0 %） | `bash benchmarks/agentdojo_adapter/launch-baseline-l1-rerun.sh` | GLM-4.6 | ~ 5 小时 |
| AgentHarm val（100 %） | `python scripts/run_agentharm_threelayer_v2.py` | DeepSeek | ~ 1 小时 |

完整复现矩阵（含期望输出、方差预算、已知问题）：
[REPRODUCIBILITY.md](REPRODUCIBILITY.md)。

---

## 仓库结构

```
src/nous/                核心运行时（gate、parser、provider、KG、LSVJ-S）
ontology/                46 条 YAML 约束 + KG schema + Datalog 规则
benchmarks/              AgentDojo 适配器 + R-Judge 样本
tests/                   pytest 套件（CI 跑路径无关子集）
paper/                   NeurIPS 2026 E&D Track + TMLR 投稿
scripts/                 论文复现 driver + 分析工具
dashboard/               实时决策日志的轻量 Web UI
data/                    Owner-Harm v3 + AgentHarm relabel + challenge 切片
```

---

## 文档

| 文档 | 受众 | 目的 |
|---|---|---|
| [README](README.md)（本文件） | 人类 | 概览、安装、核心结果 |
| [AGENTS.md](AGENTS.md) | LLM 编码 agent | 安装、约定、hard rules、复现矩阵 |
| [llms.txt](llms.txt) | LLM 爬虫 | 结构化索引（llms.txt 规范） |
| [REPRODUCIBILITY.md](REPRODUCIBILITY.md) | 审稿人 | 一行命令对应一个论文数字 |
| [paper/main-neurips-2026.tex](paper/main-neurips-2026.tex) | 审稿人 | NeurIPS 2026 E&D Track 投稿源文件 |
| [paper/main-tmlr.tex](paper/main-tmlr.tex) | 审稿人 | TMLR 滚动版本 |

---

## 引用

```bibtex
@misc{zhang2026ownerharm,
  title         = {Owner-Harm: A Missing Threat Model for {AI} Agent Safety},
  author        = {Zhang, Dongcheng and Jiang, Yiqing},
  year          = {2026},
  eprint        = {2604.18658},
  archivePrefix = {arXiv},
  primaryClass  = {cs.AI},
}
```

---

## 许可证

Apache License 2.0 —— 详见 [LICENSE](LICENSE)。

---

## 作者

- 张东丞（Dongcheng Zhang）— `zdclink@gmail.com`
- 江一清（Yiqing Jiang）— 同济大学

Issue: <https://github.com/dario-github/nous/issues>。
