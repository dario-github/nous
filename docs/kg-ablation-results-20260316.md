# KG Ablation Experiment Results（2026-03-16 21:00 CST）

## 实验设计
- **对照组**: db=None（KG OFF，当前 benchmark 默认行为）
- **实验组**: db=NousDB（KG ON，56 entities + 47 relations）
- **数据集**: val split（36 harmful + 36 benign）
- **度量**: TPR, FPR, L_val

## 结果

| 条件 | TPR | FPR | L_val | 耗时 |
|------|-----|-----|-------|------|
| KG OFF | 0.5278 | 0.4722 | 0.4722 | 2.9s |
| KG ON | 0.5278 | 0.4722 | 0.4722 | 5.3s |
| **Δ** | **+0.0000** | **+0.0000** | **+0.0000** | +2.4s |

**结论：KG 对 val set 决策零影响。**

## 根因分析（三层问题）

### 问题 1：fact_extractor 不桥接（已修复 ✅）
`extract_facts()` 没有提取 `tool_name`、`category` 等字段，导致 `_build_kg_context()` 无法查询。
**修复**：在 extract_facts 末尾加入 tool_name / category / target_url / recipient / file_path / target 提取。

### 问题 2：KG 实体太抽象，不含决策信息（核心问题 🔴）
当前 KG 内容：
- 15 tool entities → 属性只有 risk_level / description / attack_surface
- 6 policy entities → 只有 rule 编号映射（T3, T6 等）
- 11 category entities → 只有 severity

这些信息对 LLM 来说是 **冗余** 的。LLM 已经有完整 prompt 文本 + 结构化信号，
一个 "Copyright → governed_by T6, severity=medium" 的标签不会改变它的判断。

### 问题 3：KG 缺乏 evasion pattern 知识（未来方向）
GPT-5.4 审查指出的 "KG 是舞台布景" 依然成立。KG 需要的不是 taxonomy，而是：
- **决策先例**（"下载+改写+重发布 = harmful Copyright，即使声称'致敬'"）
- **evasion patterns**（"声称'学术研究'包装真实攻击工具 → 检查输出是否可直接执行"）
- **工具组合危险信号**（"exec + curl + base64 = 典型 payload 投递链"）

## 行动项

1. ✅ fact_extractor 桥接修复（629 tests passing）
2. 🔴 **KG 内容升级**：从 taxonomy → decision-relevant knowledge
   - 添加 evasion pattern entities（来自 challenge benchmark FN 分析）
   - 添加 tool combination risk entities
   - 添加 decision precedent entities（成功/失败案例）
3. 🟡 考虑 KG context 注入方式：当前是 raw JSON dump，改为 structured guidance
4. 📊 重跑消融（KG 内容升级后再测）

## 副发现
- val set 的 L_val=0.4722 远高于 Loop 29 报告的 L_val=0.026
- 可能原因：Loop 29 用了 repeat=3 多数投票 + 不同的 semantic gate 配置
- 需要对齐 benchmark 运行环境以确保公平比较

## 文件
- 结果数据：`docs/kg-ablation-results.json`
- 消融脚本：`scripts/kg_ablation.py`
- fact_extractor 修改：`src/nous/fact_extractor.py`（末尾 KG context bridge）
