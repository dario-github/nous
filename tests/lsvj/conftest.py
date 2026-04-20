"""LSVJ-S 测试 conftest：共享 fixtures。

schema_fixture  — 从 ontology YAML 加载 PrimitiveSchema
mock_evaluator  — 返回 MockEvaluator 实例（空 truth table，从 bindings 读取）
"""
from __future__ import annotations

from pathlib import Path

import pytest

from nous.lsvj.gate import MockEvaluator
from nous.lsvj.schema import PrimitiveSchema, load_schema_from_yaml

# ontology YAML 路径（相对于项目根）
_SCHEMA_YAML = (
    Path(__file__).parent.parent.parent
    / "ontology" / "schema" / "owner_harm_primitives.yaml"
)


@pytest.fixture(scope="session")
def schema_fixture() -> PrimitiveSchema:
    """加载 owner_harm_primitives.yaml，session 级缓存。"""
    return load_schema_from_yaml(str(_SCHEMA_YAML))


@pytest.fixture
def mock_evaluator() -> MockEvaluator:
    """空 truth table 的 MockEvaluator；测试通过 bindings dict 注入值。"""
    return MockEvaluator()
