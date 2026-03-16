"""tests/test_auto_extract.py — M7.1 auto_extract 模块测试（P0 修复后）"""
import asyncio
import json
from pathlib import Path
import pytest

from nous.auto_extract import (
    SKIP_TOOLS,
    ENTITY_HIGH_CONFIDENCE,
    ENTITY_LOW_CONFIDENCE,
    ENTITY_CONFIDENCE_THRESHOLD,
    RELATION_CONFIDENCE_THRESHOLD,
    extract_from_tool_call,
    parse_llm_json,
)


# ── helpers ──────────────────────────────────────────────────────────────────

class MockDB:
    def __init__(self):
        self.entities = []
        self.relations = []

    def upsert_entity(self, entity):
        self.entities.append(entity)

    def upsert_relation(self, relation):
        self.relations.append(relation)

    def upsert_entities(self, entities):
        self.entities.extend(entities)

    def upsert_relations(self, relations):
        self.relations.extend(relations)


def make_llm_fn(response: dict):
    """返回一个总是返回 response 的 mock LLM 函数"""
    async def _fn(prompt: str) -> dict:
        return response
    return _fn


def run(coro):
    """同步运行 coroutine"""
    return asyncio.run(coro)


# ── parse_llm_json ────────────────────────────────────────────────────────────

def test_parse_llm_json_plain():
    raw = '{"entities": [], "relations": []}'
    result = parse_llm_json(raw)
    assert result == {"entities": [], "relations": []}


def test_parse_llm_json_with_codeblock():
    raw = '```json\n{"entities": [{"id": "e1"}], "relations": []}\n```'
    result = parse_llm_json(raw)
    assert result["entities"] == [{"id": "e1"}]


def test_parse_llm_json_invalid():
    raw = "not json at all"
    result = parse_llm_json(raw)
    assert result == {"entities": [], "relations": []}


# ── SKIP_TOOLS ────────────────────────────────────────────────────────────────

def test_skip_tools_contains_read():
    assert "read" in SKIP_TOOLS
    assert "process" in SKIP_TOOLS
    assert "exec" in SKIP_TOOLS


def test_skip_tool_returns_zero():
    db = MockDB()
    called = []

    async def _llm(p):
        called.append(p)
        return {"entities": [], "relations": []}

    result = run(extract_from_tool_call("read", {}, "some content", db, _llm))
    assert result["extracted"] == 0
    assert result["proposed"] == 0
    assert len(called) == 0  # LLM should NOT be called for skip tools


# ── confidence filtering (P0-2: dual-track) ──────────────────────────────────

def test_low_confidence_entity_proposed(tmp_path):
    """置信度 0.5~0.8 → 进 proposal 队列，不直接写 KG"""
    db = MockDB()
    llm_resp = {
        "entities": [
            {"id": "entity:person:foo", "type": "person", "name": "Foo",
             "props": {}, "confidence": 0.65},  # between LOW(0.5) and HIGH(0.8)
        ],
        "relations": [],
    }
    result = run(extract_from_tool_call(
        "web_search", {"query": "test"}, "result", db, make_llm_fn(llm_resp),
        proposal_dir=tmp_path,
    ))
    assert result["extracted"] == 0
    assert result["proposed"] == 1
    assert len(db.entities) == 0

    # 验证 proposal 文件写入
    proposal_file = tmp_path / "pending.jsonl"
    assert proposal_file.exists()
    with open(proposal_file) as f:
        entry = json.loads(f.readline())
    assert entry["kind"] == "entity"
    assert entry["status"] == "pending"
    assert entry["confidence"] == 0.65


def test_very_low_confidence_discarded():
    """置信度 < 0.5 → 丢弃"""
    db = MockDB()
    llm_resp = {
        "entities": [
            {"id": "entity:person:ghost", "type": "person", "name": "Ghost",
             "props": {}, "confidence": 0.3},
        ],
        "relations": [],
    }
    result = run(extract_from_tool_call(
        "web_search", {"query": "test"}, "result", db, make_llm_fn(llm_resp)
    ))
    assert result["extracted"] == 0
    assert result["proposed"] == 0
    assert len(db.entities) == 0


def test_high_confidence_entity_upserted():
    db = MockDB()
    llm_resp = {
        "entities": [
            {"id": "entity:person:bar", "type": "person", "name": "Bar",
             "props": {}, "confidence": 0.9},
        ],
        "relations": [],
    }
    result = run(extract_from_tool_call(
        "web_search", {"query": "test"}, "result", db, make_llm_fn(llm_resp)
    ))
    assert result["extracted"] == 1
    assert len(db.entities) == 1
    assert db.entities[0].id == "entity:person:bar"


def test_relation_upserted():
    db = MockDB()
    llm_resp = {
        "entities": [],
        "relations": [
            {"from": "entity:person:alice", "to": "entity:project:kg",
             "type": "WORKS_ON", "props": {}, "confidence": 0.95},
        ],
    }
    result = run(extract_from_tool_call(
        "web_search", {}, "result", db, make_llm_fn(llm_resp)
    ))
    assert result["extracted"] == 1
    assert db.relations[0].rtype == "WORKS_ON"


def test_llm_error_returns_zero():
    db = MockDB()

    async def _failing_llm(p):
        raise RuntimeError("API error")

    result = run(extract_from_tool_call(
        "web_search", {}, "result", db, _failing_llm
    ))
    assert result["extracted"] == 0
    assert result["proposed"] == 0
    assert len(db.entities) == 0


def test_mixed_confidence_dual_track(tmp_path):
    """高置信写 KG，低置信进 proposal，极低丢弃"""
    db = MockDB()
    llm_resp = {
        "entities": [
            {"id": "entity:person:high", "confidence": 0.9, "type": "person", "name": "H", "props": {}},
            {"id": "entity:person:mid", "confidence": 0.65, "type": "person", "name": "M", "props": {}},
            {"id": "entity:person:low", "confidence": 0.3, "type": "person", "name": "L", "props": {}},
        ],
        "relations": [
            {"from": "entity:person:high", "to": "entity:project:x",
             "type": "WORKS_ON", "confidence": 0.85, "props": {}},
            {"from": "entity:person:high", "to": "entity:project:y",
             "type": "WORKS_ON", "confidence": 0.6, "props": {}},  # → proposal
            {"from": "entity:person:high", "to": "entity:project:z",
             "type": "WORKS_ON", "confidence": 0.2, "props": {}},  # → discard
        ],
    }
    result = run(extract_from_tool_call(
        "message", {}, "result", db, make_llm_fn(llm_resp),
        proposal_dir=tmp_path,
    ))
    assert result["extracted"] == 2  # 1 high entity + 1 high relation
    assert result["proposed"] == 2  # 1 mid entity + 1 mid relation
    assert len(db.entities) == 1
    assert len(db.relations) == 1

    # 验证 proposal
    proposal_file = tmp_path / "pending.jsonl"
    assert proposal_file.exists()
    proposals = [json.loads(l) for l in proposal_file.read_text().splitlines()]
    assert len(proposals) == 2


# ── P0-3: prompt injection resistance ────────────────────────────────────────

def test_prompt_contains_untrusted_wrapper():
    """验证 prompt 模板包含 untrusted-content 防注入标记"""
    from nous.auto_extract import EXTRACT_PROMPT
    assert "<untrusted_data>" in EXTRACT_PROMPT
    assert "</untrusted_data>" in EXTRACT_PROMPT
    assert "注入攻击" in EXTRACT_PROMPT or "injection" in EXTRACT_PROMPT.lower()
