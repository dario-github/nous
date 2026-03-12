#!/usr/bin/env python3
"""Nous — 审核队列 CLI (M3.4)

用法：
    python scripts/review_cli.py list            列出所有待审核候选规则
    python scripts/review_cli.py approve <id>    批准候选规则（移入 constraints/，触发热加载）
    python scripts/review_cli.py reject <id>     拒绝候选规则（移入 proposals/rejected/）
    python scripts/review_cli.py stats           显示待审/已批/已拒数量

    <id> 为提案文件的 stem（不含 .yaml），如 proposal-T3-1741810800

目录结构：
    ontology/proposals/          ← 待审核
    ontology/proposals/rejected/ ← 已拒绝
    ontology/constraints/        ← 已批准（approve 后写入此处）

approve 逻辑：
    读取提案 YAML → 取 id 字段 → 写入 constraints/{id}.yaml → 删除提案文件 → 触发热加载
"""
import argparse
import logging
import sys
from pathlib import Path

import yaml

# 路径常量（相对 nous/ 根目录）
_NOUS_ROOT = Path(__file__).parent.parent
_PROPOSALS_DIR = _NOUS_ROOT / "ontology" / "proposals"
_REJECTED_DIR = _PROPOSALS_DIR / "rejected"
_CONSTRAINTS_DIR = _NOUS_ROOT / "ontology" / "constraints"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("nous.review_cli")


# ── 工具函数 ────────────────────────────────────────────────────────────────


def _find_proposal_file(proposal_id: str) -> Path | None:
    """根据 proposal_id（文件 stem）查找提案文件"""
    # 先精确查找
    exact = _PROPOSALS_DIR / f"{proposal_id}.yaml"
    if exact.exists():
        return exact
    # 模糊查找（前缀匹配）
    candidates = list(_PROPOSALS_DIR.glob(f"{proposal_id}*.yaml"))
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        logger.warning("[review_cli] 找到多个匹配文件，请使用完整 ID: %s",
                       [p.name for p in candidates])
        return None
    return None


def _load_proposal_yaml(filepath: Path) -> dict:
    """加载提案 YAML 文件"""
    with open(filepath, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _list_proposals(directory: Path) -> list[Path]:
    """列出目录下所有 .yaml 提案文件（不含子目录）"""
    if not directory.exists():
        return []
    return sorted(directory.glob("*.yaml"))


# ── 子命令：list ───────────────────────────────────────────────────────────


def cmd_list(args: argparse.Namespace) -> int:
    """列出所有待审核候选规则"""
    files = _list_proposals(_PROPOSALS_DIR)
    if not files:
        print("📋 暂无待审核规则")
        return 0

    print(f"📋 待审核规则（{len(files)} 条）：\n")
    for fp in files:
        try:
            proposal = _load_proposal_yaml(fp)
            pid = fp.stem
            rule_id = proposal.get("id", "?")
            pattern = proposal.get("metadata", {}).get("gap_pattern", "?")
            action_type = proposal.get("metadata", {}).get("action_type", "?")
            generated_at = proposal.get("metadata", {}).get("generated_at", "?")
            enabled = proposal.get("enabled", True)
            verdict = proposal.get("verdict", "?")

            status_icon = "🔴 disabled" if not enabled else "🟢 enabled"
            print(f"  [{pid}]")
            print(f"    rule_id:     {rule_id}")
            print(f"    gap_pattern: {pattern}")
            print(f"    action_type: {action_type}")
            print(f"    verdict:     {verdict} ({status_icon})")
            print(f"    generated:   {generated_at}")
            print()
        except Exception as e:
            print(f"  [{fp.stem}] ⚠️  读取失败: {e}\n")

    return 0


# ── 子命令：approve ────────────────────────────────────────────────────────


def cmd_approve(args: argparse.Namespace) -> int:
    """批准候选规则：写入 constraints/ 并触发热加载"""
    proposal_id = args.id
    filepath = _find_proposal_file(proposal_id)
    if filepath is None:
        print(f"❌ 未找到提案: {proposal_id}")
        return 1

    try:
        proposal = _load_proposal_yaml(filepath)
    except Exception as e:
        print(f"❌ 读取提案失败: {e}")
        return 1

    rule_id = proposal.get("id")
    if not rule_id:
        print("❌ 提案 YAML 缺少 id 字段")
        return 1

    # 写入 constraints/{rule_id}.yaml（覆盖原有同名规则）
    _CONSTRAINTS_DIR.mkdir(parents=True, exist_ok=True)
    target = _CONSTRAINTS_DIR / f"{rule_id}.yaml"

    try:
        with open(target, "w", encoding="utf-8") as f:
            yaml.dump(proposal, f, allow_unicode=True, default_flow_style=False)
    except Exception as e:
        print(f"❌ 写入 constraints/ 失败: {e}")
        return 1

    # 删除提案文件
    try:
        filepath.unlink()
    except Exception as e:
        logger.warning("[review_cli] 删除提案文件失败（非致命）: %s", e)

    print(f"✅ 已批准：{proposal_id} → constraints/{rule_id}.yaml")

    # 触发热加载
    _trigger_hot_reload()
    return 0


# ── 子命令：reject ─────────────────────────────────────────────────────────


def cmd_reject(args: argparse.Namespace) -> int:
    """拒绝候选规则：移入 proposals/rejected/"""
    proposal_id = args.id
    filepath = _find_proposal_file(proposal_id)
    if filepath is None:
        print(f"❌ 未找到提案: {proposal_id}")
        return 1

    _REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    target = _REJECTED_DIR / filepath.name

    try:
        filepath.rename(target)
    except Exception as e:
        print(f"❌ 移动文件失败: {e}")
        return 1

    print(f"🚫 已拒绝：{proposal_id} → proposals/rejected/{filepath.name}")
    return 0


# ── 子命令：stats ──────────────────────────────────────────────────────────


def cmd_stats(args: argparse.Namespace) -> int:
    """显示待审/已批/已拒数量"""
    pending = len(_list_proposals(_PROPOSALS_DIR))
    approved = len(list(_CONSTRAINTS_DIR.glob("*.yaml"))) if _CONSTRAINTS_DIR.exists() else 0
    rejected = len(list(_REJECTED_DIR.glob("*.yaml"))) if _REJECTED_DIR.exists() else 0

    print("📊 审核队列统计：")
    print(f"  待审核：{pending}")
    print(f"  已批准：{approved}（constraints/ 中的规则总数）")
    print(f"  已拒绝：{rejected}")
    return 0


# ── 热加载触发 ─────────────────────────────────────────────────────────────


def _trigger_hot_reload() -> None:
    """
    触发约束热加载。

    如果存在 HotReloader 实例则调用 reload()，否则记录提示。
    在 CLI 脚本中无持久化进程上下文，仅记录日志。
    实际进程内使用时，调用方应在 approve 后自行调用 reloader.reload()。
    """
    print("🔄 约束目录已更新，进程内 HotReloader 将在下次文件扫描时自动加载。")
    print("   如需立即生效，请在代码中调用 reloader.reload()。")


# ── 程序化接口（供测试/集成调用） ────────────────────────────────────────────


def approve_proposal(proposal_id: str, proposals_dir: Path, constraints_dir: Path) -> Path:
    """
    程序化 approve：无 CLI 解析，直接操作文件。

    Args:
        proposal_id:     提案文件 stem（不含 .yaml）
        proposals_dir:   proposals 目录
        constraints_dir: constraints 目录

    Returns:
        写入的 constraints 文件路径

    Raises:
        FileNotFoundError: 提案文件不存在
        ValueError:        提案 YAML 缺少 id 字段
    """
    # 查找文件
    filepath = proposals_dir / f"{proposal_id}.yaml"
    if not filepath.exists():
        # 模糊匹配
        candidates = list(proposals_dir.glob(f"{proposal_id}*.yaml"))
        if len(candidates) == 1:
            filepath = candidates[0]
        else:
            raise FileNotFoundError(f"提案文件不存在: {proposal_id}")

    with open(filepath, encoding="utf-8") as f:
        proposal = yaml.safe_load(f) or {}

    rule_id = proposal.get("id")
    if not rule_id:
        raise ValueError("提案 YAML 缺少 id 字段")

    # 写入 constraints/
    constraints_dir.mkdir(parents=True, exist_ok=True)
    target = constraints_dir / f"{rule_id}.yaml"
    with open(target, "w", encoding="utf-8") as f:
        yaml.dump(proposal, f, allow_unicode=True, default_flow_style=False)

    # 删除提案文件
    filepath.unlink()

    logger.info("[review_cli] 已批准：%s → %s", proposal_id, target)
    return target


def reject_proposal(proposal_id: str, proposals_dir: Path) -> Path:
    """
    程序化 reject：无 CLI 解析，直接操作文件。

    Returns:
        移动后的文件路径（proposals/rejected/{name}）
    """
    filepath = proposals_dir / f"{proposal_id}.yaml"
    if not filepath.exists():
        candidates = list(proposals_dir.glob(f"{proposal_id}*.yaml"))
        if len(candidates) == 1:
            filepath = candidates[0]
        else:
            raise FileNotFoundError(f"提案文件不存在: {proposal_id}")

    rejected_dir = proposals_dir / "rejected"
    rejected_dir.mkdir(parents=True, exist_ok=True)
    target = rejected_dir / filepath.name
    filepath.rename(target)

    logger.info("[review_cli] 已拒绝：%s → %s", proposal_id, target)
    return target


# ── main ───────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Nous 审核队列 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="列出所有待审核候选规则")

    # approve
    p_approve = subparsers.add_parser("approve", help="批准候选规则")
    p_approve.add_argument("id", help="提案 ID（文件 stem）")

    # reject
    p_reject = subparsers.add_parser("reject", help="拒绝候选规则")
    p_reject.add_argument("id", help="提案 ID（文件 stem）")

    # stats
    subparsers.add_parser("stats", help="显示待审/已批/已拒数量")

    args = parser.parse_args()

    cmd_map = {
        "list": cmd_list,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "stats": cmd_stats,
    }
    return cmd_map[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
