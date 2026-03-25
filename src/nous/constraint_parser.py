"""Nous — YAML 约束解析器 (M2.1)

从 ontology/constraints/*.yaml 解析约束规则 → Constraint Pydantic 对象。

支持格式：
    id: T3
    name: 不可逆操作确认
    priority: 100
    enabled: true
    trigger:
      action_type:
        in: [delete_file, modify_config, ...]
    verdict: block
    reason: "T3: ..."
    rewrite_params:       # 可选，T11 之类的重写规则
      search_lang: zh-hans
    metadata: {}
"""
import time
from pathlib import Path
from typing import Optional

import yaml

from nous.schema import Constraint


# ── 异常 ───────────────────────────────────────────────────────────────────


class ConstraintLoadError(Exception):
    """FAIL_CLOSED: 约束加载失败时阻止 gate 以无约束模式运行。"""
    pass


# ── 默认约束目录 ─────────────────────────────────────────────────────────────

DEFAULT_CONSTRAINTS_DIR = (
    Path(__file__).parent.parent.parent  # nous/ 根 (src/nous/*.py → src/ → nous/)
    / "ontology"
    / "constraints"
)


# ── 解析单个文件 ──────────────────────────────────────────────────────────


def parse_constraint_file(path: Path) -> Constraint:
    """
    解析单个 YAML 文件 → Constraint 对象。

    如果文件不存在或格式错误，抛出 ValueError。
    """
    if not path.exists():
        raise FileNotFoundError(f"约束文件不存在: {path}")

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"约束文件格式错误（应为 YAML dict）: {path}")

    # 必填字段检查
    for required in ("id", "verdict"):
        if required not in raw:
            raise ValueError(f"约束文件缺少必填字段 '{required}': {path}")

    return Constraint(
        id=raw["id"],
        name=raw.get("name", ""),
        priority=raw.get("priority", 50),
        enabled=raw.get("enabled", True),
        trigger=raw.get("trigger", {}),
        verdict=raw["verdict"],
        reason=raw.get("reason", ""),
        rewrite_params=raw.get("rewrite_params", None),
        metadata=raw.get("metadata", {}),
        dialect=raw.get("dialect", "cozo"),      # M2.P4: 默认 cozo
        semantics=raw.get("semantics", None),    # M2.P4: 可选，M5+ 使用
        created_at=time.time(),
    )


# ── 批量加载目录 ──────────────────────────────────────────────────────────


def load_constraints(constraints_dir: Optional[Path] = None) -> list[Constraint]:
    """
    加载目录下所有 *.yaml 约束文件，按 priority 升序排列（数字越小优先级越高）。

    constraints_dir: 约束目录路径，默认 DEFAULT_CONSTRAINTS_DIR。
    返回 list[Constraint]，空目录返回 []。
    """
    if constraints_dir is None:
        constraints_dir = DEFAULT_CONSTRAINTS_DIR

    constraints_dir = Path(constraints_dir)

    if not constraints_dir.exists():
        raise ConstraintLoadError(
            f"约束目录不存在: {constraints_dir}. "
            f"FAIL_CLOSED: 拒绝在无约束模式运行。"
        )

    constraints = []
    errors = []

    for yaml_file in sorted(constraints_dir.glob("*.yaml")):
        try:
            c = parse_constraint_file(yaml_file)
            constraints.append(c)
        except Exception as e:
            errors.append(f"{yaml_file.name}: {e}")

    if errors:
        raise ConstraintLoadError(
            f"约束文件解析失败（FAIL_CLOSED，共 {len(errors)} 个文件）: "
            + "; ".join(errors)
        )

    # 按 priority 升序（数字越小越高优先级）
    constraints.sort(key=lambda c: c.priority)

    if not constraints:
        raise ConstraintLoadError(
            f"目录 {constraints_dir} 存在但加载了 0 条约束！"
            f"FAIL_CLOSED: 拒绝在无约束模式运行。"
        )

    return constraints


# ── 按 ID 查找 ─────────────────────────────────────────────────────────────


def get_constraint_by_id(
    constraint_id: str,
    constraints_dir: Optional[Path] = None,
) -> Optional[Constraint]:
    """根据 ID 查找单条约束，未找到返回 None"""
    all_constraints = load_constraints(constraints_dir)
    for c in all_constraints:
        if c.id == constraint_id:
            return c
    return None
