"""M7 Integration Tests — end-to-end after_tool_call → KG growth

验证完整链路：
1. NousGatewayHook.after_tool_call() 被调用
2. auto_extract 从 tool 结果中提取实体/关系
3. 实体被写入 NousDB（KG 增长）
4. 提取日志被写入
"""
import asyncio
import json
import time
from pathlib import Path

import pytest

from nous.db import NousDB
from nous.gateway_hook import NousGatewayHook
from nous.schema import Entity, Relation


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path):
    """创建临时 NousDB"""
    db = NousDB(str(tmp_path / "test.db"))
    return db


@pytest.fixture
def extract_log(tmp_path):
    return tmp_path / "extract.jsonl"


def _count_entities(db: NousDB) -> int:
    """查当前 KG 中实体总数"""
    return db.count_entities()


def _count_relations(db: NousDB) -> int:
    """查当前 KG 中关系总数"""
    return db.count_relations()


# ── Mock LLM ──────────────────────────────────────────────────────────────


def make_llm_fn(entity_data: list[dict], relation_data: list[dict] = None):
    """构造一个返回固定提取结果的 async LLM"""
    async def _fn(prompt: str) -> dict:
        return {
            "entities": entity_data,
            "relations": relation_data or [],
        }
    return _fn


# ── Integration Tests ─────────────────────────────────────────────────────


class TestM7Integration:
    """端到端集成：after_tool_call → KG 增长"""

    def test_web_search_extracts_entity(self, db, extract_log):
        """模拟 web_search 结果 → 自动提取 1 个新实体"""
        initial_count = _count_entities(db)

        llm_fn = make_llm_fn([
            {
                "id": "entity:concept:deepseek-v4",
                "type": "concept",
                "name": "DeepSeek V4",
                "props": {"release_date": "2026-03-20", "org": "DeepSeek"},
                "confidence": 0.95,
            }
        ])

        hook = NousGatewayHook(
            db=db,
            llm_fn=llm_fn,
            auto_extract_enabled=True,
            extract_log_path=extract_log,
        )

        result = hook.after_tool_call(
            tool_call={
                "tool_name": "web_search",
                "params": {"query": "DeepSeek V4 release date"},
            },
            result="DeepSeek V4 will launch next week with image+video generation...",
        )

        assert result["extracted"] == 1
        assert _count_entities(db) == initial_count + 1

        # 验证实体内容
        entities = db.find_by_type("concept")
        found = [e for e in entities if "deepseek" in e["id"].lower()]
        assert len(found) == 1
        assert found[0]["source"] == "auto_extract:web_search"

    def test_web_fetch_extracts_entity_and_relation(self, db, extract_log):
        """模拟 web_fetch 结果 → 提取实体 + 关系"""
        llm_fn = make_llm_fn(
            entity_data=[
                {
                    "id": "entity:person:john-doe",
                    "type": "person",
                    "name": "John Doe",
                    "props": {"role": "CTO"},
                    "confidence": 0.9,
                },
                {
                    "id": "entity:project:ai-safety",
                    "type": "project",
                    "name": "AI Safety Initiative",
                    "props": {},
                    "confidence": 0.85,
                },
            ],
            relation_data=[
                {
                    "from": "entity:person:john-doe",
                    "to": "entity:project:ai-safety",
                    "type": "WORKS_ON",
                    "props": {},
                    "confidence": 0.88,
                },
            ],
        )

        hook = NousGatewayHook(
            db=db,
            llm_fn=llm_fn,
            extract_log_path=extract_log,
        )

        result = hook.after_tool_call(
            tool_call={
                "tool_name": "web_fetch",
                "params": {"url": "https://example.com/about"},
            },
            result="John Doe, CTO, leads the AI Safety Initiative...",
        )

        assert result["extracted"] == 3  # 2 entities + 1 relation
        assert _count_entities(db) == 2
        assert _count_relations(db) == 1

    def test_skip_tool_no_extract(self, db, extract_log):
        """read/exec/edit 等低信号工具不提取"""
        llm_fn = make_llm_fn([{"id": "e:x:y", "type": "concept",
                                "name": "Y", "confidence": 0.99}])
        hook = NousGatewayHook(db=db, llm_fn=llm_fn, extract_log_path=extract_log)

        for tool in ["read", "exec", "edit", "write", "process", "memory_search"]:
            result = hook.after_tool_call(
                tool_call={"tool_name": tool, "params": {}},
                result="some result",
            )
            assert result["extracted"] == 0

        assert _count_entities(db) == 0

    def test_low_confidence_filtered(self, db, extract_log):
        """低置信度实体被过滤"""
        llm_fn = make_llm_fn([
            {"id": "entity:concept:maybe", "type": "concept",
             "name": "Maybe", "confidence": 0.3, "props": {}},
        ])
        hook = NousGatewayHook(db=db, llm_fn=llm_fn, extract_log_path=extract_log)

        result = hook.after_tool_call(
            tool_call={"tool_name": "web_search", "params": {"query": "test"}},
            result="vague result",
        )
        assert result["extracted"] == 0
        assert _count_entities(db) == 0

    def test_extract_log_written(self, db, extract_log):
        """提取成功时日志被写入 extract_log.jsonl"""
        llm_fn = make_llm_fn([
            {"id": "entity:event:gtc-2026", "type": "event",
             "name": "GTC 2026", "confidence": 0.9, "props": {}},
        ])
        hook = NousGatewayHook(
            db=db,
            llm_fn=llm_fn,
            extract_log_path=extract_log,
        )

        hook.after_tool_call(
            tool_call={"tool_name": "web_search", "params": {"query": "nvidia gtc"}},
            result="GTC 2026 keynote...",
            session_key="agent:main:user:integration",
        )

        assert extract_log.exists()
        with open(extract_log) as f:
            log_entry = json.loads(f.readline())
        assert log_entry["tool_name"] == "web_search"
        assert log_entry["extracted"] == 1
        assert log_entry["session_key"] == "agent:main:user:integration"

    def test_llm_error_graceful_no_kg_change(self, db, extract_log):
        """LLM 失败时 KG 不变，不崩溃"""
        # 先注入一个已知实体
        db.upsert_entities([
            Entity(id="entity:person:existing", etype="person",
                   labels=["Existing"], source="seed")
        ])
        initial_count = _count_entities(db)

        async def _failing(p):
            raise RuntimeError("API quota exceeded")

        hook = NousGatewayHook(db=db, llm_fn=_failing, extract_log_path=extract_log)

        result = hook.after_tool_call(
            tool_call={"tool_name": "web_search", "params": {}},
            result="some result",
        )

        assert result["extracted"] == 0
        assert _count_entities(db) == initial_count  # 无变更

    def test_before_and_after_full_lifecycle(self, db, tmp_path, extract_log):
        """完整生命周期：before_tool_call → (执行) → after_tool_call"""
        llm_fn = make_llm_fn([
            {"id": "entity:resource:api-endpoint", "type": "resource",
             "name": "OpenAI API", "confidence": 0.9, "props": {"base_url": "https://api.openai.com"}},
        ])

        hook = NousGatewayHook(
            shadow_mode=True,
            db=db,
            llm_fn=llm_fn,
            extract_log_path=extract_log,
            alert_log_path=tmp_path / "alerts.jsonl",
        )

        tool_call = {
            "tool_name": "web_fetch",
            "params": {"url": "https://api.openai.com/docs"},
        }

        # before_tool_call（gate 评估）
        returned = hook.before_tool_call(tool_call, session_key="agent:main:user:lifecycle")
        assert returned == tool_call  # shadow mode，原样返回

        # after_tool_call（KG 提取）
        result = hook.after_tool_call(
            tool_call=tool_call,
            result="OpenAI API documentation...",
            session_key="agent:main:user:lifecycle",
        )
        assert result["extracted"] == 1
        assert _count_entities(db) == 1

    def test_idempotent_upsert(self, db, extract_log):
        """同一实体被多次提取 → KG 只有一份（幂等）"""
        entity_data = [{
            "id": "entity:concept:rag",
            "type": "concept",
            "name": "RAG",
            "props": {},
            "confidence": 0.95,
        }]
        llm_fn = make_llm_fn(entity_data)

        hook = NousGatewayHook(db=db, llm_fn=llm_fn, extract_log_path=extract_log)

        # 调用 3 次
        for _ in range(3):
            hook.after_tool_call(
                tool_call={"tool_name": "web_search", "params": {}},
                result="RAG is a technique...",
            )

        # KG 只有 1 个实体（幂等 upsert）
        assert _count_entities(db) == 1
