# KG 消融实验预检发现（2026-03-16）

## 结论
**消融实验当前无意义** — 不是因为代码没接入，而是 KG 没有安全领域的实体。

## 数据
- KG entities: 24（全部是 person/concept，来自日常交互提取）
- Tool entities: 0
- Policy entities: 0
- Relations: 26（全部是 RELATED_TO/KNOWS，无 governed_by/restricted_to）

## `_build_kg_context()` 在 benchmark 上的行为
1. 查 `tool:{tool_name}` → None（无 tool entities）
2. 查 target_url/recipient/file_path → None（无匹配）
3. 查 category → None（无 category entities）
4. 返回 None → semantic gate 不受影响 → L_val 不变

## 真正的 P1
**不是跑消融实验，而是先种安全实体。**

需要入库的实体类型：
1. **Tool entities**: 高风险工具（exec, send_message, delete_file 等）+ 安全属性
2. **Policy entities**: 各 category 的治理规则映射
3. **Attack pattern entities**: 已知 evasion 模式（from challenge FN analysis）
4. **Target entities**: 敏感目标类型（credential stores, system configs, etc.）

估算：至少 30-50 tool entities + 10-20 policy entities 才有消融意义。

## 修正后的优先级
1. KG Entity Seeding（种安全实体） ← 新 P1
2. 消融实验（entity 种完后跑） 
3. repeat=3 多数投票

## 来源
- ae85838: `_build_kg_context()` + 11 tests（管线验证✅）
- GPT-5.4 critique: "KG 是舞台布景不是发动机"
- 此发现: 管线通了但里面没有安全领域的知识
