"""Tests for rule_generator.py — LLM → Constraint 自动生成 (E3)

Mock LLM responses，测试 generate→parse→validate 全链路。
至少 15 个测试，覆盖：正常生成、格式错误、验证通过/失败、冲突检测、incident→rule。
"""
import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from nous.rule_generator import (
    ValidationResult,
    _dict_to_constraint,
    _enforce_safety,
    _load_examples,
    _parse_multi_yaml_response,
    _parse_yaml_response,
    generate_rule,
    propose_rules,
    save_rule,
    validate_rule,
)
from nous.schema import Constraint


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def mock_llm():
    """返回一个可配置响应的 mock LLM provider"""
    provider = MagicMock()
    provider.return_value = ""
    return provider


@pytest.fixture
def valid_yaml_response():
    """一个合法的 LLM YAML 响应"""
    return """id: AUTO-MSG-no-public-after-hours
name: 工作时间外公共频道限制
priority: 75
enabled: true
trigger:
  action_type:
    in: [send_message]
  target_is_public: true
  outside_work_hours: true
verdict: confirm
reason: "禁止在工作时间外发送消息到公共频道"
metadata:
  source: auto-generated
  policy_text: "禁止在工作时间外发送消息到公共频道"
"""


@pytest.fixture
def sample_constraint():
    """一个合法的自动生成 Constraint"""
    return Constraint(
        id="AUTO-TEST-rule",
        name="Test rule",
        priority=75,
        enabled=True,
        trigger={"action_type": {"in": ["test_action"]}},
        verdict="confirm",
        reason="Test reason",
        metadata={"source": "auto-generated"},
    )


@pytest.fixture
def existing_constraints():
    """模拟现有约束列表"""
    return [
        Constraint(
            id="T3",
            verdict="block",
            trigger={"action_type": {"in": ["delete_file"]}},
            reason="T3 block",
        ),
        Constraint(
            id="T5",
            verdict="block",
            trigger={"url_has_social_pattern": True},
            reason="T5 block",
        ),
    ]


@pytest.fixture
def tmp_constraints_dir(tmp_path):
    """创建含示例约束的临时目录"""
    cdir = tmp_path / "constraints"
    cdir.mkdir()
    rule = {
        "id": "T-EXAMPLE",
        "name": "Example rule",
        "priority": 80,
        "enabled": True,
        "trigger": {"action_type": {"in": ["example"]}},
        "verdict": "block",
        "reason": "Example",
        "metadata": {},
    }
    with open(cdir / "T-EXAMPLE.yaml", "w") as f:
        yaml.dump(rule, f)
    return cdir


@pytest.fixture
def tmp_auto_dir(tmp_path):
    """临时 auto 目录"""
    adir = tmp_path / "auto"
    adir.mkdir()
    return adir


# ── Test generate_rule ─────────────────────────────────────────────────────


class TestGenerateRule:
    def test_basic_generation(self, mock_llm, valid_yaml_response):
        """正常生成：LLM 返回合法 YAML → Constraint"""
        mock_llm.return_value = valid_yaml_response

        result = generate_rule("禁止在工作时间外发送消息到公共频道", mock_llm)

        assert isinstance(result, Constraint)
        assert result.id.startswith("AUTO-")
        assert result.verdict == "confirm"
        assert result.metadata.get("source") == "auto-generated"
        assert result.trigger  # trigger 非空
        mock_llm.assert_called_once()

    def test_verdict_forced_to_confirm(self, mock_llm):
        """安全约束：即使 LLM 返回 block，也强制改为 confirm"""
        mock_llm.return_value = """id: AUTO-BAD-block-attempt
name: Attempted block
trigger:
  action_type:
    in: [dangerous]
verdict: block
reason: "Should be overridden"
metadata:
  source: auto-generated
"""
        result = generate_rule("Some policy", mock_llm)
        assert result.verdict == "confirm"

    def test_verdict_deny_forced(self, mock_llm):
        """安全约束：deny 也被强制为 confirm"""
        mock_llm.return_value = """id: AUTO-DENY-test
trigger:
  action_type:
    in: [something]
verdict: deny
reason: test
"""
        result = generate_rule("Some policy", mock_llm)
        assert result.verdict == "confirm"

    def test_empty_policy_raises(self, mock_llm):
        """空策略文本抛异常"""
        with pytest.raises(ValueError, match="empty"):
            generate_rule("", mock_llm)

        with pytest.raises(ValueError, match="empty"):
            generate_rule("   ", mock_llm)

    def test_invalid_yaml_response(self, mock_llm):
        """LLM 返回非法 YAML → ValueError"""
        mock_llm.return_value = "this is not yaml: [[[{"
        with pytest.raises(ValueError, match="parse"):
            generate_rule("Some policy", mock_llm)

    def test_non_dict_response(self, mock_llm):
        """LLM 返回 YAML 列表而非 dict → ValueError"""
        mock_llm.return_value = "- item1\n- item2"
        with pytest.raises(ValueError, match="parse"):
            generate_rule("Some policy", mock_llm)

    def test_markdown_fence_stripped(self, mock_llm):
        """LLM 返回带 markdown 代码块的 YAML → 自动去除"""
        mock_llm.return_value = """```yaml
id: AUTO-FENCED-test
name: Fenced rule
trigger:
  action_type:
    in: [test]
verdict: confirm
reason: test
metadata:
  source: auto-generated
```"""
        result = generate_rule("Test policy", mock_llm)
        assert result.id == "AUTO-FENCED-test"
        assert result.verdict == "confirm"

    def test_missing_id_auto_generated(self, mock_llm):
        """LLM 返回缺 id → 自动补全 AUTO-POLICY-*"""
        mock_llm.return_value = """trigger:
  action_type:
    in: [test]
verdict: confirm
reason: test
"""
        result = generate_rule("Test short policy", mock_llm)
        assert result.id.startswith("AUTO-")

    def test_id_without_auto_prefix(self, mock_llm):
        """LLM 返回无 AUTO- 前缀的 id → 自动补 AUTO-"""
        mock_llm.return_value = """id: CUSTOM-RULE
trigger:
  action_type:
    in: [test]
verdict: confirm
reason: test
"""
        result = generate_rule("Test", mock_llm)
        assert result.id == "AUTO-CUSTOM-RULE"

    def test_with_custom_examples(self, mock_llm, valid_yaml_response):
        """传入自定义 few-shot 示例"""
        mock_llm.return_value = valid_yaml_response
        custom_example = "id: EXAMPLE\nverdic: block\ntrigger: {}\nreason: ex"

        result = generate_rule("Test policy", mock_llm, examples=[custom_example])
        assert isinstance(result, Constraint)
        # 确认 prompt 包含了自定义示例
        call_args = mock_llm.call_args[0]
        assert "EXAMPLE" in call_args[0]

    def test_with_constraints_dir(self, mock_llm, valid_yaml_response, tmp_constraints_dir):
        """从约束目录加载 few-shot 示例"""
        mock_llm.return_value = valid_yaml_response
        result = generate_rule(
            "Test policy", mock_llm, constraints_dir=tmp_constraints_dir
        )
        assert isinstance(result, Constraint)
        call_args = mock_llm.call_args[0]
        assert "T-EXAMPLE" in call_args[0]


# ── Test validate_rule ─────────────────────────────────────────────────────


class TestValidateRule:
    def test_valid_rule_passes(self, sample_constraint):
        """合法规则验证通过"""
        vr = validate_rule(sample_constraint)
        assert vr.valid is True
        assert len(vr.errors) == 0

    def test_missing_id_fails(self):
        """缺 id 验证失败"""
        c = Constraint(id="", verdict="confirm", trigger={"x": 1})
        vr = validate_rule(c)
        assert vr.valid is False
        assert any("id" in e.lower() for e in vr.errors)

    def test_wrong_verdict_fails(self):
        """非 confirm verdict 验证失败"""
        c = Constraint(
            id="AUTO-TEST",
            verdict="block",
            trigger={"x": 1},
            metadata={"source": "auto-generated"},
        )
        vr = validate_rule(c)
        assert vr.valid is False
        assert any("confirm" in e for e in vr.errors)

    def test_empty_trigger_fails(self):
        """空 trigger 验证失败"""
        c = Constraint(
            id="AUTO-TEST",
            verdict="confirm",
            trigger={},
            metadata={"source": "auto-generated"},
        )
        vr = validate_rule(c)
        assert vr.valid is False
        assert any("trigger" in e.lower() for e in vr.errors)

    def test_none_trigger_value_fails(self):
        """trigger 含 None 值验证失败"""
        c = Constraint(
            id="AUTO-TEST",
            verdict="confirm",
            trigger={"action_type": None},
            metadata={"source": "auto-generated"},
        )
        vr = validate_rule(c)
        assert vr.valid is False

    def test_conflict_detection(self, sample_constraint, existing_constraints):
        """冲突检测：同 id 不同 verdict"""
        conflicting = Constraint(
            id="T3",  # 与 existing T3 (block) 冲突
            verdict="confirm",
            trigger={"action_type": {"in": ["delete_file"]}},
            metadata={"source": "auto-generated"},
        )
        vr = validate_rule(conflicting, existing_constraints=existing_constraints)
        assert vr.valid is False
        assert any("conflict" in e.lower() for e in vr.errors)

    def test_shadow_warning(self, sample_constraint):
        """同 id 同 verdict → 警告（shadow）"""
        existing = [Constraint(
            id="AUTO-TEST-rule",
            verdict="confirm",
            trigger={"action_type": {"in": ["other"]}},
        )]
        vr = validate_rule(sample_constraint, existing_constraints=existing)
        assert vr.valid is True  # 不是错误，只是警告
        assert any("shadow" in w.lower() for w in vr.warnings)

    def test_missing_source_warning(self):
        """缺 source 元数据 → 警告"""
        c = Constraint(
            id="AUTO-TEST",
            verdict="confirm",
            trigger={"x": 1},
            metadata={},
        )
        vr = validate_rule(c)
        assert vr.valid is True  # 只是警告
        assert any("source" in w.lower() for w in vr.warnings)

    def test_unknown_operator_warning(self):
        """未知 trigger 操作符 → 警告"""
        c = Constraint(
            id="AUTO-TEST",
            verdict="confirm",
            trigger={"field": {"unknown_op": 42}},
            metadata={"source": "auto-generated"},
        )
        vr = validate_rule(c)
        assert vr.valid is True
        assert any("unknown operator" in w for w in vr.warnings)

    def test_validate_with_constraints_dir(self, sample_constraint, tmp_constraints_dir):
        """从目录加载现有约束做冲突检测"""
        vr = validate_rule(
            sample_constraint, constraints_dir=tmp_constraints_dir
        )
        assert vr.valid is True


# ── Test propose_rules ─────────────────────────────────────────────────────


class TestProposeRules:
    def test_basic_proposal(self, mock_llm):
        """从事件日志生成候选规则"""
        mock_llm.return_value = """id: AUTO-INCIDENT-file-exfil
name: 文件外发检测
priority: 75
enabled: true
trigger:
  action_type:
    in: [upload, send_file]
  target_is_external: true
verdict: confirm
reason: "检测到多次文件外发事件"
metadata:
  source: auto-generated
"""
        incidents = [
            {"rule": "none", "trigger_type": "upload", "summary": "文件上传到外部", "result": "allowed"},
            {"rule": "none", "trigger_type": "upload", "summary": "敏感文件外发", "result": "allowed"},
        ]
        results = propose_rules(incidents, mock_llm)
        assert len(results) >= 1
        assert all(r.verdict == "confirm" for r in results)
        assert all(r.metadata.get("source") == "auto-generated" for r in results)

    def test_empty_incidents(self, mock_llm):
        """空事件日志 → 空列表"""
        results = propose_rules([], mock_llm)
        assert results == []
        mock_llm.assert_not_called()

    def test_multi_rule_proposal(self, mock_llm):
        """LLM 返回多个 YAML 文档"""
        mock_llm.return_value = """id: AUTO-INC-rule1
trigger:
  action_type:
    in: [action1]
verdict: confirm
reason: rule 1
---
id: AUTO-INC-rule2
trigger:
  action_type:
    in: [action2]
verdict: confirm
reason: rule 2
"""
        incidents = [
            {"rule": "T1", "trigger_type": "stale_data", "summary": "Stale", "result": "blocked"},
        ]
        results = propose_rules(incidents, mock_llm)
        assert len(results) == 2

    def test_invalid_rules_filtered(self, mock_llm):
        """无效规则被过滤，有效规则保留"""
        mock_llm.return_value = """id: AUTO-INC-good
trigger:
  action_type:
    in: [good_action]
verdict: confirm
reason: good
---
id: AUTO-INC-bad
trigger: {}
verdict: confirm
reason: bad empty trigger
"""
        incidents = [{"rule": "x", "trigger_type": "y", "summary": "z", "result": "w"}]
        results = propose_rules(incidents, mock_llm)
        # Only the good rule should pass validation
        assert len(results) == 1
        assert results[0].id == "AUTO-INC-good"

    def test_llm_error_returns_empty(self, mock_llm):
        """LLM 返回垃圾 → 空列表（不抛异常）"""
        mock_llm.return_value = "totally not yaml {{{[["
        incidents = [{"rule": "x", "trigger_type": "y", "summary": "z", "result": "w"}]
        results = propose_rules(incidents, mock_llm)
        assert results == []


# ── Test save_rule ─────────────────────────────────────────────────────────


class TestSaveRule:
    def test_save_valid_rule(self, sample_constraint, tmp_auto_dir):
        """保存合法规则到文件"""
        path = save_rule(sample_constraint, auto_dir=tmp_auto_dir)
        assert path.exists()
        assert path.suffix == ".yaml"

        with open(path) as f:
            loaded = yaml.safe_load(f)
        assert loaded["id"] == "AUTO-TEST-rule"
        assert loaded["verdict"] == "confirm"
        assert loaded["metadata"]["source"] == "auto-generated"

    def test_save_wrong_verdict_raises(self, tmp_auto_dir):
        """verdict 不是 confirm → 拒绝保存"""
        c = Constraint(
            id="AUTO-BAD",
            verdict="block",
            trigger={"x": 1},
            metadata={"source": "auto-generated"},
        )
        with pytest.raises(ValueError, match="confirm"):
            save_rule(c, auto_dir=tmp_auto_dir)

    def test_save_missing_source_raises(self, tmp_auto_dir):
        """缺 auto-generated source → 拒绝保存"""
        c = Constraint(
            id="AUTO-NOSRC",
            verdict="confirm",
            trigger={"x": 1},
            metadata={},
        )
        with pytest.raises(ValueError, match="source"):
            save_rule(c, auto_dir=tmp_auto_dir)

    def test_save_creates_dir(self, tmp_path):
        """目录不存在 → 自动创建"""
        new_dir = tmp_path / "new" / "auto"
        c = Constraint(
            id="AUTO-NEWDIR",
            verdict="confirm",
            trigger={"x": 1},
            metadata={"source": "auto-generated"},
        )
        path = save_rule(c, auto_dir=new_dir)
        assert path.exists()
        assert new_dir.exists()


# ── Test helper functions ──────────────────────────────────────────────────


class TestHelpers:
    def test_enforce_safety_verdict(self):
        """_enforce_safety 强制 verdict=confirm"""
        d = {"id": "X", "trigger": {"a": 1}, "verdict": "block"}
        result = _enforce_safety(d, "test")
        assert result["verdict"] == "confirm"
        assert result["metadata"]["source"] == "auto-generated"

    def test_enforce_safety_auto_id(self):
        """_enforce_safety 为无 id 的规则生成 AUTO-POLICY-*"""
        d = {"trigger": {"a": 1}, "verdict": "confirm"}
        result = _enforce_safety(d, "my policy text")
        assert result["id"].startswith("AUTO-")

    def test_enforce_safety_prefix_id(self):
        """_enforce_safety 为无 AUTO- 前缀的 id 补前缀"""
        d = {"id": "CUSTOM", "trigger": {"a": 1}, "verdict": "confirm"}
        result = _enforce_safety(d, "test")
        assert result["id"] == "AUTO-CUSTOM"

    def test_parse_yaml_response_basic(self):
        """解析基本 YAML"""
        raw = "id: test\nverdict: block\ntrigger:\n  x: 1"
        parsed = _parse_yaml_response(raw)
        assert parsed["id"] == "test"

    def test_parse_yaml_strips_fences(self):
        """解析带 markdown fence 的 YAML"""
        raw = "```yaml\nid: test\nverdict: block\n```"
        parsed = _parse_yaml_response(raw)
        assert parsed["id"] == "test"

    def test_parse_multi_yaml(self):
        """解析多 YAML 文档"""
        raw = "id: a\nx: 1\n---\nid: b\nx: 2"
        docs = _parse_multi_yaml_response(raw)
        assert len(docs) == 2
        assert docs[0]["id"] == "a"
        assert docs[1]["id"] == "b"

    def test_load_examples_empty_dir(self, tmp_path):
        """空目录 → 空字符串"""
        empty = tmp_path / "empty"
        empty.mkdir()
        assert _load_examples(empty) == ""

    def test_load_examples_with_files(self, tmp_constraints_dir):
        """有约束文件 → 返回示例文本"""
        result = _load_examples(tmp_constraints_dir)
        assert "T-EXAMPLE" in result

    def test_dict_to_constraint(self):
        """dict → Constraint 正确转换"""
        d = {
            "id": "AUTO-X",
            "name": "Test",
            "priority": 60,
            "enabled": True,
            "trigger": {"a": 1},
            "verdict": "confirm",
            "reason": "test",
            "metadata": {"source": "auto-generated"},
        }
        c = _dict_to_constraint(d)
        assert isinstance(c, Constraint)
        assert c.id == "AUTO-X"
        assert c.priority == 60


# ── Test end-to-end flow ───────────────────────────────────────────────────


class TestEndToEnd:
    def test_generate_validate_save(self, mock_llm, valid_yaml_response, tmp_auto_dir):
        """全链路：generate → validate → save"""
        mock_llm.return_value = valid_yaml_response

        # Generate
        constraint = generate_rule("Test policy", mock_llm)
        assert constraint.verdict == "confirm"

        # Validate
        vr = validate_rule(constraint)
        assert vr.valid is True

        # Save
        path = save_rule(constraint, auto_dir=tmp_auto_dir)
        assert path.exists()

        # Verify saved file
        with open(path) as f:
            loaded = yaml.safe_load(f)
        assert loaded["verdict"] == "confirm"
        assert loaded["metadata"]["source"] == "auto-generated"

    def test_incident_to_rule_flow(self, mock_llm, tmp_auto_dir):
        """事件日志 → 提案 → 验证 → 保存"""
        mock_llm.return_value = """id: AUTO-INC-mass-delete
name: 批量删除检测
priority: 70
enabled: true
trigger:
  action_type:
    in: [delete_file]
  batch_count:
    gt: 5
verdict: confirm
reason: "检测到批量删除操作"
metadata:
  source: auto-generated
"""
        incidents = [
            {"rule": "T3", "trigger_type": "irreversible_op", "summary": "批量删除10个文件", "result": "blocked"},
            {"rule": "T3", "trigger_type": "irreversible_op", "summary": "批量删除5个文件", "result": "blocked"},
        ]

        rules = propose_rules(incidents, mock_llm)
        assert len(rules) >= 1

        for rule in rules:
            vr = validate_rule(rule)
            assert vr.valid
            path = save_rule(rule, auto_dir=tmp_auto_dir)
            assert path.exists()
