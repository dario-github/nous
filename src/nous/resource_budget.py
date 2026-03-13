"""Nous — 资源预算配置加载器 (M2.P3)

从 ontology/config/resource-budget.yaml 读取 gate 预算限制，
gate() 开始时加载配置，超限时 log warning（不 block）。

配置格式：
    gate_budgets:
      max_query_depth: 5
      max_entities_scanned: 50
      delegate_token_budget: 512
      timeout_us: 5000
    enforcement: warn  # warn | enforce (M5+ 切 enforce)
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("nous.resource_budget")

# 默认预算（当配置文件不存在时使用）
_DEFAULT_BUDGETS: dict = {
    "max_query_depth": 5,
    "max_entities_scanned": 50,
    "delegate_token_budget": 512,
    "timeout_us": 5000,
}
_DEFAULT_ENFORCEMENT = "warn"

# 默认配置路径
DEFAULT_CONFIG_PATH = (
    Path(__file__).parent.parent.parent.parent  # nous/ 根
    / "ontology"
    / "config"
    / "resource-budget.yaml"
)


# ── 数据结构 ───────────────────────────────────────────────────────────────


@dataclass
class ResourceBudget:
    """gate 资源预算配置"""
    max_query_depth: int = 5
    max_entities_scanned: int = 50
    delegate_token_budget: int = 512
    timeout_us: int = 5000
    enforcement: str = "warn"   # "warn" | "enforce" (M5+ 切 enforce)


# ── 加载 ───────────────────────────────────────────────────────────────────


def load_resource_budget(config_path: Optional[Path] = None) -> ResourceBudget:
    """
    加载 resource-budget.yaml 并返回 ResourceBudget。

    config_path: 配置文件路径（默认 ontology/config/resource-budget.yaml）。
    文件不存在时返回默认预算，不抛出异常。
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    if not path.exists():
        logger.debug("[resource_budget] 配置文件不存在，使用默认预算: %s", path)
        return ResourceBudget()

    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("[resource_budget] 配置文件读取失败，使用默认预算: %s", e)
        return ResourceBudget()

    budgets = raw.get("gate_budgets", {}) or {}
    enforcement = raw.get("enforcement", _DEFAULT_ENFORCEMENT)

    return ResourceBudget(
        max_query_depth=int(budgets.get("max_query_depth", _DEFAULT_BUDGETS["max_query_depth"])),
        max_entities_scanned=int(budgets.get("max_entities_scanned", _DEFAULT_BUDGETS["max_entities_scanned"])),
        delegate_token_budget=int(budgets.get("delegate_token_budget", _DEFAULT_BUDGETS["delegate_token_budget"])),
        timeout_us=int(budgets.get("timeout_us", _DEFAULT_BUDGETS["timeout_us"])),
        enforcement=str(enforcement),
    )


# ── 检查超限 ───────────────────────────────────────────────────────────────


def check_budget(
    budget: ResourceBudget,
    entities_scanned: int = 0,
    constraints_evaluated: int = 0,
    elapsed_us: int = 0,
) -> list[str]:
    """
    检查实际资源消耗是否超出预算。

    返回超限警告消息列表（空 = 未超限）。
    仅当 enforcement="warn" 时记录 warning；"enforce" 模式由 gate() 决定是否阻断。
    """
    warnings: list[str] = []

    if entities_scanned > budget.max_entities_scanned:
        msg = (
            f"[resource-budget] entities_scanned={entities_scanned} "
            f"> max_entities_scanned={budget.max_entities_scanned}"
        )
        warnings.append(msg)
        logger.warning(msg)

    if elapsed_us > budget.timeout_us:
        msg = (
            f"[resource-budget] elapsed_us={elapsed_us} "
            f"> timeout_us={budget.timeout_us}"
        )
        warnings.append(msg)
        logger.warning(msg)

    return warnings
