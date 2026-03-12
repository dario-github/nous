import tempfile
import time
import yaml
from pathlib import Path

from nous.db import NousDB
from nous.ttl import check_rule_ttl, WARN_DAYS, DISABLE_DAYS

def test_check_rule_ttl():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db = NousDB(":memory:")
        now = time.time()
        
        # 创建 3 个约束文件
        # 1. 正常活跃（昨天创建）
        c1 = {
            "id": "T-ACTIVE",
            "verdict": "block",
            "enabled": True,
            "metadata": {"created_at": now - 86400}
        }
        # 2. 达到警告阈值 (35天前)
        c2 = {
            "id": "T-WARN",
            "verdict": "block",
            "enabled": True,
            "metadata": {"created_at": now - (WARN_DAYS + 5) * 86400}
        }
        # 3. 达到禁用阈值 (65天前)
        c3 = {
            "id": "T-DISABLE",
            "verdict": "block",
            "enabled": True,
            "metadata": {"created_at": now - (DISABLE_DAYS + 5) * 86400}
        }
        
        for c in [c1, c2, c3]:
            with open(tmp / f"{c['id']}.yaml", "w", encoding="utf-8") as f:
                yaml.dump(c, f)

        # 检查 TTL
        alerts = check_rule_ttl(tmp, db)
        
        # T-ACTIVE 不应有警告
        # T-WARN 应为 warning
        # T-DISABLE 应为 disable
        
        alert_dict = {a.rule_id: a.action for a in alerts}
        assert "T-ACTIVE" not in alert_dict
        assert alert_dict.get("T-WARN") == "warning"
        assert alert_dict.get("T-DISABLE") == "disable"
        
        # 验证 T-DISABLE 被修改为 enabled: false
        with open(tmp / "T-DISABLE.yaml", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["enabled"] is False
        assert data["metadata"]["disabled_by_ttl"] is True
