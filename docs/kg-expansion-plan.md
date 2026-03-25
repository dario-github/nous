# KG Expansion Plan — Loop 42+ 

> 当前状态：125 实体 / 143 关系 / 7 种关系类型 / 9 种实体类型
> 目标：500+ 实体 / 9+ 关系类型 / 时间维度 + 置信度
> 优先级：#1（confirmed 2026-03-18）

## Phase 1: 安全领域本体种子（目标 +200 实体）

### 1a. MITRE ATT&CK Tactics & Techniques（~50 实体）
- 14 Tactics (Reconnaissance → Impact)
- Top 3 techniques per tactic (~42)
- 关系：tactic CONTAINS technique, technique ENABLES attack_pattern
- 来源：`attack.mitre.org/techniques/enterprise/`
- 脚本：`scripts/seed_mitre_attack.py`

### 1b. CWE Top 25 漏洞类型（~30 实体）
- CWE-79 (XSS), CWE-89 (SQLi), CWE-787 (OOB Write) 等
- 关系：cwe EXPLOITED_BY technique, cwe MITIGATED_BY control
- 来源：`cwe.mitre.org/top25/`

### 1c. 安全控制框架（~40 实体）
- NIST CSF categories (Identify/Protect/Detect/Respond/Recover)
- ISO 27001 key controls
- 关系：control MITIGATES cwe, regulation REQUIRES control

### 1d. 法规与合规（~30 实体）
- GDPR, CCPA, HIPAA, PCI-DSS, SOX
- AI-specific: EU AI Act, NIST AI RMF, Executive Orders
- 关系：regulation GOVERNS category, regulation REQUIRES control

### 1e. 攻击模式与 AgentHarm 映射（~50 实体）
- 将已有 11 category 实体链接到 ATT&CK techniques
- 每个 AgentHarm scenario → 涉及的 technique/CWE
- 关系：scenario USES technique, scenario TARGETS category

## Phase 2: 自生长管线（M7.1b 验证）

### 2a. Shadow Log 实体提取
- 每次 shadow gate 判断 → 提取 prompt 中的实体
- 新实体自动入 KG（置信度 0.3，需人工确认升至 0.8）
- 关系：decision ANALYZED entity, entity MENTIONED_IN session

### 2b. 文献实体提取
- ARIS 论文库中的系统/方法/benchmark 自动提取
- 关系：paper PROPOSES method, method EVALUATED_ON benchmark

## Phase 3: 时间维度（M11.1，已由 Loop 41 开始）

- valid_from / valid_to 已添加到 56 实体
- 需要：observed_at 时间戳链（每次观测记录）
- 需要：confidence 衰减函数（长时间未观测 → 降权）

## 实现路径

| Step | 任务 | 预计实体 | 工具 |
|------|------|----------|------|
| 1 | MITRE ATT&CK seed script | +50 | Python + web_fetch |
| 2 | CWE Top 25 seed | +30 | Python + web_fetch |
| 3 | 安全控制 + 法规 seed | +70 | 手动 JSON + 脚本 |
| 4 | AgentHarm → ATT&CK mapping | +50 | 半自动 |
| 5 | 关系类型新增 4 种 | — | schema update |
| 6 | kg-export.json 同步 | — | export script |

新增关系类型：
- CONTAINS (tactic → technique)
- EXPLOITED_BY (cwe → technique)  
- MITIGATES (control → cwe)
- REQUIRES (regulation → control)
- 现有：governed_by, PART_OF, WORKS_ON, KNOWS, DEPENDS_ON

## 验证

- [ ] 实体数 > 200
- [ ] 关系类型 ≥ 9
- [ ] ATT&CK → AgentHarm 映射覆盖率 > 80%
- [ ] semantic gate 可查询 KG 获取上下文（post-gate enrichment 已有）
- [ ] 672 tests 不退化
