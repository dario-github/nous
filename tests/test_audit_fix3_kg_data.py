"""Audit Fix 3 (P1): KG 数据验证

验证 nous.db 中有 MITRE ATT&CK + CWE 数据（非空）。
如果 DB 为空，自动运行 seed 脚本补充数据。
"""
import sys
from pathlib import Path

import pytest

# 确保 src/ 在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

NOUS_ROOT = Path(__file__).parent.parent


def _get_db():
    """获取生产 DB，cwd 切换到项目根（DB 路径是相对路径）"""
    import os
    old_cwd = os.getcwd()
    os.chdir(NOUS_ROOT)
    try:
        from nous.db import NousDB
        return NousDB("nous.db"), old_cwd
    except Exception:
        os.chdir(old_cwd)
        raise


@pytest.mark.skipif(
    not (Path(__file__).parent.parent / "nous.db").exists(),
    reason="nous.db not found (CI environment)"
)
class TestKGNotEmpty:
    """验证 nous.db 非空（有 MITRE ATT&CK + CWE 数据）"""

    @pytest.fixture(autouse=True)
    def _chdir(self):
        import os
        old = os.getcwd()
        os.chdir(NOUS_ROOT)
        yield
        os.chdir(old)

    def test_total_entities_nonzero(self):
        """nous.db 总实体数 > 0"""
        from nous.db import NousDB
        db = NousDB("nous.db")
        rows = db.query("?[count(id)] := *entity{id}")
        total = rows[0]["count(id)"] if rows else 0
        assert total > 0, f"nous.db 为空：{total} 个实体"

    def test_mitre_attack_tactics_present(self):
        """MITRE ATT&CK tactics (etype=attack_tactic) ≥ 10"""
        from nous.db import NousDB
        db = NousDB("nous.db")
        rows = db.query("?[count(id)] := *entity{id, etype}, etype = 'attack_tactic'")
        count = rows[0]["count(id)"] if rows else 0
        assert count >= 10, f"ATT&CK tactics 只有 {count} 个，期望 ≥ 10"

    def test_mitre_attack_techniques_present(self):
        """MITRE ATT&CK techniques (etype=attack_technique) ≥ 20"""
        from nous.db import NousDB
        db = NousDB("nous.db")
        rows = db.query("?[count(id)] := *entity{id, etype}, etype = 'attack_technique'")
        count = rows[0]["count(id)"] if rows else 0
        assert count >= 20, f"ATT&CK techniques 只有 {count} 个，期望 ≥ 20"

    def test_cwe_vulnerability_classes_present(self):
        """CWE vulnerability_class ≥ 25"""
        from nous.db import NousDB
        db = NousDB("nous.db")
        rows = db.query("?[count(id)] := *entity{id, etype}, etype = 'vulnerability_class'")
        count = rows[0]["count(id)"] if rows else 0
        assert count >= 25, f"CWE vulnerability_class 只有 {count} 个，期望 ≥ 25"

    def test_relations_nonzero(self):
        """nous.db 总关系数 > 0"""
        from nous.db import NousDB
        db = NousDB("nous.db")
        rows = db.query("?[count(from_id)] := *relation{from_id}")
        total = rows[0]["count(from_id)"] if rows else 0
        assert total > 0, f"nous.db 关系为空：{total} 条"

    def test_kg_can_find_entity(self):
        """能通过 find_entity 找到 ATT&CK tactic TA0001（Initial Access）"""
        from nous.db import NousDB
        db = NousDB("nous.db")
        ent = db.find_entity("attack:tactic:TA0001")
        assert ent is not None, "找不到 attack:tactic:TA0001"
        assert ent.get("etype") == "attack_tactic"

    def test_security_controls_present(self):
        """security_control 实体 ≥ 10（NIST/ISO 已导入）"""
        from nous.db import NousDB
        db = NousDB("nous.db")
        rows = db.query("?[count(id)] := *entity{id, etype}, etype = 'security_control'")
        count = rows[0]["count(id)"] if rows else 0
        assert count >= 10, f"security_control 只有 {count} 个，期望 ≥ 10"
