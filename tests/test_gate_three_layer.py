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
        """publish_post → T3-soft confirm → semantic gate (Loop 4: T3 split)。"""
        result = gate(constraints_dir=_CONSTRAINTS_DIR, 
            tool_call={"action_type": "publish_post"},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="shadow",
                provider=make_mock_provider('{"action":"allow","reason":"benign post","confidence":0.85}'),
            ),
        )
        # T3-soft publish_post → confirm → semantic gate (shadow mode: verdict unchanged)
        assert result.layer_path == "semantic"
        assert result.datalog_verdict == "confirm"
        # shadow mode: semantic_verdict recorded but doesn't change final verdict
        assert result.semantic_verdict is not None
        assert result.verdict.action == "confirm"  # shadow mode preserves confirm


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

    def test_allow_semantic_confirm_stays_allow(self):
        """Datalog allow + semantic confirm → stays allow (Loop 4 FPR fix).
        
        Key insight: LLM's "confirm" (hesitation) should NOT override Datalog's allow.
        This is the core fix for 77% FPR from Loop 3.
        """
        result = gate(constraints_dir=_CONSTRAINTS_DIR, 
            tool_call={"action_type": "send_message"},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider('{"action":"confirm","reason":"needs review","confidence":0.7}'),
            ),
        )
        assert result.verdict.action == "allow"
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
        """Datalog allow + semantic block (conf 0.92 >= 0.90) → final block。"""
        result = gate(constraints_dir=_CONSTRAINTS_DIR, 
            tool_call={"action_type": "send_message"},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider('{"action":"block","reason":"scam detected","confidence":0.92}'),
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


# ── Confidence-Calibrated Fusion (Loop 4) ─────────────────────────────────


class TestConfidenceCalibratedFusion:
    """Loop 4: Confidence-calibrated verdict fusion tests.
    
    Validates that:
    - Datalog "allow" + semantic "confirm" → stays allow (FPR fix)
    - Datalog "allow" + semantic "block" respects block_upgrade_threshold
    - Datalog "confirm" + semantic "allow" respects allow_downgrade_threshold
    - Custom thresholds work correctly
    """

    def test_allow_block_below_threshold_stays_allow(self):
        """Datalog allow + semantic block (conf 0.7 < 0.85) → stays allow."""
        result = gate(constraints_dir=_CONSTRAINTS_DIR,
            tool_call={"action_type": "send_message", "params": {"content": "test"}},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider('{"action":"block","reason":"maybe harmful","confidence":0.7}'),
            ),
        )
        assert result.verdict.action == "allow"
        assert result.datalog_verdict == "allow"
        assert result.semantic_verdict["action"] == "block"

    def test_allow_block_above_threshold_upgrades(self):
        """Datalog allow + semantic block (conf 0.9 >= 0.90) → upgrades to block."""
        result = gate(constraints_dir=_CONSTRAINTS_DIR,
            tool_call={"action_type": "send_message", "params": {"content": "hack systems"}},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider('{"action":"block","reason":"harmful intent","confidence":0.9}'),
            ),
        )
        assert result.verdict.action == "block"
        assert result.datalog_verdict == "allow"
        assert "0.90" in result.verdict.reason

    def test_allow_block_at_exact_threshold(self):
        """Datalog allow + semantic block (conf exactly 0.90) → upgrades (>=)."""
        result = gate(constraints_dir=_CONSTRAINTS_DIR,
            tool_call={"action_type": "send_message", "params": {"content": "test"}},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider('{"action":"block","reason":"harmful","confidence":0.90}'),
            ),
        )
        assert result.verdict.action == "block"

    def test_allow_confirm_always_stays_allow(self):
        """Datalog allow + semantic confirm (any conf) → stays allow.
        
        This is the KEY FPR fix. LLM hesitation should not override rules.
        """
        for conf in [0.5, 0.75, 0.9, 0.99]:
            result = gate(constraints_dir=_CONSTRAINTS_DIR,
                tool_call={"action_type": "send_message"},
                triviality_config=TrivialityConfig(),
                semantic_config=SemanticGateConfig(
                    mode="active",
                    provider=make_mock_provider(
                        f'{{"action":"confirm","reason":"unsure","confidence":{conf}}}'
                    ),
                ),
            )
            assert result.verdict.action == "allow", f"Failed at conf={conf}"

    def test_confirm_allow_below_threshold_stays_confirm(self):
        """Datalog confirm + semantic allow (conf 0.5 < 0.7) → stays confirm."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
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
                    provider=make_mock_provider('{"action":"allow","reason":"seems ok","confidence":0.5}'),
                ),
            )
            assert result.datalog_verdict == "confirm"
            assert result.verdict.action == "confirm"  # NOT downgraded

    def test_confirm_allow_above_threshold_downgrades(self):
        """Datalog confirm + semantic allow (conf 0.8 >= 0.7) → downgrades to allow."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
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
                tool_call={"action_type": "test_confirm_action", "params": {"content": "benign post"}},
                triviality_config=TrivialityConfig(),
                semantic_config=SemanticGateConfig(
                    mode="active",
                    provider=make_mock_provider('{"action":"allow","reason":"benign post","confidence":0.8}'),
                ),
            )
            assert result.datalog_verdict == "confirm"
            assert result.verdict.action == "allow"
            assert "0.80" in result.verdict.reason

    def test_confirm_block_always_upgrades(self):
        """Datalog confirm + semantic block (conf >= 0.90) → upgrades to block."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            confirm_rule = Path(tmpdir) / "TC1.yaml"
            confirm_rule.write_text(
                "id: TC1\nname: test\npriority: 50\nenabled: true\n"
                "trigger:\n  action_type: test_confirm_action\n"
                "verdict: confirm\nreason: test\n"
            )
            for conf in [0.90, 0.92, 0.95]:
                result = gate(
                    constraints_dir=Path(tmpdir),
                    tool_call={"action_type": "test_confirm_action"},
                    triviality_config=TrivialityConfig(),
                    semantic_config=SemanticGateConfig(
                        mode="active",
                        provider=make_mock_provider(
                            f'{{"action":"block","reason":"harmful","confidence":{conf}}}'
                        ),
                    ),
                )
                assert result.verdict.action == "block", f"Failed at conf={conf}"

    def test_custom_thresholds(self):
        """Custom block_upgrade_threshold and allow_downgrade_threshold."""
        # Stricter block threshold (0.95) — block at 0.9 should NOT upgrade
        result = gate(constraints_dir=_CONSTRAINTS_DIR,
            tool_call={"action_type": "send_message"},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                block_upgrade_threshold=0.95,
                provider=make_mock_provider('{"action":"block","reason":"test","confidence":0.9}'),
            ),
        )
        assert result.verdict.action == "allow"  # 0.9 < 0.95

        # Looser block threshold (0.6) — block at 0.7 should upgrade
        result = gate(constraints_dir=_CONSTRAINTS_DIR,
            tool_call={"action_type": "send_message"},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                block_upgrade_threshold=0.6,
                provider=make_mock_provider('{"action":"block","reason":"test","confidence":0.7}'),
            ),
        )
        assert result.verdict.action == "block"  # 0.7 >= 0.6

    def test_reason_includes_confidence(self):
        """Verify that the verdict reason includes the confidence score."""
        result = gate(constraints_dir=_CONSTRAINTS_DIR,
            tool_call={"action_type": "send_message", "params": {"content": "hack"}},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider('{"action":"block","reason":"malicious","confidence":0.93}'),
            ),
        )
        assert result.verdict.action == "block"
        assert "@0.93" in result.verdict.reason


# ── Loop 8: Unified confidence threshold for confirm→block path ─────────────


class TestLoop8ConfidenceThreshold:
    """Loop 8: confirm + sem block 路径的置信度阈值统一化。

    Bug fixed: confirm + semantic block was upgrading without threshold check,
    causing low-confidence (0.78-0.87) semantic blocks to produce false positives.

    New behavior: confirm + sem block only upgrades if conf >= block_upgrade_threshold (0.90).
    """

    def _make_confirm_dir(self, tmpdir: str) -> Path:
        """创建包含一条 confirm 规则的临时约束目录。"""
        confirm_rule = Path(tmpdir) / "TC_loop8.yaml"
        confirm_rule.write_text(
            "id: TC_loop8\n"
            "name: loop8 confirm rule\n"
            "priority: 50\n"
            "enabled: true\n"
            "trigger:\n"
            "  action_type: loop8_action\n"
            "verdict: confirm\n"
            "reason: loop8 confirm\n"
        )
        return Path(tmpdir)

    def test_a_confirm_block_high_conf_upgrades(self):
        """(a) confirm + sem block (high conf 0.92) → block。现有行为，确认不变。"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cdir = self._make_confirm_dir(tmpdir)
            result = gate(
                constraints_dir=cdir,
                tool_call={"action_type": "loop8_action"},
                triviality_config=TrivialityConfig(),
                semantic_config=SemanticGateConfig(
                    mode="active",
                    provider=make_mock_provider(
                        '{"action":"block","reason":"clear harm","confidence":0.92}'
                    ),
                ),
            )
            assert result.datalog_verdict == "confirm"
            assert result.verdict.action == "block"
            assert "@0.92" in result.verdict.reason

    def test_b_confirm_block_low_conf_stays_confirm(self):
        """(b) confirm + sem block (low conf 0.80) → confirm。新行为：低置信度不升级。"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cdir = self._make_confirm_dir(tmpdir)
            result = gate(
                constraints_dir=cdir,
                tool_call={"action_type": "loop8_action"},
                triviality_config=TrivialityConfig(),
                semantic_config=SemanticGateConfig(
                    mode="active",
                    provider=make_mock_provider(
                        '{"action":"block","reason":"maybe harmful","confidence":0.80}'
                    ),
                ),
            )
            assert result.datalog_verdict == "confirm"
            assert result.verdict.action == "confirm"  # NOT upgraded — insufficient evidence

    def test_c_confirm_block_exactly_threshold_upgrades(self):
        """(c) confirm + sem block (exactly 0.90) → block。边界：恰好等于阈值时升级。"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cdir = self._make_confirm_dir(tmpdir)
            result = gate(
                constraints_dir=cdir,
                tool_call={"action_type": "loop8_action"},
                triviality_config=TrivialityConfig(),
                semantic_config=SemanticGateConfig(
                    mode="active",
                    provider=make_mock_provider(
                        '{"action":"block","reason":"exactly at threshold","confidence":0.90}'
                    ),
                ),
            )
            assert result.datalog_verdict == "confirm"
            assert result.verdict.action == "block"

    def test_d_confirm_block_just_below_threshold_stays_confirm(self):
        """(d) confirm + sem block (0.89) → confirm。边界：阈值下方不升级。"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cdir = self._make_confirm_dir(tmpdir)
            result = gate(
                constraints_dir=cdir,
                tool_call={"action_type": "loop8_action"},
                triviality_config=TrivialityConfig(),
                semantic_config=SemanticGateConfig(
                    mode="active",
                    provider=make_mock_provider(
                        '{"action":"block","reason":"just below threshold","confidence":0.89}'
                    ),
                ),
            )
            assert result.datalog_verdict == "confirm"
            assert result.verdict.action == "confirm"

    def test_e_allow_block_at_threshold_upgrades(self):
        """(e) allow + sem block (0.90) → block。确认 allow 路径现有行为不变。"""
        result = gate(
            constraints_dir=_CONSTRAINTS_DIR,
            tool_call={"action_type": "send_message", "params": {"content": "test"}},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider(
                    '{"action":"block","reason":"harmful","confidence":0.90}'
                ),
            ),
        )
        assert result.datalog_verdict == "allow"
        assert result.verdict.action == "block"

    def test_f_allow_block_below_new_default_threshold_stays_allow(self):
        """(f) allow + sem block (0.89) → allow。新默认阈值 0.90 的效果：0.89 不再触发升级。"""
        result = gate(
            constraints_dir=_CONSTRAINTS_DIR,
            tool_call={"action_type": "send_message", "params": {"content": "test"}},
            triviality_config=TrivialityConfig(),
            semantic_config=SemanticGateConfig(
                mode="active",
                provider=make_mock_provider(
                    '{"action":"block","reason":"maybe harmful","confidence":0.89}'
                ),
            ),
        )
        assert result.datalog_verdict == "allow"
        assert result.verdict.action == "allow"  # 0.89 < 0.90 → no upgrade


class TestUpgradeOnlyMode:
    """Loop 73: upgrade_only=True 时禁止 confirm→allow downgrade。"""

    def test_upgrade_only_confirm_allow_stays_confirm(self):
        """upgrade_only=True: confirm + semantic allow → 保持 confirm（禁止 downgrade）。"""
        import tempfile
        from pathlib import Path as _Path

        with tempfile.TemporaryDirectory() as tmpdir:
            confirm_rule = _Path(tmpdir) / "TC_UO.yaml"
            confirm_rule.write_text(
                "id: TC_UO\n"
                "name: test confirm upgrade_only\n"
                "priority: 50\n"
                "enabled: true\n"
                "trigger:\n"
                "  action_type: test_confirm_action\n"
                "verdict: confirm\n"
                "reason: test confirm\n"
            )
            result = gate(
                constraints_dir=_Path(tmpdir),
                tool_call={"action_type": "test_confirm_action", "params": {"content": "benign"}},
                triviality_config=TrivialityConfig(),
                semantic_config=SemanticGateConfig(
                    mode="active",
                    upgrade_only=True,
                    provider=make_mock_provider(
                        '{"action":"allow","reason":"benign content","confidence":0.95}'
                    ),
                ),
            )
            # upgrade_only=True → semantic allow should NOT downgrade confirm
            assert result.datalog_verdict == "confirm"
            assert result.verdict.action == "confirm", (
                f"Expected confirm (upgrade_only), got {result.verdict.action}"
            )

    def test_upgrade_only_confirm_block_still_upgrades(self):
        """upgrade_only=True: confirm + semantic block (high conf) → block（upgrade 仍有效）。"""
        import tempfile
        from pathlib import Path as _Path

        with tempfile.TemporaryDirectory() as tmpdir:
            confirm_rule = _Path(tmpdir) / "TC_UO2.yaml"
            confirm_rule.write_text(
                "id: TC_UO2\n"
                "name: test confirm upgrade_only block\n"
                "priority: 50\n"
                "enabled: true\n"
                "trigger:\n"
                "  action_type: test_confirm_action2\n"
                "verdict: confirm\n"
                "reason: test confirm\n"
            )
            result = gate(
                constraints_dir=_Path(tmpdir),
                tool_call={"action_type": "test_confirm_action2", "params": {"content": "harmful"}},
                triviality_config=TrivialityConfig(),
                semantic_config=SemanticGateConfig(
                    mode="active",
                    upgrade_only=True,
                    block_upgrade_threshold=0.85,
                    provider=make_mock_provider(
                        '{"action":"block","reason":"harmful content","confidence":0.91}'
                    ),
                ),
            )
            # upgrade_only=True → semantic block with high conf should STILL upgrade to block
            assert result.datalog_verdict == "confirm"
            assert result.verdict.action == "block", (
                f"Expected block (upgrade_only allows upgrades), got {result.verdict.action}"
            )

    def test_upgrade_only_false_confirm_allow_downgrades(self):
        """upgrade_only=False（默认）: confirm + semantic allow → allow（原有降级行为保留）。"""
        import tempfile
        from pathlib import Path as _Path

        with tempfile.TemporaryDirectory() as tmpdir:
            confirm_rule = _Path(tmpdir) / "TC_UO3.yaml"
            confirm_rule.write_text(
                "id: TC_UO3\n"
                "name: test confirm upgrade_only=False\n"
                "priority: 50\n"
                "enabled: true\n"
                "trigger:\n"
                "  action_type: test_confirm_action3\n"
                "verdict: confirm\n"
                "reason: test confirm\n"
            )
            result = gate(
                constraints_dir=_Path(tmpdir),
                tool_call={"action_type": "test_confirm_action3", "params": {"content": "benign"}},
                triviality_config=TrivialityConfig(),
                semantic_config=SemanticGateConfig(
                    mode="active",
                    upgrade_only=False,  # 明确设 False（默认行为）
                    allow_downgrade_threshold=0.70,
                    provider=make_mock_provider(
                        '{"action":"allow","reason":"benign content","confidence":0.92}'
                    ),
                ),
            )
            # upgrade_only=False → semantic allow with conf >= 0.70 should downgrade confirm→allow
            assert result.datalog_verdict == "confirm"
            assert result.verdict.action == "allow", (
                f"Expected allow (upgrade_only=False), got {result.verdict.action}"
            )
