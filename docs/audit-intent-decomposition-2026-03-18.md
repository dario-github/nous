# Intent Decomposition 多方审计结果

> 2026-03-18 04:10 CST — 东丞要求的全局审计

## 审计方

| 审计方 | 评分 | 核心判定 |
|--------|------|---------|
| Gemini 3.1 Pro | 3.5/10 | 确定性幻觉，SPOF，冻结此方向 |
| GPT-5.4 | 4/10 | 不是范式转移，证据不足，先做 ablation |

## 共识结论

1. Intent Decomposition 有局部价值，但被严重过度宣称
2. 当务之急是修评估基建（capability/统计功效/Loss），不是新架构
3. 47 类固定 taxonomy 会成为技术债
4. 回 spec，做 M8.6b 和 M7.3

## Gemini 关键批判

- LLM 提取是 SPOF：攻击者把"窃取"包装成"备份"→ 后续推理全废
- 学术对标遗漏：IFC (Information Flow Control) 和 BDI 模型
- "在没有刻度尺时做微雕"
- 建议：冻结，回 M8 基建

## GPT-5.4 关键批判

- 先例已有：OpenAI Rule-Based Rewards, Anthropic Constitutional Classifiers, DeepMind Sparrow
- taxonomy 需要 hierarchical + open-set + abstain + novel discovery
- "分类比判断准"需要 3 组 ablation 验证
- Loss function：capability=0 = 自欺，权重无业务依据
- 72 cases CI ±11.6%，5-8% 改进不可区分于噪声
- 评估应拆三层：parser eval / policy eval / e2e eval
- Loss 应改 Pareto dashboard + hard gates

## 决策

- **冻结** Intent Decomposition，代码保留为实验分支
- **回退** V3.2 → V3.1（benchmark 数据支撑）
- **回 spec**：优先 M8.6b capability + M7.3 LLM delegate
- **LOOP.md** 增加 spec 对齐步骤

## V3.2 vs V3.1 Benchmark

| 指标 | V3.1 | V3.2 |
|------|------|------|
| TPR | 100% | 97.2% |
| FPR | 2.8% | 11.1% |
| L | 0.0083 | 0.0527 |

结论：更新 ≠ 更好。V3.1 保留。
