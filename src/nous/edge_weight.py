"""Nous — 概率边权重 + 时序衰减 (M11.2)

提供 effective_confidence 计算：
  base_confidence × decay_factor(age, half_life) × access_boost(recency)

设计原则：
- 不修改 Cozo schema，decay_half_life 和 last_accessed 存在 relation.props 中
- 默认半衰期 90 天（实体关系的"记忆"周期）
- 查询时计算，不持久化衰减后的值（避免信息丢失）
- 被访问的边获得 recency boost（使用频率正反馈）
"""
from __future__ import annotations

import math
import time
from typing import Optional


# ── 默认配置 ──────────────────────────────────────────────────────────────

DEFAULT_HALF_LIFE_DAYS = 90       # 90 天半衰期
DEFAULT_HALF_LIFE_SECS = DEFAULT_HALF_LIFE_DAYS * 86400
ACCESS_BOOST_MAX = 0.15           # 最近被访问的边最多 +15% 置信度
ACCESS_BOOST_DECAY_DAYS = 7       # 访问 boost 在 7 天内衰减到 0


# ── 核心函数 ──────────────────────────────────────────────────────────────


def effective_confidence(
    base_confidence: float,
    created_at: float,
    props: dict | None = None,
    now: float | None = None,
) -> float:
    """计算边的有效置信度（考虑时间衰减 + 访问 boost）。

    Args:
        base_confidence: 原始置信度 (0.0 - 1.0)
        created_at: 关系创建时间戳（epoch seconds）
        props: 关系的 props 字典，可能包含 decay_half_life / last_accessed
        now: 当前时间戳（默认 time.time()）

    Returns:
        float: 衰减 + boost 后的有效置信度，clamp 到 [0.0, 1.0]
    """
    if now is None:
        now = time.time()

    props = props or {}

    # ── 时间衰减 ──
    half_life = props.get("decay_half_life", DEFAULT_HALF_LIFE_SECS)
    if half_life <= 0:
        half_life = DEFAULT_HALF_LIFE_SECS

    age_secs = max(0, now - created_at)
    # 指数衰减：confidence × 0.5^(age / half_life)
    decay_factor = math.pow(0.5, age_secs / half_life)

    # ── 访问 boost ──
    last_accessed = props.get("last_accessed", 0)
    access_boost = 0.0
    if last_accessed > 0:
        access_age_days = (now - last_accessed) / 86400
        if access_age_days < ACCESS_BOOST_DECAY_DAYS:
            # 线性衰减 boost
            access_boost = ACCESS_BOOST_MAX * (1 - access_age_days / ACCESS_BOOST_DECAY_DAYS)

    effective = base_confidence * decay_factor + access_boost
    return max(0.0, min(1.0, effective))


def record_access(props: dict) -> dict:
    """记录边被访问。返回更新后的 props（需要写回 DB）。

    Args:
        props: 当前 relation props

    Returns:
        dict: 更新了 last_accessed 和 access_count 的 props
    """
    new_props = dict(props)
    new_props["last_accessed"] = time.time()
    new_props["access_count"] = new_props.get("access_count", 0) + 1
    return new_props


def set_decay_half_life(props: dict, half_life_days: float) -> dict:
    """设置边的自定义衰减半衰期。

    Args:
        props: 当前 relation props
        half_life_days: 半衰期（天）

    Returns:
        dict: 更新了 decay_half_life 的 props
    """
    new_props = dict(props)
    new_props["decay_half_life"] = half_life_days * 86400
    return new_props


# ── 批量查询辅助 ──────────────────────────────────────────────────────────


def rank_relations_by_effective_confidence(
    relations: list[dict],
    now: float | None = None,
) -> list[dict]:
    """按有效置信度降序排列关系。

    Args:
        relations: list of dicts with keys: confidence, created_at, props

    Returns:
        list[dict]: 每项增加 effective_confidence 字段，降序排列
    """
    if now is None:
        now = time.time()

    for rel in relations:
        rel["effective_confidence"] = effective_confidence(
            base_confidence=rel.get("confidence", 1.0),
            created_at=rel.get("created_at", now),
            props=rel.get("props", {}),
            now=now,
        )

    return sorted(relations, key=lambda r: r["effective_confidence"], reverse=True)
