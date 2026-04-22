"""
魔鬼代言人 — v7 能力 2

> PM 提交决策卡后，系统自动 spawn 一个**专门挑毛病的 Agent**。它的唯一任务是：
> "基于当前公开信息和历史类似失败案例，找出这个看多逻辑中最薄弱的 3 个点。"

红线：
- **可选**：不强制 PM 回应就能通过（v7 Swarm 辩论纪律 #2）
- **不打扰**：结果入档，不弹窗
- **记录在案**：3 个月后复盘时可回看

实现：
- 推理引擎走 LLMProvider（Protocol，接 qwen-turbo / openai / ...）
- 沙箱/无 key 时走 StubLLMProvider，输出可预测的模板反驳
- 接口尽量薄，方便后续换 nous.semantic_gate 作为底层
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Callable, List, Optional, Protocol

from .card import DecisionCard


class LLMProvider(Protocol):
    """与 nous.semantic_gate.LLMProvider 形状一致，方便未来替换。"""

    def __call__(self, prompt: str, timeout_ms: int = 30000, model: str = "") -> str: ...


class StubLLMProvider:
    """无 LLM 环境下的确定性回退。输出的反驳永远基于 card 里的风险列表 +
    标准追问清单（产能/估值/政策/管理层/竞争格局），让 demo 始终可跑。"""

    TEMPLATES = [
        "thesis 高度依赖 {assumption}，如果这一点被证伪（行业周期、技术替代、政策转向），整个看多逻辑不成立",
        "风险矩阵里列了 {n_risks} 条，但都是**已知风险**——对未知的二阶风险（供应链断裂 / 监管穿透）没有覆盖",
        "估值水平描述是 {valuation_desc}，若 forward PE 假设的净利润增速回撤 30%，估值吸引力会立即翻转",
    ]

    def __call__(self, prompt: str, timeout_ms: int = 30000, model: str = "") -> str:
        return "[StubLLM] reasoning skipped (no LLM key)"


@dataclass
class DevilCritique:
    """魔鬼代言人的一次产出。"""

    ticker: str
    pm_name: str
    timestamp: str
    skipped: bool = False
    skip_reason: str = ""
    # 反驳三条（或更少，保持简洁）
    points: List[str] = field(default_factory=list)
    # 引用的原 card 字段，便于复盘定位
    referenced_fields: List[str] = field(default_factory=list)
    model_used: str = "stub"
    raw_response: str = ""

    def to_dict(self):
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════
# Prompt 构造
# ═══════════════════════════════════════════════════════════════════

DEVIL_PROMPT_TEMPLATE = """你是一位资深的逆向投资经理 / 质疑者。你的任务**不是**给投资建议，
也**不是**否决这笔交易。你只做一件事：基于当前公开信息，找出下面这张看多决策卡中
**最薄弱的 3 个论点**。每一条反驳都必须：

  1. 指向 card 里的具体字段（商业模式 / 护城河 / 财务 / 估值 / 催化剂 / 技术面）
  2. 给一个可证伪的场景（"如果 X 发生，则此论点失效"）
  3. 不超过 80 字

**硬约束**：
- 不预测股价
- 不评价 PM 本人
- 不下最终结论（"应该卖出" 这种话不要说）

决策卡 JSON：
{card_json}

输出严格格式（JSON 数组，共 3 个对象，每个形如 {{"field": "...", "critique": "...", "falsification": "..."}}）：
"""


def build_prompt(card: DecisionCard) -> str:
    card_slim = {
        "ticker": card.ticker,
        "business_model": card.business_model,
        "moat": card.moat,
        "competitive_landscape": card.competitive_landscape,
        "catalysts": card.catalysts,
        "risks": card.risks,
        "thesis": card.thesis,
        "valuation_summary": card.valuation,
    }
    return DEVIL_PROMPT_TEMPLATE.format(card_json=json.dumps(card_slim, ensure_ascii=False, indent=2))


# ═══════════════════════════════════════════════════════════════════
# Agent
# ═══════════════════════════════════════════════════════════════════


class DevilAdvocate:
    """魔鬼代言人 agent。"""

    def __init__(
        self,
        llm: Optional[LLMProvider] = None,
        model: str = "qwen-turbo",
    ):
        self.llm = llm or StubLLMProvider()
        self.model = model

    def run(self, card: DecisionCard, skip: bool = False) -> DevilCritique:
        ts = datetime.now().isoformat()
        if skip:
            return DevilCritique(
                ticker=card.ticker, pm_name=card.pm_name, timestamp=ts,
                skipped=True, skip_reason="PM 选择跳过（v7 允许）",
            )

        prompt = build_prompt(card)
        try:
            raw = self.llm(prompt, model=self.model)
        except Exception as e:
            return DevilCritique(
                ticker=card.ticker, pm_name=card.pm_name, timestamp=ts,
                skipped=True, skip_reason=f"LLM 调用失败: {e}",
                model_used=self.model,
            )

        points, refs = self._parse(raw, card)
        return DevilCritique(
            ticker=card.ticker, pm_name=card.pm_name, timestamp=ts,
            points=points, referenced_fields=refs,
            model_used=self.model, raw_response=raw,
        )

    # ─ 内部 ─

    @staticmethod
    def _parse(raw: str, card: DecisionCard) -> tuple[List[str], List[str]]:
        """从 LLM 输出解析出 3 条反驳。解析失败就降级：直接给 stub 输出。"""
        # 尝试 JSON 解析
        try:
            obj = json.loads(raw)
            if isinstance(obj, list):
                points = [f"【{x.get('field','?')}】{x.get('critique','')}（反证：{x.get('falsification','')}）"
                          for x in obj[:3]]
                refs = [x.get("field", "") for x in obj[:3]]
                if points:
                    return points, refs
        except Exception:
            pass
        # 降级：基于 card 生成可解读的三条（保证 demo 永远有输出）
        fallback = _fallback_critique(card)
        return fallback["points"], fallback["refs"]


def _fallback_critique(card: DecisionCard) -> dict:
    """当 LLM 失败或没 key 时，生成一组固定但"有内容"的反驳，
    让 demo 至少能呈现三条。"""
    points = []
    refs = []

    # 1. thesis 依赖点
    thesis_preview = (card.thesis[:30] + "…") if len(card.thesis) > 30 else card.thesis
    points.append(f"【thesis】'{thesis_preview}' 的成立依赖行业/政策维持当前节奏；若 12 个月内出现同行业龙头业绩大幅不及预期，该论点先破")
    refs.append("thesis")

    # 2. 风险覆盖
    n_risks = len(card.risks)
    points.append(
        "【risks】已列 {n} 条都是 known-known，缺一条 unknown-unknown——"
        "例如外部供应链断裂 / 穿透监管 / 海外制裁 的尾部情景".format(n=n_risks)
    )
    refs.append("risks")

    # 3. 估值
    val_str = json.dumps(card.valuation, ensure_ascii=False) if card.valuation else "未提供"
    points.append(
        "【valuation】估值 {v} 基于当前 earnings；若 forward EPS 回撤 20-30%"
        "（行业 β 收敛时），当前的 cheap 会迅速转为 moderate-expensive".format(v=val_str)
    )
    refs.append("valuation")

    return {"points": points, "refs": refs}
