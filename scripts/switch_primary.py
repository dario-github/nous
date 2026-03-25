"""Nous — M4.1 切换脚本 (switch_primary.py)

用法:
    python switch_primary.py --promote   # Nous 升为 primary，TS engine 降为 fallback
    python switch_primary.py --demote    # Nous 降为 shadow，TS engine 恢复 primary
    python switch_primary.py --status    # 显示当前模式

config.yaml 路径：项目根目录下 nous/config.yaml（或 CONFIG_PATH 环境变量）
"""
import argparse
import os
import sys
from pathlib import Path

import yaml

# ── 配置文件路径 ───────────────────────────────────────────────────────────

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def get_config_path() -> Path:
    """优先读取环境变量 NOUS_CONFIG，否则用默认路径"""
    env = os.environ.get("NOUS_CONFIG")
    if env:
        return Path(env)
    return DEFAULT_CONFIG_PATH


# ── 读写 config ────────────────────────────────────────────────────────────


def load_config(path: Path) -> dict:
    """加载 config.yaml，不存在则返回默认值"""
    if not path.exists():
        return {"mode": "shadow", "version": "0.1.0"}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def save_config(path: Path, config: dict) -> None:
    """保存 config.yaml"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, default_flow_style=False)


# ── 主逻辑 ─────────────────────────────────────────────────────────────────


def get_mode(config_path: Path | None = None) -> str:
    """返回当前模式：'shadow' 或 'primary'"""
    path = config_path or get_config_path()
    config = load_config(path)
    return config.get("mode", "shadow")


def promote(config_path: Path | None = None) -> dict:
    """
    Nous 升为 primary，TS engine 降为 fallback。
    返回更新后的 config dict。
    """
    path = config_path or get_config_path()
    config = load_config(path)
    old_mode = config.get("mode", "shadow")

    config["mode"] = "primary"
    save_config(path, config)

    return {"old_mode": old_mode, "new_mode": "primary", "config_path": str(path)}


def demote(config_path: Path | None = None) -> dict:
    """
    Nous 降为 shadow，TS engine 恢复 primary。
    返回更新后的 config dict。
    """
    path = config_path or get_config_path()
    config = load_config(path)
    old_mode = config.get("mode", "shadow")

    config["mode"] = "shadow"
    save_config(path, config)

    return {"old_mode": old_mode, "new_mode": "shadow", "config_path": str(path)}


# ── gateway_hook 集成入口 ─────────────────────────────────────────────────


def is_primary_mode(config_path: Path | None = None) -> bool:
    """
    返回当前是否是 primary 模式。
    供 NousGatewayHook 调用，决定是否真拦截。
    """
    return get_mode(config_path) == "primary"


# ── CLI ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Nous 模式切换脚本：promote/demote/status"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--promote",
        action="store_true",
        help="Nous 升为 primary（真正拦截），TS engine 降为 fallback",
    )
    group.add_argument(
        "--demote",
        action="store_true",
        help="Nous 降为 shadow（只观测），TS engine 恢复 primary",
    )
    group.add_argument(
        "--status",
        action="store_true",
        help="显示当前运行模式",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="config.yaml 路径（默认：项目根目录）",
    )

    args = parser.parse_args()
    config_path = args.config

    if args.status:
        mode = get_mode(config_path)
        path = config_path or get_config_path()
        print(f"[Nous] 当前模式: {mode.upper()}")
        print(f"[Nous] 配置文件: {path}")
        if mode == "primary":
            print("[Nous] → Nous 是 primary，TS engine 是 fallback（真正拦截）")
        else:
            print("[Nous] → Nous 是 shadow，TS engine 是 primary（只观测，不拦截）")
        return

    if args.promote:
        result = promote(config_path)
        print(f"[Nous] ✅ 升级成功: {result['old_mode']} → {result['new_mode']}")
        print(f"[Nous] 配置已写入: {result['config_path']}")
        print("[Nous] → Nous 现在是 PRIMARY，将真正拦截 block verdict")
        print("[Nous] ⚠️  请确保 14 天一致率 >99% 后再执行此操作")
        return

    if args.demote:
        result = demote(config_path)
        print(f"[Nous] ✅ 降级成功: {result['old_mode']} → {result['new_mode']}")
        print(f"[Nous] 配置已写入: {result['config_path']}")
        print("[Nous] → Nous 现在是 SHADOW，TS engine 恢复为 primary")


if __name__ == "__main__":
    main()
