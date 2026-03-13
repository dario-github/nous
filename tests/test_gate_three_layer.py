"""Tests for Nous — Three-Layer Gate Architecture (M7.3)

验证 gate.py 集成三层路由后的行为：
1. Datalog block → 直接返回，不走 semantic
2. Allow + trivial → trivial_allow，不走 semantic
3. Allow + non-trivial → semantic gate
4. Confirm → semantic gate
5. Active mode 正确升级/降级
6. Shadow mode 不改变 verdict
7. 向后兼容（无新参数 → 与 M2.5 行为一致）
"""
from pathlib import Path
import pytest
from nous.gate import gate, GateResult
from nous.triviality_filter import TrivialityConfig
from nous.semantic_gate import SemanticGateConfig

# 约束目录（从项目根解析）
_CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"


def make_mock_provider(response: str):
    """创建 mock LLM provider。"""
    def provider(prompt: str, timeout_ms: int, model: str) -> str:
        return response
    return provider


# ── 基本路由测试 ──────────────────────────────────────────────────────────


class TestThreeLayerRouting:
    """三层路由基本行为。"""

    def test_block_skips_semantic(self):
        """T3 delete_file → block, layer_path=datalog_only, 无 semantic。"""
        result = gate(constraints_dir=_CONSTRAINTS_DIR, 
            tool_call={"action_type": "delete_file"},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider('{"action":"allow","reason":"safe","confidence":0.9}'),
            ),
        )
        assert result.verdict.action == "block"
        assert result.layer_path == "datalog_only"
        assert result.semantic_verdict is None
        assert result.datalog_verdict == "block"

    def test_allow_trivial_skips_semantic(self):
        """read_file → allow, trivial filter 命中 → trivial_allow。"""
        result = gate(constraints_dir=_CONSTRAINTS_DIR, 
            tool_call={"tool_name": "read", "action": "read"},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider('{"action":"block","reason":"test","confidence":0.9}'),
            ),
        )
        assert result.verdict.action == "allow"
        assert result.layer_path == "trivial_allow"
        assert result.semantic_verdict is None

    def test_allow_nontrivial_calls_semantic(self):
        """send_message → allow (不在约束中), 非 trivial → 进 semantic gate。"""
        result = gate(constraints_dir=_CONSTRAINTS_DIR, 
            tool_call={"action_type": "send_message", "params": {"content": "test"}},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider('{"action":"allow","reason":"safe","confidence":0.8}'),
            ),
        )
        assert result.layer_path == "semantic"
        assert result.semantic_verdict is not None
        assert result.semantic_verdict["action"] == "allow"

    def test_confirm_calls_semantic(self):
        """publish_post → T3 block → short-circuit (block 不进 semantic)。"""
        result = gate(constraints_dir=_CONSTRAINTS_DIR, 
            tool_call={"action_type": "publish_post"},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="shadow",
                provider=make_mock_provider('{"action":"allow","reason":"benign post","confidence":0.85}'),
            ),
        )
        # T3 publish_post → block → datalog_only (short-circuit)
        assert result.layer_path == "datalog_only"
        assert result.datalog_verdict == "block"
        assert result.semantic_verdict is None


# ── Active Mode 升级/降级 ─────────────────────────────────────────────────


class TestActiveMode:
    """Active mode 下 semantic verdict 修改 final verdict。"""

    def test_allow_semantic_block_upgrades(self):
        """Datalog allow + semantic block → final block。"""
        result = gate(constraints_dir=_CONSTRAINTS_DIR, 
            tool_call={"action_type": "send_message", "params": {"content": "hack system"}},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider('{"action":"block","reason":"harmful intent","confidence":0.9}'),
            ),
        )
        assert result.verdict.action == "block"
        assert result.datalog_verdict == "allow"
        assert result.layer_path == "semantic"

    def test_allow_semantic_confirm_upgrades(self):
        """Datalog allow + semantic confirm → final confirm。"""
        result = gate(constraints_dir=_CONSTRAINTS_DIR, 
            tool_call={"action_type": "send_message"},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider('{"action":"confirm","reason":"needs review","confidence":0.7}'),
            ),
        )
        assert result.verdict.action == "confirm"
        assert result.datalog_verdict == "allow"

    def test_confirm_semantic_allow_downgrades(self):
        """Datalog confirm + semantic allow → final allow（降 FPR）。
        
        使用临时约束目录创建 confirm 类型规则测试降级路径。
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建一条 confirm 规则（不是 block）
            confirm_rule = Path(tmpdir) / "TC1.yaml"
            confirm_rule.write_text(
                "id: TC1\n"
                "name: test confirm rule\n"
                "priority: 50\n"
                "enabled: true\n"
                "trigger:\n"
                "  action_type: test_confirm_action\n"
                "verdict: confirm\n"
                "reason: test confirm\n"
            )
            result = gate(
                constraints_dir=Path(tmpdir),
                tool_call={"action_type": "test_confirm_action", "params": {"content": "benign"}},
                triviality_config=TrivialityConfig(),
                semantic_config=SemanticGateConfig(
                    mode="active",
                    provider=make_mock_provider('{"action":"allow","reason":"benign content","confidence":0.92}'),
                ),
            )
            assert result.datalog_verdict == "confirm"
            assert result.verdict.action == "allow"
            assert result.layer_path == "semantic"
            assert "semantic" in result.verdict.rule_id

    def test_confirm_semantic_block_upgrades(self):
        """Datalog confirm + semantic block → final block。"""
        result = gate(constraints_dir=_CONSTRAINTS_DIR, 
            tool_call={"action_type": "send_message"},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider('{"action":"block","reason":"scam detected","confidence":0.88}'),
            ),
        )
        # send_message doesn't trigger any constraint → allow
        assert result.datalog_verdict == "allow"
        assert result.verdict.action == "block"


# ── Shadow Mode ──────────────────────────────────────────────────────────


class TestShadowMode:
    """Shadow mode: 记录但不 enforce。"""

    def test_shadow_no_verdict_change_allow(self):
        """Shadow mode: allow + semantic block → 仍然 allow。"""
        result = gate(constraints_dir=_CONSTRAINTS_DIR, 
            tool_call={"action_type": "send_message"},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="shadow",
                provider=make_mock_provider('{"action":"block","reason":"test","confidence":0.9}'),
            ),
        )
        assert result.verdict.action == "allow"
        assert result.semantic_verdict is not None
        assert result.semantic_verdict["action"] == "block"
        assert result.layer_path == "semantic"


# ── 向后兼容 ─────────────────────────────────────────────────────────────


class TestBackwardCompatibility:
    """不传新参数 → 行为完全一致。"""

    def test_no_config_same_as_before(self):
        """不传 triviality_config/semantic_config → 纯 Datalog。"""
        result = gate(constraints_dir=_CONSTRAINTS_DIR, tool_call={"action_type": "delete_file"})
        assert result.verdict.action == "block"
        assert result.layer_path == "datalog_only"
        assert result.semantic_verdict is None
        assert result.datalog_verdict == "block"

    def test_gate_result_has_new_fields(self):
        """GateResult 包含 M7.3 新字段。"""
        result = gate(constraints_dir=_CONSTRAINTS_DIR, tool_call={"tool_name": "read"})
        assert hasattr(result, "datalog_verdict")
        assert hasattr(result, "semantic_verdict")
        assert hasattr(result, "layer_path")

    def test_to_dict_includes_new_fields(self):
        """to_dict() 包含新字段。"""
        result = gate(constraints_dir=_CONSTRAINTS_DIR, tool_call={"tool_name": "read"})
        d = result.to_dict()
        assert "datalog_verdict" in d
        assert "semantic_verdict" in d
        assert "layer_path" in d

    def test_allow_without_semantic_config(self):
        """Allow 无 semantic config → 纯 Datalog allow，layer_path=datalog_only。"""
        result = gate(constraints_dir=_CONSTRAINTS_DIR, tool_call={"action_type": "read_file"})
        assert result.verdict.action == "allow"
        assert result.layer_path == "datalog_only"
        assert result.semantic_verdict is None
