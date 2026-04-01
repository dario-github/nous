# Nous Session 上下文
> 生成于：2026-03-28 04:45 UTC | 供东丞×晏在 Nous 主 session 使用

---

## 当前状态速览

| 维度 | 状态 |
|------|------|
| Loop 轮次 | 78（2026-03-25） |
| Owner-harm L_val | **0.0**（TPR 100% / FPR 0%，200/200 blocked） |
| AgentHarm L1+L2 only | TPR 55.6% / FPR 47.2%（社会危害类，非 owner-relevant，L3 offline 时基线） |
| L_challenge | 0.0（45/45，Loop 60 冻结） |
| Tests | **1068** (green) |
| 论文 ARIS | **7.5/10 Ready**（3 轮迭代完成，03-28） |
| arXiv 截稿 | **3/31 AoE（3 天）** |

---

## 论文（paper/main.tex）当前状态

### 已完成 ✅
- 署名：`Dongcheng Zhang · BlueFocus Communication Group · dongcheng.zhang@bluefocus.com`
- Figure 1：`figure1.pdf` 已生成（03-27，render_figure1.py）
- Related Work：Doshi + STPA + MCP（c5343d0）
- Baselines Table 5（d6710ac）
- Owner-Centric 95% CI（Wilson method）
- InjecAgent limitations（Section 4）
- ARIS 3 轮 auto-review：5/10 → 6.5/10 → 7.5/10

### ARIS 改了什么
| 轮 | 核心修复 |
|----|---------|
| R1 | 去掉 neurosymbolic 过度宣称、缩小到 single-turn、修正消融不一致、加外部基线、补生产证据 |
| R2 | 加 frozen OOD 评估（held-out domain split）、"组合何时有效"科学分析、缓和强声明、matched-FPR 基线、生产审计 CI |
| R3 | OOD 表加 CI、部署指导、最终润色 |

### 可选锦上添花（非 blocker）
- Claude Mythos → Discussion 加一句：随着更强 agent 模型出现（如能主动挖漏洞的 Mythos 级），runtime 行为约束的紧迫性将进一步上升

### 待核对
- 实验数据与实际运行结果对应（L3 semantic gate 完整跑需要 OPENAI_API_KEY / DeepSeek key）

---

## 紧急 P 项（loop-state.json urgent）

| 级别 | 任务 |
|------|------|
| **P1** | 重跑 `shadow_live.py` 验证生产环境语义判断正常产出 |
| **P1** | 运行 `seed_security_entities.py` 将 decision entities（含 precedents）写入生产 DB |
| **P2** | 对抗红队 benchmark 验证 decision entities + precedents 是否提升语义门准确率 |
| **P2** | 重建 owner-harm benchmark 数据（`harmful.json` 缺失，原在 /tmp，需从历史或重新生成） |
| **P3** | `gateway_hook` integration — config 未传递 → L2/L3 生产未激活 |

---

## Loop 78 做了什么

**M7.2 Part 3（最后一块）**：
- 7 个 precedent entities（decision case law，4 block / 3 allow）
- 从 FP/FN 历史中提取，通过 `RESOLVED_BY` 关系连接到 evasion/combo 实体
- `markov_blanket.py` props 传播修复：属性（pattern_type/severity/guidance 等）现在正确到达 `format_blanket_for_prompt`
- KG：45→52 entities，41→48 relations
- 1068 tests green

---

## KG 当前状态

- **生产 DB（nous.db）**：482 entities / 579 relations（Loop 71 前数据）
- **Loop 77-78 新增**（仅内存/seed）：52 entities / 48 relations（decision 层）
- **待同步**：`seed_security_entities.py` 将新 decision entities 写入生产 DB（P1 urgent）

---

## 技术环境

| 项 | 值 |
|----|---|
| Semantic gate 模型 | DeepSeek-V3.2（生产）/ GPT-5.4（Judge/评估） |
| Python 运行环境 | Python 3.12.11（`/Users/user/.local/bin/python3.12`）或 3.13（homebrew）需 PYTHONPATH=./src |
| Benchmark 脚本 | `scripts/run_split_benchmark.py val/test/all` |
| Loop state | `docs/loop-state.json` |
| 论文目录 | `paper/` |

---

## 本 session 建议优先顺序

1. **paper 最终确认**：东丞过一眼 ARIS 改动，确认没有被 hallucinate 的数据，commit → arXiv 上传
2. **P1 urgent**：`seed_security_entities.py` 写入生产 DB，然后 `shadow_live.py` 验证
3. **P3**：`gateway_hook` config 传递修复（生产 L2/L3 激活）
4. 可选：Claude Mythos 加入 Discussion

---

*由晏生成，2026-03-28 04:45 UTC*
