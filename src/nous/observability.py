"""Nous — 可观测性框架 (M1.10)

DecisionLog 采样策略：
- block → 100% 记录
- allow → 10% 记录（可配置）
- schema_version 字段
"""
import random
import time
from dataclasses import dataclass, field
from typing import Optional

from nous.proof_trace import ProofTrace


# ── 采样策略 ────────────────────────────────────────────────────────────────


@dataclass
class SamplingPolicy:
    """
    决策日志采样策略。

    block_rate: block verdict 的记录概率（默认 1.0 = 100%）
    allow_rate: allow verdict 的记录概率（默认 0.1 = 10%）
    confirm_rate: confirm verdict 的记录概率（默认 1.0 = 100%）
    warn_rate: warn verdict 的记录概率（默认 0.5 = 50%）
    """
    block_rate: float = 1.0
    allow_rate: float = 0.1
    confirm_rate: float = 1.0
    warn_rate: float = 0.5

    def should_log(self, verdict: str) -> bool:
        """根据 verdict 和采样率决定是否记录"""
        rate_map = {
            "block": self.block_rate,
            "allow": self.allow_rate,
            "confirm": self.confirm_rate,
            "warn": self.warn_rate,
        }
        rate = rate_map.get(verdict, self.allow_rate)
        return random.random() < rate


# ── 当前 schema 版本 ────────────────────────────────────────────────────────

SCHEMA_VERSION = "1.0"


# ── 决策日志写入 ──────────────────────────────────────────────────────────


def log_decision(
    verdict: str,
    proof_trace: Optional[ProofTrace],
    sampling_policy: SamplingPolicy,
    db=None,
    session_key: str = "",
    tool_name: str = "",
    facts: Optional[dict] = None,
    latency_us: int = 0,
) -> bool:
    """
    根据采样策略决定是否写入 decision_log。

    返回 True 表示已写入，False 表示被采样跳过。
    """
    if not sampling_policy.should_log(verdict):
        return False

    if db is None:
        return True  # 无 DB 时视为"会写入"（测试用）

    ts = time.time()
    sk = session_key or f"auto:{ts:.6f}"
    trace_dict = proof_trace.to_dict() if proof_trace else {}

    try:
        db.db.run(
            "?[ts, session_key, tool_name, facts, gates, latency_us, "
            "outcome, proof_trace, schema_version] "
            "<- [[$ts, $sk, $tn, $facts, $gates, $lu, $outcome, $pt, $sv]] "
            ":put decision_log {ts, session_key => tool_name, facts, gates, "
            "latency_us, outcome, proof_trace, schema_version}",
            {
                "ts": ts,
                "sk": sk,
                "tn": tool_name,
                "facts": facts or {},
                "gates": [],
                "lu": latency_us,
                "outcome": verdict,
                "pt": trace_dict,
                "sv": SCHEMA_VERSION,
            },
        )
        return True
    except Exception as e:
        # 可观测性不应阻断主流程
        return False


def get_decision_stats(db) -> dict:
    """
    统计 decision_log 中各 verdict 的分布。

    返回 {"block": n, "allow": n, "confirm": n, "warn": n, "total": n}
    """
    if db is None:
        return {}

    try:
        rows = db.query(
            "?[outcome, count(ts)] := *decision_log{ts, outcome}"
        )
        # Cozo 聚合列名格式 count(ts)
        count_key = "count(ts)"
        stats = {r["outcome"]: r[count_key] for r in rows}
        stats["total"] = sum(stats.values())
        return stats
    except Exception:
        return {}
