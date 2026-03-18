"""Tests for M11.3 — 时序查询 API"""
import time
import pytest

from nous.temporal_query import query_at, entity_timeline, TemporalSnapshot
from nous.db import NousDB
from nous.schema import Entity, Relation


@pytest.fixture
def db(tmp_path):
    """临时 DB，带几个有时间属性的实体"""
    d = NousDB(str(tmp_path / "test.db"))
    now = time.time()

    d.upsert_entities([
        Entity(
            id="test:alpha", etype="project", labels=["project"],
            properties={"name": "Alpha", "valid_from": now - 10 * 86400},
            confidence=0.9, source="test",
        ),
        Entity(
            id="test:beta", etype="project", labels=["project"],
            properties={"name": "Beta", "valid_from": now - 5 * 86400},
            confidence=0.8, source="test",
        ),
        Entity(
            id="test:gamma", etype="concept", labels=["concept"],
            properties={
                "name": "Gamma",
                "valid_from": now - 20 * 86400,
                "status": "draft",
                "history": [
                    {"timestamp": now - 15 * 86400, "changes": {"status": "active"}},
                    {"timestamp": now - 3 * 86400, "changes": {"status": "archived", "version": "2.0"}},
                ],
            },
            confidence=1.0, source="test",
        ),
    ])

    d.upsert_relations([
        Relation(
            from_id="test:alpha", to_id="test:beta", rtype="DEPENDS_ON",
            properties={}, confidence=0.95, source="test",
        ),
    ])

    # 手动设 created_at 为 3 天前
    d.db.run(
        "?[from_id, to_id, rtype, props, confidence, source, created_at] "
        "<- [['test:alpha', 'test:beta', 'DEPENDS_ON', {}, 0.95, 'test', $cat]] "
        ":put relation {from_id, to_id, rtype => props, confidence, source, created_at}",
        {"cat": now - 3 * 86400},
    )

    d._now = now
    return d


class TestQueryAt:
    """query_at 测试"""

    def test_current_time(self, db):
        """当前时间查询正常返回"""
        snap = query_at(db, "test:alpha")
        assert snap.exists is True
        assert snap.entity is not None
        assert snap.entity["props"]["name"] == "Alpha"

    def test_entity_not_found(self, db):
        """不存在的实体"""
        snap = query_at(db, "test:nonexistent")
        assert snap.exists is False
        assert "not found" in snap.note

    def test_before_valid_from(self, db):
        """在 valid_from 之前查询 → 不存在"""
        snap = query_at(db, "test:beta", timestamp=db._now - 10 * 86400)
        assert snap.exists is False
        assert "valid_from" in snap.note

    def test_after_valid_from(self, db):
        """在 valid_from 之后查询 → 存在"""
        snap = query_at(db, "test:beta", timestamp=db._now - 2 * 86400)
        assert snap.exists is True

    def test_relations_filtered_by_time(self, db):
        """关系按 created_at 过滤"""
        # 7 天前：alpha 存在但 A→B 关系还没建（3天前才建）
        snap = query_at(db, "test:alpha", timestamp=db._now - 7 * 86400)
        assert snap.exists is True
        assert snap.relations is not None
        assert len(snap.relations) == 0  # 关系 3 天前才有

    def test_relations_after_creation(self, db):
        """关系建立后可见"""
        snap = query_at(db, "test:alpha", timestamp=db._now)
        assert snap.exists is True
        assert len(snap.relations) >= 1

    def test_history_snapshot_early(self, db):
        """gamma 在 15 天前变更前，status = draft"""
        snap = query_at(db, "test:gamma", timestamp=db._now - 18 * 86400)
        assert snap.exists is True
        # 18 天前，还没有 history 事件（第一个是 15 天前），所以保持原 props
        assert snap.entity["props"].get("status") == "draft"

    def test_history_snapshot_mid(self, db):
        """gamma 在 10 天前，status = active（15天前变更）"""
        snap = query_at(db, "test:gamma", timestamp=db._now - 10 * 86400)
        assert snap.exists is True
        assert snap.entity["props"]["status"] == "active"

    def test_history_snapshot_latest(self, db):
        """gamma 现在，status = archived"""
        snap = query_at(db, "test:gamma", timestamp=db._now)
        assert snap.exists is True
        assert snap.entity["props"]["status"] == "archived"
        assert snap.entity["props"]["version"] == "2.0"

    def test_no_relations_when_disabled(self, db):
        """include_relations=False 不查关系"""
        snap = query_at(db, "test:alpha", include_relations=False)
        assert snap.relations is None


class TestEntityTimeline:
    """entity_timeline 测试"""

    def test_gamma_timeline(self, db):
        """gamma 有创建+2次变更=3个事件"""
        events = entity_timeline(db, "test:gamma")
        assert len(events) >= 3
        types = [e["type"] for e in events]
        assert "entity_created" in types
        assert types.count("property_change") >= 2

    def test_timeline_sorted(self, db):
        """事件按时间排序"""
        events = entity_timeline(db, "test:alpha")
        timestamps = [e["timestamp"] for e in events]
        assert timestamps == sorted(timestamps)

    def test_nonexistent_entity(self, db):
        """不存在的实体返回空"""
        events = entity_timeline(db, "test:nobody")
        assert events == []
