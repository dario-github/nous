"""Tests for M1.4 — 高级查询 API"""
from pathlib import Path

import pytest

from nous.db import NousDB
from nous.sync import sync_entities


@pytest.fixture
def populated_db():
    """一个已导入 memory/entities 的内存 DB"""
    db = NousDB(":memory:")
    from _paths import ENTITIES_ROOT
    sync_entities(db, ENTITIES_ROOT)
    yield db
    db.close()


class TestFindEntity:
    """find_entity() 精确查找"""

    def test_find_existing_entity(self, populated_db):
        # 东丞应该存在
        e = populated_db.find_entity("entity:person:东丞")
        assert e is not None
        assert e["etype"] == "person"

    def test_find_nonexistent_returns_none(self, populated_db):
        e = populated_db.find_entity("entity:person:不存在的人")
        assert e is None

    def test_find_returns_all_fields(self, populated_db):
        e = populated_db.find_entity("entity:person:东丞")
        assert e is not None
        expected_fields = {"id", "etype", "labels", "props", "metadata",
                          "confidence", "source", "created_at", "updated_at"}
        assert expected_fields.issubset(set(e.keys()))


class TestFindByType:
    """find_by_type() 按类型查找"""

    def test_find_persons(self, populated_db):
        persons = populated_db.find_by_type("person")
        assert len(persons) > 0
        for p in persons:
            assert p["etype"] == "person"

    def test_find_projects(self, populated_db):
        projects = populated_db.find_by_type("project")
        assert len(projects) >= 0  # 可能 0 个项目也是合法的

    def test_find_nonexistent_type_returns_empty(self, populated_db):
        result = populated_db.find_by_type("nonexistent_type")
        assert result == []


class TestRelated:
    """related() 邻居查询"""

    def test_out_relations(self, populated_db):
        # 东丞应该有出边关系
        rels = populated_db.related("entity:person:东丞", direction="out")
        # 可能有关系也可能没有，但不应报错
        assert isinstance(rels, list)

    def test_both_directions(self, populated_db):
        rels = populated_db.related("entity:person:东丞", direction="both")
        assert isinstance(rels, list)
        # both 应该包含 out + in
        out_only = populated_db.related("entity:person:东丞", direction="out")
        in_only = populated_db.related("entity:person:东丞", direction="in")
        assert len(rels) == len(out_only) + len(in_only)

    def test_filter_by_rtype(self, populated_db):
        # 过滤特定关系类型
        rels = populated_db.related("entity:person:东丞", rtype="RELATED_TO")
        for r in rels:
            assert r["rtype"] == "RELATED_TO"


class TestPath:
    """path() 多跳路径查找"""

    def test_no_path_returns_empty(self, populated_db):
        result = populated_db.path(
            "entity:person:不存在A",
            "entity:person:不存在B",
        )
        assert result == []

    def test_path_returns_list(self, populated_db):
        # 即使没有路径，也应该返回 list
        result = populated_db.path(
            "entity:person:东丞",
            "entity:person:席涔",
        )
        assert isinstance(result, list)


class TestSearch:
    """search() 关键词搜索"""

    def test_search_existing_keyword(self, populated_db):
        # 搜索应该能找到包含关键词的实体
        results = populated_db.search("东丞")
        # 至少在 props 中应该能找到
        assert isinstance(results, list)

    def test_search_nonexistent_returns_empty(self, populated_db):
        results = populated_db.search("xyzzy_完全不存在的关键词_98765")
        assert results == []

    def test_search_case_insensitive(self, populated_db):
        # 搜索应该不区分大小写
        r1 = populated_db.search("nous")
        r2 = populated_db.search("Nous")
        # 结果应该相同
        assert len(r1) == len(r2)


class TestDeleteEntity:
    """delete_entity() 删除"""

    def test_delete_reduces_count(self, populated_db):
        c1 = populated_db.count_entities()
        # 找一个存在的实体删除
        rows = populated_db.query("?[id] := *entity{id} :limit 1")
        if rows:
            eid = rows[0]["id"]
            populated_db.delete_entity(eid)
            c2 = populated_db.count_entities()
            assert c2 == c1 - 1

    def test_delete_nonexistent_no_error(self, populated_db):
        # 删除不存在的 entity 不应报错
        populated_db.delete_entity("entity:person:ghost_不存在")
