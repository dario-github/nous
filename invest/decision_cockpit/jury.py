"""
多视角陪审团 — v7 能力 3

> 对同一标的，系统同时运行三个独立的分析 Agent：
>   - 价值视角（估值安全边际、ROIC、护城河、资本配置）
>   - 动量视角（资金流向、技术形态、板块热度）
>   - 事件催化（政策变化、供需拐点、管理层变动）
> 三方独立打分然后投票：3/3 强信号 / 2/3 中等+高亮分歧 / 1-0/3 建议暂缓

红线：
- 不隐藏加权系数 — 三路各自的分**显式**展示
- 不替 PM 投票 — 系统只**呈现分歧**
- 不做价格预测 — 评分范围是 -3..+3（看空..看多），不是涨跌幅
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional

from .card import DecisionCard
from .devil import LLMProvider, StubLLMProvider


# ═══════════════════════════════════════════════════════════════════
# Juror perspectives
# ═══════════════════════════════════════════════════════════════════

JUROR_PROMPT = {
    "value": """你是"价值派"陪审员。基于决策卡，**只从**以下维度给出打分（-3=强烈看空，+3=强烈看多）：
  - 估值安全边际（当前估值 vs 历史分位 vs 内在价值）
  - ROIC / 资本回报
  - 护城河的可持续性
  - 资本配置（分红、回购、并购纪律）

禁止：不评估技术面、动量、主题催化。

卡片：
{card_json}

输出 JSON：{{"score": <-3..3>, "reasoning": "一句话 ≤ 60 字", "concerns": ["...", "..."]}}
""",
    "momentum": """你是"动量派"陪审员。基于决策卡，**只从**以下维度给出打分（-3..+3）：
  - 技术形态（均线、支撑阻力、RSI/MACD 极端）
  - 资金流向（北向 / 融资融券 / 大单方向）
  - 板块/主题热度

禁止：不评估基本面、估值、催化事件。

卡片：
{card_json}

输出 JSON：{{"score": <-3..3>, "reasoning": "一句话 ≤ 60 字", "concerns": ["...", "..."]}}
""",
    "catalyst": """你是"事件催化"陪审员。基于决策卡，**只从**以下维度给出打分（-3..+3）：
  - 政策变化（行业新规、监管口径、产业政策）
  - 供需拐点（产能周期、价格拐点）
  - 管理层 / 公司治理重大变动（董监高、股权、战略）

禁止：不评估基本面细节、技术面。

卡片：
{card_json}

输出 JSON：{{"score": <-3..3>, "reasoning": "一句话 ≤ 60 字", "concerns": ["...", "..."]}}
""",
}


@dataclass
class JurorVote:
    perspective: str           # "value" / "momentum" / "catalyst"
    score: int                 # -3..+3
    reasoning: str
    concerns: List[str] = field(default_factory=list)
    raw_response: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class JuryVerdict:
    """三路投票汇总。"""

    ticker: str
    pm_name: str
    timestamp: str
    votes: List[JurorVote] = field(default_factory=list)
    # 聚合层（透明显式）
    scores_by_perspective: Dict[str, int] = field(default_factory=dict)
    disagreement_range: int = 0      # max(score) - min(score)
    n_bullish: int = 0               # score > 0 的数量
    n_bearish: int = 0               # score < 0 的数量
    n_neutral: int = 0               # score == 0
    signal_label: str = ""           # "strong" / "moderate+disagreement" / "weak-pause"

    def to_dict(self):
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════
# Jury agent
# ═══════════════════════════════════════════════════════════════════


class Jury:
    def __init__(
        self,
        llm: Optional[LLMProvider] = None,
        model: str = "qwen-turbo",
        disagreement_alert_threshold: int = 4,
    ):
        """
        Parameters
        ----------
        disagreement_alert_threshold : int
            三路打分极差 >= 此阈值时，label 打 'moderate+disagreement'
            (默认 4：例如 一家 +2 一家 -2 就会触发)
        """
        self.llm = llm or StubLLMProvider()
        self.model = model
        self.disagreement_alert_threshold = disagreement_alert_threshold

    # ─ 主流程 ─

    def run(self, card: DecisionCard) -> JuryVerdict:
        ts = datetime.now().isoformat()
        votes: List[JurorVote] = []
        for perspective in ("value", "momentum", "catalyst"):
            vote = self._juror(perspective, card)
            votes.append(vote)

        scores = {v.perspective: v.score for v in votes}
        rng = max(scores.values()) - min(scores.values()) if scores else 0
        n_bull = sum(1 for s in scores.values() if s > 0)
        n_bear = sum(1 for s in scores.values() if s < 0)
        n_neu = sum(1 for s in scores.values() if s == 0)

        label = self._label(n_bull, n_bear, rng)

        return JuryVerdict(
            ticker=card.ticker, pm_name=card.pm_name, timestamp=ts,
            votes=votes, scores_by_perspective=scores,
            disagreement_range=rng,
            n_bullish=n_bull, n_bearish=n_bear, n_neutral=n_neu,
            signal_label=label,
        )

    # ─ 单 juror ─

    def _juror(self, perspective: str, card: DecisionCard) -> JurorVote:
        prompt = JUROR_PROMPT[perspective].format(
            card_json=json.dumps(self._card_slim(card), ensure_ascii=False, indent=2)
        )
        try:
            raw = self.llm(prompt, model=self.model)
        except Exception as e:
            return self._fallback_vote(perspective, card, reason=f"LLM error: {e}")

        try:
            obj = json.loads(raw)
            return JurorVote(
                perspective=perspective,
                score=int(obj.get("score", 0)),
                reasoning=str(obj.get("reasoning", ""))[:100],
                concerns=[str(x)[:80] for x in obj.get("concerns", [])][:3],
                raw_response=raw,
            )
        except Exception:
            return self._fallback_vote(perspective, card, reason="parse failed")

    @staticmethod
    def _card_slim(card: DecisionCard) -> dict:
        return {
            "ticker": card.ticker,
            "business_model": card.business_model,
            "moat": card.moat,
            "valuation": card.valuation,
            "technicals": card.technicals,
            "catalysts": card.catalysts,
            "policy_env": card.policy_env,
            "risks": card.risks,
        }

    def _label(self, n_bull: int, n_bear: int, rng: int) -> str:
        if n_bull == 3:
            return "strong_bullish"
        if n_bear == 3:
            return "strong_bearish"
        if rng >= self.disagreement_alert_threshold:
            return "disagreement_flagged"
        if n_bull == 2:
            return "moderate_bullish"
        if n_bear == 2:
            return "moderate_bearish"
        return "weak_pause"

    # ─ Fallback，保证 demo 永远有输出 ─

    @staticmethod
    def _fallback_vote(perspective: str, card: DecisionCard, reason: str) -> JurorVote:
        """当 LLM 无法使用时，基于卡片中的线索做确定性评分。用意是让 demo
        能在 5/15 当天演示，不需要 API key。真实部署请配置 LLM。"""
        score = 0
        reasoning = f"（fallback，{reason}）"
        concerns: List[str] = []
        if perspective == "value":
            val = card.valuation or {}
            pe = val.get("pe") or val.get("PE")
            if pe is not None:
                if pe < 20:
                    score, reasoning = 1, "估值偏低，有安全边际"
                elif pe > 50:
                    score, reasoning = -2, "估值偏贵，缺乏安全边际"
                else:
                    score, reasoning = 0, "估值中性"
            concerns = ["ROIC 未在卡片中显式给出"]
        elif perspective == "momentum":
            tech = (card.technicals or "").lower()
            if any(k in tech for k in ["上涨", "突破", "强势", "金叉", "放量"]):
                score, reasoning = 2, "技术面给出积极信号"
            elif any(k in tech for k in ["下跌", "破位", "弱势", "死叉", "缩量"]):
                score, reasoning = -2, "技术面偏弱"
            concerns = ["资金流数据未在卡片中体现"]
        elif perspective == "catalyst":
            cats = (card.catalysts or "")
            pol = (card.policy_env or "")
            if cats and len(cats) > 30:
                score, reasoning = 1, "催化剂清晰"
            if "收紧" in pol or "新规" in pol:
                score -= 1
                reasoning += " / 政策收紧是风险"
            concerns = ["供需拐点需要额外数据验证"]
        return JurorVote(
            perspective=perspective, score=score,
            reasoning=reasoning, concerns=concerns,
            raw_response=f"[fallback: {reason}]",
        )
