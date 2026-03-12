"""Tests — M4.2 仪表盘聚合逻辑 (test_dashboard.py)

用 mock 数据验证聚合逻辑。不依赖真实 DB 数据。
"""
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# conftest 已加 src/；这里加 scripts/
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dashboard import aggregate_metrics, print_dashboard
from nous.db import NousDB


# ── 内存 DB fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def mem_db():
    """内存 DB（空）"""
    db = NousDB(":memory:")
    yield db
    db.close()


@pytest.fixture
def populated_db(mem_db):
    """
    填充 mock 数据的内存 DB：
    - 3 条 decision_log（2 allow，1 block）
    - 1 条 fp 记录
    - 2 个 entity
    - 1 条 proposal（pending）
    - 1 条 constraint（T3）
    """
    db = mem_db
    now = time.time()

    # 写入 constraint（T3）
    db.db.run(
        "?[id, rule_body, verdict, priority, enabled, ttl_days, metadata, created_at] "
        "<- [[$id, $rb, $v, $p, $e, $ttl, $meta, $cat]] "
        ":put constraint {id => rule_body, verdict, priority, enabled, ttl_days, metadata, created_at}",
        {
            "id": "T3", "rb": "action_type in irreversible", "v": "confirm",
            "p": 10, "e": True, "ttl": 90, "meta": {}, "cat": now - 100,
        }
    )

    # 写入 decision_log（allow × 2）
    for i in range(2):
        db.db.run(
            "?[ts, session_key, tool_name, facts, gates, latency_us, outcome, proof_trace, schema_version] "
            "<- [[$ts, $sk, $tn, $facts, $gates, $lu, $outcome, $pt, $sv]] "
            ":put decision_log {ts, session_key => tool_name, facts, gates, latency_us, outcome, proof_trace, schema_version}",
            {
                "ts": now - i * 60,
                "sk": f"s-allow-{i}",
                "tn": "web_search",
                "facts": {},
                "gates": [],
                "lu": 1200 + i * 100,   # 1.2ms, 1.3ms
                "outcome": "allow",
                "pt": {},
                "sv": "2.0",
            }
        )

    # 写入 decision_log（block，触发 T3）
    db.db.run(
        "?[ts, session_key, tool_name, facts, gates, latency_us, outcome, proof_trace, schema_version] "
        "<- [[$ts, $sk, $tn, $facts, $gates, $lu, $outcome, $pt, $sv]] "
        ":put decision_log {ts, session_key => tool_name, facts, gates, latency_us, outcome, proof_trace, schema_version}",
        {
            "ts": now - 120,
            "sk": "s-block-1",
            "tn": "exec",
            "facts": {"action_type": "delete_file"},
            "gates": ["T3"],
            "lu": 800,   # 0.8ms
            "outcome": "block",
            "pt": {},
            "sv": "2.0",
        }
    )

    # 写入 fp 记录
    db.db.run(
        "?[ts, session_key, tool_name, facts, gates, latency_us, outcome, proof_trace, schema_version] "
        "<- [[$ts, $sk, $tn, $facts, $gates, $lu, $outcome, $pt, $sv]] "
        ":put decision_log {ts, session_key => tool_name, facts, gates, latency_us, outcome, proof_trace, schema_version}",
        {
            "ts": now - 3600,
            "sk": "s-fp-1",
            "tn": "read",
            "facts": {},
            "gates": ["T3"],
            "lu": 2500,
            "outcome": "fp",
            "pt": {},
            "sv": "2.0",
        }
    )

    # 写入 entity（2 个）
    from nous.schema import Entity
    entities = [
        Entity(id="entity:person:dongcheng", etype="person", labels=["人员"]),
        Entity(id="entity:project:nous", etype="project", labels=["项目"]),
    ]
    db.upsert_entities(entities)

    # 写入 proposal（1 条 pending）
    db.db.run(
        "?[id, constraint_draft, trigger_pattern, confidence, status, created_at, reviewed_at] "
        "<- [[$id, $cd, $tp, $conf, $s, $cat, $rat]] "
        ":put proposal {id => constraint_draft, trigger_pattern, confidence, status, created_at, reviewed_at}",
        {
            "id": "proposal-test-001",
            "cd": {"id": "T5-v2"},
            "tp": "github URL blocked",
            "conf": 0.75,
            "s": "pending",
            "cat": now - 100,
            "rat": 0.0,
        }
    )

    return db


# ── aggregate_metrics 测试 ────────────────────────────────────────────────


def test_aggregate_empty_db(mem_db):
    """空 DB 时聚合不报错，返回合理零值"""
    metrics = aggregate_metrics(mem_db, days=30)
    assert metrics["decisions"]["total"] == 0
    assert metrics["latency"]["sample_count"] == 0
    assert metrics["latency"]["p50_ms"] == 0.0
    assert metrics["latency"]["p99_ms"] == 0.0
    assert metrics["knowledge_graph"]["entity_count"] == 0
    assert metrics["proposals"]["total"] == 0


def test_aggregate_decision_counts(populated_db):
    """决策数按 verdict 正确分组"""
    metrics = aggregate_metrics(populated_db, days=30)
    dec = metrics["decisions"]
    assert dec["total"] == 4  # 2 allow + 1 block + 1 fp
    assert dec["by_verdict"].get("allow", 0) == 2
    assert dec["by_verdict"].get("block", 0) == 1
    assert dec["by_verdict"].get("fp", 0) == 1


def test_aggregate_latency(populated_db):
    """延迟 P50/P99 计算合理"""
    metrics = aggregate_metrics(populated_db, days=30)
    lat = metrics["latency"]
    assert lat["sample_count"] == 4
    assert lat["p50_ms"] >= 0
    assert lat["p99_ms"] >= lat["p50_ms"]


def test_aggregate_fp_fn_rate(populated_db):
    """FP 率计算：1/4 = 25%，FN 率 = 0%"""
    metrics = aggregate_metrics(populated_db, days=30)
    dec = metrics["decisions"]
    assert dec["fp_rate_pct"] == 25.0
    assert dec["fn_rate_pct"] == 0.0


def test_aggregate_entity_count(populated_db):
    """entity 数量正确"""
    metrics = aggregate_metrics(populated_db, days=30)
    assert metrics["knowledge_graph"]["entity_count"] == 2


def test_aggregate_rule_coverage(populated_db):
    """规则覆盖率：T3 触发，总 1 条规则 → 100%"""
    metrics = aggregate_metrics(populated_db, days=30)
    rules = metrics["rules"]
    assert rules["total_enabled"] == 1
    assert rules["triggered"] == 1
    assert rules["coverage_pct"] == 100.0
    assert "T3" in rules["triggered_ids"]


def test_aggregate_proposals(populated_db):
    """提议统计正确"""
    metrics = aggregate_metrics(populated_db, days=30)
    prop = metrics["proposals"]
    assert prop["total"] == 1
    assert prop["pending"] == 1
    assert prop["approved"] == 0
    assert prop["reject_rate_pct"] == 0.0


def test_aggregate_window_days(populated_db):
    """window_days 字段正确"""
    metrics = aggregate_metrics(populated_db, days=7)
    assert metrics["window_days"] == 7


def test_aggregate_generated_at(populated_db):
    """generated_at 字段存在"""
    metrics = aggregate_metrics(populated_db, days=30)
    assert "generated_at" in metrics
    assert len(metrics["generated_at"]) > 0


# ── print_dashboard 测试 ──────────────────────────────────────────────────


def test_print_dashboard_no_crash(populated_db, capsys):
    """print_dashboard 不崩溃，输出包含关键字段"""
    metrics = aggregate_metrics(populated_db, days=30)
    print_dashboard(metrics)
    out = capsys.readouterr().out
    assert "P99" in out or "p99" in out.lower() or "延迟" in out
    assert "决策" in out or "total" in out.lower()


def test_print_dashboard_empty_db(mem_db, capsys):
    """空 DB 时 print_dashboard 不崩溃"""
    metrics = aggregate_metrics(mem_db, days=30)
    print_dashboard(metrics)
    out = capsys.readouterr().out
    assert len(out) > 0


# ── JSON 输出测试 ─────────────────────────────────────────────────────────


def test_aggregate_json_serializable(populated_db):
    """聚合结果可以 JSON 序列化"""
    metrics = aggregate_metrics(populated_db, days=30)
    json_str = json.dumps(metrics, ensure_ascii=False)
    parsed = json.loads(json_str)
    assert parsed["decisions"]["total"] == 4
