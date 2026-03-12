"""Tests — M4.1 切换脚本 (test_switch.py)

覆盖：
- 默认配置为 shadow
- promote 将 mode 改为 primary
- demote 将 mode 改回 shadow
- 重复 promote/demote 幂等
- is_primary_mode 正确反映配置
- config 文件不存在时的默认行为
"""
import sys
from pathlib import Path

import pytest

# conftest.py 已把 src/ 加入 path；这里再加 scripts/
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from switch_primary import (
    demote,
    get_mode,
    is_primary_mode,
    load_config,
    promote,
    save_config,
)


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_config(tmp_path) -> Path:
    """临时 config.yaml，初始 mode: shadow"""
    path = tmp_path / "config.yaml"
    save_config(path, {"mode": "shadow", "version": "0.1.0"})
    return path


@pytest.fixture
def nonexistent_config(tmp_path) -> Path:
    """不存在的 config 路径（用于测试默认行为）"""
    return tmp_path / "no_config.yaml"


# ── 基本读取 ──────────────────────────────────────────────────────────────


def test_load_config_default(nonexistent_config):
    """不存在的 config 返回 shadow 默认值"""
    config = load_config(nonexistent_config)
    assert config["mode"] == "shadow"


def test_get_mode_default(nonexistent_config):
    """不存在的 config 返回 shadow"""
    mode = get_mode(nonexistent_config)
    assert mode == "shadow"


def test_get_mode_shadow(tmp_config):
    """读取 shadow 模式正确"""
    mode = get_mode(tmp_config)
    assert mode == "shadow"


# ── promote ────────────────────────────────────────────────────────────────


def test_promote_shadow_to_primary(tmp_config):
    """promote 将 shadow → primary"""
    result = promote(tmp_config)
    assert result["old_mode"] == "shadow"
    assert result["new_mode"] == "primary"

    # 文件确实写了
    config = load_config(tmp_config)
    assert config["mode"] == "primary"


def test_promote_writes_config_file(tmp_config):
    """promote 后 config 文件存在且内容正确"""
    promote(tmp_config)
    assert tmp_config.exists()
    config = load_config(tmp_config)
    assert config["mode"] == "primary"


def test_promote_idempotent(tmp_config):
    """重复 promote 不报错，结果保持 primary"""
    promote(tmp_config)
    result = promote(tmp_config)
    assert result["new_mode"] == "primary"
    assert load_config(tmp_config)["mode"] == "primary"


# ── demote ─────────────────────────────────────────────────────────────────


def test_demote_primary_to_shadow(tmp_config):
    """demote 将 primary → shadow"""
    # 先 promote
    promote(tmp_config)
    result = demote(tmp_config)
    assert result["old_mode"] == "primary"
    assert result["new_mode"] == "shadow"

    config = load_config(tmp_config)
    assert config["mode"] == "shadow"


def test_demote_shadow_stays_shadow(tmp_config):
    """对已经是 shadow 的执行 demote，仍是 shadow"""
    result = demote(tmp_config)
    assert result["new_mode"] == "shadow"
    assert load_config(tmp_config)["mode"] == "shadow"


def test_demote_idempotent(tmp_config):
    """重复 demote 不报错"""
    demote(tmp_config)
    demote(tmp_config)
    assert load_config(tmp_config)["mode"] == "shadow"


# ── promote → demote 往返 ─────────────────────────────────────────────────


def test_promote_then_demote_roundtrip(tmp_config):
    """promote → demote 往返，最终是 shadow"""
    promote(tmp_config)
    assert get_mode(tmp_config) == "primary"

    demote(tmp_config)
    assert get_mode(tmp_config) == "shadow"


def test_multiple_roundtrips(tmp_config):
    """多次 promote/demote 往返"""
    for _ in range(3):
        promote(tmp_config)
        assert get_mode(tmp_config) == "primary"
        demote(tmp_config)
        assert get_mode(tmp_config) == "shadow"


# ── is_primary_mode ────────────────────────────────────────────────────────


def test_is_primary_mode_false_when_shadow(tmp_config):
    """shadow 模式下 is_primary_mode 返回 False"""
    assert is_primary_mode(tmp_config) is False


def test_is_primary_mode_true_after_promote(tmp_config):
    """promote 后 is_primary_mode 返回 True"""
    promote(tmp_config)
    assert is_primary_mode(tmp_config) is True


def test_is_primary_mode_false_after_demote(tmp_config):
    """demote 后 is_primary_mode 返回 False"""
    promote(tmp_config)
    demote(tmp_config)
    assert is_primary_mode(tmp_config) is False


def test_is_primary_mode_default_nonexistent(nonexistent_config):
    """不存在的 config，默认不是 primary"""
    assert is_primary_mode(nonexistent_config) is False


# ── config 文件写入格式 ────────────────────────────────────────────────────


def test_promote_preserves_version(tmp_config):
    """promote 保留 config 中其他字段"""
    promote(tmp_config)
    config = load_config(tmp_config)
    assert "version" in config


def test_save_load_roundtrip(tmp_path):
    """save + load 往返正确"""
    path = tmp_path / "test.yaml"
    save_config(path, {"mode": "primary", "version": "1.0", "extra": "data"})
    config = load_config(path)
    assert config["mode"] == "primary"
    assert config["version"] == "1.0"
    assert config["extra"] == "data"
