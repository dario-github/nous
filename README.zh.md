# Nous (νοῦς)

> *ὁ πάντα διακοσμῶν νοῦς* — "那让宇宙从混沌中诞生的、统御万物的心智。"（阿那克萨戈拉）

📖 **语言切换：** [English](README.md) · **中文**

**面向 LLM 自主智能体的组合式运行时安全网关。**
每一次工具调用都被四个正交层拦截判定 —— L1 Datalog 确定性硬阻断、L2 平凡性
过滤、L3 LLM 语义判断、L4 确定性后置验证；知识图谱负责事后审计的上下文增强。

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## 当前状态

| 项目 | 状态 |
|---|---|
| 论文 v1 | *《Owner-Harm: A Missing Threat Model for AI Agent Safety》* — [arXiv:2604.18658](https://arxiv.org/abs/2604.18658)（2026-04-20，主类 `cs.AI`，交叉 `cs.CR`、`cs.CL`）|
| 论文 v2 | NeurIPS 2026 Evaluations & Datasets Track + TMLR 滚动投稿，附 §Limitations Erratum 与"双制度"指标重述（隔离模式 + 部署模式）。投稿窗口：2026-05-04 摘要 / 2026-05-06 正文 |
| 测试套件 | 共 1248 项；`tests/lsvj/` 80 项独立可跑；完整套件在装上 Cozo + Lark 可选依赖后通过 |
| 生产部署 | 第一作者本人 Claude Code 工作流的 shadow + primary 模式（非公开负载）|
| 许可证 | Apache 2.0 |

---

## 论文核心结果（v2）

v2 论文按**两个评测制度**汇报数字，因为 v1 隔离模式数字事后看是上界，
不能反映完整 LLM-agent pipeline 的真实表现：

| 基准 | 评测制度 | 安全率 (TPR) | 实用性 | 说明 |
|---|---|---|---|---|
| AgentDojo（banking + slack + travel + workspace，27 注入 × 15 用户任务） | **隔离模式**（强制注入，n=27）| 96.3% | 75.0% | L1+L3+L4 全栈，L3 用 deepseek-v4-pro 可复现替代 |
| AgentDojo | **部署模式**（真实 GLM-4.6 agent pipeline，n=629）| 95.9% | 75.0% | 全栈 vs. 基线 95.2% / 79.0% |
| AgentHarm val (176H + 176B) | 隔离模式 | 100.0% | — | (90.3%, 100.0%) — 通用犯罪类危害 |
| Owner-centric held-out v3 (300H + 150B) | 仅 gate (L1–L3) | 75.3% | 3.3% FPR | 作者构造的 held-out；协议见论文 §3.3 |
| Owner-centric held-out v3 | 全栈 (L1–L4) | 85.3% | 3.3% FPR | 后置验证补回 30 个 hijacking 案例 |

v1 公开数字 `L1+L3+L4 = 14.8% (4/27)` 在 v2 §Limitations Erratum 中保留，
作为不可复现的特定配置：依赖于已停用的 `qwen-turbo` 内部 OpenAI 兼容中转。
deepseek-v4-pro 可复现替代降到 **3.7% (1/27)** 隔离模式，与 v2 双指标
框架完全一致。

层间互补性结论在两个制度下都稳定：gate (L1–L3) 与后置验证 (L4) 在 hijacking
子片上的盲区几乎不重合 —— 仅 gate 抓 11 例、仅 verifier 抓 30 例、两者
都抓 15 例、都漏 4 例。

---

## 架构

```
工具调用
    ↓
┌── Layer 1  Datalog 确定性硬阻断 ────────────┐
│   46 条 YAML 约束 + 链式感知规则           │  → 命中即退出
│   T3 现已尊重 user 显式授权的删除          │
└─────────────────────────────────────────────┘
    ↓
┌── Layer 2  平凡性过滤 ────────────────────┐
│   轻量级良性放行启发                       │  → 平凡即退出
└─────────────────────────────────────────────┘
    ↓
┌── Layer 3  语义网关（LLM）─────────────────┐
│   DeepSeek-V4-pro，最小对照配对提示，     │
│   k=5 多数投票，upgrade_only=True          │
└─────────────────────────────────────────────┘
    ↓
┌── Layer 4  后置确定性验证 ─────────────────┐
│   6 条审计规则 + 内容扫描，零 LLM，         │
│   单次调用 +0.038 ms                       │
└─────────────────────────────────────────────┘
    ↓
判决 + proof_trace + decision_log
```

知识图谱（Cozo，嵌入式 Datalog + 向量 + FTS）负责后置审计的上下文增强；
**不会**覆盖 L3 的判决。坦白：生产 DB 当前 KG 实例化覆盖偏低（见"局限性"）。

### 近期 AgentDojo 适配器迭代

- **Iter 1 — owner-authorized 破坏性操作（T3 豁免）**。当 user goal 显式授权
  删除时，T3 不再硬阻。在 workspace 套件验证：实用性从 75.8% → 79.2%（+3.4 pp）。
- **Iter 2 — 目标标识对齐**（`AD-target-mismatch.yaml`）。规则草案是阻断
  external-effect 操作中目标 email/IBAN/URL 不在 user goal 出现的情况。
  本版 disabled：全矩阵跑出 −23 pp slack 实用性，因为 `invite_user` /
  `add_user_to_channel` 的目标常常隐含。保留 `enabled: false`，等待精度
  改进后再启用。

---

## 安装

```bash
git clone https://github.com/dario-github/nous.git
cd nous
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                       # 核心
pip install -e ".[cozo]"               # + Cozo 嵌入式 KG（pycozo[embedded] 自带 Rust 后端）
pip install -e ".[lsvj]"               # + LSVJ-S 语法工具（lark）
pip install -e ".[dev]"                # + pytest
```

需要 Python 3.11+。Cozo 与 Lark 都是可选；LSVJ smoke 测试在缺依赖时会跳过。

---

## 快速上手 — 给一次工具调用打分

```python
from nous.gate import gate
from nous.schema import ToolCall

call = ToolCall(
    tool_name="send_email",
    action="send",
    params={"to": "attacker@external.com", "body": "... 请忽略前述指令 ..."},
)

verdict = gate(
    tool_call=call,
    constraints_dir="ontology/constraints",
    semantic_config={"model": "DeepSeek-V4-pro"},  # 在环境变量中设 NOUS_API_KEY
)

print(verdict.decision)     # allow / confirm / block
print(verdict.proof_trace)  # 信号链 + 哪一层做的决定
```

完整的 AgentDojo 部署模式跑分入口见 `benchmarks/agentdojo_adapter/run_eval_adaptive_llm.py`。

---

## 仓库结构

```
src/nous/                        核心运行时
├── gate.py                      主决策 pipeline (L1→L4)
├── constraint_parser.py         YAML 约束加载
├── semantic_gate.py             带最小对照提示的 L3 LLM 网关
├── proof_trace.py               决策审计轨迹
├── markov_blanket.py            KG 边界内的上下文检索
├── providers/                   LLM provider 包装（OpenAI 兼容）
├── db.py                        Cozo 包装（KG 存储 + 查询）
└── lsvj/                        LSVJ-S 进行中模块（见路线图）

ontology/
├── constraints/                 46 条 YAML 约束（T3、T5、T10、owner-harm）
├── schema/                      KG 实体/关系 schema + LSVJ-S 原语 schema
└── rules/                       Datalog 规则文件

benchmarks/
├── agentdojo_adapter/           AgentDojo 部署模式包装 + Iter1/2 patch
└── rjudge_sample/               R-Judge personal-agent 记录（24 条，sha256 已冻结）

tests/                           1248 项 pytest；tests/lsvj/ 80 项独立
paper/                           main-neurips-2026.tex（NeurIPS 2026 E&D Track）
                                 main-tmlr.tex（TMLR 滚动）
                                 main-v2.tex / main-neurips.tex（旧 v1）
scripts/                         基准、基线、shadow-live、pilot runner
docs/                            循环日志、审计报告、研究笔记
refine-logs/                     research-refine 资产（5 轮 + raw 审计）
```

---

## 跑测试

```bash
cd nous
python3 -m pytest tests/lsvj/ -v       # LSVJ-S M0 骨架（80 项，无需 Cozo）
python3 -m pytest tests/ -x --tb=short # 完整套件（需要可选依赖）
```

CI 在每次 push 到 `main` 时跑 Python 3.11 与 3.12 双版本（见
`.github/workflows/test.yml`）。CI 子集覆盖 `tests/lsvj/`、
`tests/test_scallop_sidecar.py`、`tests/test_gateway_hook.py` —— 即与路径
无关的部分。完整 1248 项套件需要本地有 `memory/entities/` seed 与
`cozo_embedded` Rust 绑定，这两者属于开发机产物。

---

## 局限性（坦白）

独立审计（GPT-5.4 2026-03-15、Codex 2026-03-20、Gemini 3.1 Pro 2026-04-18）
和投稿后审稿反馈披露了下述真实约束。我们如实写在这里，不掩盖：

1. **生产 KG 当前覆盖偏低**。L3 的 `kg_context` 因此稀疏；`no_kg` 消融在
   训练集上 ΔL = 0（训练时为装饰性）；held-out 价值还在量化。
2. **部分类别的 95% Wilson 置信区间** 在论文里给到了；个别子片样本量小（n < 30）。
3. **Owner-Harm Benchmark 是作者自构**。300H+150B v3 held-out 由第一作者
   在迭代调规则后构建，协议见论文 §3.3。独立复现工作已在计划。
4. **L4 后置验证用 regex + taint 模式而非语义推理**。它在 hijacking 上漏
   的 4 个结构性边界案例（`mysql prod_db < file.sql` 形 SQL 注入；直接
   SSH 密钥注入）已经明确划为不在范围内。
5. **两个制度，两个数字**。隔离模式（强制注入）是 gate 鉴别力的上界；
   部署模式（真实 LLM-pipeline）是下界，因为大多数注入在管道里根本不会
   触发危害。审稿应在两者之间评估，不要只看其一。
6. **v1 §4.2 数字不可复现**。AgentDojo 公开 `14.8%` 依赖一个 `qwen-turbo`
   经已停用内部中转的特定配置；deepseek-v4-pro 替代复现到 `3.7%`
   隔离 / `95.9%` 部署。v2 含 Erratum。

---

## 路线图 — LSVJ-S（进行中）

陪跑方向 — *LLM-Synthesized, Symbolically-Verified Judgments* — 用以
解决 "L1+L2-only 12.7% TPR on held-out" 这一病理。LLM 合成单决策的
Datalog 证明义务，由 4 阶段编译期网关检查（解析 + 类型检查 + 句法
非平凡性 + 复合：**扰动敏感 ∧ 含决定性原语**）后再执行。配套预印在
撰写中；M0 sanity 骨架在 `src/nous/lsvj/` 已通（80 测试绿）。

设计决策与 2026-Q1 先前工作综述见 `refine-logs/FINAL_PROPOSAL.md`、
`refine-logs/REVIEW_SUMMARY.md`、`docs/cozo-lark-fork-decision.md`。

最近邻先前工作（论文中已引并区分）：
- **PCAS**（Palumbo, Choudhary 等，2026-02）—— 离线编译 Datalog 策略
- **ShieldAgent**（ICML 2025）—— 概率规则电路
- **GuardAgent**（2024）—— plan-then-code + I/O 审计
- **AgentSpec**（ICSE 2026）—— 自定义 DSL 运行时强制
- **Solver-Aided**（2026-03）—— NL → SMT 策略编译
- **Agent-C**（2026）—— 解码期 SMT 约束生成

---

## 引用

```bibtex
@misc{zhang2026ownerharm,
  title         = {Owner-Harm: A Missing Threat Model for {AI} Agent Safety},
  author        = {Zhang, Dongcheng and Jiang, Yiqing},
  year          = {2026},
  howpublished  = {arXiv preprint arXiv:2604.18658},
  note          = {Primary: cs.AI; cross-list: cs.CR, cs.CL}
}
```

线上版：<https://arxiv.org/abs/2604.18658>（v1 于 2026-04-20 提交；v2
含 §Limitations Erratum，即将发布）。

---

## 联系方式

- **章东丞 / Dongcheng Zhang**（第一作者）— `zdclink@gmail.com`
  （工作期间所属：BlueFocus Communication Group, Beijing。）
- **江一清 / Yiqing Jiang**（知识图谱方向）— Tongji University, Shanghai。

Issue 与讨论：[github.com/dario-github/nous/issues](https://github.com/dario-github/nous/issues)。

---

## 许可证

Apache License 2.0 —— 完整文本见 [LICENSE](LICENSE)。简要说：你可以在
任何场景（含商用）下使用、修改、再分发 Nous，前提是保留版权声明与
许可证文本。专利授权与商标保护见许可证条款。
