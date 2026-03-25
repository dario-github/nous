"""Tests — M2.P3: resource-budget.yaml 配置加载 + gate() 集成

验证：
- resource-budget.yaml 正确加载
- 默认值在文件不存在时生效
- 超限时 log warning（不 block gate）
- gate() 集成：预算检查不影响正常 verdict
"""
import logging
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

SRC_DIR = Path(__file__).parent.parent / "src"
CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"
CONFIG_DIR = Path(__file__).parent.parent / "ontology" / "config"
sys.path.insert(0, str(SRC_DIR))

from nous.resource_budget import (
    ResourceBudget,
    check_budget,
    load_resource_budget,
    DEFAULT_CONFIG_PATH,
)
from nous.db import NousDB
from nous.gate import gate


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mem_db():
    db = NousDB(":memory:")
    yield db
    db.close()


@pytest.fixture
def tmp_config_dir(tmp_path):
    return tmp_path


# ── ResourceBudget 默认值 ─────────────────────────────────────────────────


class TestResourceBudgetDefaults:
    def test_default_values(self):
        b = ResourceBudget()
        assert b.max_query_depth == 5
        assert b.max_entities_scanned == 50
        assert b.delegate_token_budget == 512
        assert b.timeout_us == 5000
        assert b.enforcement == "warn"

    def test_load_nonexistent_file_returns_defaults(self, tmp_config_dir):
        b = load_resource_budget(tmp_config_dir / "nonexistent.yaml")
        assert b.max_query_depth == 5
        assert b.enforcement == "warn"


# ── load_resource_budget ─────────────────────────────────────────────────


class TestLoadResourceBudget:
    def test_load_real_config(self):
        """加载真实的 resource-budget.yaml (Loop 74: 路径修复后读真实 YAML)"""
        b = load_resource_budget(DEFAULT_CONFIG_PATH)
        assert b.max_query_depth == 5
        assert b.max_entities_scanned == 200   # Loop 74: KG 482 entities
        assert b.delegate_token_budget == 512
        assert b.timeout_us == 300000000       # 5 min — benchmark with semantic gate
        assert b.enforcement == "warn"

    def test_load_custom_config(self, tmp_config_dir):
        config = {
            "gate_budgets": {
                "max_query_depth": 10,
                "max_entities_scanned": 100,
                "delegate_token_budget": 1024,
                "timeout_us": 10000,
            },
            "enforcement": "enforce",
        }
        config_file = tmp_config_dir / "resource-budget.yaml"
        config_file.write_text(yaml.dump(config), encoding="utf-8")

        b = load_resource_budget(config_file)
        assert b.max_query_depth == 10
        assert b.max_entities_scanned == 100
        assert b.delegate_token_budget == 1024
        assert b.timeout_us == 10000
        assert b.enforcement == "enforce"

    def test_load_partial_config(self, tmp_config_dir):
        """部分字段缺失时用默认值补全"""
        config = {"gate_budgets": {"max_query_depth": 3}}
        config_file = tmp_config_dir / "resource-budget.yaml"
        config_file.write_text(yaml.dump(config), encoding="utf-8")

        b = load_resource_budget(config_file)
        assert b.max_query_depth == 3
        assert b.max_entities_scanned == 50   # 默认值
        assert b.enforcement == "warn"        # 默认值

    def test_load_empty_file_returns_defaults(self, tmp_config_dir):
        config_file = tmp_config_dir / "resource-budget.yaml"
        config_file.write_text("", encoding="utf-8")
        b = load_resource_budget(config_file)
        assert b.max_query_depth == 5

    def test_load_malformed_yaml_returns_defaults(self, tmp_config_dir):
        config_file = tmp_config_dir / "resource-budget.yaml"
        config_file.write_text(": invalid: yaml: {{{{", encoding="utf-8")
        b = load_resource_budget(config_file)
        assert b.max_query_depth == 5


# ── check_budget ─────────────────────────────────────────────────────────


class TestCheckBudget:
    def test_no_warnings_within_budget(self):
        b = ResourceBudget(max_entities_scanned=50, timeout_us=5000)
        warnings = check_budget(b, entities_scanned=10, elapsed_us=1000)
        assert warnings == []

    def test_entities_scanned_over_budget(self, caplog):
        b = ResourceBudget(max_entities_scanned=5)
        with caplog.at_level(logging.WARNING, logger="nous.resource_budget"):
            warnings = check_budget(b, entities_scanned=10)
        assert len(warnings) == 1
        assert "entities_scanned" in warnings[0]

    def test_timeout_over_budget(self, caplog):
        b = ResourceBudget(timeout_us=1000)
        with caplog.at_level(logging.WARNING, logger="nous.resource_budget"):
            warnings = check_budget(b, elapsed_us=9999)
        assert len(warnings) == 1
        assert "timeout_us" in warnings[0] or "elapsed_us" in warnings[0]

    def test_multiple_violations(self, caplog):
        b = ResourceBudget(max_entities_scanned=1, timeout_us=1)
        with caplog.at_level(logging.WARNING, logger="nous.resource_budget"):
            warnings = check_budget(b, entities_scanned=100, elapsed_us=9999)
        assert len(warnings) == 2

    def test_exactly_at_limit_no_warning(self):
        b = ResourceBudget(max_entities_scanned=10, timeout_us=5000)
        warnings = check_budget(b, entities_scanned=10, elapsed_us=5000)
        # 等于限制值不触发警告（> 才触发）
        assert warnings == []


# ── gate() 集成：预算不 block ─────────────────────────────────────────────


class TestGateBudgetIntegration:
    def test_gate_still_returns_verdict_even_if_over_budget(self, mem_db):
        """资源超限时 gate() 仍返回正常 verdict（warn 模式不 block）"""
        # 正常的 delete_file 应被 block，预算超限不影响这个
        tc = {"tool_name": "exec", "action_type": "delete_file"}
        result = gate(
            tool_call=tc,
            db=mem_db,
            constraints_dir=CONSTRAINTS_DIR,
            session_key="budget-test-001",
        )
        assert result.verdict.action == "block"
        assert result.latency_ms >= 0.0

    def test_gate_allow_with_real_budget_config(self, mem_db):
        """正常放行操作不受预算检查影响"""
        from nous.observability import SamplingPolicy
        policy = SamplingPolicy(allow_rate=1.0)
        tc = {"tool_name": "web_search", "action_type": "search"}
        result = gate(
            tool_call=tc,
            db=mem_db,
            constraints_dir=CONSTRAINTS_DIR,
            session_key="budget-allow-test",
            sampling_policy=policy,
        )
        assert result.verdict.action == "allow"

    def test_gate_does_not_raise_when_config_missing(self, mem_db, monkeypatch):
        """config 文件不存在时 gate() 使用默认预算，不抛异常"""
        import nous.resource_budget as rb_mod
        monkeypatch.setattr(rb_mod, "DEFAULT_CONFIG_PATH", Path("/nonexistent/path.yaml"))

        tc = {"tool_name": "web_search", "action_type": "search"}
        result = gate(
            tool_call=tc,
            db=mem_db,
            constraints_dir=CONSTRAINTS_DIR,
        )
        # 应正常返回，不抛异常
        assert result.verdict is not None
