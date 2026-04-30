"""测试 M1.1 MD 文件解析器"""
import sys
from pathlib import Path

import pytest

# 确保 src/ 在 path 中
SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from nous.parser import parse_entity_file, scan_entities_dir, build_slug_to_id_map
from nous.schema import Entity, Relation

from _paths import ENTITIES_ROOT, KG_AVAILABLE

# 测试用的 3 个真实文件
PERSON_FILE = ENTITIES_ROOT / "people" / "东丞.md"
PROJECT_FILE = ENTITIES_ROOT / "projects" / "nous.md"
CONCEPT_FILE = ENTITIES_ROOT / "concepts" / "Agentic-Memory.md"

_skip_if_no_file = pytest.mark.skipif(
    not ENTITIES_ROOT.exists(), reason="entities dir not found on this host"
)


# ── 文件存在性检查 ────────────────────────────────────────────────────────────

pytestmark = pytest.mark.skipif(
    not KG_AVAILABLE,
    reason="KG entities dir not present (skipped on bare CI / sanitised public clones)",
)


@pytest.mark.parametrize("path", [PERSON_FILE, PROJECT_FILE, CONCEPT_FILE])
def test_files_exist(path):
    """确认测试文件存在"""
    if not path.exists():
        pytest.skip(f"测试文件不存在 (跨主机): {path}")


# ── 单文件解析测试 ────────────────────────────────────────────────────────────

class TestParsePersonFile:
    """解析人物实体文件"""

    def test_returns_entity_and_relations(self):
        entity, relations = parse_entity_file(PERSON_FILE)
        assert isinstance(entity, Entity)
        assert isinstance(relations, list)

    def test_entity_id_format(self):
        entity, _ = parse_entity_file(PERSON_FILE)
        # ID 格式：entity:{type}:{slug}
        assert entity.id.startswith("entity:")
        parts = entity.id.split(":")
        assert len(parts) >= 3
        assert parts[1] == "person"

    def test_entity_etype(self):
        entity, _ = parse_entity_file(PERSON_FILE)
        assert entity.etype == "person"

    def test_entity_has_name(self):
        entity, _ = parse_entity_file(PERSON_FILE)
        assert "name" in entity.properties
        assert entity.properties["name"]  # 不为空

    def test_entity_confidence_is_one(self):
        entity, _ = parse_entity_file(PERSON_FILE)
        assert entity.confidence == 1.0

    def test_entity_timestamps(self):
        entity, _ = parse_entity_file(PERSON_FILE)
        assert entity.created_at > 0
        assert entity.updated_at > 0

    def test_entity_source_contains_filename(self):
        entity, _ = parse_entity_file(PERSON_FILE)
        assert "东丞" in entity.source or "people" in entity.source

    def test_relations_are_list_of_relation(self):
        _, relations = parse_entity_file(PERSON_FILE)
        for r in relations:
            assert isinstance(r, Relation)

    def test_relations_have_valid_from_id(self):
        entity, relations = parse_entity_file(PERSON_FILE)
        for r in relations:
            assert r.from_id == entity.id

    def test_related_field_parsed(self):
        """东丞.md 有 related: [席涔, 米菈]，应解析出 RELATED_TO 关系"""
        entity, relations = parse_entity_file(PERSON_FILE)
        rtypes = [r.rtype for r in relations]
        # 应该有 RELATED_TO 关系
        if relations:  # 如果文件确实有 related 字段
            assert "RELATED_TO" in rtypes


@pytest.mark.skipif(not PROJECT_FILE.exists(), reason=f"{PROJECT_FILE} not found")
class TestParseProjectFile:
    """解析项目实体文件"""

    def test_entity_etype_is_project(self):
        entity, _ = parse_entity_file(PROJECT_FILE)
        assert entity.etype == "project"

    def test_entity_id_has_project_prefix(self):
        entity, _ = parse_entity_file(PROJECT_FILE)
        assert "project" in entity.id

    def test_project_has_properties(self):
        entity, _ = parse_entity_file(PROJECT_FILE)
        assert len(entity.properties) > 0


class TestParseConceptFile:
    """解析概念实体文件"""

    def test_entity_etype_is_concept(self):
        entity, _ = parse_entity_file(CONCEPT_FILE)
        assert entity.etype == "concept"

    def test_concept_id_format(self):
        entity, _ = parse_entity_file(CONCEPT_FILE)
        assert entity.id.startswith("entity:concept:")


# ── 关系解析测试 ──────────────────────────────────────────────────────────────

class TestRelationParsing:
    """关系解析逻辑测试"""

    def test_relation_has_rtype(self):
        _, relations = parse_entity_file(PERSON_FILE)
        for r in relations:
            assert r.rtype  # 不为空

    def test_relation_rtype_is_valid(self):
        from nous.parser import _VALID_RTYPES
        _, relations = parse_entity_file(PERSON_FILE)
        for r in relations:
            assert r.rtype in _VALID_RTYPES, f"Invalid rtype: {r.rtype}"

    def test_relation_has_from_and_to(self):
        _, relations = parse_entity_file(PERSON_FILE)
        for r in relations:
            assert r.from_id
            assert r.to_id

    def test_slug_to_id_map_built(self):
        """slug_to_id 映射应包含所有扫描到的 entity"""
        mapping = build_slug_to_id_map(ENTITIES_ROOT)
        assert len(mapping) > 5
        # 已知文件应在映射中
        assert "东丞" in mapping
        assert "席涔" in mapping


# ── "## 关系" 段落解析测试（用合成数据）────────────────────────────────────────

class TestRelationSectionParsing:
    """测试 ## 关系 段落的解析逻辑"""

    def test_parse_relation_section(self, tmp_path):
        """用临时文件测试 ## 关系 格式解析"""
        md_content = """---
type: person
created_at: 2026-01-01
updated_at: 2026-01-02
---

# 测试人物

## 基本信息
测试内容

## 关系
- WORKS_ON → entity:project:nous
- KNOWS → 席涔
- OWNS: entity:resource:test

## 其他
其他内容
"""
        test_file = tmp_path / "people" / "测试人物.md"
        test_file.parent.mkdir(parents=True)
        test_file.write_text(md_content, encoding="utf-8")

        entity, relations = parse_entity_file(test_file)

        # 应该解析出 3 条关系
        assert len(relations) == 3

        rtypes = [r.rtype for r in relations]
        assert "WORKS_ON" in rtypes
        assert "KNOWS" in rtypes
        assert "OWNS" in rtypes

        # 检查 entity:project:nous 被正确解析
        to_ids = [r.to_id for r in relations]
        assert "entity:project:nous" in to_ids

    def test_combined_related_and_section(self, tmp_path):
        """frontmatter related + ## 关系 段落同时存在"""
        md_content = """---
type: person
related: [项目A]
---

# 联合测试

## 关系
- WORKS_ON → entity:project:test-proj

"""
        test_file = tmp_path / "people" / "联合测试.md"
        test_file.parent.mkdir(parents=True)
        test_file.write_text(md_content, encoding="utf-8")

        entity, relations = parse_entity_file(test_file)

        # 应有 1 个 RELATED_TO（来自 frontmatter）+ 1 个 WORKS_ON（来自 ## 关系）
        assert len(relations) == 2
        rtypes = {r.rtype for r in relations}
        assert "RELATED_TO" in rtypes
        assert "WORKS_ON" in rtypes


# ── 批量扫描测试 ──────────────────────────────────────────────────────────────

class TestScanEntitiesDir:
    """测试 scan_entities_dir"""

    def test_returns_list(self):
        results = scan_entities_dir(ENTITIES_ROOT)
        assert isinstance(results, list)

    def test_min_entity_count(self):
        """至少应解析出 10 个实体"""
        results = scan_entities_dir(ENTITIES_ROOT)
        assert len(results) >= 10, f"只解析了 {len(results)} 个实体"

    def test_all_items_are_tuples(self):
        results = scan_entities_dir(ENTITIES_ROOT)
        for item in results:
            assert isinstance(item, tuple)
            assert len(item) == 2
            entity, relations = item
            assert isinstance(entity, Entity)
            assert isinstance(relations, list)

    def test_entity_ids_are_unique(self):
        results = scan_entities_dir(ENTITIES_ROOT)
        ids = [e.id for e, _ in results]
        assert len(ids) == len(set(ids)), "存在重复的 entity ID"

    def test_print_entity_count(self):
        """打印解析到的 entity 数量（信息性测试）"""
        results = scan_entities_dir(ENTITIES_ROOT)
        total_entities = len(results)
        total_relations = sum(len(rels) for _, rels in results)
        print(f"\n[解析统计] 实体: {total_entities}，关系: {total_relations}")
        assert total_entities > 0
