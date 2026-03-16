# Nous Geopolitical Reasoning — RL Training Framework

> 目标：让 Nous 基于本体论推理"美国对伊朗开战的走势"
> 方法：Agent RL，reward 驱动自动迭代
> 核心约束：**只用开战前数据训练，不泄漏未来**

## 1. 问题定义

**任务**：给定 T 时刻前的所有公开情报，预测 T+1 ~ T+N 天的关键事件/走势。

**具体化**：
- 输入：2/28 开战前的情报集合（地缘、军事、经济、政治信号）
- 输出：结构化预测（事件类型 × 概率 × 时间窗口 × 因果链）
- 评估：与实际事件对比，计算 reward

**为什么这是好的 benchmark**：
1. 我们有详尽的时间线数据（782 行 iran-war-tracker.md）
2. 事件已经发生，可以精确评估
3. 因果链复杂度高，需要真正的推理
4. 完美模拟"agent 在不确定环境中做决策"

## 2. 数据架构

### 2.1 时间线切分

```
[情报期] ────── [训练窗口] ────── [验证窗口] ────── [测试窗口]
  ~2/27及更早      2/28-3/7          3/8-3/11          3/12-3/16
   背景知识        Day 1-8           Day 9-12          Day 13-17
```

**训练集（Train）**：2/28 前的全部公开情报 + Day 1-8 实际事件
- 用途：建立 KG、调规则、训练推理链
- 可以看，可以反复跑

**验证集（Val）**：Day 9-12（3/8-3/11）的实际事件
- 用途：每轮计算 L_val，判断是否过拟合
- 不能用于调参

**测试集（Test）**：Day 13-17（3/12-3/16）的实际事件
- 用途：仅 milestone 时运行
- 冻结，不看

### 2.2 情报数据结构

每条情报 = 一个 **Signal**：

```json
{
  "id": "sig_001",
  "timestamp": "2026-02-25T10:00:00Z",
  "source_type": "news|intelligence|data|social|official",
  "source_credibility": 0.0-1.0,
  "content": "以色列空军在塞浦路斯 Akrotiri 进行大规模演习",
  "entities": ["entity:country:israel", "entity:facility:akrotiri"],
  "relations": ["CONDUCTS_EXERCISE_AT"],
  "signal_type": "military_posture|economic|political|diplomatic|humanitarian",
  "implications": ["force_projection_capability", "cyprus_as_staging_area"],
  "confidence": 0.85
}
```

### 2.3 事件数据结构（Ground Truth）

```json
{
  "id": "evt_001",
  "date": "2026-02-28",
  "day": 1,
  "event_type": "military_strike|diplomatic|economic|humanitarian|escalation|de_escalation",
  "description": "美以联合空袭伊朗，哈梅内伊遇害",
  "severity": 5,
  "actors": ["US", "Israel", "Iran"],
  "targets": ["Tehran", "military_facilities"],
  "consequences": ["leadership_decapitation", "retaliation_cycle"],
  "causal_parents": ["sig_001", "sig_015", "evt_000"],
  "category": "military_escalation",
  "surprise_factor": 0.3
}
```

## 3. Reward 设计（关键）

### 3.1 Composite Reward Function

```
R = w1·R_event + w2·R_causal + w3·R_timing + w4·R_calibration - w5·R_hallucination

权重：
  w1 = 0.30  事件预测准确率
  w2 = 0.25  因果链质量
  w3 = 0.15  时间窗口准确度
  w4 = 0.20  概率校准度
  w5 = 0.10  幻觉惩罚
```

### 3.2 各分项定义

**R_event（事件预测准确率）**：
- 预测 N 个事件，实际发生 M 个
- Precision = 预测中命中的 / 总预测数
- Recall = 命中的 / 实际发生的关键事件数
- R_event = F1(Precision, Recall)
- 事件匹配用语义相似度（GPT-5.4 judge 判断是否"实质匹配"）

**R_causal（因果链质量）**：
- 每个预测必须附带因果推理链
- GPT-5.4 judge 评分 0-5：
  - 5: 因果链逻辑严密，引用了正确的前因
  - 3: 方向对但细节有偏
  - 1: 因果关系错误或循环论证
  - 0: 无因果链或纯猜测
- R_causal = avg_score / 5

**R_timing（时间窗口准确度）**：
- 对每个命中事件，计算预测时间窗口 vs 实际时间
- timing_error = |predicted_day - actual_day| / window_size
- R_timing = 1 - mean(timing_error)，clip to [0, 1]

**R_calibration（概率校准度）**：
- 预测"80% 概率发生"的事件，实际应有 ~80% 发生
- Brier Score = mean((predicted_prob - actual_binary)^2)
- R_calibration = 1 - Brier_Score

**R_hallucination（幻觉惩罚）**：
- 预测了完全没有发生的事件
- R_hallucination = count(hallucinated_events) / total_predictions
- 这是惩罚项（前面有负号）

### 3.3 Global Loss

```
L_geo = 1 - R
L_geo = 1 - (0.30·R_event + 0.25·R_causal + 0.15·R_timing + 0.20·R_calibration - 0.10·R_hallucination)
```

## 4. 本体论推理架构

### 4.1 KG Schema（地缘推理专用）

**实体类型**：
| 类型 | 示例 |
|------|------|
| country | US, Iran, Israel, Saudi Arabia |
| leader | Trump, Khamenei, Netanyahu, Pezeshkian |
| military_unit | CENTCOM, IRGC, IDF, Hezbollah |
| facility | Kharg Island, Natanz, Parchin, Akrotiri |
| weapon_system | Fateh-110, Iron Dome, B-2, S-300 |
| economic_asset | Hormuz Strait, Shaybah oilfield, SPR |
| alliance | Gulf Coalition, Axis of Resistance |
| event | Operation Epic Fury |

**关系类型**（9 种 + 地缘扩展）：
| 关系 | 含义 |
|------|------|
| ALLIED_WITH | 联盟/同盟关系 |
| HOSTILE_TO | 敌对关系 |
| CONTROLS | 控制（领土/资源/组织） |
| DEPENDS_ON | 依赖（经济/军事/政治） |
| THREATENS | 威胁（声明/部署/行动） |
| RETALIATES_AGAINST | 报复 |
| MEDIATES | 调解/斡旋 |
| SUPPLIES | 供应（武器/资源/情报） |
| SUCCEEDS | 继任/接替 |
| LOCATED_AT | 物理位置 |
| PRODUCES | 生产（石油/武器） |

### 4.2 推理规则（Datalog 约束）

```prolog
% 报复升级链：A 攻击 B 的关键设施 → B 大概率报复 A 或 A 的盟友
retaliation_likely(B, A) :-
    attacks(A, B, Target),
    strategic_asset(Target, B),
    military_capability(B, retaliate).

% 联盟牵连：A 攻击 B → B 的盟友 C 可能介入
alliance_involvement(C, A) :-
    attacks(A, B, _),
    allied_with(B, C),
    military_capability(C, intervene).

% 经济武器化：控制关键通道 → 对依赖方施压
economic_pressure(Controller, Dependent) :-
    controls(Controller, Chokepoint),
    depends_on(Dependent, Chokepoint, "trade_route").

% 领导力真空：领导人被消灭 → 继任危机 → 政策不确定
leadership_vacuum(Country) :-
    leader(Country, Leader),
    eliminated(Leader),
    not successor_confirmed(Country).

% 升级螺旋检测
escalation_spiral(A, B) :-
    retaliates_against(A, B, T1),
    retaliates_against(B, A, T2),
    T2 > T1,
    severity(B_action_at_T2) > severity(A_action_at_T1).
```

### 4.3 推理流程

```
Signal Ingestion → KG Update → Datalog Inference → LLM Synthesis → Prediction
     ↓                ↓              ↓                  ↓              ↓
  结构化信号     实体/关系入库    规则推导新事实    综合分析+概率    结构化输出
                                                   ↓
                                              Ground Truth 对比
                                                   ↓
                                              Reward 计算
                                                   ↓
                                              策略更新（规则/KG/prompt）
```

## 5. RL 迭代循环

### 5.1 策略空间（Policy）

Nous 的"策略"不是神经网络权重，而是：
1. **KG 结构** — 哪些实体/关系被建模
2. **Datalog 规则** — 推理规则集合
3. **LLM Prompt** — 综合分析的 prompt 模板
4. **信号权重** — 不同类型信号的重要性权重
5. **置信度阈值** — 什么级别的推理结果输出为预测

### 5.2 迭代步骤

每轮迭代（~ 1 iteration = 1 complete cycle）：

```
Step 1: Ingest（信号摄入）
  - 读取当前时间窗口内的所有信号
  - 用 auto_extract 自动建 KG
  
Step 2: Reason（推理）
  - 运行 Datalog 规则，推导新事实
  - LLM 综合分析，生成预测
  
Step 3: Predict（预测输出）
  - 结构化预测：事件 × 概率 × 时间窗 × 因果链
  - 写入 predictions.json
  
Step 4: Evaluate（评估）
  - 对比 ground truth（val set）
  - 计算 R_event, R_causal, R_timing, R_calibration, R_hallucination
  - 计算 L_geo
  
Step 5: Update（策略更新）
  - L_geo 下降 → 保留变更
  - L_geo 上升 → 回滚
  - 分析哪个 R 分项最差 → 针对性改进
  
Step 6: Reflect（反思）
  - 写 loop-log
  - 更新 loop-state.json
```

### 5.3 Curriculum（课程学习）

```
Phase 1 — 单事件预测（Day 1-3）
  输入：开战前情报 + Day 0 事件
  预测：Day 1-3 的关键事件
  退出条件：R_event > 0.5 且 R_causal > 0.6

Phase 2 — 连锁推理（Day 1-8）
  输入：开战前情报 + Day 0 事件
  预测：Day 1-8 的事件序列
  重点：因果链和升级螺旋
  退出条件：R_event > 0.4 且 R_timing > 0.5

Phase 3 — 全景预测（Day 1-12）
  输入：开战前情报
  预测：整个 val 窗口的走势
  重点：概率校准和幻觉控制
  退出条件：L_geo_val < 0.30
```

## 6. 防泄漏协议（Critical）

### 时间隔离墙

| 阶段 | 可见数据 | 不可见 |
|------|---------|--------|
| Phase 1 训练 | ≤2/28 情报 + Day 0 | Day 1+ 事件 |
| Phase 1 验证 | 同上 | Day 1+ 事件（只用于评估） |
| Phase 2 训练 | ≤2/28 + Day 0 | Day 1+ |
| Phase 2 验证 | 同上 | Day 1+ |
| Phase 3 测试 | ≤2/28 + Day 0 | Day 1+ |

**关键**：模型推理时看到的上下文 = 严格 ≤ 2/28 的信息。
Day 1+ 的事件只在评估阶段用作 ground truth，不注入推理 prompt。

### 防泄漏检查

每次推理前运行 `temporal_leak_check(prompt, cutoff_date)`：
- 扫描 prompt 中的所有日期引用
- 任何 > cutoff_date 的引用 → 拒绝并报错
- 检查实体名（如"穆杰塔巴"在 2/28 前不应出现为"最高领袖"）

## 7. 实现计划

### Phase 0: 数据准备（1 天）
- [ ] 从 iran-war-tracker.md 提取结构化事件
- [ ] 从 memory 中收集 2/28 前的情报信号
- [ ] 生成 train/val/test JSON 文件
- [ ] 建立地缘 KG schema（entities.yaml + relations.yaml）

### Phase 1: 基线推理（2 天）
- [ ] 手动构建 pre-war KG（关键实体+关系）
- [ ] 写 Datalog 推理规则（v0.1）
- [ ] 跑一次完整推理，生成 baseline predictions
- [ ] 实现 reward 计算脚本（judge_geo.py）
- [ ] 计算 baseline L_geo

### Phase 2: 自动迭代（3 天）
- [ ] 实现 geo_train_loop.py（完整 RL 循环）
- [ ] Phase 1 curriculum（单事件预测）
- [ ] Phase 2 curriculum（连锁推理）
- [ ] 每轮自动：ingest → reason → predict → evaluate → update

### Phase 3: 验证+测试（1 天）
- [ ] 在 val set 上验证 L_geo 趋势
- [ ] 解锁 test set，最终评估
- [ ] 生成完整分析报告

## 8. 与现有 Nous 的融合

**这不是独立系统，是 Nous 的新能力层**：

- KG schema 扩展（地缘实体/关系类型加入 ontology/schema/）
- auto_extract 支持地缘信号提取
- gate.py 可以用地缘推理来增强安全判断
  （例：识别"帮我分析攻击伊朗核设施的方法" = 安全敏感）
- Datalog 规则复用（约束框架一致）

**最终验证目标**：给 Nous 2/28 前的情报，它能推理出：
1. 伊朗会报复（霍尔木兹封锁 + 导弹）
2. 油价会暴涨（$55 → $100+）
3. 领导力真空会导致不确定性
4. 海湾国家会被卷入
5. 升级螺旋难以控制
