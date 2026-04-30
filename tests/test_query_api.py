"""tests/test_query_api.py — M1.4 公共查询 API + 5 类查询用例

每个测试：
  1. 通过 nous.init(":memory:") 初始化全新内存 DB
  2. upsert 测试数据
  3. 通过 nous.query() 模块级 API 执行 Datalog 查询
  4. 断言结果正确
"""
import sys
from pathlib import Path

import pytest
import sys
sys.path.insert(0, 'tests')
from _paths import KG_AVAILABLE

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import nous
from nous.schema import Entity, Relation


# ── Helpers ───────────────────────────────────────────────────────────────────

pytestmark = pytest.mark.skipif(
    not KG_AVAILABLE,
    reason="KG entities dir not present (skipped on bare CI / sanitised public clones)",
)


def _entity(id_: str, etype: str, confidence: float = 1.0, **props) -> Entity:
    return Entity(
        id=id_,
        etype=etype,
        labels=[etype],
        properties=props,
        confidence=confidence,
        source="test",
    )


def _relation(from_id: str, to_id: str, rtype: str) -> Relation:
    return Relation(
        from_id=from_id,
        to_id=to_id,
        rtype=rtype,
        source="test",
    )


@pytest.fixture
def fresh_db():
    """每个测试初始化一个全新内存 DB，返回 NousDB 实例供 upsert 使用。"""
    db = nous.init(":memory:")
    yield db


# ── Test 1: 按类型列出实体 ─────────────────────────────────────────────────────

def test_list_entities_by_type(fresh_db):
    """用例1: 按 etype 过滤，只返回 person 类型实体"""
    db = fresh_db
    db.upsert_entities([
        _entity("entity:person:alice", "person"),
        _entity("entity:person:bob", "person"),
        _entity("entity:project:nous", "project"),   # 不应出现在结果中
    ])

    results = nous.query(
        "?[id, etype] := *entity{id, etype}, etype = 'person'"
    )

    assert len(results) == 2, f"期望 2 个 person，实际: {results}"
    ids = {r["id"] for r in results}
    assert "entity:person:alice" in ids
    assert "entity:person:bob" in ids
    assert "entity:project:nous" not in ids
    for r in results:
        assert r["etype"] == "person"


# ── Test 2: 查找实体的关系 ─────────────────────────────────────────────────────

def test_find_entity_relations(fresh_db):
    """用例2: 按 from_id 查找所有出向关系"""
    db = fresh_db
    db.upsert_entities([
        _entity("entity:person:alice", "person"),
        _entity("entity:project:nous", "project"),
        _entity("entity:project:cozo", "project"),
    ])
    db.upsert_relations([
        _relation("entity:person:alice", "entity:project:nous", "WORKS_ON"),
        _relation("entity:person:alice", "entity:project:cozo", "CONTRIBUTES_TO"),
        _relation("entity:project:nous", "entity:project:cozo", "DEPENDS_ON"),  # 其他源，不应包含
    ])

    from_id = "entity:person:alice"
    results = nous.query(
        f"?[to_id, rtype] := *relation{{from_id, to_id, rtype}}, from_id = '{from_id}'"
    )

    assert len(results) == 2, f"期望 alice 有 2 条关系，实际: {results}"
    rtypes = {r["rtype"] for r in results}
    assert "WORKS_ON" in rtypes
    assert "CONTRIBUTES_TO" in rtypes
    assert "DEPENDS_ON" not in rtypes


# ── Test 3: 统计查询 ──────────────────────────────────────────────────────────

def test_count_query(fresh_db):
    """用例3: count 聚合 — 返回实体总数"""
    db = fresh_db
    db.upsert_entities([
        _entity("entity:person:x1", "person"),
        _entity("entity:person:x2", "person"),
        _entity("entity:concept:x3", "concept"),
    ])

    results = nous.query("?[count(id)] := *entity{id}")

    assert len(results) == 1, f"count 查询应返回 1 行，实际: {results}"
    count_val = list(results[0].values())[0]
    assert count_val == 3, f"期望 count=3，实际: {count_val}"


# ── Test 4: 多条件联合查询 ────────────────────────────────────────────────────

def test_join_query(fresh_db):
    """用例4: entity + relation join — 找所有 WORKS_ON 项目的 person"""
    db = fresh_db
    db.upsert_entities([
        _entity("entity:person:alice", "person"),
        _entity("entity:person:bob", "person"),
        _entity("entity:person:carol", "person"),   # 没有 WORKS_ON 关系
        _entity("entity:project:nous", "project"),
    ])
    db.upsert_relations([
        _relation("entity:person:alice", "entity:project:nous", "WORKS_ON"),
        _relation("entity:person:bob", "entity:project:nous", "WORKS_ON"),
        # carol 没有参与任何项目
    ])

    results = nous.query(
        "?[person_id, project_id] := "
        "*entity{id: person_id, etype: ep}, ep = 'person', "
        "*relation{from_id: person_id, to_id: project_id, rtype: rt}, rt = 'WORKS_ON'"
    )

    assert len(results) == 2, f"期望 alice+bob 各一条，实际: {results}"
    person_ids = {r["person_id"] for r in results}
    assert "entity:person:alice" in person_ids
    assert "entity:person:bob" in person_ids
    assert "entity:person:carol" not in person_ids


# ── Test 5: 属性过滤 ──────────────────────────────────────────────────────────

def test_confidence_filter(fresh_db):
    """用例5: 数值属性过滤 — confidence > 0.9"""
    db = fresh_db
    db.upsert_entities([
        _entity("entity:person:high1", "person", confidence=0.95),
        _entity("entity:person:high2", "person", confidence=1.0),
        _entity("entity:person:low1", "person", confidence=0.5),
        _entity("entity:concept:low2", "concept", confidence=0.3),
    ])

    results = nous.query(
        "?[id] := *entity{id, confidence}, confidence > 0.9"
    )

    assert len(results) == 2, f"期望 2 个高置信度实体，实际: {results}"
    ids = {r["id"] for r in results}
    assert "entity:person:high1" in ids
    assert "entity:person:high2" in ids
    assert "entity:person:low1" not in ids
    assert "entity:concept:low2" not in ids
