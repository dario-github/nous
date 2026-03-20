"""M11.4 Entity 版本化测试

测试覆盖：
1. 新实体写入 - 无 version 记录（entity_version 表为空）
2. 属性变更 - entity_version 中有 1 条记录
3. 多次变更 - 版本号递增（v1, v2, v3）
4. 无变更重复写入 - entity_version 不增加（幂等）
5. get_entity_history() - 返回正确历史列表
6. get_entity_at() - 时间点在 v1 时返回 v1 数据
7. get_entity_at() - 时间点在当前版本返回当前数据
8. changed_fields - 正确记录变更字段名（如 ["props", "confidence"]）
9. labels 变更也被检测
10. metadata 变更也被检测
"""
import sys
import time
from pathlib import Path

import pytest

# 把 src/ 加入 PYTHONPATH
SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from nous.schema import Entity
from nous.db import NousDB


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """每个测试用独立内存 DB"""
    _db = NousDB(":memory:")
    yield _db
    _db.close()


def _make_entity(
    id_: str = "entity:person:alice",
    etype: str = "person",
    name: str = "Alice",
    confidence: float = 1.0,
    labels: list | None = None,
    metadata: dict | None = None,
    updated_at: float | None = None,
) -> Entity:
    """工厂函数：构造测试用 Entity"""
    now = updated_at or time.time()
    return Entity(
        id=id_,
        etype=etype,
        labels=labels if labels is not None else [etype],
        properties={"name": name},
        metadata=metadata if metadata is not None else {},
        confidence=confidence,
        source="test",
        created_at=now,
        updated_at=now,
    )


def _count_versions(db: NousDB, entity_id: str) -> int:
    """辅助：查询 entity_version 表中指定 entity_id 的版本数"""
    rows = db._query_with_params(
        "?[version] := *entity_version{entity_id, version}, entity_id = $eid",
        {"eid": entity_id},
    )
    return len(rows)


# ── 测试 1: 新实体写入不产生 version 记录 ────────────────────────────────────

class TestNewEntityNoVersion:
    def test_new_entity_has_no_version_records(self, db):
        """新实体首次写入时，entity_version 表中不应有任何记录"""
        e = _make_entity()
        db.upsert_entities([e])

        count = _count_versions(db, e.id)
        assert count == 0, f"新实体不应有 version 记录，实际有 {count} 条"

    def test_new_entity_is_queryable(self, db):
        """新实体写入后可以通过 find_entity 查到"""
        e = _make_entity()
        db.upsert_entities([e])

        found = db.find_entity(e.id)
        assert found is not None
        assert found["etype"] == "person"


# ── 测试 2: 属性变更后 entity_version 有 1 条记录 ─────────────────────────────

class TestSingleUpdate:
    def test_props_change_creates_one_version(self, db):
        """修改 props 后，entity_version 应有 1 条记录"""
        # 第一次写入（初始版本）
        e1 = _make_entity(name="Alice")
        db.upsert_entities([e1])

        # 更新 name
        e2 = _make_entity(name="Alice Updated")
        db.upsert_entities([e2])

        count = _count_versions(db, e1.id)
        assert count == 1, f"props 变更应产生 1 条 version 记录，实际有 {count} 条"

    def test_current_entity_reflects_latest_data(self, db):
        """更新后当前实体应反映最新数据"""
        db.upsert_entities([_make_entity(name="Alice")])
        db.upsert_entities([_make_entity(name="Alice Updated")])

        current = db.find_entity("entity:person:alice")
        assert current is not None
        assert current["props"]["name"] == "Alice Updated"


# ── 测试 3: 多次变更，版本号递增 ──────────────────────────────────────────────

class TestMultipleUpdates:
    def test_version_numbers_increment(self, db):
        """多次变更后，版本号应从 v1 递增到 vN"""
        # v0: 初始写入
        db.upsert_entities([_make_entity(name="Alice v0")])
        # 触发 v1
        db.upsert_entities([_make_entity(name="Alice v1")])
        # 触发 v2
        db.upsert_entities([_make_entity(name="Alice v2")])
        # 触发 v3
        db.upsert_entities([_make_entity(name="Alice v3")])

        count = _count_versions(db, "entity:person:alice")
        assert count == 3, f"3 次变更应产生 3 条 version 记录，实际有 {count} 条"

        # 版本号应为 1, 2, 3
        history = db.get_entity_history("entity:person:alice")
        versions = [r["version"] for r in history]
        assert versions == [1, 2, 3], f"版本号应为 [1, 2, 3]，实际为 {versions}"


# ── 测试 4: 无变更重复写入幂等性 ──────────────────────────────────────────────

class TestIdempotentWrite:
    def test_identical_write_no_new_version(self, db):
        """相同数据重复写入不增加 version 记录"""
        e = _make_entity(name="Alice")
        db.upsert_entities([e])  # 初始写入

        # 完全相同的数据，重复写入 3 次
        for _ in range(3):
            db.upsert_entities([_make_entity(name="Alice")])

        count = _count_versions(db, e.id)
        assert count == 0, f"无变更重复写入不应增加 version 记录，实际有 {count} 条"

    def test_change_then_same_no_extra_version(self, db):
        """变更后再重复写入相同数据，不应继续累积版本"""
        db.upsert_entities([_make_entity(name="Alice")])
        db.upsert_entities([_make_entity(name="Alice Updated")])  # 触发 v1

        # 再次写入同样的 "Alice Updated"，不应增加第二条 version 记录
        db.upsert_entities([_make_entity(name="Alice Updated")])
        db.upsert_entities([_make_entity(name="Alice Updated")])

        count = _count_versions(db, "entity:person:alice")
        assert count == 1, f"重复写入同样数据后应仍有 1 条 version 记录，实际有 {count} 条"


# ── 测试 5: get_entity_history() 返回正确历史列表 ────────────────────────────

class TestGetEntityHistory:
    def test_history_returns_correct_list(self, db):
        """get_entity_history 应返回正确的历史快照列表"""
        db.upsert_entities([_make_entity(name="Alice v0")])
        db.upsert_entities([_make_entity(name="Alice v1")])
        db.upsert_entities([_make_entity(name="Alice v2")])

        history = db.get_entity_history("entity:person:alice")
        assert len(history) == 2, f"应有 2 条历史记录，实际有 {len(history)} 条"

        # 第一条版本的 name 应为 v0（第一次被替换掉的）
        assert history[0]["props"]["name"] == "Alice v0"
        # 第二条版本的 name 应为 v1
        assert history[1]["props"]["name"] == "Alice v1"

    def test_history_sorted_by_version_ascending(self, db):
        """get_entity_history 结果应按 version 升序排列"""
        db.upsert_entities([_make_entity(name="A")])
        db.upsert_entities([_make_entity(name="B")])
        db.upsert_entities([_make_entity(name="C")])

        history = db.get_entity_history("entity:person:alice")
        versions = [r["version"] for r in history]
        assert versions == sorted(versions), f"版本号应升序，实际为 {versions}"

    def test_history_empty_for_new_entity(self, db):
        """新实体（未曾更新）的历史应为空列表"""
        db.upsert_entities([_make_entity(name="Alice")])
        history = db.get_entity_history("entity:person:alice")
        assert history == [], f"新实体历史应为空，实际为 {history}"

    def test_history_empty_for_nonexistent_entity(self, db):
        """不存在的实体历史应返回空列表"""
        history = db.get_entity_history("entity:person:nonexistent")
        assert history == []


# ── 测试 6: get_entity_at() 时间点在 v1 时返回 v1 数据 ─────────────────────

class TestGetEntityAtHistoricalVersion:
    def test_entity_at_v1_timestamp_returns_v1(self, db):
        """给定时间戳在 v1 有效期内时，应返回 v1 数据"""
        t0 = time.time()

        # 初始写入（v0，此时 updated_at = t0）
        e0 = _make_entity(name="Alice v0", updated_at=t0)
        db.upsert_entities([e0])

        # 稍等确保时间戳不同
        t1 = t0 + 10  # 模拟 10 秒后更新

        # 更新为 v1（此时旧版本的 valid_to = t1_write_time，valid_from = t0）
        # 注意：_check_and_save_version 记录的 valid_from = existing.updated_at = t0
        # valid_to = now()，但测试环境 now() 不可控，需要用实际写入时间
        # 所以我们检查 valid_from 是否合理，而不是精确匹配
        e1 = _make_entity(name="Alice v1", updated_at=t1)
        db.upsert_entities([e1])

        # 查询 v1 写入之前的时刻（t0 ~ t1 之间），valid_from = t0，valid_to ≈ 写入时刻
        # 直接从历史记录拿到精确的 valid_from / valid_to
        history = db.get_entity_history("entity:person:alice")
        assert len(history) >= 1, "应有至少 1 条历史记录"

        v1_record = history[0]
        vf = v1_record["valid_from"]
        vt = v1_record["valid_to"]

        # 查询 valid_from ~ valid_to 中间的时刻
        mid_ts = (vf + vt) / 2.0
        snapshot = db.get_entity_at("entity:person:alice", mid_ts)

        assert snapshot is not None, "中间时刻应能找到快照"
        assert snapshot["props"]["name"] == "Alice v0", (
            f"中间时刻应返回 v0 数据（Alice v0），实际返回：{snapshot['props']['name']}"
        )


# ── 测试 7: get_entity_at() 时间点在当前版本返回当前数据 ──────────────────────

class TestGetEntityAtCurrentVersion:
    def test_entity_at_future_timestamp_returns_current(self, db):
        """未来时间戳应返回当前版本"""
        db.upsert_entities([_make_entity(name="Alice")])
        db.upsert_entities([_make_entity(name="Alice Updated")])

        # 未来时间戳（远超任何 valid_to）
        future_ts = time.time() + 999999
        snapshot = db.get_entity_at("entity:person:alice", future_ts)

        assert snapshot is not None
        assert snapshot["props"]["name"] == "Alice Updated", (
            f"未来时间戳应返回当前版本，实际：{snapshot['props']['name']}"
        )

    def test_entity_at_returns_none_for_nonexistent(self, db):
        """不存在的实体应返回 None"""
        result = db.get_entity_at("entity:person:ghost", time.time())
        assert result is None


# ── 测试 8: changed_fields 正确记录变更字段名 ─────────────────────────────────

class TestChangedFields:
    def test_props_change_recorded_in_changed_fields(self, db):
        """props 变更时 changed_fields 应包含 'props'"""
        db.upsert_entities([_make_entity(name="Alice")])
        db.upsert_entities([_make_entity(name="Alice New")])

        history = db.get_entity_history("entity:person:alice")
        assert len(history) == 1
        cf = history[0]["changed_fields"]
        assert "props" in cf, f"changed_fields 应包含 'props'，实际为 {cf}"

    def test_confidence_change_recorded_in_changed_fields(self, db):
        """confidence 变更时 changed_fields 应包含 'confidence'"""
        db.upsert_entities([_make_entity(name="Alice", confidence=1.0)])
        db.upsert_entities([_make_entity(name="Alice", confidence=0.5)])

        history = db.get_entity_history("entity:person:alice")
        assert len(history) == 1
        cf = history[0]["changed_fields"]
        assert "confidence" in cf, f"changed_fields 应包含 'confidence'，实际为 {cf}"

    def test_props_and_confidence_both_in_changed_fields(self, db):
        """props 和 confidence 同时变更时，changed_fields 应同时包含两者"""
        db.upsert_entities([_make_entity(name="Alice", confidence=1.0)])
        db.upsert_entities([_make_entity(name="Bob", confidence=0.8)])

        history = db.get_entity_history("entity:person:alice")
        assert len(history) == 1
        cf = history[0]["changed_fields"]
        assert "props" in cf, f"changed_fields 应包含 'props'，实际为 {cf}"
        assert "confidence" in cf, f"changed_fields 应包含 'confidence'，实际为 {cf}"

    def test_labels_change_recorded_in_changed_fields(self, db):
        """labels 变更时 changed_fields 应包含 'labels'"""
        db.upsert_entities([_make_entity(labels=["person"])])
        db.upsert_entities([_make_entity(labels=["person", "vip"])])

        history = db.get_entity_history("entity:person:alice")
        assert len(history) == 1
        cf = history[0]["changed_fields"]
        assert "labels" in cf, f"changed_fields 应包含 'labels'，实际为 {cf}"

    def test_metadata_change_recorded_in_changed_fields(self, db):
        """metadata 变更时 changed_fields 应包含 'metadata'"""
        db.upsert_entities([_make_entity(metadata={})])
        db.upsert_entities([_make_entity(metadata={"tag": "important"})])

        history = db.get_entity_history("entity:person:alice")
        assert len(history) == 1
        cf = history[0]["changed_fields"]
        assert "metadata" in cf, f"changed_fields 应包含 'metadata'，实际为 {cf}"
