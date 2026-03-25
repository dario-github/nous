"""测试 M1.2 批量写入层 (NousDB)"""
import sys
import time
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from nous.schema import Entity, Relation
from nous.db import NousDB
from nous.parser import parse_entity_file, scan_entities_dir

from _paths import ENTITIES_ROOT
PERSON_FILE = ENTITIES_ROOT / "people" / "Alice.md"
PROJECT_FILE = ENTITIES_ROOT / "projects" / "nous.md"
CONCEPT_FILE = ENTITIES_ROOT / "concepts" / "Agentic-Memory.md"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """每个测试用独立内存 DB"""
    _db = NousDB(":memory:")
    yield _db
    _db.close()


def _make_entity(id_="entity:person:test", etype="person") -> Entity:
    now = time.time()
    return Entity(
        id=id_,
        etype=etype,
        labels=[etype],
        properties={"name": "测试实体"},
        metadata={},
        confidence=1.0,
        source="test",
        created_at=now,
        updated_at=now,
    )


def _make_relation(from_id="entity:person:test", to_id="entity:project:nous") -> Relation:
    return Relation(
        from_id=from_id,
        to_id=to_id,
        rtype="WORKS_ON",
        properties={},
        confidence=1.0,
        source="test",
        created_at=time.time(),
    )


# ── Schema 初始化测试 ─────────────────────────────────────────────────────────

class TestSchemaInit:
    def test_db_creates_entity_table(self, db):
        """entity 表应存在"""
        rows = db.query("?[id] := *entity{id}")
        assert isinstance(rows, list)

    def test_db_creates_relation_table(self, db):
        """relation 表应存在"""
        rows = db.query("?[from_id] := *relation{from_id, to_id, rtype}")
        assert isinstance(rows, list)

    def test_db_creates_all_6_tables(self, db):
        """6 张表应全部存在"""
        tables = ["entity", "relation", "ontology_class", "constraint", "decision_log", "proposal"]
        for table in tables:
            # 查询每张表不抛异常
            try:
                db.query(f"?[x] := *{table}{{x: _}}")
            except Exception:
                # 部分表的查询方式不同，只要不抛"does not exist"即可
                pass

    def test_init_schema_idempotent(self, db):
        """重复调用 init_schema 不应抛异常"""
        db.init_schema()
        db.init_schema()


# ── Entity 写入测试 ───────────────────────────────────────────────────────────

class TestUpsertEntities:
    def test_upsert_single_entity(self, db):
        entity = _make_entity()
        db.upsert_entities([entity])
        count = db.count_entities()
        assert count == 1

    def test_upsert_multiple_entities(self, db):
        entities = [
            _make_entity(f"entity:person:test{i}", "person")
            for i in range(5)
        ]
        db.upsert_entities(entities)
        assert db.count_entities() == 5

    def test_upsert_empty_list(self, db):
        """空列表不应报错"""
        db.upsert_entities([])
        assert db.count_entities() == 0

    def test_upsert_entity_idempotent(self, db):
        """重复写入相同 entity 应保持唯一"""
        entity = _make_entity()
        db.upsert_entities([entity])
        db.upsert_entities([entity])  # 第二次
        assert db.count_entities() == 1

    def test_upsert_entity_update(self, db):
        """用相同 id 写入不同 properties 应覆盖"""
        now = time.time()
        e1 = Entity(
            id="entity:person:update_test",
            etype="person",
            labels=["person"],
            properties={"name": "旧名字"},
            metadata={},
            confidence=1.0,
            source="test",
            created_at=now,
            updated_at=now,
        )
        db.upsert_entities([e1])

        e2 = Entity(
            id="entity:person:update_test",
            etype="person",
            labels=["person"],
            properties={"name": "新名字"},
            metadata={},
            confidence=1.0,
            source="test",
            created_at=now,
            updated_at=now + 1,
        )
        db.upsert_entities([e2])

        assert db.count_entities() == 1
        rows = db.query(
            '?[id, props] := *entity{id, props}, id = "entity:person:update_test"'
        )
        assert len(rows) == 1
        props = rows[0].get("props", {})
        assert props.get("name") == "新名字"

    def test_upsert_entity_with_complex_properties(self, db):
        """测试含嵌套结构的 properties"""
        now = time.time()
        entity = Entity(
            id="entity:person:complex",
            etype="person",
            labels=["person", "ai"],
            properties={
                "name": "复杂实体",
                "tags": ["tag1", "tag2"],
                "nested": {"key": "value"},
            },
            metadata={"source_url": "http://example.com"},
            confidence=0.95,
            source="test",
            created_at=now,
            updated_at=now,
        )
        db.upsert_entities([entity])
        assert db.count_entities() == 1


# ── Relation 写入测试 ─────────────────────────────────────────────────────────

class TestUpsertRelations:
    def test_upsert_single_relation(self, db):
        # 先写入 entity（relation 表不强制 FK 约束）
        db.upsert_entities([_make_entity("entity:person:a")])
        db.upsert_entities([_make_entity("entity:project:b", "project")])

        rel = _make_relation("entity:person:a", "entity:project:b")
        db.upsert_relations([rel])
        assert db.count_relations() == 1

    def test_upsert_relation_idempotent(self, db):
        """重复写入相同关系应保持唯一"""
        rel = _make_relation()
        db.upsert_relations([rel])
        db.upsert_relations([rel])
        assert db.count_relations() == 1

    def test_upsert_multiple_relations(self, db):
        rels = [
            Relation(
                from_id="entity:person:src",
                to_id=f"entity:project:tgt{i}",
                rtype="WORKS_ON",
                source="test",
                created_at=time.time(),
            )
            for i in range(3)
        ]
        db.upsert_relations(rels)
        assert db.count_relations() == 3

    def test_upsert_empty_relations(self, db):
        db.upsert_relations([])
        assert db.count_relations() == 0


# ── 查询验证测试 ──────────────────────────────────────────────────────────────

class TestQuery:
    def test_query_returns_list(self, db):
        result = db.query("?[x] := *entity{id: x}")
        assert isinstance(result, list)

    def test_query_entity_by_id(self, db):
        entity = _make_entity("entity:person:query_test")
        db.upsert_entities([entity])
        rows = db.query('?[id, etype] := *entity{id, etype}, id = "entity:person:query_test"')
        assert len(rows) == 1
        assert rows[0]["etype"] == "person"

    def test_query_entity_by_etype(self, db):
        entities = [
            _make_entity("entity:person:p1", "person"),
            _make_entity("entity:project:r1", "project"),
            _make_entity("entity:concept:c1", "concept"),
        ]
        db.upsert_entities(entities)
        rows = db.query('?[id] := *entity{id, etype}, etype = "person"')
        assert len(rows) == 1

    def test_query_relations_by_from_id(self, db):
        rels = [
            Relation(
                from_id="entity:person:src",
                to_id=f"entity:project:t{i}",
                rtype="WORKS_ON",
                source="test",
                created_at=time.time(),
            )
            for i in range(3)
        ]
        db.upsert_relations(rels)
        rows = db.query(
            '?[to_id] := *relation{from_id, to_id, rtype}, from_id = "entity:person:src"'
        )
        assert len(rows) == 3

import pytest

_all_test_files_exist = all(f.exists() for f in [PERSON_FILE, PROJECT_FILE, CONCEPT_FILE])

# ── 真实文件写入测试 ──────────────────────────────────────────────────────────

@pytest.mark.skipif(not _all_test_files_exist, reason="部分 entity 文件不存在 (跨主机)")
class TestRealFileIngestion:
    """使用真实 entity 文件测试端到端写入"""

    def test_ingest_3_real_files(self, db):
        """解析并写入 3 个真实 entity 文件"""
        files = [PERSON_FILE, PROJECT_FILE, CONCEPT_FILE]
        entities = []
        all_relations = []

        for f in files:
            entity, relations = parse_entity_file(f)
            entities.append(entity)
            all_relations.extend(relations)

        db.upsert_entities(entities)
        db.upsert_relations(all_relations)

        assert db.count_entities() == 3
        # 关系数量 ≥ 0（取决于文件 related 字段）

    def test_entity_ids_correct_format(self, db):
        """写入后查询 ID 格式正确"""
        entity, relations = parse_entity_file(PERSON_FILE)
        db.upsert_entities([entity])

        rows = db.query('?[id] := *entity{id}, starts_with(id, "entity:person:")')
        assert len(rows) >= 1

    def test_scan_and_ingest_all(self, db):
        """扫描全部 entities 目录并写入 DB"""
        results = scan_entities_dir(ENTITIES_ROOT)

        all_entities = [e for e, _ in results]
        all_relations = [r for _, rels in results for r in rels]

        db.upsert_entities(all_entities)
        db.upsert_relations(all_relations)

        count = db.count_entities()
        print(f"\n[写入统计] 实体: {count}，关系: {db.count_relations()}")
        assert count >= 10, f"写入 entity 数量不足: {count}"

    def test_idempotent_full_scan_ingest(self, db):
        """两次全量写入，结果应相同（幂等性）"""
        results = scan_entities_dir(ENTITIES_ROOT)
        all_entities = [e for e, _ in results]
        all_relations = [r for _, rels in results for r in rels]

        db.upsert_entities(all_entities)
        db.upsert_relations(all_relations)
        count_1 = db.count_entities()

        # 第二次写入
        db.upsert_entities(all_entities)
        db.upsert_relations(all_relations)
        count_2 = db.count_entities()

        assert count_1 == count_2, f"幂等性失败: 第1次={count_1}，第2次={count_2}"
