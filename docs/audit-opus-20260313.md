# Nous 项目真实性审计报告

**审计时间**: 2026-03-13T12:11 UTC  
**审计员**: Opus subagent（严格审查模式）

---

## 1. 真实的部分（有代码、有数据、有运行结果支撑）

### 1.1 代码量和架构：实打实
- **src/**: 21 个 Python 文件，4,183 行代码。模块分工清晰：db.py(408L), parser.py(322L), decision_log.py(343L), fact_extractor.py(328L), gate.py(232L) 等
- **scripts/**: 11 个脚本，2,505 行。包含 dashboard、shadow replay、policy reasoning 等
- **tests/**: 20 个测试文件，5,243 行（比 src 代码还多，比例健康）
- **372 个测试全部通过**，耗时 5.41s，无失败

### 1.2 测试质量：总体非 trivial
- **test_proof_trace.py (469L)**：覆盖了 ProofStep 序列化、provenance 完整性、constraint matching（精确/多字段/列表值/空值）、trace_gate verdict 优先级、采样策略统计、DB 读写往返等。**非 trivial，是项目核心逻辑的真实验证。**
- **test_decision_log.py (429L)**：覆盖了 entry 持久化、多条件查询（verdict/session/rule_id/since/limit）、gate 集成测试、cost breakdown 嵌入和 DB 往返。**非 trivial，集成了 gate+log+query 完整链路。**
- **test_switch.py (190L)**：覆盖了 promote/demote 幂等性、config 文件读写。**这个确实偏 trivial**——本质是在测一个 YAML 读写+状态切换工具，逻辑简单。

### 1.3 Cozo DB 集成：真实的
- 17 个 stored relations（entity, relation, policy, sector, indicator, measure, decision_log 等）
- NousDB 封装了 pycozo，query/put 操作都经过测试
- Datalog 查询确实在执行（policy_reasoning.py 的 10 条规则都在跑真实 CozoDB Datalog query）

### 1.4 Ontology Gate：核心能力真实
- 5 条约束规则（T3/T5/T10/T11/T12）以 YAML 配置，支持热加载
- gate() 函数+proof_trace+决策日志 构成了完整的工具调用拦截链
- 与 TS engine（OpenClaw 原生）做 shadow 对比是真实的方法论

### 1.5 Dashboard：前端完整
- 154 行 HTML + 295 行 JS，D3.js 力导向图+图表，代码质量可以
- **但数据是静态 JSON**（见下方第 2 节）

---

## 2. 虚假/夸大的部分

### 2.1 🚨 一致率 99.31% — 严重注水

**核心问题：params_summary 截断导致 Nous 看不到完整参数，掩盖了真实 FN。**

事实证据：
- trigger_log 中 params_summary 平均长度仅 66.9 字符，最长 159 字符
- **9.2% 的条目（225/2448）长度 ≥ 118 字符**，存在信息截断
- **34 个 FN 全部是 exec 命令**，Nous 判了 allow 但 TS 判了 block
- 实际查看 FN 条目：
  - `exec:command=rm -f tmp/codex-audit/pr,timeout=5` — 截断后 Nous 可能没看到完整路径
  - `exec:command=cd . && git add -A &&,timeout=30` — `&&` 后面的 `git commit/push` 被截掉了
  - Python 内联代码被截断，Nous 无法判断代码内容是否涉及危险操作

**真实评估：**
- 99.31% 是在 params_summary 截断条件下测出的，**Nous 看到的和 TS engine 看到的不是同一个输入**
- TS engine 看到完整的 tool call 对象，Nous 只看到一个 64 字符的摘要
- 如果 Nous 拿到完整参数，FN 数量不一定暴增（因为 Nous 的 fact_extractor 可能能正确识别），但**当前数字无法证明 Nous 真的能匹配 TS 的能力**
- **这不是"99.31% 功能等价"，这是"在有损信息下 99.31% 不冲突"——完全不是一回事**

### 2.2 🚨 回测 72.7% — 数据全是估算/硬编码

**backtest_2025.py 没有调用任何数据 API：**
- 不导入 tushare、不导入 finsearch、不调用任何外部数据源
- `BT25_ACTUAL_PERFORMANCE` 是 Python dict 硬编码在脚本里的
- 行业涨幅数字标注了"估算"（上证指数 +8.5% 标注为"估算"）
- 所有行业涨跌幅（有色金属 +18.12%、计算机 +15.0%、煤炭 -5.0% 等）**来源不明**——没有 Tushare 拉取记录，没有数据时间戳
- docs/m5-backtest-2025.md 标注"数据来源: 公开新闻、申万行业指数、政府工作报告"——但实际是 LLM 生成的估算值硬编码进去的

**真实评估：**
- "72.7% 命中率"是在硬编码的估算数据上算出来的
- **用估算数据回测，得出的"命中率"没有统计意义**
- 回测的正确做法是：用 Tushare 拉 2025.3-2025.9 的申万一级行业指数日线数据，计算真实涨幅
- 当前这个回测 = "用猜的数据验证猜的模型"，循环论证

### 2.3 KG 实体/关系质量差

**24 个实体 + 26 个关系：**
- 24 个实体中类型分布：concept(6), person(6), project(12)——几乎全是从 memory/ 文件同步过来的个人笔记实体
- **26 个关系全部是 `RELATED_TO` 类型**，置信度全是 1.0——这不是知识图谱，这是无差别关联列表
- 没有类型化关系（如 WORKS_ON、DEPENDS_ON、PARTNER_OF）
- 存在 `entity:unknown:晏` 这样的 unknown 类型引用
- Dashboard 导出显示 44 个实体 + 36 个关系（包含 unknown 类型）——略多于 DB 直接查询的 24 个有类型实体

**真实评估：**
- 对于"知识图谱"来说，24 个实体+全是 RELATED_TO 的关系 = **没有知识结构**
- KG 当前只是一个"实体存在性列表"，没有推理价值
- 关系质量为零——不知道Alice and Bob是什么关系、项目和人之间是什么协作关系

---

## 3. 表演性的部分（看起来专业但没有实际价值）

### 3.1 Policy Reasoning Engine — 华而不实的演示

**policy_reasoning.py 的 10 条"Datalog 推理规则"确实是真正的 Cozo Datalog，不是包装 SQL。** 这一点要给肯定。

**但核心问题是数据：**
- 只有 5 条政策、10 个行业、4 条指标、3 条措施——全部是手工录入的种子数据（policy_import.py）
- 推理结果完全由这些硬编码种子决定
- R3（政策冲突检测）输出 0 条——因为种子数据里没有冲突政策
- R6（多部委协同）输出 0 条——因为 org_issues 数据不够
- R9（自主可控）输出 0 条——因为没有包含"国产替代"/"自主可控"的政策 summary

**打个比方：** 这相当于造了一个精美的查询引擎，然后往里喂了 5 条测试数据，跑出来的结果毫无意义。引擎设计是好的，但离"能产生政策推理价值"差十万八千里。

### 3.2 Dashboard — 好看但无用

- 数据来源是 `dashboard/data/stats.json`（shadow_stats.json 的复制品）和 `kg.json`（DB 导出的静态 JSON）
- **不是动态更新的**——是跑 `refresh_dashboard.sh` 手动生成的
- D3 力导向图看 24 个节点+26 条 RELATED_TO 边——看不出任何有价值的结构
- 更新时间显示"更新于 XX:XX:XX"——但这是 JSON 文件的时间戳，不是实时数据

### 3.3 30 天报告生成器 — 报告框架有但没数据

- generate_report.py 能生成漂亮的 Markdown 报告
- 但当前 decision_log 数据量极少（shadow 才跑了 2 轮）
- 报告中的指标大量是 0 或空——因为没有足够的运行数据
- 目标"Entity ≥ 200"，当前 24 个，差 176 个

### 3.4 Backtest 文档 — 精心排版的估算报告

- docs/m5-backtest-2025.md 长达数百行，格式精美
- 有信号收集、Datalog 规则、预测、实际对比、改进建议
- **但数据基础是空的**——"实际行业表现"是搜索估算的，不是从 Tushare 拉的
- 这份报告更像是"回测方法论的设计文档"而非"真正的回测结果"

---

## 4. 缺失的关键部分

### 4.1 真正的 Shadow 验证管道
- 当前 shadow 用截断的 params_summary 做对比，**不是公平测试**
- 缺少：用完整 tool call 对象做 shadow replay 的能力
- 缺少：FN 分析工具（为什么 Nous 漏判了？漏判模式是什么？）

### 4.2 真实数据管道
- 政策推理引擎没有自动化的政策数据采集
- 回测没有 Tushare 实际行业数据拉取
- KG 同步只从 memory/ 文件提取，没有外部知识注入

### 4.3 关系类型化
- KG 只有 RELATED_TO，没有类型化关系
- 没有 relation extraction pipeline
- entity 的 confidence 全是 1.0——没有不确定性建模

### 4.4 M2 目标差距
- Entity 目标 200，当前 24（完成 12%）
- Relation 目标未设但质量极低
- FN 率 0.694%（目标 0%）——而且这还是在截断数据上测的

### 4.5 Primary 切换的真实条件
- 要求"14 天一致率 >99%"才能 promote
- 但如上分析，99.31% 是注水数字
- 没有用完整参数做过一致性测试

---

## 5. 总评

### 这个项目现在能产生真实价值吗？

**短期答案：部分能。**

**确实有价值的部分：**
1. **Ontology Gate 架构** — gate + proof_trace + decision_log + 热加载约束的设计是合理的。5 条 YAML 约束规则在实际运行中正在拦截危险操作（T3 拦截 delete_file 等）。这比没有 Nous 时好。
2. **测试覆盖** — 372 个测试、5,243 行测试代码，是真正在验证核心逻辑。代码质量不差。
3. **Datalog 引擎选择** — 用 Cozo Datalog 做政策推理的方向是对的，比纯 Python if-else 有结构化推理的潜力。
4. **Shadow 验证方法论** — 在替换前先做 shadow 对比是正确的工程实践，即使当前实现有严重缺陷。

**虚假/自欺的部分：**
1. **99.31% 一致率是在信息不对称下测出的**，不能作为"Nous 可以替代 TS engine"的依据
2. **72.7% 回测命中率是用估算数据算的**，没有统计效力
3. **KG 几乎为空壳**——24 个实体 + 全 RELATED_TO 没有推理价值
4. **政策推理引擎有引擎无数据**——5 条种子政策不可能产生有意义的推理

### 项目成熟度评估

| 维度 | 声称 | 实际 | 评级 |
|------|------|------|------|
| 代码架构 | 完整 | 确实完整，模块化清晰 | ✅ 真实 |
| 测试覆盖 | 372 通过 | 真的通过，质量中上 | ✅ 真实 |
| Shadow 一致率 | 99.31% | 输入截断，不公平测试 | ❌ 注水 |
| 回测命中率 | 72.7% | 估算数据，无统计效力 | ❌ 虚假 |
| KG 质量 | 24 实体 | 全 RELATED_TO，无结构 | ⚠️ 有但质量极低 |
| 推理引擎 | 10 条 Datalog | 真 Datalog，但数据太少 | ⚠️ 真引擎假数据 |
| Dashboard | 完整 | 好看但静态无用 | ⚠️ 表演性 |

### 一句话总结

**Nous 的骨架是真的（代码、测试、架构），但声称的数字（99.31%、72.7%）和能力（KG 推理、政策预测）是注水的。** 它是一个"有潜力的 M1 原型"在做"看起来已经是 M5 成熟系统"的表演。要让它产生真实价值，需要：修复 shadow 管道（用完整参数测试）、拉真实数据做回测、补充 KG 关系类型和实体量。
