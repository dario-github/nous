"""Tests — M2.P4: constraint YAML dialect + semantics 字段

验证：
- 现有 5 条约束默认 dialect="cozo"
- 新 YAML 可显式指定 dialect 和 semantics
- 缺失字段时使用默认值，兼容现有约束
"""
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

SRC_DIR = Path(__file__).parent.parent / "src"
CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"
sys.path.insert(0, str(SRC_DIR))

from nous.constraint_parser import load_constraints, parse_constraint_file
from nous.schema import Constraint


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_constraint_dir(tmp_path):
    """提供临时约束目录用于测试新 YAML"""
    return tmp_path


# ── M2.P4: 默认 dialect ───────────────────────────────────────────────────


class TestDialectDefault:
    def test_existing_constraints_have_default_dialect(self):
        """现有 5 条约束文件未设 dialect → 默认应为 'cozo'"""
        constraints = load_constraints(CONSTRAINTS_DIR)
        assert len(constraints) == 10  # T3+T3-soft+T3-upload+T5+T10+T11+T12+T-disinformation-election+T-grooming+T-roleplay-bypass
        for c in constraints:
            assert c.dialect == "cozo", f"{c.id} dialect should default to 'cozo'"

    def test_existing_constraints_have_none_semantics(self):
        """现有约束未设 semantics → 默认 None"""
        constraints = load_constraints(CONSTRAINTS_DIR)
        for c in constraints:
            assert c.semantics is None, f"{c.id} semantics should default to None"

    def test_schema_default_dialect(self):
        """Constraint 模型默认 dialect='cozo'"""
        c = Constraint(id="test", verdict="block")
        assert c.dialect == "cozo"

    def test_schema_default_semantics_none(self):
        """Constraint 模型默认 semantics=None"""
        c = Constraint(id="test", verdict="block")
        assert c.semantics is None


# ── M2.P4: 显式 dialect ──────────────────────────────────────────────────


class TestDialectExplicit:
    def test_parse_dialect_cozo(self, tmp_constraint_dir):
        yaml_content = {
            "id": "T99",
            "verdict": "block",
            "dialect": "cozo",
        }
        f = tmp_constraint_dir / "T99.yaml"
        f.write_text(yaml.dump(yaml_content), encoding="utf-8")
        c = parse_constraint_file(f)
        assert c.dialect == "cozo"

    def test_parse_dialect_scallop(self, tmp_constraint_dir):
        yaml_content = {
            "id": "T98",
            "verdict": "warn",
            "dialect": "scallop",
        }
        f = tmp_constraint_dir / "T98.yaml"
        f.write_text(yaml.dump(yaml_content), encoding="utf-8")
        c = parse_constraint_file(f)
        assert c.dialect == "scallop"

    def test_parse_dialect_lobster(self, tmp_constraint_dir):
        yaml_content = {
            "id": "T97",
            "verdict": "confirm",
            "dialect": "lobster",
        }
        f = tmp_constraint_dir / "T97.yaml"
        f.write_text(yaml.dump(yaml_content), encoding="utf-8")
        c = parse_constraint_file(f)
        assert c.dialect == "lobster"

    def test_parse_dialect_missing_defaults_to_cozo(self, tmp_constraint_dir):
        """未设 dialect → 默认 cozo"""
        yaml_content = {"id": "T96", "verdict": "block"}
        f = tmp_constraint_dir / "T96.yaml"
        f.write_text(yaml.dump(yaml_content), encoding="utf-8")
        c = parse_constraint_file(f)
        assert c.dialect == "cozo"


# ── M2.P4: semantics 字段 ─────────────────────────────────────────────────


class TestSemantics:
    def test_parse_semantics_boolean_algebra(self, tmp_constraint_dir):
        yaml_content = {
            "id": "T95",
            "verdict": "block",
            "dialect": "cozo",
            "semantics": {
                "logic_algebra": "boolean",
                "weight_algebra": None,
            },
        }
        f = tmp_constraint_dir / "T95.yaml"
        f.write_text(yaml.dump(yaml_content), encoding="utf-8")
        c = parse_constraint_file(f)
        assert c.semantics is not None
        assert c.semantics["logic_algebra"] == "boolean"
        assert c.semantics["weight_algebra"] is None

    def test_parse_semantics_missing_defaults_none(self, tmp_constraint_dir):
        yaml_content = {"id": "T94", "verdict": "warn"}
        f = tmp_constraint_dir / "T94.yaml"
        f.write_text(yaml.dump(yaml_content), encoding="utf-8")
        c = parse_constraint_file(f)
        assert c.semantics is None

    def test_parse_semantics_arbitrary_dict(self, tmp_constraint_dir):
        yaml_content = {
            "id": "T93",
            "verdict": "block",
            "semantics": {"custom_field": "future_value", "version": 5},
        }
        f = tmp_constraint_dir / "T93.yaml"
        f.write_text(yaml.dump(yaml_content), encoding="utf-8")
        c = parse_constraint_file(f)
        assert c.semantics["custom_field"] == "future_value"


# ── M2.P4: 批量加载兼容性 ─────────────────────────────────────────────────


class TestLoadCompatibility:
    def test_load_real_constraints_not_broken(self):
        """加载真实约束目录：5 条全部解析成功，不受新字段影响"""
        constraints = load_constraints(CONSTRAINTS_DIR)
        assert len(constraints) == 10  # T3+T3-soft+T3-upload+T5+T10+T11+T12+T-disinformation-election+T-grooming+T-roleplay-bypass
        ids = {c.id for c in constraints}
        assert {"T3", "T3-soft", "T3-upload", "T5", "T10", "T11", "T12", "T-disinformation-election", "T-grooming", "T-roleplay-bypass"} == ids

    def test_mixed_dir_old_and_new(self, tmp_constraint_dir):
        """新旧格式混合加载，全部成功"""
        # 旧格式（无 dialect/semantics）
        old = {"id": "OLD1", "verdict": "block"}
        (tmp_constraint_dir / "OLD1.yaml").write_text(yaml.dump(old), encoding="utf-8")

        # 新格式（带 dialect/semantics）
        new = {
            "id": "NEW1",
            "verdict": "warn",
            "dialect": "scallop",
            "semantics": {"logic_algebra": "boolean"},
        }
        (tmp_constraint_dir / "NEW1.yaml").write_text(yaml.dump(new), encoding="utf-8")

        constraints = load_constraints(tmp_constraint_dir)
        assert len(constraints) == 2
        by_id = {c.id: c for c in constraints}
        assert by_id["OLD1"].dialect == "cozo"   # 默认
        assert by_id["NEW1"].dialect == "scallop"
        assert by_id["NEW1"].semantics == {"logic_algebra": "boolean"}
