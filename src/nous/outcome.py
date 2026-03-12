"""Nous — Outcome 回填 (M3.1)

gate() 返回后，post-execution 阶段可调用 backfill_outcome()
将真实执行结果回填到 decision_log 表的 outcome 字段。

OutcomeType:
    allowed  — gate 放行，执行正常（true negative）
    blocked  — gate 拦截，执行被阻止（true positive）
    fp       — false positive：gate 拦截了不该拦截的操作
    fn       — false negative：gate 放行了本该拦截的操作

设计：gate() 初始 outcome 字段存放 gate verdict（block/allow/confirm/warn）。
     backfill_outcome() 将其更新为真实执行结果（allowed/blocked/fp/fn）。
     get_pending_outcomes() 返回尚未回填的记录。
"""
from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger("nous.outcome")

# ── 已完成回填的 outcome 值集合 ─────────────────────────────────────────────

FINAL_OUTCOMES = {"allowed", "blocked", "fp", "fn"}

# gate() 初始写入的 verdict 值（这些视为"待回填"）
PENDING_OUTCOMES = {"block", "allow", "confirm", "warn", "rewrite",
                    "transform", "delegate", "require", ""}


# ── OutcomeType ────────────────────────────────────────────────────────────


class OutcomeType(str, Enum):
    """执行结果类型（回填到 decision_log.outcome）"""
    allowed = "allowed"   # gate 放行，执行正常（true negative）
    blocked = "blocked"   # gate 拦截，执行被阻止（true positive）
    fp = "fp"             # false positive：gate 过度拦截
    fn = "fn"             # false negative：gate 漏放


# ── 回填函数 ───────────────────────────────────────────────────────────────


def backfill_outcome(
    decision_log_id: str,
    outcome: "OutcomeType",
    db,
) -> bool:
    """
    将 decision_log 表中 session_key = decision_log_id 的记录的 outcome 字段更新为真实结果。

    Args:
        decision_log_id: gate() 返回的 decision_log_id（即 session_key）
        outcome:         OutcomeType 枚举值
        db:              NousDB 实例

    Returns:
        True 更新成功，False 失败或未找到记录
    """
    if db is None:
        return False

    if not decision_log_id:
        logger.warning("[outcome] backfill_outcome: decision_log_id 为空")
        return False

    try:
        # Step 1: 查询所有匹配 session_key 的记录（获取 ts）
        rows = db._query_with_params(
            "?[ts, session_key] := "
            "*decision_log{ts, session_key}, "
            "session_key = $sk",
            {"sk": decision_log_id},
        )

        if not rows:
            logger.debug("[outcome] backfill_outcome: 未找到 session_key=%s", decision_log_id)
            return False

        # Step 2: 逐行更新 outcome 字段
        updated = 0
        for row in rows:
            ts = row.get("ts", 0.0)
            try:
                db.db.run(
                    "?[ts, session_key, outcome] <- [[$ts, $sk, $outcome]] "
                    ":update decision_log {ts, session_key => outcome}",
                    {
                        "ts": ts,
                        "sk": decision_log_id,
                        "outcome": outcome.value,
                    },
                )
                updated += 1
            except Exception as e:
                logger.error("[outcome] 更新行失败 ts=%.6f sk=%s: %s", ts, decision_log_id, e)

        return updated > 0

    except Exception as e:
        logger.error("[outcome] backfill_outcome 异常: %s", e)
        return False


# ── 查询待回填记录 ─────────────────────────────────────────────────────────


def get_pending_outcomes(db, limit: int = 50) -> list[dict]:
    """
    返回尚未回填 outcome 的决策记录（outcome 仍为初始 gate verdict）。

    "待回填"定义：outcome 不在 FINAL_OUTCOMES 中，即仍为 gate 初始写入值。

    Args:
        db:    NousDB 实例
        limit: 最多返回条数（默认 50）

    Returns:
        list[dict]，每条为 decision_log 记录
    """
    if db is None:
        return []

    try:
        rows = db._query_with_params(
            f"?[ts, session_key, tool_name, facts, gates, outcome] := "
            f"*decision_log{{ts, session_key, tool_name, facts, gates, outcome}} "
            f":order -ts :limit {limit}",
            {},
        )
    except Exception as e:
        logger.error("[outcome] get_pending_outcomes 查询失败: %s", e)
        return []

    # 在 Python 层过滤：排除已回填的 outcome
    pending = [
        row for row in rows
        if row.get("outcome", "") not in FINAL_OUTCOMES
    ]

    return pending


# ── 统计工具 ───────────────────────────────────────────────────────────────


def get_outcome_coverage(db) -> dict:
    """
    返回 outcome 回填覆盖率统计。

    Returns:
        dict with keys: total, backfilled, pending, coverage_pct
    """
    if db is None:
        return {"total": 0, "backfilled": 0, "pending": 0, "coverage_pct": 0.0}

    try:
        rows = db._query_with_params(
            "?[ts, outcome] := *decision_log{ts, outcome} :limit 10000",
            {},
        )
    except Exception as e:
        logger.error("[outcome] get_outcome_coverage 查询失败: %s", e)
        return {"total": 0, "backfilled": 0, "pending": 0, "coverage_pct": 0.0}

    total = len(rows)
    backfilled = sum(1 for r in rows if r.get("outcome", "") in FINAL_OUTCOMES)
    pending = total - backfilled
    coverage = (backfilled / total * 100) if total > 0 else 0.0

    return {
        "total": total,
        "backfilled": backfilled,
        "pending": pending,
        "coverage_pct": round(coverage, 1),
    }
