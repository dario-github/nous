"""Nous — 候选规则自动生成测试 (M3.3)"""
import tempfile
from pathlib import Path

from nous.constraint_parser import parse_constraint_file
from nous.gap_detector import GapPattern
from nous.rule_proposer import propose_rule_fix, save_proposal


def test_propose_rule_fix_too_strict_generates_disabled_yaml():
    gap = GapPattern(
        pattern_type="too_strict",
        action_type="safe_operation",
        rule_id="TEST-STRICT",
        count=3,
        examples=[],
        suggested_fix="disable it",
    )

    proposal = propose_rule_fix(gap)

    assert proposal["id"] == "TEST-STRICT"
    assert proposal["enabled"] is False
    assert proposal["verdict"] == "block"
    assert proposal["trigger"]["action_type"]["in"] == ["safe_operation"]

    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_proposal(proposal, tmpdir)
        parsed = parse_constraint_file(path)
        assert parsed.id == "TEST-STRICT"
        assert parsed.enabled is False
        assert parsed.verdict == "block"


def test_propose_rule_fix_too_loose_generates_block_yaml():
    gap = GapPattern(
        pattern_type="too_loose",
        action_type="dangerous_operation",
        count=1,
        examples=[],
        suggested_fix="add block",
    )

    proposal = propose_rule_fix(gap)

    assert proposal["enabled"] is True
    assert proposal["verdict"] == "block"
    assert proposal["trigger"]["action_type"]["in"] == ["dangerous_operation"]

    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_proposal(proposal, tmpdir)
        parsed = parse_constraint_file(path)
        assert parsed.enabled is True
        assert parsed.verdict == "block"
