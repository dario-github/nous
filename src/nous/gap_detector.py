"""Nous — 规则缺口检测 (M3.2)

分析 decision_log 中的 fp/fn 记录，识别规则过严或过松的模式。

GapPattern 类型：
    too_strict  — fp ≥ 2 次同 action_type：规则过于严格
    too_loose   — fn ≥ 1 次同 action_type：规则过于宽松
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("nous.gap_detector")


# ── GapPattern ─────────────────────────────────────────────────────────────


@dataclass
class GapPattern:
    """
    规则缺口模式。

    Attributes:
        pattern_type:  "too_strict"（过严，fp）或 "too_loose"（过松，fn）
        action_type:   触发问题的操作类型
        rule_id:       关联的规则 ID（too_strict 时为被误触发的规则；too_loose 时为空）
        count:         问题记录数量
        examples:      原始 decision_log 记录样本（最多 3 条）
        suggested_fix: 建议的修复说明
    """
    pattern_type: str            # "too_strict" | "too_loose"
    action_type: str
    rule_id: str = ""            # too_strict 时有值，too_loose 时为空
    count: int = 0
    examples: list = field(default_factory=list)
    suggested_fix: str = ""


# ── 工具函数 ────────────────────────────────────────────────────────────────


def _parse_json_field(val) -> dict | list:
    """将 DB 返回的 JSON 字段（可能是 str 或 dict/list）解析为 Python 对象"""
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            pass
    return {} if not isinstance(val, list) else []


def _get_action_type(facts) -> Optional[str]:
    """从 facts 字段中提取 action_type"""
    parsed = _parse_json_field(facts)
    if isinstance(parsed, dict):
        return parsed.get("action_type")
    return None


def _get_gate_rule_ids(gates) -> list[str]:
    """从 gates 字段中提取命中的规则 ID 列表"""
    parsed = _parse_json_field(gates)
    if isinstance(parsed, list):
        return [str(r) for r in parsed]
    return []


# ── 主检测函数 ─────────────────────────────────────────────────────────────


def detect_gaps(db, days: int = 7) -> list[GapPattern]:
    """
    分析最近 N 天的 fp/fn 记录，检测规则缺口模式。

    算法：
        1. 查询最近 days 天内 outcome 为 "fp" 或 "fn" 的记录
        2. 按 (action_type, outcome_type) 聚合
        3. fp ≥ 2 次同 action_type → 标记为 too_strict
        4. fn ≥ 1 次同 action_type → 标记为 too_loose

    Args:
        db:   NousDB 实例
        days: 分析窗口（天），默认 7

    Returns:
        list[GapPattern]，按 count 降序排列
    """
    if db is None:
        return []

    since = time.time() - days * 86400

    try:
        # 查询 FP 记录
        fp_rows = db._query_with_params(
            "?[ts, session_key, tool_name, facts, gates, outcome] := "
            "*decision_log{ts, session_key, tool_name, facts, gates, outcome}, "
            "ts >= $since, outcome = $outcome "
            ":order -ts :limit 500",
            {"since": since, "outcome": "fp"},
        )
        # 查询 FN 记录
        fn_rows = db._query_with_params(
            "?[ts, session_key, tool_name, facts, gates, outcome] := "
            "*decision_log{ts, session_key, tool_name, facts, gates, outcome}, "
            "ts >= $since, outcome = $outcome "
            ":order -ts :limit 500",
            {"since": since, "outcome": "fn"},
        )
    except Exception as e:
        logger.error("[gap_detector] 查询失败: %s", e)
        return []

    # ── 按 session_key 去重（gate_with_decision_log 会写两条记录）────────
    # 每个 session_key 保留 gates 非空的那条（含命中规则信息），无则保留第一条
    def _dedup_by_session(rows: list) -> list:
        seen: dict[str, dict] = {}
        for row in rows:
            sk = row.get("session_key", "")
            if sk not in seen:
                seen[sk] = row
            else:
                # 优先保留 gates 非空的记录
                existing_gates = _get_gate_rule_ids(seen[sk].get("gates", []))
                new_gates = _get_gate_rule_ids(row.get("gates", []))
                if new_gates and not existing_gates:
                    seen[sk] = row
        return list(seen.values())

    fp_rows = _dedup_by_session(fp_rows)
    fn_rows = _dedup_by_session(fn_rows)

    # ── 分析 FP (too_strict) ────────────────────────────────────────────
    # 按 (action_type, rule_id) 分组
    fp_groups: dict[tuple, list] = defaultdict(list)
    for row in fp_rows:
        action_type = _get_action_type(row.get("facts", {}))
        if not action_type:
            action_type = row.get("tool_name") or "unknown"
        rule_ids = _get_gate_rule_ids(row.get("gates", []))
        top_rule = rule_ids[0] if rule_ids else ""
        key = (action_type, top_rule)
        fp_groups[key].append(row)

    # ── 分析 FN (too_loose) ─────────────────────────────────────────────
    # 按 action_type 分组
    fn_groups: dict[str, list] = defaultdict(list)
    for row in fn_rows:
        action_type = _get_action_type(row.get("facts", {}))
        if not action_type:
            action_type = row.get("tool_name") or "unknown"
        fn_groups[action_type].append(row)

    patterns: list[GapPattern] = []

    # fp ≥ 2 → too_strict
    for (action_type, rule_id), rows in fp_groups.items():
        if len(rows) >= 2:
            patterns.append(GapPattern(
                pattern_type="too_strict",
                action_type=action_type,
                rule_id=rule_id,
                count=len(rows),
                examples=rows[:3],
                suggested_fix=(
                    f"规则 {rule_id!r} 对 action_type={action_type!r} "
                    f"触发了 {len(rows)} 次 false positive。"
                    f"建议：禁用或放宽该规则的触发条件。"
                ),
            ))

    # fn ≥ 1 → too_loose
    for action_type, rows in fn_groups.items():
        if len(rows) >= 1:
            patterns.append(GapPattern(
                pattern_type="too_loose",
                action_type=action_type,
                rule_id="",
                count=len(rows),
                examples=rows[:3],
                suggested_fix=(
                    f"action_type={action_type!r} 触发了 {len(rows)} 次 false negative。"
                    f"建议：添加针对该操作类型的 block 规则。"
                ),
            ))

    # 按 count 降序
    patterns.sort(key=lambda p: p.count, reverse=True)

    logger.info(
        "[gap_detector] 检测完成：%d FP 分组，%d FN 分组，%d 个缺口模式",
        len(fp_groups),
        len(fn_groups),
        len(patterns),
    )

    return patterns
