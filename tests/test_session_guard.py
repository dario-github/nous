"""Tests — M2.8 Session 隔离 (test_session_guard.py)

覆盖：
- is_eval_session 多种 context 格式
- eval session 写 memory → block
- normal session 写 memory → allow
- gate_with_session_guard 集成
"""
import pytest
from pathlib import Path

from nous.session_guard import (
    guard_memory_write,
    is_eval_session,
    gate_with_session_guard,
)


# ── is_eval_session ───────────────────────────────────────────────────────


class TestIsEvalSession:
    def test_eval_tag_detected(self):
        assert is_eval_session({"session_tag": "eval"}) is True

    def test_test_tag_detected(self):
        assert is_eval_session({"session_tag": "test"}) is True

    def test_case_insensitive(self):
        assert is_eval_session({"session_tag": "EVAL"}) is True
        assert is_eval_session({"session_tag": "Test"}) is True

    def test_tags_list_eval(self):
        assert is_eval_session({"tags": ["production", "eval"]}) is True

    def test_tags_list_no_eval(self):
        assert is_eval_session({"tags": ["production", "live"]}) is False

    def test_session_id_contains_eval(self):
        assert is_eval_session({"session_id": "agent:eval:12345"}) is True

    def test_session_id_contains_test(self):
        assert is_eval_session({"session_id": "test_run_001"}) is True

    def test_session_type_evaluation(self):
        assert is_eval_session({"session_type": "evaluation"}) is True

    def test_mode_sandbox(self):
        assert is_eval_session({"mode": "sandbox"}) is True

    def test_normal_session_false(self):
        assert is_eval_session({"session_tag": "production"}) is False
        assert is_eval_session({"session_tag": "live"}) is False
        assert is_eval_session({"session_id": "agent:main:discord:123"}) is False

    def test_empty_context_false(self):
        assert is_eval_session({}) is False

    def test_non_dict_context_false(self):
        assert is_eval_session(None) is False  # type: ignore
        assert is_eval_session("eval") is False  # type: ignore


# ── guard_memory_write ────────────────────────────────────────────────────


class TestGuardMemoryWrite:
    # eval session + memory 写入 → block

    def test_eval_session_write_memory_blocked(self):
        tc = {
            "tool_name": "write",
            "path": "memory/entities/test.md",
        }
        ctx = {"session_tag": "eval"}
        verdict = guard_memory_write(tc, ctx)
        assert verdict.action == "block"
        assert "eval" in verdict.reason.lower() or "memory" in verdict.reason.lower()

    def test_eval_session_write_memory_subdir_blocked(self):
        tc = {
            "tool_name": "write_file",
            "params": {"path": "memory/rules/new_rule.md"},
        }
        ctx = {"session_tag": "test"}
        verdict = guard_memory_write(tc, ctx)
        assert verdict.action == "block"

    def test_eval_session_edit_memory_blocked(self):
        tc = {
            "tool_name": "edit",
            "path": "memory/inner-state.yaml",
        }
        ctx = {"session_tag": "eval"}
        verdict = guard_memory_write(tc, ctx)
        assert verdict.action == "block"

    # normal session → allow

    def test_normal_session_write_memory_allowed(self):
        tc = {
            "tool_name": "write",
            "path": "memory/entities/test.md",
        }
        ctx = {"session_tag": "production"}
        verdict = guard_memory_write(tc, ctx)
        assert verdict.action == "allow"

    def test_normal_session_no_context_allowed(self):
        tc = {
            "tool_name": "write",
            "path": "memory/test.md",
        }
        ctx = {}
        verdict = guard_memory_write(tc, ctx)
        assert verdict.action == "allow"

    # eval session + 非 memory 写入 → allow

    def test_eval_session_write_tmp_allowed(self):
        tc = {
            "tool_name": "write",
            "path": "/tmp/result.txt",
        }
        ctx = {"session_tag": "eval"}
        verdict = guard_memory_write(tc, ctx)
        assert verdict.action == "allow"

    def test_eval_session_read_memory_allowed(self):
        """eval session 读取 memory 是允许的"""
        tc = {
            "tool_name": "read",
            "path": "memory/entities/test.md",
        }
        ctx = {"session_tag": "eval"}
        verdict = guard_memory_write(tc, ctx)
        assert verdict.action == "allow"

    def test_eval_session_web_search_allowed(self):
        tc = {
            "tool_name": "web_search",
            "params": {"query": "test"},
        }
        ctx = {"session_tag": "eval"}
        verdict = guard_memory_write(tc, ctx)
        assert verdict.action == "allow"

    # block verdict 携带规则 ID

    def test_block_has_rule_id(self):
        tc = {"tool_name": "write", "path": "memory/test.md"}
        ctx = {"session_tag": "eval"}
        verdict = guard_memory_write(tc, ctx)
        assert verdict.action == "block"
        assert verdict.rule_id == "session-guard:eval-memory-write"


# ── gate_with_session_guard 集成 ──────────────────────────────────────────


class TestGateWithSessionGuard:
    """集成测试：session guard 与 gate() pipeline 协同工作"""

    def test_eval_write_memory_blocked_before_gate(self):
        """eval session 写 memory → session guard 先于 gate 拦截"""
        tc = {
            "tool_name": "write",
            "action_type": "write_file",
            "path": "memory/test.md",
        }
        ctx = {"session_tag": "eval"}
        result = gate_with_session_guard(tc, context=ctx)
        assert result.verdict.action == "block"
        assert result.verdict.rule_id == "session-guard:eval-memory-write"

    def test_normal_session_memory_write_goes_to_gate(self):
        """normal session 写 memory → 交给 gate pipeline 处理"""
        tc = {
            "tool_name": "write",
            "action_type": "write_file",
            "path": "memory/test.md",
        }
        ctx = {"session_tag": "production"}
        result = gate_with_session_guard(tc, context=ctx)
        # gate pipeline 对普通写操作可能 allow
        # 关键：不被 session guard 拦截（rule_id 不是 session-guard:eval-memory-write）
        assert result.verdict.rule_id != "session-guard:eval-memory-write"

    def test_eval_session_web_search_passes(self):
        """eval session 做 web_search → 不被 session guard 拦截"""
        tc = {
            "tool_name": "web_search",
            "action_type": "search",
            "params": {"query": "test"},
        }
        ctx = {"session_tag": "eval"}
        result = gate_with_session_guard(tc, context=ctx)
        assert result.verdict.rule_id != "session-guard:eval-memory-write"

    def test_no_context_passes_through(self):
        """context 为 None → 正常走 gate pipeline"""
        tc = {"tool_name": "web_search", "action_type": "search"}
        result = gate_with_session_guard(tc, context=None)
        # 不应抛出异常
        assert result is not None
        assert result.verdict.action in {
            "allow", "block", "confirm", "warn", "require", "rewrite", "delegate"
        }
