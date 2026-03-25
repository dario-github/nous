# Lobster 精读分析：GPU Datalog + NeSy 工程参考

> 论文：Lobster — A GPU-Accelerated Framework for Neurosymbolic Programming  
> ArXiv: 2503.21937 | ASPLOS 2026  
> 精读重点：APM 中间语言、GPU 编译策略、对 Nous 的工程参考

---

## 一、APM (Abstract Parallel Machine) 架构详解

### 1.1 设计哲学：把 GPU 约束显式化为语言约束

APM 不是通用 IR，而是一个 **专门为 GPU 执行特性设计的低级汇编风格语言**。核心设计哲学：
> 把 GPU 编程的隐式约束显式编码为语言层面的限制，一旦程序通过 APM 合法性检查，高效 GPU 执行就有保证。

三个设计约束直接对应 GPU 硬件的三个核心限制：

| GPU 硬件约束 | APM 的响应 |
|---|---|
| SIMD lockstep（warp 内 32 线程同指令） | **无控制流**：APM 没有 branch/loop，消除 thread divergence |
| 动态内存分配代价极高 | **静态单赋值 (SSA)**：每寄存器只赋值一次；`alloc` 是唯一内存分配点 |
| 需要 coalesced memory access | **向量寄存器 + 列式存储**：所有寄存器存储同类型值的定长缓冲区 |

### 1.2 指令集完整清单

#### 内存管理
```
alloc⟨τ₁,...,τₙ⟩(r̄ₙ, S)
```
- 分配 n 个类型为 τ₁...τₙ 的寄存器，每个大小为 S
- APM 中**唯一的内存分配点**
- 由于无循环/分支，每次迭代的 alloc 数量编译时完全已知

#### 数据操作
```
d̄ₘ ← eval⟨αₙ,ₘ⟩(s̄ₙ)     // projection：对每行并行应用函数 α（完美 SIMD）
d̄ₙ ← gather(i, s̄ₙ)        // 按索引 i 重排行（间接索引访问）
d  ← gather⟨αₙ,₁⟩(ī̄ₙ, s̄ₙ) // 带归约函数 α 的 gather（用于 join 中 tag 合并）
d̄ₙ ← copy(s̄ₙ)             // 复制，目标小于源时截断
```

`eval` 是 projection 的核心实现，每个 GPU 线程处理一行，完美 SIMD。  
`gather⟨⊗⟩` 是 join 中 provenance tag 合并的载体，α 就是 semiring 的 ⊗ 操作。

#### 数据库 I/O
```
store⟨ρ⟩(s̄ₙ, sₜ)           // 将寄存器写回数据库关系 ρ
[s̄ₙ, sₜ] = load⟨ρ⟩()       // 从数据库加载关系 ρ（n个数据列 + 1个 tag 列）
```

关系表示：n 个数据列寄存器 + 1 个 tag 寄存器，列式布局。

#### Hash Join 四件套（完整 pipeline）
```
d      ← build(s̄ₙ)                          // 构建 hash index（open addressing + linear probing）
d̄ₙ    ← count(b̄ₙ, h, āₙ)                  // probe：统计每行的匹配数（histogram）
d̄ₙ    ← scan(s)                             // exclusive prefix sum → 确定写入位置
[dₗ, dᵣ] ← join⟨W⟩(b̄ₘ, āₙ, h, c, o)      // 执行 join，输出左右表的索引对
```

设计精妙处：`scan` 的最后一个值 = join 输出总行数 → 可精确 `alloc`，无运行时重分配。  
`join` 只输出索引对，实际数据通过 `gather` 收集，解耦了 join 的时空复杂度与关系宽度。

#### 排序与去重
```
d̄ₙ     ← sort(s̄ₙ)              // 字典序排序
[d̄ₙ, s] ← unique⟨σ⟩(s̄ₙ)      // 合并相邻重复行，σ 是 tag 合并函数（= semiring ⊕）
d̄ₙ     ← merge(āₙ, b̄ₙ)        // 合并两个已排序表（用于 stable ∪ recent）
```

`unique` 中的 σ 就是 semiring 的 ⊕ 操作（析取）。同一事实的不同推导路径在此合并。

### 1.3 内存模型

```
关系 ρ（arity=n） = [r₁列, r₂列, ..., rₙ列] + [rₜ tag列]
```

- **列式布局 (columnar)**：每列操作产生连续内存访问，最大化 GPU 内存带宽利用率（接近 memory-bound 程序的理论上限）
- **向量寄存器**：每个寄存器是定长同类型值的缓冲区，大小必须在 `alloc` 时显式声明
- **定点迭代的三分区**（Semi-naive）：
  - `F_stable`：所有历史已知 facts（已排序，用 merge 更新）
  - `F_recent`：上一迭代新产生的 facts
  - `F_Δ`：当前迭代新产生的 facts（待 sort + unique 后升级为 recent）
- **Static 寄存器**：跨迭代保持值（`static h ← build(...)` 实现 hash index reuse）

---

## 二、Datalog → GPU 的编译策略

### 2.1 整体编译 Pipeline

```
用户 Datalog / Scallop 程序
    ↓ (Scallop 前端 + query planner，Lobster 复用)
RAM (Relational Algebra Machine)
    ↓ (Lobster compiler: compile 函数)
APM 程序（指令序列）
    ↓ (Lobster runtime: CUDA kernel 执行)
GPU 上并行执行
```

Lobster 自实现的核心：**RAM → APM 编译器** + **APM 运行时（CUDA）**。

### 2.2 RAM 语言（编译器源语言）

```
表达式 ε ::= ρ | π_α(ε) | σ_β(ε) | ε₁ ⋈ₙ ε₂ | ε₁ ∪ ε₂ | ε₁ × ε₂ | ε₁ ∩ ε₂
规则   ψ ::= ρ ← ε
层     φ ::= {ψ₁, ..., ψₙ}        // 同一 stratum 的规则集
程序   φ̄ ::= φ₁; ...; φₙ          // 按 stratum 顺序执行
```

RAM 程序是一个 **DAG**（多源单汇数据流图），compile 函数将 DAG 展平为线性指令序列。

### 2.3 核心 Operator 的编译

#### Projection 的编译

对于 `π_{λ(i,j).(j,i)}(ρ)`:
```apm
alloc([r2₁, r2₂, r2ₜ], size(r1₁))          // 输出大小 = 输入大小，编译时可知
[r2₁, r2₂] ← eval⟨λ(i,j).(j,i)⟩([r1₁, r1₂])  // 每行并行执行，零依赖
[r2ₜ]      ← copy(r1ₜ)                           // tag 直接穿透（provenance 不变）
```

#### Join 的编译（最关键）

以 `path(x,y) :- path(x,z), edge(z,y)` 为例：

```apm
// Step 1: 构建 hash index（对不变的 EDB 用 static 跨迭代复用！）
alloc(h, size(r3₁) * O)
static h ← build([r3₁])            // static = 只初始化一次，后续迭代直接复用

// Step 2: 确定输出大小（count + scan）
alloc([c, o], size(r2₁))
c ← count([r2₁], h, [r3₁])         // path 每行在 edge 中有多少匹配 → histogram
o ← scan(c)                          // 前缀和 → 每行输出的写入偏移

// Step 3: 精确分配 + 执行 join
alloc([iₗ, iᵣ, r4₁, r4₂, r4₃, r4ₜ], last(o))  // last(o) = 总输出行数
[iₗ, iᵣ] ← join⟨1⟩([r2₁, r2₂], [r3₁, r3₂], h, c, o)  // 输出索引对
[r4₁, r4₂] ← gather(iₗ, [r3₁, r3₂])           // 从左表按索引收集数据
[r4₃]      ← gather(iᵣ, [r2₂])                  // 从右表按索引收集数据
r4ₜ        ← gather⟨⊗⟩([iₗ, iᵣ], [r3ₜ, r2ₜ])  // ⊗ 合并两侧 tag（join = 逻辑AND）
```

**关键设计选择**：
1. `last(o)` 在 join 前就确定了输出大小 → 精确 `alloc`，无运行时重分配
2. join 输出索引对，数据通过 `gather` 收集 → 解耦 join 算法与数据宽度
3. `static h` 跨迭代复用 hash index → 对线性递归程序避免重复构建

#### Union + 去重的编译

对于 `ρ ← ε₁ ∪ ε₂`（两个已排序输入）：
```apm
d_merged ← merge(ε₁_result, ε₂_result)   // GPU 上的并行归并排序
d_unique ← unique⟨⊕⟩(d_merged)            // 合并重复行，⊕ 合并 tag（union = OR）
store⟨ρ⟩(d_unique)
```

### 2.4 Semi-naive Evaluation 在 GPU 上的实现

**三分区维护**（每次迭代）：
```
F_Δ → sort → unique → 升级为 F_recent
F_stable ← merge(F_stable, F_recent)  // 归并两个已排序表
```

**规则体的展开策略**：对于递归关系 ρ 的规则体 `π(ρ ⋈ edb)`，semi-naive 展开为：
```
delta_ρ ← π(F_Δ(ρ) ⋈ edb)         // 新 delta 与 EDB 的 join
```
（标准 semi-naive：只用上一轮的 delta 去推新 facts）

### 2.5 Stratum Offloading Scheduling（CPU-GPU 传输优化）

1. 启发式识别最长运行 stratum（基于递归 join 数量）
2. 在该 stratum 之前一次性传数据到 GPU，之后传回 CPU
3. 从该 stratum 向前/后扩展，将邻近 strata 也纳入 GPU 执行
4. 扩展直到 stratum 的输入输出规模变小（类似 min-cut 策略）

### 2.6 表达式求值的两条代码路径

- **纯列置换/子集**的 projection：退化为一系列列式内存拷贝
- **含算术/比较**的 projection：编译为简单栈机 bytecode，每个 GPU 线程对一个 fact 执行，使用线程本地的小型固定大小栈

---

## 三、Provenance 在 GPU 上的实现

### 3.1 Semiring 形式化

Provenance semiring **T** = (T, **0**, **1**, ⊕, ⊗)：
- T：tag 类型空间
- **0**：假（False），**1**：真（True）
- ⊕：析取（disjunction，对应 union），⊗：合取（conjunction，对应 join）

### 3.2 Lobster 实现的 7 个 Semiring

| Semiring | T | ⊕ | ⊗ | 用途 |
|---|---|---|---|---|
| Unit (Bool) | {⊥, ⊤} | ∨ | ∧ | 离散 Datalog |
| MaxMinProb | [0,1] | max | min | 概率推理（路径最大概率） |
| AddMultProb | [0,1] | + | × | 精确概率（独立假设） |
| Top-1-Proof | DNF 集合 | 保留概率最高 1 个证明 | 合并证明集 | 近似概率+可解释 |
| diff-top-1-proofs | Top-1-Proof + 梯度 | 同上 | 同上 | 端到端可微训练 |
| diff-max-min-prob | MaxMinProb + 梯度 | max | min | 可微概率 |
| diff-add-mult-prob | AddMultProb + 梯度 | + | × | 可微概率 |

### 3.3 Tag 在并行环境中的传播机制

**关键设计**：不同 operator 对 tag 的处理方式不同，APM 将其编码为不同指令的 α/σ/⊗ 参数：

| Operator | Tag 处理 | 实现 |
|---|---|---|
| Project (π) | 1:1 透传 | `copy(sₜ)` |
| Join (⋈) | ⊗ 合并（AND） | `gather⟨⊗⟩([iₗ, iᵣ], [aₜ, bₜ])` |
| Union (∪) | ⊕ 合并（OR） | `unique⟨⊕⟩` 中的 σ 函数 |
| Select (σ) | 直接透传 | - |

**并行正确性保证**：
- Join 中：`gather⟨⊗⟩` 对每对匹配 (iₗ, iᵣ) 独立计算 ⊗，行间无依赖 → 完美并行
- Union/去重中：先排序（stable sort）→ 相同 fact 变相邻 → `unique` 扫描合并，每个 group 内串行（但 group 间完全并行）
- 排序的 uniqueness 保证了 ⊕ 应用时不会有竞争条件

### 3.4 Top-1-Proof 的特殊处理

Top-1-Proof semiring 追踪每个 fact 最可能的一个推导路径（布尔变量引用集合）：
- Tag = 布尔变量集合（DNF 的一个 clause）
- ⊕ = 选择概率更高的 1 个 proof（近似，非精确）
- ⊗ = 合并两个 proof（集合并，检查冲突）
- **固定大小限制**：证明大小上限编译时指定（benchmark 中设为 300），确保 alloc 可静态确定
- diff 版本：tag 额外附带梯度信息，支持反向传播

---

## 四、性能数据

### 4.1 vs Scallop（主要对比基准）

#### 训练 Speedup（Figure 8）
| Task | 说明 | Speedup |
|---|---|---|
| CLUTRR | 关系推理 NLP | 1.22× |
| HWF | 手写数学公式识别 | 1.22× |
| Pathfinder | 图路径 + 视觉 | 1.26× |
| **PacMan** | 规划 | **16.46×** |

- Pathfinder 端到端训练：Scallop 41h → Lobster 32h

#### 推理 Speedup（Figure 9）
| Task | Speedup |
|---|---|
| CLUTRR | 3.69× |
| HWF | 1.22× |
| Pathfinder | 1.55× |
| PacMan | 2.11× |

#### 概率静态分析 Speedup（Figure 11）
| 数据集 | Speedup |
|---|---|
| avrora | 12.38× |
| biojava | 14.16× |
| graphchi | 1.59× |
| jme3 | 18.73× |
| pmd | ~12× |
| sunflow-core | 1.18× |
| sunflow | 14.47× |

#### RNA 二级结构预测 Speedup（Figure 12）
| 序列长度 | 近似 Speedup |
|---|---|
| 28 bp | **0.6×**（慢 40%，启动开销主导） |
| ~60 bp | ~40× |
| ~100 bp | ~200× |
| ~160 bp | **~550-600×** |

**关键发现**：在小规模输入上 GPU overhead 反而慢；超过某个规模阈值后，加速比与问题规模正相关，最高超过 500×。

#### 综合平均
- **9 个应用平均加速比：3.9× over Scallop**

### 4.2 vs CPU Datalog（Soufflé / FVLog）

#### Transitive Closure（Figure 13）
- Scallop 比 Soufflé 慢 30-90×（说明 provenance 开销巨大）
- Lobster 比 Soufflé 快 5-80×（视图而定）
- Lobster 在大多数图上超过 FVLog（另一 GPU Datalog 引擎）
- ProbLog 在大图上全部超时（>2h）

#### Same Generation（Table 3，Lobster vs FVLog）
| 数据集 | Lobster (s) | FVLog (s) | 备注 |
|---|---|---|---|
| fe-sphere | **3.91** | 12.99 | |
| CA-HepTH | **2.16** | 6.40 | |
| ego-Facebook | **0.53** | OOM | FVLog 内存不足 |
| fe_body | **10.17** | 21.17 | |
| loc-Brightkite | **1.45** | OOM | |
| SF.cedge | **14.01** | 23.72 | |
| vsp_finan | OOM | **90.10** | Lobster 内存不足 |

双方均能完成的数据集上，Lobster 至少快 2×。

#### CSPA（Table 4，Lobster vs FVLog）
| 数据集 | Lobster (s) | FVLog (s) |
|---|---|---|
| httpd | 3.61 | **2.57** |
| linux | **1.81** | 3.91 |
| postgres | **3.32** | 4.39 |

几何平均：Lobster 1.27× over FVLog。

### 4.3 Ablation Study（Figure 10）

测试四种配置对 Pathfinder/PacMan 的影响：
- **None**：无优化 → grid size > 20 后退化到接近 Scallop
- **Alloc**（arena + buffer reuse）：贡献最大
- **Stratum**（offloading scheduling）：大问题上有显著贡献
- **Both**：两者结合效果最佳

---

## 五、对 Nous 的具体建议

### 5.1 当前 Nous 状态对比

| 维度 | Nous 当前 | Lobster 方案 |
|---|---|---|
| 推理引擎 | Cozo (嵌入式 Datalog, CPU) | GPU Datalog via APM |
| P99 延迟 | <1ms | 小规模下有 GPU 启动开销（~ms 级） |
| 并行性 | CPU 单线程/多核 | GPU 数千线程 |
| Provenance | 未提及 | semiring 统一框架 |
| 后端接口 | dialect 字段预留 | 需要 backend trait |

### 5.2 现在可以预留的接口设计

#### A. 推理后端抽象层（最重要）

```rust
/// Nous 推理后端接口
trait ReasoningBackend {
    type Relation;     // 关系类型（CPU: BTreeMap, GPU: 列式向量）
    type Tag;          // Provenance tag 类型（unit / prob / diff）
    type Semiring;     // (T, 0, 1, ⊕, ⊗)

    /// 执行一个 stratum 的不动点迭代
    fn eval_stratum(&mut self, rules: &[Rule]) -> Result<()>;
    
    /// 加载 EDB（外部数据库，来自神经网络输出）
    fn load_edb(&mut self, facts: Vec<Fact<Self::Tag>>) -> Result<()>;
    
    /// 查询结果
    fn query(&self, relation: &str) -> Vec<Tuple<Self::Tag>>;
}

/// 支持 static index reuse 的后端需实现此 trait
trait StaticIndexBackend: ReasoningBackend {
    fn build_static_index(&self, relation: &str) -> Self::Index;
    fn invalidate_static_index(&mut self, relation: &str);
}
```

**为什么现在就要**：Lobster 的 `static h ← build(...)` 跨迭代复用 hash index 是 3-16× 加速的核心之一。未来接入 GPU 后端时，如果当前设计把 EDB 每次都重传，将丢失这个优化。现在就要在接口上声明「哪些关系是 static 的」。

#### B. 列式关系表示（数据格式兼容）

```rust
/// 同时支持 CPU 行式和 GPU 列式的关系表示
enum RelationLayout {
    RowMajor(Vec<Vec<Value>>),      // Cozo 当前：行式
    ColumnMajor {                    // GPU 后端需要：列式
        columns: Vec<Vec<Value>>,   // 每列独立
        tags: Vec<Tag>,             // 与 Lobster 的 tag 寄存器对应
    },
}

/// 关系转换（CPU↔GPU 迁移时调用）
fn to_column_major(rows: &[Vec<Value>]) -> RelationLayout;
fn to_row_major(cols: &RelationLayout) -> Vec<Vec<Value>>;
```

**为什么现在就要**：将来 GPU 后端需要列式数据，接口层做一次转换比散落在业务逻辑里好维护。

#### C. Matcher 的 Provenance-Aware 抽象

Nous 的 gate pipeline matcher 需要支持 provenance 传播：

```rust
/// Matcher 的 provenance 上下文
struct MatchContext<S: Semiring> {
    tag: S::Tag,      // 当前推导的 provenance tag
}

/// Matcher 结果需携带 tag
struct MatchResult<S: Semiring> {
    bindings: HashMap<String, Value>,
    tag: S::Tag,                      // 从 neural 输出继承的概率/梯度
}

/// Gate pipeline 中的 semiring join
fn combine_match_results<S: Semiring>(
    left: &MatchResult<S>, 
    right: &MatchResult<S>
) -> MatchResult<S> {
    MatchResult {
        bindings: merge_bindings(&left.bindings, &right.bindings),
        tag: S::conjunction(&left.tag, &right.tag),  // = ⊗
    }
}
```

**为什么**：Lobster 的核心是 `gather⟨⊗⟩` —— join 时 tag 通过 ⊗ 合并。Nous 的 matcher 如果将来要支持概率推理或可微训练，需要同样的机制。

#### D. Stratum 级别的调度元数据

```rust
/// 规则的 stratum 信息（供后端优化调度）
struct StratumMeta {
    id: usize,
    is_recursive: bool,          // 是否递归（影响 fix-point 迭代需求）
    estimated_join_depth: usize, // 递归 join 数量（Lobster 用于 stratum offloading）
    edb_relations: Vec<String>,  // 不动点内不变的关系（可建 static index）
    idb_relations: Vec<String>,  // 推导关系（需 delta 管理）
}
```

**为什么**：Lobster 的 stratum offloading 核心是识别「最长 stratum」并把它整体放 GPU。Nous 如果现在记录 `is_recursive` 和 `estimated_join_depth`，未来零改造就能接入这个优化。

### 5.3 Gate Pipeline 兼容 GPU 后端的关键设计

#### 当前 matcher 的潜在问题

Lobster 对 GPU 不友好的设计是：
1. **动态数据结构**：pointer-based trees 不适合 GPU
2. **行式访问**：非连续内存访问
3. **控制流**：条件分支导致 warp divergence

#### Nous matcher 的建议

```
现在做（低成本）：
1. matcher 的中间结果用列式存储（或至少支持转换）
2. 约束集合表示为固定大小的位集（而非动态链表），GPU 上天然并行
3. 「候选 facts」的过滤条件编译为 predicate bytecode（参考 Lobster 的 bytecode interpreter）

未来 GPU 化时获益：
4. 过滤 predicate → GPU kernel（一行一线程）
5. hash join 替代嵌套循环 join（count+scan+join 三件套）
6. 规则体内多个 matcher 的依赖关系 → stratum DAG → 整体 offload 到 GPU
```

### 5.4 何时考虑 GPU 后端

根据 Lobster 的 benchmark 数据，给出 Nous 的阈值建议：

| 条件 | 建议 |
|---|---|
| 约束规模 < 50 条规则，P99 <1ms | 继续 Cozo CPU，GPU 启动开销 (>1ms) 反而变慢 |
| 约束规模 200+，或 fix-point 迭代 >50 轮 | 考虑 GPU 后端（参考 RNA SSP：~60bp 时开始 40× 加速） |
| 需要概率推理（P(policy|context)） | GPU 后端价值大（Lobster: prob static analysis 12-18×） |
| 需要端到端可微训练（policy network + symbolic rules） | GPU 后端**必须**（消除 Amdahl 瓶颈） |

### 5.5 dialect 字段的扩展建议

Nous 已预留的 `dialect` 字段，建议扩展为：

```yaml
reasoning_backend:
  dialect: datalog          # datalog | prolog | asp
  engine: cozo              # cozo | lobster | souffle | custom
  provenance: unit          # unit | top1proof | addmult | maxmin | diff-*
  execution: cpu            # cpu | gpu | hybrid
  static_relations:         # 指定哪些关系可建 static hash index
    - edge
    - constraint_base
  stratum_offload: auto     # auto | gpu | cpu（未来 Lobster 集成时使用）
```

---

## 六、关键洞察总结

1. **APM 的核心价值是「正确性即性能」**：只要写出合法 APM 程序（无控制流、SSA、静态 alloc），就自动获得 GPU 效率保证。这个设计思路可以借鉴到 Nous 的 matcher IR 设计。

2. **static 寄存器是关键优化**：对于 Nous 这类「约束库基本不变，只有 context 变化」的场景，EDB 建的 hash index 完全可以跨请求复用（类似 prepared statement）。

3. **列式存储是 GPU 适配的必要条件**：不是充分条件，但没有列式布局基本没有 GPU 加速。这是现在 Cozo 要改成本最高的部分，值得提前在接口层隔离。

4. **小规模 GPU 比 CPU 慢**：RNA SSP 28bp 时 Lobster 比 Scallop 慢 40%。Nous 当前 P99 <1ms 的场景不要急着上 GPU，但要为 scale-up 预留接口。

5. **Provenance semiring 统一框架的工程价值**：用同一套抽象支持离散/概率/可微三种模式，只需换 semiring 参数，不需要改编译器。Nous 的 `Tag` 类型如果现在设计成泛型参数，未来切换 provenance 类型零成本。

---

*分析完成 | 基于 ArXiv 2503.21937v2 (ASPLOS 2026) | 2026-03-13*
