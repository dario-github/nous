"""Tests — M2.7 Gateway Hook (test_gateway_hook.py)

覆盖：
- shadow mode 下 block verdict 仍然返回 allow（不拦截）
- 不一致 alert 正确写入 shadow_alerts.jsonl
- primary mode 下 block verdict 真正 block（抛出 BlockedByNous）
- compare_with_legacy 逻辑
"""
import json
import tempfile
from pathlib import Path

import pytest

from nous.gateway_hook import BlockedByNous, NousGatewayHook, _summarize_tool_call


# ── 辅助 fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def tmp_alert_log(tmp_path):
    """临时 alert 日志文件路径"""
    return tmp_path / "shadow_alerts.jsonl"


@pytest.fixture
def real_constraints_dir():
    """指向项目真实约束目录"""
    return Path(__file__).parent.parent / "ontology" / "constraints"


# 会触发 T3 block 的 tool_call
BLOCK_TOOL_CALL = {
    "tool_name": "exec",
    "action_type": "delete_file",
    "params": {"path": "/tmp/test.txt"},
}

# 不会触发任何约束的 tool_call
ALLOW_TOOL_CALL = {
    "tool_name": "web_search",
    "action_type": "search",
    "params": {"query": "hello world"},
}


# ── shadow mode ───────────────────────────────────────────────────────────


class TestShadowMode:
    def test_block_verdict_returns_tool_call_unchanged(
        self, tmp_alert_log, real_constraints_dir
    ):
        """shadow mode 下即使 gate() 返回 block，before_tool_call 也原样返回 tool_call"""
        hook = NousGatewayHook(
            shadow_mode=True,
            alert_log_path=tmp_alert_log,
            constraints_dir=real_constraints_dir,
        )
        result = hook.before_tool_call(BLOCK_TOOL_CALL)
        # 原样返回，不拦截
        assert result == BLOCK_TOOL_CALL

    def test_allow_verdict_returns_tool_call_unchanged(
        self, tmp_alert_log, real_constraints_dir
    ):
        """shadow mode 下 allow verdict 也原样返回"""
        hook = NousGatewayHook(
            shadow_mode=True,
            alert_log_path=tmp_alert_log,
            constraints_dir=real_constraints_dir,
        )
        result = hook.before_tool_call(ALLOW_TOOL_CALL)
        assert result == ALLOW_TOOL_CALL

    def test_shadow_mode_does_not_raise(self, tmp_alert_log, real_constraints_dir):
        """shadow mode 下不应抛出 BlockedByNous"""
        hook = NousGatewayHook(
            shadow_mode=True,
            alert_log_path=tmp_alert_log,
            constraints_dir=real_constraints_dir,
        )
        try:
            hook.before_tool_call(BLOCK_TOOL_CALL)
        except BlockedByNous:
            pytest.fail("shadow mode 下不应抛出 BlockedByNous")


# ── alert 写入 ────────────────────────────────────────────────────────────


class TestShadowAlert:
    def test_diverged_alert_written(self, tmp_alert_log, real_constraints_dir):
        """Nous=block, legacy=allow → 不一致 → 写入 alert"""
        hook = NousGatewayHook(
            shadow_mode=True,
            alert_log_path=tmp_alert_log,
            constraints_dir=real_constraints_dir,
        )
        hook.before_tool_call(
            BLOCK_TOOL_CALL,
            legacy_verdict="allow",  # 旧引擎放行，Nous 会 block → 不一致
        )
        assert tmp_alert_log.exists(), "alert 文件应存在"
        lines = tmp_alert_log.read_text().strip().splitlines()
        assert len(lines) == 1
        alert = json.loads(lines[0])
        assert alert["nous_verdict"] == "block"
        assert alert["legacy_verdict"] == "allow"
        assert alert["tool_name"] == "exec"

    def test_consistent_alert_not_written(self, tmp_alert_log, real_constraints_dir):
        """Nous=allow, legacy=allow → 一致 → 不写 alert"""
        hook = NousGatewayHook(
            shadow_mode=True,
            alert_log_path=tmp_alert_log,
            constraints_dir=real_constraints_dir,
        )
        hook.before_tool_call(
            ALLOW_TOOL_CALL,
            legacy_verdict="allow",  # 两者都是 allow → 一致
        )
        if tmp_alert_log.exists():
            content = tmp_alert_log.read_text().strip()
            assert content == "", "一致时不应写 alert"

    def test_both_block_no_alert(self, tmp_alert_log, real_constraints_dir):
        """Nous=block, legacy=block → 一致 → 不写 alert"""
        hook = NousGatewayHook(
            shadow_mode=True,
            alert_log_path=tmp_alert_log,
            constraints_dir=real_constraints_dir,
        )
        hook.before_tool_call(
            BLOCK_TOOL_CALL,
            legacy_verdict="block",
        )
        if tmp_alert_log.exists():
            content = tmp_alert_log.read_text().strip()
            assert content == ""

    def test_multiple_alerts_appended(self, tmp_alert_log, real_constraints_dir):
        """多次不一致触发 → 多条 alert 追加写入"""
        hook = NousGatewayHook(
            shadow_mode=True,
            alert_log_path=tmp_alert_log,
            constraints_dir=real_constraints_dir,
        )
        for _ in range(3):
            hook.before_tool_call(BLOCK_TOOL_CALL, legacy_verdict="allow")

        lines = tmp_alert_log.read_text().strip().splitlines()
        assert len(lines) == 3


# ── primary mode ──────────────────────────────────────────────────────────


class TestPrimaryMode:
    def test_block_raises_blocked_by_nous(self, tmp_alert_log, real_constraints_dir):
        """primary mode 下 block verdict → 抛出 BlockedByNous"""
        hook = NousGatewayHook(
            shadow_mode=False,
            alert_log_path=tmp_alert_log,
            constraints_dir=real_constraints_dir,
        )
        with pytest.raises(BlockedByNous) as exc_info:
            hook.before_tool_call(BLOCK_TOOL_CALL)

        err = exc_info.value
        assert err.rule_id  # 有规则 ID
        assert "Nous" in str(err) or "block" in str(err).lower()

    def test_allow_does_not_raise(self, tmp_alert_log, real_constraints_dir):
        """primary mode 下 allow verdict → 正常返回"""
        hook = NousGatewayHook(
            shadow_mode=False,
            alert_log_path=tmp_alert_log,
            constraints_dir=real_constraints_dir,
        )
        result = hook.before_tool_call(ALLOW_TOOL_CALL)
        assert result == ALLOW_TOOL_CALL

    def test_blocked_by_nous_has_rule_id(self, tmp_alert_log, real_constraints_dir):
        """BlockedByNous 异常携带 rule_id 和 reason"""
        hook = NousGatewayHook(
            shadow_mode=False,
            alert_log_path=tmp_alert_log,
            constraints_dir=real_constraints_dir,
        )
        with pytest.raises(BlockedByNous) as exc_info:
            hook.before_tool_call(BLOCK_TOOL_CALL)

        err = exc_info.value
        assert isinstance(err.rule_id, str)
        assert isinstance(err.reason, str)


# ── compare_with_legacy ───────────────────────────────────────────────────


class TestCompareWithLegacy:
    def test_both_block_consistent(self, tmp_alert_log):
        hook = NousGatewayHook(alert_log_path=tmp_alert_log)
        assert hook.compare_with_legacy("block", "block") is False

    def test_both_allow_consistent(self, tmp_alert_log):
        hook = NousGatewayHook(alert_log_path=tmp_alert_log)
        assert hook.compare_with_legacy("allow", "allow") is False

    def test_nous_block_legacy_allow_diverged(self, tmp_alert_log):
        hook = NousGatewayHook(alert_log_path=tmp_alert_log)
        assert hook.compare_with_legacy("block", "allow") is True

    def test_nous_allow_legacy_block_diverged(self, tmp_alert_log):
        hook = NousGatewayHook(alert_log_path=tmp_alert_log)
        assert hook.compare_with_legacy("allow", "block") is True

    def test_nous_confirm_legacy_allow_consistent(self, tmp_alert_log):
        """confirm 和 allow 都视为"非 block"，一致"""
        hook = NousGatewayHook(alert_log_path=tmp_alert_log)
        assert hook.compare_with_legacy("confirm", "allow") is False


# ── 辅助函数 ──────────────────────────────────────────────────────────────


class TestSummarizeToolCall:
    def test_short_tool_call(self):
        tc = {"tool_name": "exec", "action": "read"}
        s = _summarize_tool_call(tc, max_len=200)
        assert "exec" in s
        assert len(s) <= 200

    def test_truncates_long_tool_call(self):
        tc = {"tool_name": "x" * 300}
        s = _summarize_tool_call(tc, max_len=50)
        assert len(s) <= 53  # 50 + "..."
        assert s.endswith("...")
