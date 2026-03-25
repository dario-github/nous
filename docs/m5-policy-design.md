# M5.1 — 政策网络 Schema 设计

> Nous M5 政府决策 POC 的数据模型设计
> 2026-03-13 | 基于两会 2026 数据

## 1. Cozo Schema

```cozo
:create policy { id: String => name: String, level: String, issuer: String,
  date: String, status: String, source: String, summary: String, props: Json, created_at: Float }
:create sector { id: String => name: String, parent: String?, props: Json, created_at: Float }
:create measure { id: String => name: String, type: String, amount: String?,
  duration: String?, props: Json, created_at: Float }
:create indicator { id: String => name: String, value_2026: String, value_2025: String?,
  unit: String, direction: String, props: Json, created_at: Float }
:create organization { id: String => name: String, level: String, parent: String?,
  props: Json, created_at: Float }
:create policy_targets { policy_id: String, sector_id: String => strength: String,
  mechanism: String?, created_at: Float }
:create policy_implements { measure_id: String, policy_id: String => status: String, created_at: Float }
:create policy_impacts { policy_id: String, indicator_id: String => direction: String,
  magnitude: String?, created_at: Float }
:create org_issues { org_id: String, policy_id: String => created_at: Float }
:create sector_depends { from_sector: String, to_sector: String => type: String,
  strength: String, created_at: Float }
:create policy_supersedes { new_policy: String, old_policy: String => created_at: Float }
```

## 2. 推理规则（10 条 Datalog）

| # | 规则 | 逻辑 |
|---|------|------|
| R1 | 政策传导 | 政策→目标行业→上游行业（supply_chain 依赖）间接受益 |
| R2 | 财政扩张 | 赤字率 >3.5% → 基建受益 |
| R3 | 政策冲突 | 同一行业被两个政策分别正面/负面影响 |
| R4 | 政策过期 | 被 supersede 的政策自动标记 |
| R5 | 资金传导 | 产业基金→落实政策→目标行业 |
| R6 | 多部委协同 | 同一行业被 ≥2 个部委关注 = 高优先级 |
| R7 | GDP 下调 | GDP 目标下调 → 防御板块受益 |
| R8 | AI+ 传导 | "全面 AI+"政策 → AI 全产业链受益 |
| R9 | 自主可控 | 含"自主可控"的政策 → 行业安全加码 |
| R10 | 权限覆盖 | 国务院政策与部委政策冲突时，国务院优先 |

## 3. 种子数据（两会 2026）

**组织 5 个**: 国务院/发改委/工信部/科技部/财政部
**指标 4 个**: GDP 4.5-5%(↓) / 赤字率 4%(↑) / 研发占比 2.8%(↑) / 国防预算 7.2%(→)
**行业 10 个**: AI/半导体/算力/信息技术/新能源/基建/化工/军工/生物/卫星
**政策 5 个**: 全面AI+/积极财政/集成电路大项目/算力网络/卫星互联网
**措施 4 个**: AI基金/芯片并购基金/算力补贴/研发加计扣除
**依赖链 4 条**: AI→算力(demand) / AI→半导体(supply) / 算力→半导体(supply) / 卫星→半导体(supply)
**政策目标 6 条**: AI→AI行业 / AI→算力 / 芯片→半导体 / 算力→算力 / 卫星→卫星 / 财政→基建

## 4. 回测方案

输入：2025 两会政策（GDP 5%, 赤字 3%）
预测：R1 传导 AI→算力→半导体 / R2 财政扩张→基建 / R6 多部委→半导体高优先
验证：对比 2025H2 行业指数 alpha（Tushare 日线）
命中率 = 受益行业跑赢大盘的比例

## 5. 下一步

M5.2: 政策数据导入器（YAML→Cozo 写入脚本）
M5.3: 推理规则集实现（上述 10 条 Datalog 在 Cozo 中跑通）
M5.4: 第一次回测（2025 两会→行业表现对比）
