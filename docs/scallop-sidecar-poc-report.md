# Scallop Sidecar PoC — Status Report

## 完成项

### 1. scallop_sidecar.py (src/nous/scallop_sidecar.py)
- `ScallopSidecar` 类: 预加载 KG (482 entities, 579 relations) + 概率推理
- `ScallopVerdict` 结果结构: p_block, p_allow, uncertainty, decision, proof_paths
- `scallop_evaluate()` 便捷函数: 一行调用
- 三段式决策: hard_block (T3 硬拦截) → soft_block (T3-soft 审查) → trivial_allow (日历等)
- 概率传播: KG 边置信度 → topkproofs semiring → 多路径证据合并

### 2. 单元测试 (tests/test_scallop_sidecar.py)
- **8/8 pass**: T3 hard block × 3, T3-soft review, T5 social URL, T-disinfo, trivial allow, upload review
- CozoDB 对比: 4 cases, 2 agree / 2 expected disagree (fact extraction 差异)

### 3. AgentHarm 全集对比 (scripts/scallop_agentharm.py)
- 352 cases (176 harmful + 176 benign)
- **100% agreement** with CozoDB L1
- TPR: 4.5% (both) — L1 alone catches few; L3 semantic gate is the main defense
- FPR: 2.3% (both)
- Scallop block=4, review=8, allow=340

## 性能

| 引擎 | avg | p50 |
|------|-----|-----|
| CozoDB | 14.5ms | 14.3ms |
| Scallop | 142.0ms | 141.2ms |

**Scallop 10x 慢的原因**: 每次请求创建新 ScallopContext + 重新加载全部 KG facts。
**优化方向**: 预编译规则、增量 fact 注入、或维持长驻 context。

## 架构

```
Request → fact_extractor → CozoDB L1 (hard gate)
                              │
                   ┌──────────┴──────────┐
                   │ hard_block 命中      │ 否则
                   ↓                     ↓
                BLOCK              Scallop sidecar
                                   (概率推理层)
                                        │
                                   ┌────┴────┐
                                   ↓         ↓
                              p_block    p_allow
                                   ↓
                            Policy fusion
                                   ↓
                         block/review/allow
```

## 下一步

1. **性能优化**: Scallop context 复用 (预编译 + 增量注入)
2. **概率差异化**: 给 harmful 和 benign 加不同的 action_confidence,
   测试概率层能否在 CozoDB 无法区分的边界 case 上提供增益
3. **threshold sweep**: 遍历 τ_block ∈ [0.1, 0.9], 画 TPR/FPR 曲线
4. **GPT-5.4 批判审计**: 待执行
