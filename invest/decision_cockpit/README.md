# decision_cockpit/ — 决策驾驶舱（v7 三大能力单 ticker 闭环）

> 给 5/15 孙总 demo 的 A1"工具形态"骨架。
> 对外**不**叫 AI 系统 / 不叫智能投顾。这是一份"备忘录助手 + 风控提醒"。

## 这是什么

v7 设计文档 §二 的三大核心能力，做成一个最小可跑的单标的闭环：

1. **结构化决策卡**（能力 1）— 12 维度 checklist，客观字段系统填，主观字段 PM 自己填
2. **魔鬼代言人**（能力 2）— 可选的反驳 Agent，**记录但不打扰** PM 决策流
3. **多视角陪审团**（能力 3）— 价值/动量/事件催化 三独立打分，**显式**分歧

## 红线遵守（v7 §设计红线 + Swarm 纪律）

- ✅ **不替代 PM 判断** — 系统只校验 schema + 提供反驳视角 + 打标签
- ✅ **PM 先独立判断** — card 内容是 PM 自填，devil/jury 后运行
- ✅ **魔鬼代言人可选** — `skip_devil=True` 时只记"跳过"，不拦截
- ✅ **不做价格预测** — jury 分数是 -3..+3 的"看空/看多"，不是涨跌幅
- ✅ **不排名 PM** — 本模块只处理单卡，不聚合跨 PM
- ✅ **数据本地** — records 落到本地，不外发

## 运行

### 最快一行

```bash
cd /path/to/nous
python3 -m invest.decision_cockpit.demo
```

这会用内置的**贵州茅台 600519.SH**示例卡跑一遍全流程，输出：
- 控制台 Markdown 报告（可直接贴进微信）
- `invest/decision_cockpit/records/600519.SH_<timestamp>.json`
- `invest/decision_cockpit/records/600519.SH_<timestamp>.md`

### 跳过魔鬼代言人

```bash
python3 -m invest.decision_cockpit.demo --skip-devil
```

### 用自己的卡

```bash
python3 -m invest.decision_cockpit.demo --card-json my_card.json
```

JSON 格式参考：`DecisionCard` 的 dataclass schema（12 维度 + ticker/pm_name）。

## LLM 配置

默认用 `StubLLMProvider`（无 LLM key 时的确定性 fallback）。
要换成真 LLM（qwen-turbo / openai / ...），构造 `Cockpit` 时传 `llm=`：

```python
from invest.decision_cockpit import Cockpit, DecisionCard

def my_llm(prompt: str, timeout_ms: int = 30000, model: str = "") -> str:
    # call your LLM here
    ...

cockpit = Cockpit(llm=my_llm)
```

未来迁移路径：`nous.semantic_gate.LLMProvider` 的 Protocol 跟本模块一致，
可直接用 `from nous.providers.openai_provider import ...`。

## 测试

```bash
python3 -m pytest invest/tests/test_decision_cockpit.py -v
```

覆盖：card 完整性 / 端到端闭环 / skip_devil / 落盘 / 分歧 label。

## 代码结构

```
decision_cockpit/
├── __init__.py
├── card.py              # DecisionCard schema + 12 维度 + 完整性检查
├── devil.py             # 魔鬼代言人（+ stub fallback）
├── jury.py              # 价值/动量/事件催化 3 陪审员 + signal label
├── cockpit.py           # 编排 + 落盘 + Markdown 输出
├── demo.py              # 单 ticker CLI demo（贵州茅台内置）
└── records/             # 落盘的决策档案（.gitignored？自己加）
```

## 后续演进方向（不在本次 skeleton 范围）

- 接 `nous.gate` 做字段完整性硬 block（现在只是 schema 级报告）
- 接 `nous.semantic_gate` 做 devil + jury 的 LLM 调用
- 接 `nous.decision_log` 做可审计留痕（现在只是 JSON 落盘）
- 接 `dashboard/api.py` 让 PM / 孙总 在 UI 上看 records
- 跟 `institutional/pipeline.py` 联动：单 ticker 决策 → 组合构建
- 微信推送通道（v7 §3.2 企微机器人）

## 给 5/15 demo 准备的 5 分钟剧本

```
1. "这不是 AI 系统，这是一个备忘录助手。"（1 句开场）
2. 运行 demo，把贵州茅台的完整 Markdown 投屏
3. 指向 12 维度 checklist — "这是给 PM 的飞行员起飞前检查表"
4. 指向魔鬼代言人 3 条 — "这些不是反对意见，是'你下次复盘会想回看的东西'"
5. 指向陪审团 3 路 + 分歧极差 — "系统不合成结论，显式呈现分歧"
6. "全部 PM 审核后才生效；系统不替任何人决策。"（1 句收尾）
```

**不**说：
- "AI 选股"
- "智能投顾"
- "机器学习预测股价"
- "替代分析师"
