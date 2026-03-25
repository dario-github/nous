"""Audit Fix 1 (P0): gateway_hook 接通 L2/L3

验证：
- NousGatewayHook 接受 triviality_config 和 semantic_config 参数
- 传入 config 后，gate result 的 layer_path 不再全为 datalog_only
- shadow_mode 默认仍为 True（不拦截）
- 传入 triviality_config 时，trivial 操作走 trivial_allow 路径（layer_path 体现）
- 传入 semantic_config 时，非 trivial 操作走 semantic 路径
"""
from pathlib import Path
import pytest
from nous.gateway_hook import NousGatewayHook
from nous.triviality_filter import TrivialityConfig
from nous.semantic_gate import SemanticGateConfig

_CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"

# 不触发任何硬约束的 allow 操作（web_search 是 trivial 操作）
TRIVIAL_TOOL_CALL = {
    "tool_name": "web_search",
    "action_type": "web_search",
    "params": {"query": "python tutorial"},
}

# 不触发任何硬约束的 non-trivial allow 操作
NON_TRIVIAL_TOOL_CALL = {
    "tool_name": "send_message",
    "action_type": "send_message",
    "params": {"content": "hello world"},
}


def make_mock_provider(response: str):
    def provider(prompt: str, timeout_ms: int, model: str) -> str:
        return response
    return provider


class TestGatewayHookL2L3Params:
    """Fix 1: gateway_hook 接受并传递 L2/L3 config"""

    def test_accepts_triviality_config(self, tmp_path):
        """NousGatewayHook 构造时可接受 triviality_config 参数"""
        hook = NousGatewayHook(
            alert_log_path=tmp_path / "alert.jsonl",
            constraints_dir=_CONSTRAINTS_DIR,
            triviality_config=TrivialityConfig(),
        )
        assert hook.triviality_config is not None

    def test_accepts_semantic_config(self, tmp_path):
        """NousGatewayHook 构造时可接受 semantic_config 参数"""
        hook = NousGatewayHook(
            alert_log_path=tmp_path / "alert.jsonl",
            constraints_dir=_CONSTRAINTS_DIR,
            semantic_config=SemanticGateConfig(mode="shadow"),
        )
        assert hook.semantic_config is not None

    def test_without_configs_shadow_mode_unchanged(self, tmp_path):
        """未传 config 时，shadow_mode 默认 True，行为不变"""
        hook = NousGatewayHook(
            alert_log_path=tmp_path / "alert.jsonl",
            constraints_dir=_CONSTRAINTS_DIR,
        )
        assert hook.shadow_mode is True
        assert hook.triviality_config is None
        assert hook.semantic_config is None
        result = hook.before_tool_call(TRIVIAL_TOOL_CALL)
        assert result == TRIVIAL_TOOL_CALL  # shadow mode：原样返回

    def test_with_triviality_config_trivial_allow_path(self, tmp_path):
        """传入 triviality_config 后，web_search（trivial）走 trivial_allow 路径"""
        from nous.gate import gate
        from nous.gate import GateResult

        # 直接调用 gate 验证 layer_path
        result: GateResult = gate(
            tool_call=TRIVIAL_TOOL_CALL,
            constraints_dir=_CONSTRAINTS_DIR,
            triviality_config=TrivialityConfig(),
        )
        assert result.layer_path == "trivial_allow", (
            f"期望 trivial_allow，实际 {result.layer_path}"
        )

    def test_with_semantic_config_non_trivial_semantic_path(self, tmp_path):
        """传入 semantic_config 后，non-trivial allow 操作走 semantic 路径"""
        from nous.gate import gate

        result = gate(
            tool_call=NON_TRIVIAL_TOOL_CALL,
            constraints_dir=_CONSTRAINTS_DIR,
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="shadow",
                provider=make_mock_provider(
                    '{"action":"allow","reason":"safe","confidence":0.8}'
                ),
            ),
        )
        assert result.layer_path == "semantic", (
            f"期望 semantic，实际 {result.layer_path}"
        )
        assert result.semantic_verdict is not None

    def test_gateway_hook_triviality_config_passes_to_gate(self, tmp_path):
        """gateway_hook 传入 triviality_config 后，gate 走 L2 路径（通过 layer_path 验证）"""
        # 使用 monkeypatch 捕获实际传入 gate() 的参数
        captured = {}
        original_gate = __import__("nous.gate", fromlist=["gate"]).gate

        def mock_gate(**kwargs):
            captured.update(kwargs)
            return original_gate(**kwargs)

        import nous.gateway_hook as gh_module
        old_gate = gh_module.gate
        gh_module.gate = mock_gate

        try:
            hook = NousGatewayHook(
                alert_log_path=tmp_path / "alert.jsonl",
                constraints_dir=_CONSTRAINTS_DIR,
                triviality_config=TrivialityConfig(),
                semantic_config=SemanticGateConfig(mode="shadow"),
            )
            hook.before_tool_call(TRIVIAL_TOOL_CALL)
        finally:
            gh_module.gate = old_gate

        assert "triviality_config" in captured, "gate() 未收到 triviality_config"
        assert captured["triviality_config"] is not None
        assert "semantic_config" in captured, "gate() 未收到 semantic_config"
        assert captured["semantic_config"] is not None

    def test_shadow_mode_stays_true_with_configs(self, tmp_path):
        """传入 L2/L3 config 后，shadow_mode 默认仍为 True（不拦截）"""
        hook = NousGatewayHook(
            shadow_mode=True,
            alert_log_path=tmp_path / "alert.jsonl",
            constraints_dir=_CONSTRAINTS_DIR,
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider(
                    '{"action":"block","reason":"test","confidence":0.99}'
                ),
            ),
        )
        # shadow mode 下，即使 semantic 说 block，也不拦截
        result = hook.before_tool_call(NON_TRIVIAL_TOOL_CALL)
        assert result == NON_TRIVIAL_TOOL_CALL, "shadow mode 下应原样返回"
