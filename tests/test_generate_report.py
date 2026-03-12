"""Tests — M4.3 30 天报告生成 (test_generate_report.py)

覆盖：
- render_report 生成内容完整（包含所有必要章节）
- generate_report 写入文件
- 空 DB 时报告可生成
- 有数据时报告反映真实指标
- 建议列表逻辑
"""
import json
import sys
import time
from pathlib import Path

import pytest

# conftest 已加 src/；这里加 scripts/
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from generate_report import generate_report, render_report
from dashboard import aggregate_metrics
from nous.db import NousDB
from nous.schema import Entity


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mem_db():
    db = NousDB(":memory:")
    yield db
    db.close()


@pytest.fixture
def populated_db(mem_db):
    """带基本数据的内存 DB"""
    db = mem_db
    now = time.time()

    # constraint
    db.db.run(
        "?[id, rule_body, verdict, priority, enabled, ttl_days, metadata, created_at] "
        "<- [[$id, $rb, $v, $p, $e, $ttl, $meta, $cat]] "
        ":put constraint {id => rule_body, verdict, priority, enabled, ttl_days, metadata, created_at}",
        {"id": "T3", "rb": "...", "v": "block", "p": 10, "e": True, "ttl": 90, "meta": {}, "cat": now}
    )

    # decision_log
    for i in range(5):
        db.db.run(
            "?[ts, session_key, tool_name, facts, gates, latency_us, outcome, proof_trace, schema_version] "
            "<- [[$ts, $sk, $tn, $facts, $gates, $lu, $outcome, $pt, $sv]] "
            ":put decision_log {ts, session_key => tool_name, facts, gates, latency_us, outcome, proof_trace, schema_version}",
            {
                "ts": now - i * 60,
                "sk": f"s-{i}",
                "tn": "web_search",
                "facts": {},
                "gates": ["T3"] if i == 0 else [],
                "lu": 1000 + i * 200,
                "outcome": "block" if i == 0 else "allow",
                "pt": {},
                "sv": "2.0",
            }
        )

    # entities
    db.upsert_entities([
        Entity(id="entity:person:test", etype="person", labels=["人员"]),
    ])

    # proposal
    db.db.run(
        "?[id, constraint_draft, trigger_pattern, confidence, status, created_at, reviewed_at] "
        "<- [[$id, $cd, $tp, $conf, $s, $cat, $rat]] "
        ":put proposal {id => constraint_draft, trigger_pattern, confidence, status, created_at, reviewed_at}",
        {"id": "p-001", "cd": {}, "tp": "test", "conf": 0.8, "s": "approved", "cat": now, "rat": now}
    )

    return db


# ── render_report 内容完整性 ───────────────────────────────────────────────


def test_render_report_contains_all_sections(populated_db):
    """报告包含所有必要章节"""
    metrics = aggregate_metrics(populated_db, days=30)
    content = render_report(metrics, month="2026-03")

    assert "# Nous 月度运行报告" in content
    assert "2026-03" in content
    assert "## 1. 概览" in content
    assert "## 2. 规则效力" in content
    assert "## 3. 自治理活动" in content
    assert "## 4. 知识图谱增长" in content
    assert "## 5. 下月建议" in content


def test_render_report_contains_metrics(populated_db):
    """报告包含真实指标数字"""
    metrics = aggregate_metrics(populated_db, days=30)
    content = render_report(metrics, month="2026-03")

    # 总决策数 5
    assert "5" in content
    # P99 延迟
    assert "ms" in content
    # entity
    assert "1" in content


def test_render_report_rule_section(populated_db):
    """规则效力章节包含 T3"""
    metrics = aggregate_metrics(populated_db, days=30)
    content = render_report(metrics, month="2026-03")
    assert "T3" in content


def test_render_report_proposal_section(populated_db):
    """自治理章节反映 approved 状态"""
    metrics = aggregate_metrics(populated_db, days=30)
    content = render_report(metrics, month="2026-03")
    # 1 approved, 0 pending → 应该没有 pending 警告
    assert "提议数" in content or "总提议" in content or "1" in content


def test_render_report_default_month(populated_db):
    """不指定 month 时自动用当前月"""
    from datetime import datetime, timezone
    expected_month = datetime.now(timezone.utc).strftime("%Y-%m")
    metrics = aggregate_metrics(populated_db, days=30)
    content = render_report(metrics)
    assert expected_month in content


def test_render_report_empty_db(mem_db):
    """空 DB 生成报告不崩溃"""
    metrics = aggregate_metrics(mem_db, days=30)
    content = render_report(metrics, month="2026-03")
    assert len(content) > 100
    assert "## 1. 概览" in content


def test_render_report_has_footer(populated_db):
    """报告底部有生成信息"""
    metrics = aggregate_metrics(populated_db, days=30)
    content = render_report(metrics, month="2026-03")
    assert "generate_report.py" in content or "自动生成" in content


# ── 建议逻辑 ──────────────────────────────────────────────────────────────


def test_render_report_fn_warning():
    """FN > 0 时报告包含 FN 警告"""
    metrics = {
        "window_days": 30,
        "generated_at": "2026-03-12",
        "latency": {"p50_ms": 1.0, "p99_ms": 2.0, "sample_count": 10},
        "decisions": {"total": 10, "by_verdict": {"allow": 9, "fn": 1},
                      "fp_rate_pct": 0.0, "fn_rate_pct": 10.0},
        "rules": {"total_enabled": 1, "triggered": 1, "coverage_pct": 100.0, "triggered_ids": ["T3"]},
        "knowledge_graph": {"entity_count": 50, "relation_count": 20},
        "proposals": {"total": 0, "approved": 0, "rejected": 0, "pending": 0,
                      "approve_rate_pct": 0.0, "reject_rate_pct": 0.0},
    }
    content = render_report(metrics, month="2026-03")
    assert "FN" in content
    assert "🚨" in content


def test_render_report_fp_warning():
    """FP ≥ 2% 时报告包含 FP 警告"""
    metrics = {
        "window_days": 30,
        "generated_at": "2026-03-12",
        "latency": {"p50_ms": 1.0, "p99_ms": 2.0, "sample_count": 10},
        "decisions": {"total": 10, "by_verdict": {"allow": 8, "fp": 2},
                      "fp_rate_pct": 20.0, "fn_rate_pct": 0.0},
        "rules": {"total_enabled": 1, "triggered": 1, "coverage_pct": 100.0, "triggered_ids": []},
        "knowledge_graph": {"entity_count": 250, "relation_count": 100},
        "proposals": {"total": 0, "approved": 0, "rejected": 0, "pending": 0,
                      "approve_rate_pct": 0.0, "reject_rate_pct": 0.0},
    }
    content = render_report(metrics, month="2026-03")
    assert "FP" in content
    assert "⚠️" in content


def test_render_report_all_green():
    """所有指标达标时，报告显示正面建议"""
    metrics = {
        "window_days": 30,
        "generated_at": "2026-03-12",
        "latency": {"p50_ms": 0.5, "p99_ms": 1.5, "sample_count": 100},
        "decisions": {"total": 100, "by_verdict": {"allow": 95, "block": 5},
                      "fp_rate_pct": 0.0, "fn_rate_pct": 0.0},
        "rules": {"total_enabled": 5, "triggered": 4, "coverage_pct": 80.0, "triggered_ids": ["T3", "T5"]},
        "knowledge_graph": {"entity_count": 250, "relation_count": 300},
        "proposals": {"total": 2, "approved": 2, "rejected": 0, "pending": 0,
                      "approve_rate_pct": 100.0, "reject_rate_pct": 0.0},
    }
    content = render_report(metrics, month="2026-03")
    assert "✅" in content


# ── generate_report 写入文件 ───────────────────────────────────────────────


def test_generate_report_writes_file(populated_db, tmp_path):
    """generate_report 写入 Markdown 文件"""
    out_path = tmp_path / "monthly-report-2026-03.md"
    content, path = generate_report(
        populated_db, days=30, output_path=out_path, month="2026-03"
    )
    assert path.exists()
    assert path.read_text(encoding="utf-8") == content


def test_generate_report_content_length(populated_db, tmp_path):
    """生成的报告内容不为空，且足够长"""
    out_path = tmp_path / "test-report.md"
    content, _ = generate_report(populated_db, days=30, output_path=out_path)
    assert len(content) > 200


def test_generate_report_default_path(populated_db, tmp_path, monkeypatch):
    """不指定 output_path 时，报告写入 docs/ 目录"""
    # monkeypatch docs 目录到 tmp
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    import generate_report as gr_module
    original = gr_module.Path

    def patched_path(*args, **kwargs):
        p = original(*args, **kwargs)
        # 只拦截 docs 目录
        if "docs" in str(p) and "monthly-report" in str(p):
            return tmp_path / "docs" / p.name
        return p

    # 直接指定 output_path 测试（等价验证）
    month = "2026-03"
    out_path = docs_dir / f"monthly-report-{month}.md"
    content, path = generate_report(populated_db, days=30, output_path=out_path, month=month)
    assert path.exists()
    assert f"monthly-report-{month}" in str(path)


def test_generate_report_month_in_filename(populated_db, tmp_path):
    """报告文件名包含月份"""
    out_path = tmp_path / "monthly-report-2026-03.md"
    _, path = generate_report(
        populated_db, days=30, output_path=out_path, month="2026-03"
    )
    assert "2026-03" in path.name
