"""测试 M1.7 — LLM 本体构建最小闭环 (llm_ontology.py)

mock LLM 输出，验证 propose→confirm→ingest 流程。
"""
import json
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from nous.db import NousDB
from nous.llm_ontology import (
    EntityCandidate,
    Proposal,
    extract_entities_from_text,
    propose_entity,
    confirm_proposal,
    ingest_text,
    _call_llm,
)


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def db():
    _db = NousDB(":memory:")
    yield _db
    _db.close()


MOCK_LLM_OUTPUT = json.dumps({
    "entities": [
        {
            "name": "张三",
            "type": "person",
            "confidence": 0.95,
            "properties": {"role": "AI技术副总监"},
            "relations": [
                {"to": "某科技公司", "type": "WORKS_AT", "confidence": 0.9}
            ]
        },
        {
            "name": "Nous 项目",
            "type": "project",
            "confidence": 0.92,
            "properties": {"status": "M1 进行中"},
            "relations": []
        },
        {
            "name": "知识图谱",
            "type": "concept",
            "confidence": 0.85,
            "properties": {},
            "relations": []
        }
    ]
})

LOW_CONF_LLM_OUTPUT = json.dumps({
    "entities": [
        {
            "name": "未知实体",
            "type": "concept",
            "confidence": 0.6,
            "properties": {},
            "relations": []
        }
    ]
})


# ── 测试 extract_entities_from_text ──────────────────────────────────────


class TestExtractEntitiesFromText:
    def test_returns_list(self):
        with patch("nous.llm_ontology._call_llm", return_value=MOCK_LLM_OUTPUT):
            result = extract_entities_from_text("张三是某科技公司的AI副总监")
        assert isinstance(result, list)
        assert len(result) == 3

    def test_entity_fields(self):
        with patch("nous.llm_ontology._call_llm", return_value=MOCK_LLM_OUTPUT):
            result = extract_entities_from_text("test")
        person = next(e for e in result if e["type"] == "person")
        assert person["name"] == "张三"
        assert person["confidence"] == 0.95
        assert "role" in person["properties"]

    def test_strips_markdown_fence(self):
        fenced = "```json\n" + MOCK_LLM_OUTPUT + "\n```"
        with patch("nous.llm_ontology._call_llm", return_value=fenced):
            result = extract_entities_from_text("test")
        assert len(result) == 3

    def test_invalid_json_raises(self):
        with patch("nous.llm_ontology._call_llm", return_value="not json"):
            with pytest.raises(ValueError, match="非法 JSON"):
                extract_entities_from_text("test")

    def test_empty_entities(self):
        with patch("nous.llm_ontology._call_llm",
                   return_value=json.dumps({"entities": []})):
            result = extract_entities_from_text("empty")
        assert result == []


# ── 测试 propose_entity ───────────────────────────────────────────────────


class TestProposeEntity:
    def test_returns_proposal(self, db):
        entity_dict = {
            "name": "张三",
            "type": "person",
            "confidence": 0.95,
            "properties": {"role": "test"},
        }
        proposal = propose_entity(entity_dict, db=db)
        assert isinstance(proposal, Proposal)
        assert proposal.status == "pending"
        assert proposal.confidence == 0.95
        assert proposal.id.startswith("prop:")

    def test_entity_id_format(self, db):
        entity_dict = {"name": "Nous 项目", "type": "project", "confidence": 0.9}
        proposal = propose_entity(entity_dict, db=db)
        assert proposal.entity is not None
        assert proposal.entity["id"].startswith("entity:project:")

    def test_written_to_db(self, db):
        entity_dict = {"name": "测试实体", "type": "concept", "confidence": 0.8}
        proposal = propose_entity(entity_dict, db=db)
        # 查询 DB 确认已写入
        rows = db._query_with_params(
            "?[id, status] := *proposal{id, status}, id = $pid",
            {"pid": proposal.id},
        )
        assert len(rows) == 1
        assert rows[0]["status"] == "pending"

    def test_without_db(self):
        entity_dict = {"name": "无DB实体", "type": "concept", "confidence": 0.7}
        proposal = propose_entity(entity_dict, db=None)
        assert proposal.id.startswith("prop:")
        assert proposal.entity is not None

    def test_validation_error(self):
        with pytest.raises((ValueError, Exception)):
            # 缺少 name 字段
            propose_entity({"type": "person", "confidence": 0.9}, db=None)


# ── 测试 confirm_proposal ────────────────────────────────────────────────


class TestConfirmProposal:
    def test_pending_to_confirmed(self, db):
        # 先 propose
        entity_dict = {"name": "待确认实体", "type": "concept", "confidence": 0.95}
        proposal = propose_entity(entity_dict, db=db)

        # 然后 confirm
        entity = confirm_proposal(proposal.id, db)

        # 验证 entity 写入 DB
        found = db.find_entity(entity.id)
        assert found is not None
        assert found["etype"] == "concept"

    def test_proposal_status_updated(self, db):
        entity_dict = {"name": "状态测试", "type": "concept", "confidence": 0.9}
        proposal = propose_entity(entity_dict, db=db)
        confirm_proposal(proposal.id, db)

        # 验证状态变为 confirmed
        rows = db._query_with_params(
            "?[status] := *proposal{id, status}, id = $pid",
            {"pid": proposal.id},
        )
        assert rows[0]["status"] == "confirmed"

    def test_nonexistent_proposal_raises(self, db):
        with pytest.raises(ValueError, match="不存在"):
            confirm_proposal("prop:nonexistent", db)

    def test_already_confirmed_raises(self, db):
        entity_dict = {"name": "重复确认", "type": "concept", "confidence": 0.9}
        proposal = propose_entity(entity_dict, db=db)
        confirm_proposal(proposal.id, db)
        with pytest.raises(ValueError, match="confirmed"):
            confirm_proposal(proposal.id, db)


# ── 测试 ingest_text ─────────────────────────────────────────────────────


class TestIngestText:
    def test_full_pipeline_with_db(self, db):
        with patch("nous.llm_ontology._call_llm", return_value=MOCK_LLM_OUTPUT):
            result = ingest_text("张三做 Nous 项目", db=db)

        assert result["extracted"] == 3
        assert result["proposed"] == 3
        # confidence 0.95, 0.92 > 0.9 → 2 auto-confirmed; 0.85 < 0.9 → not
        assert result["confirmed"] == 2
        assert len(result["entities"]) == 2
        assert result["errors"] == []

    def test_low_confidence_not_auto_confirmed(self, db):
        with patch("nous.llm_ontology._call_llm", return_value=LOW_CONF_LLM_OUTPUT):
            result = ingest_text("test", db=db, auto_confirm_threshold=0.9)
        assert result["extracted"] == 1
        assert result["proposed"] == 1
        assert result["confirmed"] == 0

    def test_custom_threshold(self, db):
        with patch("nous.llm_ontology._call_llm", return_value=LOW_CONF_LLM_OUTPUT):
            result = ingest_text("test", db=db, auto_confirm_threshold=0.5)
        assert result["confirmed"] == 1

    def test_without_db(self):
        with patch("nous.llm_ontology._call_llm", return_value=MOCK_LLM_OUTPUT):
            result = ingest_text("test", db=None)
        assert result["extracted"] == 3
        assert result["proposed"] == 3
        assert result["confirmed"] == 2  # 0.95, 0.92 > 0.9

    def test_llm_failure_handled(self):
        with patch("nous.llm_ontology._call_llm", side_effect=RuntimeError("LLM down")):
            result = ingest_text("test", db=None)
        assert result["extracted"] == 0
        assert len(result["errors"]) == 1
        assert "提取失败" in result["errors"][0]
