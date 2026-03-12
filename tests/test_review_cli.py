"""Nous — 审核队列 CLI 测试 (M3.4)"""
import tempfile
from pathlib import Path

from nous.rule_proposer import save_proposal

# 测试直接导入内部方法
import sys
import argparse
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import review_cli


def test_review_cli_approve_reject():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        proposals_dir = tmp / "proposals"
        constraints_dir = tmp / "constraints"

        # 构造提案
        prop = {"id": "TEST-R1", "verdict": "block", "enabled": True}
        fp = save_proposal(prop, proposals_dir)
        pid = fp.stem  # proposal-TEST-R1-123456

        assert fp.exists()

        # Approve
        target = review_cli.approve_proposal(pid, proposals_dir, constraints_dir)
        assert not fp.exists()
        assert target.exists()
        assert target.name == "TEST-R1.yaml"

        # 构造第二个提案用于 Reject
        prop2 = {"id": "TEST-R2", "verdict": "block"}
        fp2 = save_proposal(prop2, proposals_dir)
        pid2 = fp2.stem

        target2 = review_cli.reject_proposal(pid2, proposals_dir)
        assert not fp2.exists()
        assert target2.exists()
        assert "rejected" in target2.parts
        assert target2.name == fp2.name
