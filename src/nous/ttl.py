"""Nous — 规则 TTL 衰减 (M3.5)

定期检查 constraints/ 下的规则最后触发时间：
- 30 天未触发 → warning
- 60 天未触发 → disable（设 enabled: false）

触发时间计算：
1. 查询 decision_log 中包含该 rule_id 的最近记录 ts
2. 若从未触发，则取 YAML 中的 metadata.created_at（或文件解析时的 created_at）
"""
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from nous.constraint_parser import load_constraints

logger = logging.getLogger("nous.ttl")

# TTL 阈值（天）
WARN_DAYS = 30
DISABLE_DAYS = 60


@dataclass
class TTLAlert:
    """
    规则 TTL 警报。

    Attributes:
        rule_id:             规则 ID
        days_since_trigger:  距离最后触发（或创建）的天数
        action:              执行动作（"warning" 或 "disable"）
    """
    rule_id: str
    days_since_trigger: int
    action: str


def check_rule_ttl(constraints_dir: Path, db) -> list[TTLAlert]:
    """
    检查所有约束的 TTL，返回警报列表。

    对于达到 DISABLE_DAYS 的规则，会自动修改原 YAML 文件设为 enabled: false。
    """
    if db is None:
        return []

    alerts = []
    now = time.time()
    constraints = load_constraints(constraints_dir)

    for c in constraints:
        if not c.enabled:
            continue

        # 1. 查询最后触发时间
        last_triggered = _get_last_trigger_ts(db, c.id)

        # 2. 如果未触发过，取创建时间
        if last_triggered == 0.0:
            last_triggered = c.metadata.get("created_at", c.created_at)

        # 3. 计算天数
        days_since = int((now - last_triggered) / 86400)

        # 4. 判断阈值
        if days_since >= DISABLE_DAYS:
            alerts.append(TTLAlert(
                rule_id=c.id,
                days_since_trigger=days_since,
                action="disable"
            ))
            _disable_rule_in_file(constraints_dir, c.id)
        elif days_since >= WARN_DAYS:
            alerts.append(TTLAlert(
                rule_id=c.id,
                days_since_trigger=days_since,
                action="warning"
            ))

    return alerts


def _get_last_trigger_ts(db, rule_id: str) -> float:
    """从 decision_log 获取规则最后一次命中的时间戳"""
    try:
        # Cozo 中对 JSON 数组进行 contains 过滤较麻烦，因此拉取最近记录后 Python 端过滤
        # 为了效率，只查近期的 1000 条
        rows = db._query_with_params(
            "?[ts, gates] := *decision_log{ts, gates} :order -ts :limit 10000",
            {},
        )
    except Exception as e:
        logger.error("[ttl] 查询 decision_log 失败: %s", e)
        return 0.0

    for r in rows:
        gates = r.get("gates")
        if isinstance(gates, str):
            import json
            try:
                gates = json.loads(gates)
            except Exception:
                gates = []
        if isinstance(gates, list) and rule_id in gates:
            return r.get("ts", 0.0)

    return 0.0


def _disable_rule_in_file(constraints_dir: Path, rule_id: str) -> bool:
    """修改 YAML 文件，将 enabled 设为 false"""
    # 查找对应文件（可能有不同命名，通常等于 rule_id.yaml）
    filepath = constraints_dir / f"{rule_id}.yaml"
    if not filepath.exists():
        # 回退：遍历所有
        for p in constraints_dir.glob("*.yaml"):
            try:
                with open(p, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data and data.get("id") == rule_id:
                    filepath = p
                    break
            except Exception:
                pass

    if not filepath.exists():
        logger.warning("[ttl] 未找到规则 %s 对应的文件，无法禁用", rule_id)
        return False

    try:
        with open(filepath, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return False

        data["enabled"] = False
        data.setdefault("metadata", {})["disabled_by_ttl"] = True
        data["metadata"]["disabled_at"] = time.time()

        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

        logger.info("[ttl] 已自动禁用过期规则: %s", filepath)
        return True
    except Exception as e:
        logger.error("[ttl] 禁用规则失败 %s: %s", filepath, e)
        return False
