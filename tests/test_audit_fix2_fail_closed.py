"""Audit Fix 2 (P0): 约束解析 fail-closed

验证：
- 损坏的 YAML 文件 → load_constraints 抛出 ConstraintLoadError（不静默跳过）
- gate() 遇到 ConstraintLoadError → 返回 confirm（fail-closed）
- 多文件场景：任一文件损坏 → 整体 fail-closed
"""
import pytest
from pathlib import Path
from nous.constraint_parser import load_constraints, ConstraintLoadError
from nous.gate import gate


def _write_yaml(tmp_path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


class TestConstraintFailClosed:
    """Fix 2: 单个 YAML 损坏 → 抛异常，不静默跳过"""

    def test_valid_yaml_loads_ok(self, tmp_path):
        """正常 YAML → 加载成功"""
        _write_yaml(tmp_path, "T99.yaml", """\
id: T99
verdict: block
reason: test
trigger:
  action_type:
    in: [test_action]
""")
        constraints = load_constraints(tmp_path)
        assert len(constraints) == 1
        assert constraints[0].id == "T99"

    def test_corrupted_yaml_raises_constraint_load_error(self, tmp_path):
        """损坏的 YAML 文件 → 抛出 ConstraintLoadError（fail-closed）"""
        _write_yaml(tmp_path, "T_good.yaml", """\
id: T_good
verdict: allow
trigger: {}
""")
        _write_yaml(tmp_path, "T_bad.yaml", """\
id: [broken yaml
  - this is not: valid yaml
  : : :
""")
        with pytest.raises(ConstraintLoadError) as exc_info:
            load_constraints(tmp_path)
        err_msg = str(exc_info.value)
        assert "T_bad.yaml" in err_msg or "FAIL_CLOSED" in err_msg, (
            f"错误消息应包含文件名或 FAIL_CLOSED: {err_msg}"
        )

    def test_missing_required_field_raises_error(self, tmp_path):
        """缺少必填字段 verdict → 抛出 ConstraintLoadError"""
        _write_yaml(tmp_path, "T_good.yaml", """\
id: T_good
verdict: block
trigger: {}
""")
        _write_yaml(tmp_path, "T_no_verdict.yaml", """\
id: T_missing
# verdict 字段缺失
reason: no verdict here
trigger: {}
""")
        with pytest.raises(ConstraintLoadError):
            load_constraints(tmp_path)

    def test_single_corrupted_file_triggers_fail_closed(self, tmp_path):
        """即使只有一个文件损坏，也要 fail-closed（不加载任何约束）"""
        # 写 5 个好文件 + 1 个坏文件
        for i in range(5):
            _write_yaml(tmp_path, f"T_good_{i}.yaml", f"""\
id: T_good_{i}
verdict: allow
trigger: {{}}
""")
        _write_yaml(tmp_path, "T_broken.yaml", "not: valid: yaml: :::")

        with pytest.raises(ConstraintLoadError):
            load_constraints(tmp_path)


class TestGateFailClosedOnConstraintError:
    """gate() 遇到 ConstraintLoadError → 返回 confirm（fail-closed）"""

    def test_corrupted_constraint_dir_returns_confirm(self, tmp_path):
        """约束目录有损坏文件 → gate 返回 confirm（不是 allow）"""
        # 一个好文件 + 一个坏文件
        _write_yaml(tmp_path, "T_good.yaml", """\
id: T_good
verdict: allow
trigger: {}
""")
        _write_yaml(tmp_path, "T_corrupt.yaml", "broken: yaml: :: :")

        result = gate(
            tool_call={"tool_name": "web_search", "action_type": "search"},
            constraints_dir=tmp_path,
        )
        assert result.verdict.action == "confirm", (
            f"约束损坏时应 fail-closed=confirm，实际: {result.verdict.action}"
        )

    def test_corrupted_constraint_dir_not_allow(self, tmp_path):
        """约束损坏时绝不能是 allow（安全检查）"""
        _write_yaml(tmp_path, "T_good.yaml", """\
id: T_good
verdict: block
trigger:
  action_type:
    in: [delete_file]
""")
        _write_yaml(tmp_path, "T_broken.yaml", "id: [unclosed")

        result = gate(
            tool_call={"tool_name": "web_search"},
            constraints_dir=tmp_path,
        )
        assert result.verdict.action != "allow", (
            "约束损坏时不应返回 allow（高风险）"
        )
        assert result.verdict.action == "confirm"

    def test_fail_closed_verdict_has_meaningful_reason(self, tmp_path):
        """fail-closed 的 verdict 应有可读的 reason"""
        _write_yaml(tmp_path, "T_bad.yaml", "broken: : :")

        result = gate(
            tool_call={"tool_name": "exec"},
            constraints_dir=tmp_path,
        )
        assert result.verdict.action == "confirm"
        assert result.verdict.reason, "fail-closed reason 不应为空"
        assert "constraint" in result.verdict.reason.lower() or "error" in result.verdict.reason.lower()
