# M0 POC 报告 — Cozo 选型决策

**日期**：2026-03-12  
**执行人**：晏（subagent nous-m0-auto）  
**结论**：✅ 选定 Cozo（cozo-embedded Python wheel），纯 Python 开发

---

## 1. POC 执行结果

### 1.1 环境

- Python 3.12（venv）
- pycozo（cozo-embedded wheel，无 Rust 编译）
- 测试图：100 节点 × 200 边 × 5 条约束规则
- 测试机：yanfeather（Linux 6.8.0-101-generic x64）

### 1.2 P99 延迟数据（100 次 × 5 类查询）

| 查询类型 | P50 (ms) | P95 (ms) | P99 (ms) |
|---------|----------|----------|----------|
| 实体查询（entity_lookup） | 0.092 | 0.148 | 0.198 |
| 一跳关系（one_hop） | 0.105 | 0.167 | 0.221 |
| 多跳路径（two_hop，2 跳） | 0.312 | 0.521 | 0.796 |
| 数值条件过滤（numeric_filter） | 0.088 | 0.143 | 0.189 |
| 字符串匹配（constraint_check） | 0.094 | 0.152 | 0.203 |

**最大 P99：0.796ms（目标 <5ms）— 超额达标 6.3 倍**

### 1.3 5 类查询全通过

| # | 查询类型 | Datalog 表达 | 通过 |
|---|---------|------------|------|
| Q1 | 实体查询 | `?[id,name] := *entity{id,name,type}, type="person"` | ✅ |
| Q2 | 一跳关系 | `?[to_id,rtype] := *rel{from_id:"e0",to_id,type:rtype}` | ✅ |
| Q3 | 多跳路径 | 两跳 join | ✅ |
| Q4 | 数值条件 | `age > 60` 数值比较 | ✅ |
| Q5 | 字符串 CONTAINS | `str_includes(pattern, "xhs")` | ✅ |

### 1.4 热加载验证

- 修改 `constraint.verdict`（T3: confirm → block）：无需重启，DB `put` 即生效
- 变更到生效时间：<1ms（内存级原子写入）
- 回滚验证：重新写入原值，立即生效
- ✅ 热加载通过，规则变更到生效 <1s

### 1.5 Rust 依赖验证

- `cozo-embedded` 提供预编译 Python wheel（CPython 3.12 / Linux x86_64）
- **无需 rustup / cargo** — `pip install pycozo` 直接完成
- 验证：`python -c "from pycozo.client import Client; db = Client('mem',''); print('ok')"` ✅

---

## 2. 选型结论

**选定：Cozo（cozo-embedded Python wheel）**

| 验收标准 | 目标 | 实测 | 判定 |
|---------|------|------|------|
| P99 延迟 | <5ms | 0.796ms | ✅ |
| 5 类查询 | 全通过 | 5/5 | ✅ |
| 热加载 | 规则变更 <1s | <1ms | ✅ |
| Python 集成 | <1 天 | 2h | ✅ |
| Rust 依赖 | 可选 | **不需要** | ✅ 优于预期 |

**核心优势（最终决策依据）**：
1. **零运维**：嵌入式，无进程管理，无网络依赖
2. **原生 Datalog**：确定性推理是一等公民，非叠加层
3. **预编译 wheel**：无 Rust 编译要求，pip install 即用
4. **性能超标**：P99 0.796ms，比目标快 6x+
5. **热加载原生支持**：DB 层 atomic write 即热加载

---

## 3. Neo4j/TypeDB 跳过理由

Cozo 在所有 POC 验收标准上全部达标，且在以下维度明显领先：

| 理由 | 说明 |
|------|------|
| **Cozo 全部达标** | 无需继续测试其他候选（tasks.md M0 go/no-go gate 原则） |
| **零运维优势** | Neo4j AuraDB 需注册云服务+网络 RTT，P99 含网络延迟（通常 5-20ms）；TypeDB 需 Docker 自部署 |
| **原生 Datalog 确定性推理** | Neo4j Cypher 是图遍历语言，确定性规则推理需要额外层；TypeDB TypeQL 学习曲线高，生态小 |
| **嵌入式 vs 网络服务** | Cozo 与 Python 进程同生命周期，无额外进程管理成本 |
| **项目原则** | 东丞原则："不重复造轮子，选最成熟的工具"——Cozo 在本场景是最优解 |

---

## 4. 后续决策

| 决策 | 内容 |
|------|------|
| **图数据库** | cozo-embedded（`pycozo`），嵌入式 |
| **存储后端** | 先 SQLite（简单），扩展时迁 RocksDB |
| **核心语言** | 纯 Python（无 Rust/PyO3 依赖） |
| **本体格式** | YAML → 运行时编译为 Cozo schema |
| **热加载** | `watchfiles` 监控 `ontology/constraints/*.yaml` → atomic put → 生效 |

M0.6 Schema 冻结，M1 知识图谱 MVP 启动。

---

*POC 代码：`nous/tests/m0_cozo_poc.py`*
