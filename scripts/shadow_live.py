#!/usr/bin/env python3
"""Nous Live Shadow — 增量处理 trigger_log.jsonl 新条目

每次运行：
1. 读取上次处理位置（offset file）
2. 处理新增 tool call 通过 Nous gate
3. 写入 shadow_live.jsonl
4. 更新 offset

设计用于 cron 每 5 分钟运行一次，14 天后产出完整 shadow 数据。
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.gate import gate, GateResult
from nous.db import NousDB
from nous.triviality_filter import TrivialityConfig
from nous.semantic_gate import SemanticGateConfig

TRIGGER_LOG = Path.home() / ".openclaw/ontology-gate/trigger_log.jsonl"
SHADOW_DIR = Path(__file__).parent.parent / "logs"
SHADOW_FILE = SHADOW_DIR / "shadow_live.jsonl"
OFFSET_FILE = SHADOW_DIR / ".shadow_offset"
STATS_FILE = SHADOW_DIR / "shadow_stats.json"


def load_offset() -> int:
    if OFFSET_FILE.exists():
        return int(OFFSET_FILE.read_text().strip())
    return 0


def save_offset(offset: int):
    OFFSET_FILE.write_text(str(offset))


def parse_tool_call(entry: dict) -> dict:
    ctx = entry.get("tool_context", {})
    params_summary = ctx.get("params_summary", "")
    params = {}
    if ":" in params_summary:
        parts = params_summary.split(":", 1)
        if len(parts) > 1:
            for kv in parts[1].split(","):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    params[k.strip()] = v.strip()
    return {
        "tool_name": entry.get("tool", ctx.get("name", "unknown")),
        "params": params,
    }


def update_stats(stats_path: Path, new_results: list):
    """累计更新统计"""
    stats = {"total": 0, "allow": 0, "block": 0, "confirm": 0,
             "consistent": 0, "inconsistent": 0, "fn": 0, "fp": 0,
             "started_at": None, "last_run": None, "runs": 0}

    if stats_path.exists():
        try:
            stats = json.loads(stats_path.read_text())
        except:
            pass

    if stats["started_at"] is None:
        stats["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    stats["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    stats["runs"] += 1

    for r in new_results:
        stats["total"] += 1
        v = r["nous_verdict"]
        stats[v] = stats.get(v, 0) + 1
        if r["consistent"]:
            stats["consistent"] += 1
        else:
            stats["inconsistent"] += 1
            if r["ts_blocked"] and not (v == "block"):
                stats["fn"] += 1
            elif not r["ts_blocked"] and v == "block":
                stats["fp"] += 1

    total = stats["total"]
    if total > 0:
        stats["consistency_pct"] = round(stats["consistent"] / total * 100, 2)
        stats["fp_pct"] = round(stats.get("fp", 0) / total * 100, 3)
        stats["fn_pct"] = round(stats.get("fn", 0) / total * 100, 3)

    stats_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    return stats


def main():
    if not TRIGGER_LOG.exists():
        return

    SHADOW_DIR.mkdir(parents=True, exist_ok=True)

    # 读取所有行
    with open(TRIGGER_LOG) as f:
        all_lines = f.readlines()

    offset = load_offset()
    new_lines = all_lines[offset:]

    if not new_lines:
        return

    # 初始化 Nous
    db_path = Path(__file__).parent.parent / "data" / "nous.db"
    db = NousDB(str(db_path)) if db_path.exists() else None
    constraints_dir = Path(__file__).parent.parent / "ontology" / "constraints"

    # L2 Triviality + L3 Semantic Gate 配置（P0 修复：之前未传入导致只跑 L1）
    triviality_cfg = TrivialityConfig()
    semantic_cfg = SemanticGateConfig(
        enabled=True,
        mode="shadow",
        model="openai/gpt-5-mini",  # T2 production, config.yaml
    )

    results = []
    with open(SHADOW_FILE, "a") as out:
        for i, line in enumerate(new_lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            tool_call = parse_tool_call(entry)
            t0 = time.perf_counter_ns()

            try:
                result = gate(
                    tool_call=tool_call,
                    db=db,
                    constraints_dir=constraints_dir,
                    session_key=entry.get("session_key", f"shadow:{offset+i}"),
                    triviality_config=triviality_cfg,
                    semantic_config=semantic_cfg,
                )
                verdict = result.verdict.action
                rule_id = result.verdict.rule_id
                layer_path = getattr(result, "layer_path", "unknown")
                datalog_v = getattr(result, "datalog_verdict", None)
                semantic_v = getattr(result, "semantic_verdict", None)
            except Exception:
                verdict = "error"
                rule_id = None
                layer_path = "error"
                datalog_v = None
                semantic_v = None

            latency_us = (time.perf_counter_ns() - t0) // 1000
            ts_gates = entry.get("gates", [])
            ts_blocked = any(g.get("verdict") == "block" for g in ts_gates) if ts_gates else False
            nous_blocked = verdict == "block"
            consistent = ts_blocked == nous_blocked

            record = {
                "ts": entry.get("ts"),
                "tool": tool_call["tool_name"],
                "nous_verdict": verdict,
                "nous_rule_id": rule_id,
                "layer_path": layer_path,
                "latency_us": latency_us,
                "ts_blocked": ts_blocked,
                "consistent": consistent,
            }
            # Add L1/L2/L3 layer details when available
            if datalog_v is not None:
                record["datalog_verdict"] = datalog_v
            if semantic_v is not None:
                # Extract key semantic fields (confidence, model) to keep log compact
                record["semantic_verdict"] = semantic_v.get("verdict") if isinstance(semantic_v, dict) else str(semantic_v)
                if isinstance(semantic_v, dict) and "confidence" in semantic_v:
                    record["semantic_conf"] = semantic_v["confidence"]
            # 对不一致的记录，额外保存命令摘要以便调试
            if not consistent:
                ctx = entry.get("tool_context", {})
                cmd_summary = ctx.get("params_summary", "")[:200]
                if not cmd_summary:
                    # fallback: 尝试从 params 提取
                    params = entry.get("params", {})
                    cmd_summary = str(params.get("command", params.get("text", "")))[:200]
                record["cmd_summary"] = cmd_summary
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            results.append(record)

    save_offset(len(all_lines))

    # 更新统计
    stats = update_stats(STATS_FILE, results)

    if results:
        print(f"[nous-shadow] +{len(results)} calls | total={stats['total']} | consistency={stats.get('consistency_pct', 0)}% | FP={stats.get('fp', 0)} FN={stats.get('fn', 0)}")


if __name__ == "__main__":
    main()
