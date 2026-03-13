"""Nous — Proof Trace 基础设施 (M1.9)

记录 gate 推导路径，支持任意 block/confirm 可追溯到具体规则+事实绑定。
"""
import time
from dataclasses import dataclass, field, asdict
from typing import Optional


# ── 数据结构 ────────────────────────────────────────────────────────────────


@dataclass
class ProofStep:
    """单条规则的匹配记录"""
    rule_id: str                    # 约束规则 ID
    fact_bindings: dict             # 绑定的事实（来自 tool_call）
    verdict: str                    # "match" | "no-match"
    timestamp: float = field(default_factory=time.time)
    provenance: Optional[dict] = None  # M2.P1: 推导来源元数据（引擎/版本/数据集等）

    def to_dict(self) -> dict:
        d: dict = {
            "rule_id": self.rule_id,
            "fact_bindings": self.fact_bindings,
            "verdict": self.verdict,
            "timestamp": self.timestamp,
        }
        if self.provenance is not None:
            d["provenance"] = self.provenance
        return d


@dataclass
class ProofTrace:
    """完整的推导轨迹"""
    steps: list[ProofStep] = field(default_factory=list)
    final_verdict: str = "allow"    # "block" | "allow" | "confirm" | "warn"
    total_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "final_verdict": self.final_verdict,
            "total_ms": round(self.total_ms, 3),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProofTrace":
        steps = [
            ProofStep(
                rule_id=s["rule_id"],
                fact_bindings=s["fact_bindings"],
                verdict=s["verdict"],
                timestamp=s.get("timestamp", 0.0),
                provenance=s.get("provenance"),  # M2.P1
            )
            for s in data.get("steps", [])
        ]
        return cls(
            steps=steps,
            final_verdict=data.get("final_verdict", "allow"),
            total_ms=data.get("total_ms", 0.0),
        )


# ── 约束匹配逻辑 ──────────────────────────────────────────────────────────


def _match_constraint(tool_call: dict, constraint: dict) -> tuple[bool, dict]:
    """
    检查 tool_call 是否触发 constraint。

    简单模式匹配（MVP 实现）：
    - constraint.rule_body 可包含 key=value 检查
    - 格式：{"action_type": "delete_file", ...} 风格的 match_patterns

    返回 (matched: bool, bindings: dict)
    """
    patterns = constraint.get("match_patterns", {})

    if not patterns:
        # 没有 match_patterns → 尝试从 rule_body 解析（Datalog 简化版）
        rule_body = constraint.get("rule_body", "")
        # 简单实现：检查 tool_call 的 action 字段
        if "action_type" in rule_body:
            # 提取 action_type 值 e.g. action_type = delete_file
            for part in rule_body.split(","):
                part = part.strip()
                if "action_type" in part and "=" in part:
                    _, val = part.split("=", 1)
                    val = val.strip().strip('"').strip("'")
                    if tool_call.get("action_type") == val:
                        return True, {"action_type": val}
        return False, {}

    # 逐字段匹配
    bindings = {}
    for key, expected_val in patterns.items():
        actual_val = tool_call.get(key)
        if actual_val is None:
            # 尝试 nested 访问 e.g. "params.path"
            parts = key.split(".")
            obj = tool_call
            for p in parts:
                if isinstance(obj, dict):
                    obj = obj.get(p)
                else:
                    obj = None
                    break
            actual_val = obj

        if actual_val is None:
            return False, {}

        if isinstance(expected_val, list):
            if actual_val not in expected_val:
                return False, {}
        else:
            if actual_val != expected_val:
                return False, {}

        bindings[key] = actual_val

    return True, bindings


# ── 主函数 ────────────────────────────────────────────────────────────────


def trace_gate(tool_call: dict, constraints: list, db=None) -> ProofTrace:
    """
    遍历约束列表，记录每条规则的匹配/不匹配 + 绑定的事实。

    tool_call: 工具调用 dict，包含 tool_name/action_type/params 等
    constraints: list[dict]，每个 constraint 含 id/rule_body/verdict/match_patterns
    db: NousDB 实例（可选，用于查询额外事实）

    返回 ProofTrace（含所有 steps + final_verdict + total_ms）
    """
    t_start = time.perf_counter()
    trace = ProofTrace()

    final_verdict = "allow"

    for constraint in constraints:
        rule_id = constraint.get("id", "unknown")
        verdict_if_match = constraint.get("verdict", "block")
        enabled = constraint.get("enabled", True)

        if not enabled:
            continue

        matched, bindings = _match_constraint(tool_call, constraint)

        step = ProofStep(
            rule_id=rule_id,
            fact_bindings=bindings if matched else {},
            verdict="match" if matched else "no-match",
            timestamp=time.time(),
        )
        trace.steps.append(step)

        # 优先级：block > confirm > warn > allow
        if matched:
            _PRIORITY = {"block": 4, "confirm": 3, "warn": 2, "allow": 1}
            if _PRIORITY.get(verdict_if_match, 0) > _PRIORITY.get(final_verdict, 0):
                final_verdict = verdict_if_match

    trace.final_verdict = final_verdict
    trace.total_ms = (time.perf_counter() - t_start) * 1000

    return trace


def write_proof_trace_to_log(trace: ProofTrace, decision_log_id: str, db) -> bool:
    """
    将 ProofTrace 写入 DecisionLog 的 proof_trace 字段。

    返回是否写入成功。
    """
    if db is None:
        return False

    trace_dict = trace.to_dict()

    try:
        # 更新 decision_log 的 gates 字段（追加 proof_trace）
        # decision_log 用 (ts, session_key) 作为主键，这里仅作简化处理
        # 实际生产应通过 session_key 查询后更新
        db.db.run(
            "?[ts, session_key, tool_name, facts, gates, latency_us, outcome, "
            "proof_trace, schema_version] := "
            "*decision_log{ts, session_key, tool_name, facts, gates, "
            "latency_us, outcome}, "
            "session_key = $sk, "
            "proof_trace = $pt, schema_version = $sv "
            ":put decision_log {ts, session_key => tool_name, facts, gates, "
            "latency_us, outcome, proof_trace, schema_version}",
            {
                "sk": decision_log_id,
                "pt": trace_dict,
                "sv": "1.0",
            },
        )
        return True
    except Exception:
        return False
