# invest/benchmarks/ — 对董事长可汇报的基线对照

## 为什么有这个目录

孙总不会看学术 leaderboard，他想知道的是**"跟业界标准比我们在哪"**。
这个目录的脚本都干一件事：把我们的模型和**同时段的 Qlib 官方 Alpha158 LGB
基线**摆在一起，apples-to-apples。

## 脚本

### `d_same_period_comparison.py` — 4/21 任务 D

对比两件东西，**相同 train/valid/test 切分**：

| 模型 | 特征数 | 参数 | 数据源 |
|------|-------|------|-------|
| A. 我们的 `run_round2_simple` | 8 | sane (L1=L2=0.1) | `invest/data/tushare_csi300_*.csv` |
| B. Qlib 官方 Alpha158 + LGB | 158 | Qlib canonical (L1=205.7, L2=580.9) | `~/.qlib/qlib_data/cn_data` |

切分（硬编码，对齐 `run_round2_simple.py`）：
- Train ≤ **2024-06-30**
- Valid = **2024-07-01 ~ 2025-03-31**
- Test = **2025-04-01 ~ 2026-04-15**

### 运行前置

1. tushare CSV 就位：
   ```
   invest/data/tushare_csi300_202310_202604.csv
   ```
2. Qlib bin 就位（用 `convert_to_qlib_bin.py` 转过一次）：
   ```
   ~/.qlib/qlib_data/cn_data/
   ```
3. Python 依赖同 `invest/requirements.txt`

### 一行命令

```bash
cd invest
python3 benchmarks/d_same_period_comparison.py
```

预期运行时间：5-20 分钟（Qlib Alpha158 特征计算较慢）。

### 输出

- 控制台：side-by-side 表
- 文件：`invest/benchmarks/d_results.json`

### 读法

**场景 1：Qlib Alpha158 在此时段也 < 0.03**
→ 2025-04~2026-04 市场整体对因子模型更难（量化新规、市场结构变化）
→ 我们的 0.0212 在此背景下合理，**向董事长说："业界基线在此时段也受挫"**

**场景 2：Qlib Alpha158 达到 0.04+**
→ 我们的 round2_simple 有明显改进空间（8 因子 vs 158 是主因）
→ 向董事长说："我们当前用的是极简特征集，下一步上 Alpha158 + ensemble 能追上基线"

## 对照的第二梯度（未写）

后续可以加：
- 私募排排网量化多头指数同期表现（需要订阅）
- 朝阳永续量化股票中性指数（需要订阅）
- 中证 500 指数 passive 对照（免费）
- 任意 5-10 家头部量化私募的同期业绩（部分公开）

这些不在 D 脚本里，因为它们是"汇报口径素材"而非"我们模型验证"。
