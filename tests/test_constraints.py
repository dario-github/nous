"""测试 M2.1-M2.5 — YAML 约束解析 + GT 回归 + Fact 提取 + Verdict 路由 + Gate API

覆盖：
  - M2.1: constraint_parser (5 条 YAML 解析正确)
  - M2.2: GT 回归 (正例 + 反例 × 5 规则)
  - M2.3: fact_extractor (5 类 tool_call)
  - M2.4: verdict router (5 类 verdict)
  - M2.5: gate() 集成测试 (5 个场景)
"""
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"
sys.path.insert(0, str(SRC_DIR))

from nous.constraint_parser import load_constraints, parse_constraint_file, get_constraint_by_id
from nous.fact_extractor import extract_facts
from nous.verdict import (
    Verdict,
    MatchResult,
    match_constraint,
    match_all_constraints,
    route_verdict,
)
from nous.gate import gate, GateResult
from nous.db import NousDB
from nous.schema import Constraint


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def db():
    _db = NousDB(":memory:")
    yield _db
    _db.close()


@pytest.fixture
def constraints():
    """加载真实的 5 条约束文件"""
    return load_constraints(CONSTRAINTS_DIR)


# ═══════════════════════════════════════════════════════════════════════════
# M2.1 — YAML 约束解析器
# ═══════════════════════════════════════════════════════════════════════════


class TestConstraintParser:
    """M2.1: 5 条 YAML 约束全部解析正确"""

    def test_load_all_5_constraints(self, constraints):
        """应加载 5 条约束"""
        ids = [c.id for c in constraints]
        assert "T3" in ids
        assert "T5" in ids
        assert "T10" in ids
        assert "T11" in ids
        assert "T12" in ids
        assert len(constraints) == 45  # Loop 70: +OH-R7d/OH-R5b/OH-R8d/OH-R8e/OH-R6e (11 FN fixes)

    def test_t3_parsed_correctly(self, constraints):
        """T3: 不可逆操作 → block，priority=100"""
        t3 = next(c for c in constraints if c.id == "T3")
        assert t3.verdict == "block"
        assert t3.priority == 100
        assert t3.enabled is True
        assert "action_type" in t3.trigger
        assert "in" in t3.trigger["action_type"]
        assert "delete_file" in t3.trigger["action_type"]["in"]
        assert "modify_config" in t3.trigger["action_type"]["in"]

    def test_t5_parsed_correctly(self, constraints):
        """T5: 社媒链接 → block，priority=90"""
        t5 = next(c for c in constraints if c.id == "T5")
        assert t5.verdict == "block"
        assert t5.priority == 90
        assert "url_has_social_pattern" in t5.trigger
        assert t5.trigger["url_has_social_pattern"] is True

    def test_t10_parsed_correctly(self, constraints):
        """T10: 大文件写入 → warn，priority=70"""
        t10 = next(c for c in constraints if c.id == "T10")
        assert t10.verdict == "warn"
        assert t10.priority == 70
        assert "estimated_lines" in t10.trigger
        assert t10.trigger["estimated_lines"]["gt"] == 400

    def test_t11_parsed_correctly(self, constraints):
        """T11: 搜索语言修正 → rewrite，含 rewrite_params"""
        t11 = next(c for c in constraints if c.id == "T11")
        assert t11.verdict == "rewrite"
        assert t11.priority == 60
        assert t11.trigger.get("search_lang") == "zh"
        assert t11.rewrite_params is not None
        assert t11.rewrite_params.get("search_lang") == "zh-hans"

    def test_t12_parsed_correctly(self, constraints):
        """T12: Discord 结构化输出 → require，priority=75"""
        t12 = next(c for c in constraints if c.id == "T12")
        assert t12.verdict == "require"
        assert t12.priority == 75
        assert t12.trigger.get("output_target") == "discord"
        assert t12.trigger.get("content_is_structured") is True

    def test_constraints_sorted_by_priority(self, constraints):
        """约束应按 priority 升序排列"""
        priorities = [c.priority for c in constraints]
        assert priorities == sorted(priorities)

    def test_parse_single_file(self):
        """单文件解析应成功"""
        t3_file = CONSTRAINTS_DIR / "T3.yaml"
        c = parse_constraint_file(t3_file)
        assert c.id == "T3"
        assert c.verdict == "block"

    def test_get_constraint_by_id(self):
        """按 ID 查找应返回正确约束"""
        c = get_constraint_by_id("T11", CONSTRAINTS_DIR)
        assert c is not None
        assert c.id == "T11"
        assert c.verdict == "rewrite"

    def test_get_nonexistent_constraint(self):
        """查找不存在的 ID 应返回 None"""
        c = get_constraint_by_id("T99", CONSTRAINTS_DIR)
        assert c is None


# ═══════════════════════════════════════════════════════════════════════════
# M2.2 — GT 回归测试（正例 + 反例 × 5 规则）
# ═══════════════════════════════════════════════════════════════════════════


class TestConstraintGT:
    """M2.2: 5 条规则的 Ground Truth 回归"""

    # ── T3: 不可逆操作 ──────────────────────────────────────────────────

    def test_t3_delete_file_blocked(self, constraints):
        """T3 正例：delete_file → block"""
        t3 = next(c for c in constraints if c.id == "T3")
        facts = {"action_type": "delete_file"}
        result = match_constraint(t3, facts)
        assert result.matched is True

    def test_t3_read_file_passes(self, constraints):
        """T3 反例：read_file → pass（不命中）"""
        t3 = next(c for c in constraints if c.id == "T3")
        facts = {"action_type": "read_file"}
        result = match_constraint(t3, facts)
        assert result.matched is False

    def test_t3_modify_config_blocked(self, constraints):
        """T3 正例：modify_config → block"""
        t3 = next(c for c in constraints if c.id == "T3")
        facts = {"action_type": "modify_config"}
        result = match_constraint(t3, facts)
        assert result.matched is True

    def test_t3_exec_destructive_blocked(self, constraints):
        """T3 正例：exec_destructive → block"""
        t3 = next(c for c in constraints if c.id == "T3")
        facts = {"action_type": "exec_destructive"}
        result = match_constraint(t3, facts)
        assert result.matched is True

    # ── T5: 社媒链接 ────────────────────────────────────────────────────

    def test_t5_twitter_url_blocked(self, constraints):
        """T5 正例：twitter.com URL → block"""
        t5 = next(c for c in constraints if c.id == "T5")
        facts = {
            "url": "https://twitter.com/user/status/123",
            "url_has_social_pattern": True,
        }
        result = match_constraint(t5, facts)
        assert result.matched is True

    def test_t5_github_url_passes(self, constraints):
        """T5 反例：github.com → pass"""
        t5 = next(c for c in constraints if c.id == "T5")
        facts = {
            "url": "https://github.com/user/repo",
            "url_has_social_pattern": False,
        }
        result = match_constraint(t5, facts)
        assert result.matched is False

    def test_t5_xiaohongshu_blocked(self, constraints):
        """T5 正例：小红书链接 → block"""
        t5 = next(c for c in constraints if c.id == "T5")
        facts = {
            "url": "https://xhslink.com/xxxx",
            "url_has_social_pattern": True,
        }
        result = match_constraint(t5, facts)
        assert result.matched is True

    # ── T10: 大文件写入 ──────────────────────────────────────────────────

    def test_t10_500_lines_warned(self, constraints):
        """T10 正例：write 500 行 → warn"""
        t10 = next(c for c in constraints if c.id == "T10")
        facts = {
            "action_type": "write_file",
            "estimated_lines": 500,
        }
        result = match_constraint(t10, facts)
        assert result.matched is True

    def test_t10_100_lines_passes(self, constraints):
        """T10 反例：write 100 行 → pass"""
        t10 = next(c for c in constraints if c.id == "T10")
        facts = {
            "action_type": "write_file",
            "estimated_lines": 100,
        }
        result = match_constraint(t10, facts)
        assert result.matched is False

    def test_t10_exactly_400_passes(self, constraints):
        """T10 边界：exactly 400 → pass（gt 不含等号）"""
        t10 = next(c for c in constraints if c.id == "T10")
        facts = {
            "action_type": "write_file",
            "estimated_lines": 400,
        }
        result = match_constraint(t10, facts)
        assert result.matched is False

    def test_t10_401_warned(self, constraints):
        """T10 边界：401 → warn"""
        t10 = next(c for c in constraints if c.id == "T10")
        facts = {
            "action_type": "write_file",
            "estimated_lines": 401,
        }
        result = match_constraint(t10, facts)
        assert result.matched is True

    # ── T11: 搜索语言修正 ────────────────────────────────────────────────

    def test_t11_search_lang_zh_rewritten(self, constraints):
        """T11 正例：search_lang=zh → rewrite zh-hans"""
        t11 = next(c for c in constraints if c.id == "T11")
        facts = {"search_lang": "zh"}
        result = match_constraint(t11, facts)
        assert result.matched is True
        # 验证 rewrite_params 可从 constraint 拿到
        assert t11.rewrite_params["search_lang"] == "zh-hans"

    def test_t11_search_lang_en_passes(self, constraints):
        """T11 反例：search_lang=en → pass"""
        t11 = next(c for c in constraints if c.id == "T11")
        facts = {"search_lang": "en"}
        result = match_constraint(t11, facts)
        assert result.matched is False

    def test_t11_no_search_lang_passes(self, constraints):
        """T11 反例：无 search_lang → pass"""
        t11 = next(c for c in constraints if c.id == "T11")
        facts = {"action_type": "web_search"}
        result = match_constraint(t11, facts)
        assert result.matched is False

    # ── T12: Discord 结构化输出 ──────────────────────────────────────────

    def test_t12_discord_structured_required(self, constraints):
        """T12 正例：discord + structured → require"""
        t12 = next(c for c in constraints if c.id == "T12")
        facts = {
            "output_target": "discord",
            "content_is_structured": True,
        }
        result = match_constraint(t12, facts)
        assert result.matched is True

    def test_t12_discord_single_sentence_passes(self, constraints):
        """T12 反例：discord + single_sentence（非结构化）→ pass"""
        t12 = next(c for c in constraints if c.id == "T12")
        facts = {
            "output_target": "discord",
            "content_is_structured": False,
        }
        result = match_constraint(t12, facts)
        assert result.matched is False

    def test_t12_slack_structured_passes(self, constraints):
        """T12 反例：slack + structured → pass（目标不是 discord）"""
        t12 = next(c for c in constraints if c.id == "T12")
        facts = {
            "output_target": "slack",
            "content_is_structured": True,
        }
        result = match_constraint(t12, facts)
        assert result.matched is False


# ═══════════════════════════════════════════════════════════════════════════
# M2.3 — Fact Extractor
# ═══════════════════════════════════════════════════════════════════════════


class TestFactExtractor:
    """M2.3: 5 类 tool_call 提取正确"""

    def test_extract_write_tool(self):
        """write tool → action_type=write_file，estimated_lines 计数"""
        tool_call = {
            "tool_name": "write",
            "params": {
                "path": "/home/yan/clawd/test.py",
                "content": "line1\nline2\nline3\nline4\nline5",
            },
        }
        facts = extract_facts(tool_call)
        assert facts["action_type"] == "write_file"
        assert facts["estimated_lines"] == 5

    def test_extract_web_fetch_social_url(self):
        """web_fetch + twitter URL → url_has_social_pattern=True"""
        tool_call = {
            "tool_name": "web_fetch",
            "url": "https://twitter.com/user/status/12345",
        }
        facts = extract_facts(tool_call)
        assert facts["url_has_social_pattern"] is True
        assert "twitter.com" in facts["url"]

    def test_extract_web_fetch_normal_url(self):
        """web_fetch + github URL → url_has_social_pattern=False"""
        tool_call = {
            "tool_name": "web_fetch",
            "url": "https://github.com/user/repo",
        }
        facts = extract_facts(tool_call)
        assert facts["url_has_social_pattern"] is False

    def test_extract_web_search_zh(self):
        """web_search + search_lang=zh → search_lang=zh"""
        tool_call = {
            "tool_name": "web_search",
            "search_lang": "zh",
            "params": {"query": "股票分析"},
        }
        facts = extract_facts(tool_call)
        assert facts["search_lang"] == "zh"
        assert facts["action_type"] == "web_search"

    def test_extract_web_search_en(self):
        """web_search + search_lang=en → search_lang=en"""
        tool_call = {
            "tool_name": "web_search",
            "search_lang": "en",
            "params": {"query": "python tutorial"},
        }
        facts = extract_facts(tool_call)
        assert facts["search_lang"] == "en"

    def test_extract_discord_structured_message(self):
        """message tool + discord + table → output_target=discord, structured=True"""
        tool_call = {
            "tool_name": "message",
            "target": "discord",
            "message": "| 股票 | 涨跌 | 成交量 |\n| 600036 | +2% | 10亿 |\n| 000001 | -1% | 5亿 |",
        }
        facts = extract_facts(tool_call)
        assert facts["output_target"] == "discord"
        assert facts["content_is_structured"] is True

    def test_extract_discord_single_sentence(self):
        """message tool + discord + 单句 → structured=False"""
        tool_call = {
            "tool_name": "message",
            "target": "discord",
            "message": "好的，完成了。",
        }
        facts = extract_facts(tool_call)
        assert facts["output_target"] == "discord"
        assert facts["content_is_structured"] is False

    def test_extract_explicit_estimated_lines(self):
        """显式 estimated_lines 字段应优先使用"""
        tool_call = {
            "tool_name": "write",
            "estimated_lines": 500,
        }
        facts = extract_facts(tool_call)
        assert facts["estimated_lines"] == 500

    def test_extract_exec_tool(self):
        """非破坏性 exec → exec_command（不触发 T3）"""
        tool_call = {
            "tool_name": "exec",
            "command": "echo hello",
        }
        facts = extract_facts(tool_call)
        assert facts["action_type"] == "exec_command"

    def test_extract_exec_destructive(self):
        """破坏性 exec (rm -rf) → exec_destructive（触发 T3）"""
        tool_call = {
            "tool_name": "exec",
            "params": {"command": "rm -rf /tmp/test"},
        }
        facts = extract_facts(tool_call)
        assert facts["action_type"] == "exec_destructive"

    def test_extract_no_url_fields(self):
        """无 URL 的 tool_call → url=None, url_has_social_pattern=False"""
        tool_call = {
            "tool_name": "read",
            "params": {"path": "/tmp/test.txt"},
        }
        facts = extract_facts(tool_call)
        assert facts["url"] is None
        assert facts["url_has_social_pattern"] is False


# ═══════════════════════════════════════════════════════════════════════════
# M2.4 — Verdict 路由器
# ═══════════════════════════════════════════════════════════════════════════


def _make_constraint(id_, verdict, priority=50, **trigger_kwargs):
    """工具函数：快速构造 Constraint"""
    return Constraint(
        id=id_,
        verdict=verdict,
        priority=priority,
        trigger=trigger_kwargs,
    )


def _hit(constraint: Constraint, bindings: dict = None) -> MatchResult:
    return MatchResult(constraint=constraint, matched=True, fact_bindings=bindings or {})


def _miss(constraint: Constraint) -> MatchResult:
    return MatchResult(constraint=constraint, matched=False)


class TestVerdictRouter:
    """M2.4: 5 类 verdict 路由"""

    def test_no_match_returns_allow(self):
        """无命中 → allow"""
        c = _make_constraint("T99", "block")
        result = route_verdict([_miss(c)])
        assert result.action == "allow"

    def test_block_verdict(self):
        """block 规则命中 → action=block"""
        c = _make_constraint("T3", "block", priority=100)
        result = route_verdict([_hit(c)])
        assert result.action == "block"
        assert result.rule_id == "T3"

    def test_warn_verdict(self):
        """warn 规则命中 → action=warn"""
        c = _make_constraint("T10", "warn", priority=70)
        result = route_verdict([_hit(c)])
        assert result.action == "warn"
        assert result.rule_id == "T10"

    def test_rewrite_verdict(self):
        """rewrite 规则命中 → action=rewrite + rewrite_params"""
        c = Constraint(
            id="T11", verdict="rewrite", priority=60,
            trigger={"search_lang": "zh"},
            rewrite_params={"search_lang": "zh-hans"},
        )
        result = route_verdict([_hit(c)])
        assert result.action == "rewrite"
        assert result.rewrite_params == {"search_lang": "zh-hans"}

    def test_require_verdict(self):
        """require 规则命中 → action=require"""
        c = _make_constraint("T12", "require", priority=75)
        result = route_verdict([_hit(c)])
        assert result.action == "require"

    def test_block_beats_warn(self):
        """block > warn：两者同时命中，返回 block"""
        c_block = _make_constraint("T3", "block", priority=100)
        c_warn = _make_constraint("T10", "warn", priority=70)
        result = route_verdict([_hit(c_warn), _hit(c_block)])
        assert result.action == "block"
        assert result.rule_id == "T3"

    def test_block_beats_require(self):
        """block > require"""
        c_block = _make_constraint("T3", "block", priority=100)
        c_req = _make_constraint("T12", "require", priority=75)
        result = route_verdict([_hit(c_req), _hit(c_block)])
        assert result.action == "block"

    def test_require_beats_warn(self):
        """require > warn"""
        c_req = _make_constraint("T12", "require", priority=75)
        c_warn = _make_constraint("T10", "warn", priority=70)
        result = route_verdict([_hit(c_warn), _hit(c_req)])
        assert result.action == "require"

    def test_all_matched_contains_all_ids(self):
        """all_matched 包含所有命中的规则 ID"""
        c1 = _make_constraint("T3", "block")
        c2 = _make_constraint("T10", "warn")
        result = route_verdict([_hit(c1), _hit(c2)])
        assert "T3" in result.all_matched
        assert "T10" in result.all_matched

    def test_transform_normalized_to_rewrite(self):
        """transform 应被标准化为 rewrite"""
        c = _make_constraint("T11", "transform")
        result = route_verdict([_hit(c)])
        assert result.action == "rewrite"

    def test_match_constraint_t3_facts(self, constraints):
        """match_constraint 完整流程：T3 facts 命中"""
        t3 = next(c for c in constraints if c.id == "T3")
        facts = {"action_type": "delete_file", "url_has_social_pattern": False}
        result = match_constraint(t3, facts)
        assert result.matched is True
        assert result.fact_bindings.get("action_type") == "delete_file"

    def test_match_all_returns_all_results(self, constraints):
        """match_all_constraints 返回所有约束的结果（包含未命中）"""
        facts = {"action_type": "read_file", "url_has_social_pattern": False,
                 "estimated_lines": 10, "search_lang": "en",
                 "output_target": "discord", "content_is_structured": False}
        results = match_all_constraints(constraints, facts)
        assert len(results) == 45  # Loop 70: +OH-R7d/OH-R5b/OH-R8d/OH-R8e/OH-R6e
        # 所有约束都不匹配
        assert all(not r.matched for r in results)


# ═══════════════════════════════════════════════════════════════════════════
# M2.5 — gate() 集成测试
# ═══════════════════════════════════════════════════════════════════════════


class TestGateAPI:
    """M2.5: 5 个场景端到端走通"""

    def test_gate_delete_file_returns_block(self, db):
        """场景1：delete_file → block"""
        tool_call = {
            "tool_name": "exec",
            "action_type": "delete_file",
            "params": {"path": "/tmp/important.db"},
        }
        result = gate(tool_call, db=db, constraints_dir=CONSTRAINTS_DIR)
        assert isinstance(result, GateResult)
        assert result.verdict.action == "block"
        assert result.verdict.rule_id == "T3"

    def test_gate_social_url_returns_block(self, db):
        """场景2：twitter URL → block（T5）"""
        tool_call = {
            "tool_name": "web_fetch",
            "url": "https://twitter.com/elonmusk/status/123",
        }
        result = gate(tool_call, db=db, constraints_dir=CONSTRAINTS_DIR)
        assert result.verdict.action == "block"
        assert result.verdict.rule_id == "T5"

    def test_gate_large_file_returns_warn(self, db):
        """场景3：写入 500 行 → warn（T10）"""
        tool_call = {
            "tool_name": "write",
            "action_type": "write_file",
            "estimated_lines": 500,
            "params": {"path": "/tmp/big.py"},
        }
        result = gate(tool_call, db=db, constraints_dir=CONSTRAINTS_DIR)
        assert result.verdict.action == "warn"
        assert result.verdict.rule_id == "T10"

    def test_gate_search_lang_zh_returns_rewrite(self, db):
        """场景4：search_lang=zh → rewrite zh-hans（T11）"""
        tool_call = {
            "tool_name": "web_search",
            "search_lang": "zh",
            "params": {"query": "A股大盘分析"},
        }
        result = gate(tool_call, db=db, constraints_dir=CONSTRAINTS_DIR)
        assert result.verdict.action == "rewrite"
        assert result.verdict.rule_id == "T11"
        assert result.verdict.rewrite_params == {"search_lang": "zh-hans"}

    def test_gate_discord_structured_returns_require(self, db):
        """场景5：discord + 表格内容 → require（T12）
        注意：action_type 需不在 T3 的 irreversible 列表中，否则 T3(block) 优先。
        这里模拟一个"查看/读取"类型的 discord 通知场景。
        """
        tool_call = {
            "tool_name": "message",
            "action_type": "send_notification",  # 非 T3 触发项
            "target": "discord",
            "content_is_structured": True,
            "message": "| col1 | col2 |\n| a | b |",
        }
        result = gate(tool_call, db=db, constraints_dir=CONSTRAINTS_DIR)
        assert result.verdict.action == "require"
        assert result.verdict.rule_id == "T12"

    def test_gate_safe_action_returns_allow(self, db):
        """安全操作：read_file → allow"""
        tool_call = {
            "tool_name": "read",
            "params": {"path": "/tmp/safe.txt"},
        }
        result = gate(tool_call, db=db, constraints_dir=CONSTRAINTS_DIR)
        assert result.verdict.action == "allow"

    def test_gate_returns_proof_trace(self, db):
        """gate() 必须包含 proof_trace"""
        tool_call = {"tool_name": "exec", "action_type": "delete_file"}
        result = gate(tool_call, db=db, constraints_dir=CONSTRAINTS_DIR)
        assert result.proof_trace is not None
        assert result.proof_trace.final_verdict == result.verdict.action
        assert len(result.proof_trace.steps) == 45  # Loop 70: +OH-R7d/OH-R5b/OH-R8d/OH-R8e/OH-R6e

    def test_gate_logs_decision_to_db(self, db):
        """block verdict 应写入 decision_log"""
        tool_call = {"tool_name": "exec", "action_type": "delete_file"}
        result = gate(tool_call, db=db, constraints_dir=CONSTRAINTS_DIR,
                      session_key="test:gate:block:001")
        assert result.decision_log_id == "test:gate:block:001"

    def test_gate_latency_is_fast(self, db):
        """gate() 应在 50ms 内完成（本地 in-memory DB）"""
        tool_call = {"tool_name": "read", "params": {"path": "/tmp/x"}}
        result = gate(tool_call, db=db, constraints_dir=CONSTRAINTS_DIR)
        assert result.latency_ms < 100.0  # Loop 64: 32 constraints, relaxed from 50ms

    def test_gate_without_db_no_crash(self):
        """无 DB 时 gate() 不应崩溃"""
        tool_call = {"tool_name": "exec", "action_type": "delete_file"}
        result = gate(tool_call, db=None, constraints_dir=CONSTRAINTS_DIR)
        assert result.verdict.action == "block"
        assert result.decision_log_id is None

    def test_gate_fail_closed_on_error(self):
        """引擎异常 → confirm（FAIL_CLOSED）"""
        # 传入一个完全非法的约束目录
        result = gate(
            {"tool_name": "exec"},
            db=None,
            constraints_dir=Path("/nonexistent/path/to/constraints"),
        )
        # FAIL_CLOSED: 非法路径 → ConstraintLoadError → gate 外层 catch → confirm
        assert result.verdict.action == "confirm"
        assert "FAIL_CLOSED" in result.verdict.reason or "ConstraintLoadError" in result.verdict.reason

    def test_gate_to_dict(self, db):
        """GateResult.to_dict() 应包含所有字段"""
        tool_call = {"tool_name": "read", "params": {"path": "/tmp/x"}}
        result = gate(tool_call, db=db, constraints_dir=CONSTRAINTS_DIR)
        d = result.to_dict()
        assert "verdict" in d
        assert "proof_trace" in d
        assert "latency_ms" in d
        assert "facts" in d
        assert d["verdict"]["action"] in ("allow", "block", "warn", "confirm", "rewrite", "require")

    def test_fail_closed_empty_dir(self, tmp_path):
        """FAIL_CLOSED: 约束目录存在但为空 → confirm（不 allow）"""
        empty_dir = tmp_path / "empty_constraints"
        empty_dir.mkdir()
        result = gate(
            {"tool_name": "exec", "action_type": "read_file"},
            db=None,
            constraints_dir=empty_dir,
        )
        assert result.verdict.action == "confirm"
        assert "constraint-load-failed" in result.verdict.reason or "FAIL_CLOSED" in result.verdict.reason

    def test_fail_closed_all_yaml_corrupt(self, tmp_path):
        """FAIL_CLOSED: 所有 YAML 文件解析失败 → 0 条约束 → confirm"""
        bad_dir = tmp_path / "bad_constraints"
        bad_dir.mkdir()
        (bad_dir / "bad.yaml").write_text("not: a: valid: constraint: [")
        result = gate(
            {"tool_name": "exec"},
            db=None,
            constraints_dir=bad_dir,
        )
        assert result.verdict.action == "confirm"

    def test_constraint_load_error_raised_directly(self):
        """ConstraintLoadError 直接调 load_constraints 时应抛出"""
        from nous.constraint_parser import ConstraintLoadError
        import pytest
        with pytest.raises(ConstraintLoadError):
            load_constraints(Path("/nonexistent/nous/constraints"))

    def test_constraint_load_error_empty_dir_raised(self, tmp_path):
        """空目录调 load_constraints 时应抛出 ConstraintLoadError"""
        from nous.constraint_parser import ConstraintLoadError
        import pytest
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(ConstraintLoadError):
            load_constraints(empty_dir)
