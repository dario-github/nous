"""
决策驾驶舱（对外不叫 AI 系统）

v7 设计文档 §二 的三大能力 + 能力四的入口：
- 能力 1：结构化决策卡（12 维度 checklist）
- 能力 2：魔鬼代言人（反驳 Agent，可选）
- 能力 3：多视角陪审团（价值/动量/事件催化三独立打分）
- 能力 4：AI4Science 因子流水线（此模块不直接做，由 institutional 管道接）

红线遵守：
- 不替代 PM 判断（系统只补客观数据 + 问 checklist）
- PM 先独立填卡，系统后出手
- 魔鬼代言人可选，不强制门槛
- 不做价格预测
- 决策日志本地持久化

用法：
    from invest.decision_cockpit import Cockpit, DecisionCard

    card = DecisionCard(
        ticker="600519.SH", pm_name="张经理",
        thesis="..", business_model="..", ...)
    cockpit = Cockpit()
    record = cockpit.run(card, skip_devil=False)
    print(record.to_markdown())
"""
from .card import DecisionCard, CardField, DIMENSIONS
from .cockpit import Cockpit, DecisionRecord
from .devil import DevilAdvocate, DevilCritique
from .jury import Jury, JuryVerdict

__all__ = [
    "DecisionCard", "CardField", "DIMENSIONS",
    "Cockpit", "DecisionRecord",
    "DevilAdvocate", "DevilCritique",
    "Jury", "JuryVerdict",
]
