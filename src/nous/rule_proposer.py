"""Nous — 候选规则自动生成 (M3.3)

基于 GapPattern 自动生成候选约束 YAML，写入 ontology/proposals/ 目录。
生成的 YAML 与 constraints/ 格式一致，可被热加载器直接读取。

too_strict  → 生成禁用原规则的候选 YAML（enabled: false）
too_loose   → 生成新 block 规则的候选 YAML
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import yaml

from nous.gap_detector import GapPattern

logger = logging.getLogger("nous.rule_proposer")

# 默认 proposals 目录（相对于 nous/ 根目录）
_DEFAULT_PROPOSALS_DIR = (
    Path(__file__).parent.parent.parent.parent  # nous/ 根
    / "ontology"
    / "proposals"
)


# ── propose_rule_fix ───────────────────────────────────────────────────────


def propose_rule_fix(gap: GapPattern) -> dict:
    """
    根据 GapPattern 生成候选规则 YAML（作为 Python dict）。

    too_strict → 生成禁用原规则的候选（enabled: false，保留原触发条件）
    too_loose  → 生成新的 block 规则（针对该 action_type）

    Args:
        gap: GapPattern 实例

    Returns:
        dict，可被 yaml.dump() 序列化并被 constraint_parser 读取
    """
    ts_str = _ts_label()

    if gap.pattern_type == "too_strict":
        # 生成禁用原规则的提案
        rule_id = gap.rule_id or f"AUTO-DISABLE-{gap.action_type.upper()}"
        proposal = {
            "id": rule_id,
            "name": f"[自动提案] 禁用规则（过多 FP）: {rule_id}",
            "priority": 100,
            "enabled": False,          # 关键：禁用原规则
            "trigger": {
                "action_type": {
                    "in": [gap.action_type],
                }
            },
            "verdict": "block",
            "reason": (
                f"[自动生成 {ts_str}] 原规则 {rule_id!r} "
                f"对 action_type={gap.action_type!r} 触发了 {gap.count} 次 FP。"
                f"已禁用，请人工审核后决定是否修改触发条件。"
            ),
            "metadata": {
                "auto_generated": True,
                "gap_pattern": "too_strict",
                "action_type": gap.action_type,
                "fp_count": gap.count,
                "original_rule_id": gap.rule_id,
                "generated_at": ts_str,
            },
        }

    elif gap.pattern_type == "too_loose":
        # 生成新的 block 规则
        new_id = f"AUTO-BLOCK-{gap.action_type.upper()}-{ts_str}"
        proposal = {
            "id": new_id,
            "name": f"[自动提案] 新增 block 规则（FN 检测）: {gap.action_type}",
            "priority": 80,
            "enabled": True,
            "trigger": {
                "action_type": {
                    "in": [gap.action_type],
                }
            },
            "verdict": "block",
            "reason": (
                f"[自动生成 {ts_str}] action_type={gap.action_type!r} "
                f"触发了 {gap.count} 次 FN（漏放）。"
                f"已自动生成 block 规则，请人工审核触发条件范围。"
            ),
            "metadata": {
                "auto_generated": True,
                "gap_pattern": "too_loose",
                "action_type": gap.action_type,
                "fn_count": gap.count,
                "generated_at": ts_str,
            },
        }

    else:
        raise ValueError(f"未知 gap.pattern_type: {gap.pattern_type!r}")

    return proposal


# ── save_proposal ──────────────────────────────────────────────────────────


def save_proposal(
    proposal: dict,
    proposals_dir: Optional[Path | str] = None,
) -> Path:
    """
    将候选规则 dict 写入 ontology/proposals/ 目录下的 YAML 文件。

    文件命名规则：
        proposal-{rule_id}-{timestamp}.yaml
        其中 rule_id 取自 proposal["id"]，timestamp 为当前 Unix 时间戳（整秒）

    Args:
        proposal:      由 propose_rule_fix() 生成的 dict
        proposals_dir: proposals 目录路径（默认 ontology/proposals/）

    Returns:
        写入的文件 Path
    """
    if proposals_dir is None:
        proposals_dir = _DEFAULT_PROPOSALS_DIR
    proposals_dir = Path(proposals_dir)
    proposals_dir.mkdir(parents=True, exist_ok=True)

    rule_id = proposal.get("id", "unknown")
    # 文件名：proposal-{safe_id}-{timestamp}.yaml
    safe_id = _safe_filename(rule_id)
    ts_int = int(time.time())
    filename = f"proposal-{safe_id}-{ts_int}.yaml"
    filepath = proposals_dir / filename

    # 如果同名文件已存在（极端情况），加毫秒后缀
    if filepath.exists():
        ts_ms = int(time.time() * 1000)
        filename = f"proposal-{safe_id}-{ts_ms}.yaml"
        filepath = proposals_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(proposal, f, allow_unicode=True, default_flow_style=False)

    logger.info("[rule_proposer] 候选规则已写入: %s", filepath)
    return filepath


# ── 工具函数 ────────────────────────────────────────────────────────────────


def _ts_label() -> str:
    """返回 YYYY-MM-DD 格式的日期标签"""
    import datetime
    return datetime.date.today().isoformat()


def _safe_filename(name: str) -> str:
    """将 rule_id 转换为安全的文件名（替换非法字符）"""
    import re
    return re.sub(r"[^\w\-]", "_", name)[:60]
