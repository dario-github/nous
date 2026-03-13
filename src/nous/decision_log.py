"""Nous — 决策日志持久化 (M2.9)

DecisionLogEntry dataclass + persist_decision + query_decisions。
集成到 gate() pipeline：gate 返回前自动持久化。

Schema：
    DecisionLogEntry(
        timestamp, tool_call_summary, verdict, proof_trace,
        rule_ids, session_id, schema_version
    )

存储：写入 NousDB.decision_log 表（已在 M1 定义）。
"""
import json
import time
from dataclasses import dataclass, field
from typing import Optional

from nous.proof_trace import ProofTrace
from nous.verdict import Verdict

# 当前 schema 版本
DECISION_LOG_SCHEMA_VERSION = "2.0"


# ── CostBreakdown (M2.P2) ─────────────────────────────────────────────────


@dataclass
class CostBreakdown:
    """
    gate pipeline 各阶段的资源消耗明细 (M2.P2)。

    Attributes:
        fact_extraction_us:    事实提取阶段耗时（微秒）
        constraint_match_us:   约束匹配阶段耗时（微秒）
        delegate_us:           M5+ LLM 审议阶段耗时（微秒，当前为 None）
        delegate_tokens:       M5+ LLM 审议 token 数（当前为 None）
        entities_scanned:      扫描的实体/事实维度数
        constraints_evaluated: 评估的约束条数
    """
    fact_extraction_us: int = 0
    constraint_match_us: int = 0
    delegate_us: Optional[int] = None       # M5+ LLM 审议阶段耗时
    delegate_tokens: Optional[int] = None   # M5+ LLM 审议 token 数
    entities_scanned: int = 0
    constraints_evaluated: int = 0

    def to_dict(self) -> dict:
        d: dict = {
            "fact_extraction_us": self.fact_extraction_us,
            "constraint_match_us": self.constraint_match_us,
            "entities_scanned": self.entities_scanned,
            "constraints_evaluated": self.constraints_evaluated,
        }
        if self.delegate_us is not None:
            d["delegate_us"] = self.delegate_us
        if self.delegate_tokens is not None:
            d["delegate_tokens"] = self.delegate_tokens
        return d


# ── 数据结构 ───────────────────────────────────────────────────────────────


@dataclass
class DecisionLogEntry:
    """
    一条决策日志记录。

    Attributes:
        timestamp:         Unix 时间戳（秒，float）
        tool_call_summary: tool_call 的文本摘要（最多 200 字符）
        verdict:           裁决动作（block/allow/confirm/warn 等）
        proof_trace:       ProofTrace 对象（可序列化为 dict）
        rule_ids:          命中的规则 ID 列表（来自 proof_trace）
        session_id:        会话 ID（gate session_key）
        schema_version:    日志格式版本（默认 DECISION_LOG_SCHEMA_VERSION）
        latency_ms:        gate pipeline 耗时（毫秒）
        tool_name:         工具名称（可选）
        facts:             提取到的事实（可选）
        cost_breakdown:    各阶段资源消耗明细（M2.P2，可选）
    """
    timestamp: float = field(default_factory=time.time)
    tool_call_summary: str = ""
    verdict: str = "allow"
    proof_trace: Optional[ProofTrace] = None
    rule_ids: list[str] = field(default_factory=list)
    session_id: str = ""
    schema_version: str = DECISION_LOG_SCHEMA_VERSION
    latency_ms: float = 0.0
    tool_name: str = ""
    facts: dict = field(default_factory=dict)
    cost_breakdown: Optional[CostBreakdown] = None  # M2.P2

    def to_db_dict(self) -> dict:
        """转换为写入 decision_log 表的字段 dict"""
        trace_dict = self.proof_trace.to_dict() if self.proof_trace else {}
        # M2.P2: 将 cost_breakdown 嵌入 proof_trace JSON blob
        if self.cost_breakdown is not None:
            trace_dict["cost_breakdown"] = self.cost_breakdown.to_dict()
        return {
            "ts": self.timestamp,
            "sk": self.session_id or f"dl:{self.timestamp:.6f}",
            "tn": self.tool_name,
            "facts": self.facts,
            "gates": self.rule_ids,
            "lu": int(self.latency_ms * 1000),  # 毫秒 → 微秒
            "outcome": self.verdict,
            "pt": trace_dict,
            "sv": self.schema_version,
        }


# ── 从 GateResult 构建 Entry ──────────────────────────────────────────────


def entry_from_gate_result(
    gate_result,
    session_id: str = "",
    tool_call_summary: str = "",
) -> "DecisionLogEntry":
    """
    从 GateResult 构建 DecisionLogEntry。

    Args:
        gate_result:       GateResult 实例
        session_id:        会话 ID（覆盖 gate_result.decision_log_id）
        tool_call_summary: tool_call 摘要字符串

    Returns:
        DecisionLogEntry
    """
    # 从 proof_trace 提取命中的规则 ID
    rule_ids: list[str] = []
    if gate_result.proof_trace:
        for step in gate_result.proof_trace.steps:
            if step.verdict == "match":
                rule_ids.append(step.rule_id)

    return DecisionLogEntry(
        timestamp=time.time(),
        tool_call_summary=tool_call_summary[:200] if tool_call_summary else "",
        verdict=gate_result.verdict.action,
        proof_trace=gate_result.proof_trace,
        rule_ids=rule_ids,
        session_id=session_id or gate_result.decision_log_id or "",
        schema_version=DECISION_LOG_SCHEMA_VERSION,
        latency_ms=gate_result.latency_ms,
        tool_name=gate_result.facts.get("tool_name", ""),
        facts=gate_result.facts,
        cost_breakdown=gate_result.cost_breakdown,  # M2.P2
    )


# ── 持久化 ─────────────────────────────────────────────────────────────────


def persist_decision(entry: DecisionLogEntry, db) -> bool:
    """
    将 DecisionLogEntry 事务写入 decision_log 表。

    Args:
        entry: DecisionLogEntry 实例
        db:    NousDB 实例

    Returns:
        True 写入成功，False 写入失败（不抛出异常）
    """
    if db is None:
        return False

    d = entry.to_db_dict()

    try:
        db.db.run(
            "?[ts, session_key, tool_name, facts, gates, latency_us, "
            "outcome, proof_trace, schema_version] "
            "<- [[$ts, $sk, $tn, $facts, $gates, $lu, $outcome, $pt, $sv]] "
            ":put decision_log {ts, session_key => tool_name, facts, gates, "
            "latency_us, outcome, proof_trace, schema_version}",
            d,
        )
        return True
    except Exception as e:
        import logging
        logging.getLogger("nous.decision_log").error(
            "[decision_log] persist_decision 失败: %s", e
        )
        return False


# ── 查询 ──────────────────────────────────────────────────────────────────


def query_decisions(filters: dict, db) -> list[dict]:
    """
    按过滤条件查询 decision_log。

    支持过滤字段：
        verdict (str):        按裁决类型过滤（block/allow/confirm 等）
        rule_id (str):        按命中规则 ID 过滤（检查 gates 列表中是否包含）
        session_id (str):     按 session_key 精确匹配
        since (float):        Unix 时间戳，只返回 ts >= since 的记录
        until (float):        Unix 时间戳，只返回 ts <= until 的记录
        tool_name (str):      按工具名称过滤
        limit (int):          最多返回 N 条（默认 100）

    Args:
        filters: 过滤条件 dict
        db:      NousDB 实例

    Returns:
        list[dict]，每条为 decision_log 记录
    """
    if db is None:
        return []

    # 基础查询
    base_q = (
        "?[ts, session_key, tool_name, facts, gates, latency_us, "
        "outcome, proof_trace, schema_version] := "
        "*decision_log{ts, session_key, tool_name, facts, gates, "
        "latency_us, outcome, proof_trace, schema_version}"
    )

    conditions = []
    params: dict = {}

    # verdict 过滤
    verdict = filters.get("verdict")
    if verdict:
        conditions.append("outcome = $verdict")
        params["verdict"] = verdict

    # session_id 过滤
    session_id = filters.get("session_id")
    if session_id:
        conditions.append("session_key = $session_id")
        params["session_id"] = session_id

    # since/until 时间范围
    since = filters.get("since")
    if since is not None:
        conditions.append("ts >= $since")
        params["since"] = float(since)

    until = filters.get("until")
    if until is not None:
        conditions.append("ts <= $until")
        params["until"] = float(until)

    # tool_name 过滤
    tool_name = filters.get("tool_name")
    if tool_name:
        conditions.append("tool_name = $tool_name")
        params["tool_name"] = tool_name

    # 拼接条件
    if conditions:
        base_q += ", " + ", ".join(conditions)

    # 排序 + limit
    limit = int(filters.get("limit", 100))
    base_q += f" :order -ts :limit {limit}"

    try:
        rows = db._query_with_params(base_q, params)
    except Exception as e:
        import logging
        logging.getLogger("nous.decision_log").error(
            "[decision_log] query_decisions 失败: %s", e
        )
        return []

    # rule_id 后过滤（Cozo 对 JSON 数组的 contains 支持有限，Python 层过滤）
    rule_id = filters.get("rule_id")
    if rule_id and rows:
        filtered = []
        for row in rows:
            gates = row.get("gates", [])
            if isinstance(gates, list) and rule_id in gates:
                filtered.append(row)
            elif isinstance(gates, str):
                # 可能是序列化的 JSON 字符串
                try:
                    gates_list = json.loads(gates)
                    if rule_id in gates_list:
                        filtered.append(row)
                except Exception:
                    pass
        rows = filtered

    return rows


# ── gate() 集成入口 ────────────────────────────────────────────────────────


def gate_with_decision_log(
    tool_call: dict,
    db=None,
    constraints_dir=None,
    session_key: Optional[str] = None,
    sampling_policy=None,
    auto_persist: bool = True,
):
    """
    gate() 的包装器：gate 返回前自动持久化 DecisionLogEntry。

    与原 gate() 相比：
    - 不改变任何 gate 逻辑
    - 额外将完整 entry 写入 decision_log（包含 rule_ids 字段）
    - auto_persist=False 时跳过持久化（等价于直接调用 gate()）

    Returns:
        GateResult（与 gate() 相同）
    """
    from nous.gate import gate

    result = gate(
        tool_call=tool_call,
        db=db,
        constraints_dir=constraints_dir,
        session_key=session_key,
        sampling_policy=sampling_policy,
    )

    if auto_persist and db is not None:
        # 构建 summary
        try:
            summary = json.dumps(tool_call, ensure_ascii=False)[:200]
        except Exception:
            summary = str(tool_call)[:200]

        entry = entry_from_gate_result(
            gate_result=result,
            session_id=session_key or result.decision_log_id or "",
            tool_call_summary=summary,
        )
        persist_decision(entry, db)

    return result
