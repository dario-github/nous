"""Nous — Gateway Hook (M2.7 + M7.1a)

模拟 OpenClaw gateway 的 before_tool_call / after_tool_call hook，支持 shadow mode。

Shadow mode（默认开启）：
  - before: 调用 gate() 获取 verdict，与 legacy 对比记录 alert
  - after: 调用 auto_extract 从结果中提取实体/关系入 KG
  - **不拦截**：始终返回原始 tool_call（只观测，不阻断）

Primary mode（shadow_mode=False）：
  - block verdict → 真正抛出 BlockedByNous 异常（阻断调用）
  - 其他 verdict → 放行
  - after: 同样调用 auto_extract

注：这是模拟 hook，不直接接入 OpenClaw gateway（需要东丞配合集成）。
提供标准接口 + 完整集成测试，方便后续对接。
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from nous.gate import GateResult, gate
from nous.db import NousDB

logger = logging.getLogger("nous.gateway_hook")

# 默认 alert 日志路径
_DEFAULT_ALERT_LOG = Path(__file__).parent.parent.parent.parent / "logs" / "shadow_alerts.jsonl"
_DEFAULT_EXTRACT_LOG = Path(__file__).parent.parent.parent.parent / "logs" / "extract_log.jsonl"


# ── 异常 ───────────────────────────────────────────────────────────────────


class BlockedByNous(Exception):
    """Primary mode 下 block verdict 触发此异常"""
    def __init__(self, rule_id: str, reason: str):
        self.rule_id = rule_id
        self.reason = reason
        super().__init__(f"[Nous] Blocked by rule {rule_id!r}: {reason}")


# ── NousGatewayHook ───────────────────────────────────────────────────────


@dataclass
class NousGatewayHook:
    """
    Gateway before_tool_call / after_tool_call hook。

    Attributes:
        shadow_mode:      True = 只记录不拦截（默认）；False = 真正拦截
        db:               NousDB 实例（可选，用于写 decision_log + KG）
        alert_log_path:   shadow alert JSONL 文件路径
        extract_log_path: auto_extract 结果 JSONL 文件路径
        constraints_dir:  约束目录（None = 使用默认）
        llm_fn:           异步 LLM 函数（用于 auto_extract，可选）
        auto_extract_enabled: 是否启用 after_tool_call 自动提取（默认 True）
    """
    shadow_mode: bool = True
    db: Optional[NousDB] = field(default=None, repr=False)
    alert_log_path: Path = field(default_factory=lambda: _DEFAULT_ALERT_LOG)
    extract_log_path: Path = field(default_factory=lambda: _DEFAULT_EXTRACT_LOG)
    constraints_dir: Optional[Path] = None
    llm_fn: Optional[Any] = field(default=None, repr=False)
    auto_extract_enabled: bool = True

    def before_tool_call(
        self,
        tool_call: dict,
        session_key: Optional[str] = None,
        legacy_verdict: Optional[str] = None,
    ) -> dict:
        """
        在工具调用执行前运行 gate()。

        Args:
            tool_call:       工具调用 dict
            session_key:     日志会话标识（可选）
            legacy_verdict:  旧引擎的裁决（用于 shadow 对比，可选）

        Returns:
            tool_call dict（shadow mode 始终原样返回；primary mode 下 block 抛异常）

        Raises:
            BlockedByNous: primary mode 且 verdict == "block"
        """
        sk = session_key or f"hook:{time.perf_counter():.6f}"

        # 运行 gate pipeline
        try:
            result: GateResult = gate(
                tool_call=tool_call,
                db=self.db,
                constraints_dir=self.constraints_dir,
                session_key=sk,
            )
            nous_verdict = result.verdict.action
        except Exception as e:
            logger.error("[gateway_hook] gate() 异常，FAIL_CLOSED → confirm: %s", e)
            nous_verdict = "confirm"
            result = None

        # 记录日志
        logger.debug(
            "[gateway_hook] tool=%s verdict=%s shadow=%s",
            tool_call.get("tool_name") or tool_call.get("name", "?"),
            nous_verdict,
            self.shadow_mode,
        )

        # shadow 对比
        if legacy_verdict is not None:
            diverged = self.compare_with_legacy(nous_verdict, legacy_verdict)
            if diverged:
                self._write_shadow_alert(
                    tool_call=tool_call,
                    nous_verdict=nous_verdict,
                    legacy_verdict=legacy_verdict,
                    gate_result=result,
                    session_key=sk,
                )

        # shadow mode：只观测，不阻断
        if self.shadow_mode:
            return tool_call

        # primary mode：block → 真正拦截
        if nous_verdict == "block":
            rule_id = result.verdict.rule_id if result else "unknown"
            reason = result.verdict.reason if result else "blocked"
            raise BlockedByNous(rule_id=rule_id, reason=reason)

        return tool_call

    def compare_with_legacy(self, nous_verdict: str, legacy_verdict: str) -> bool:
        """
        对比 Nous 和旧引擎裁决是否一致。

        "一致"定义：两者都是 block，或两者都是非 block（allow/warn/confirm 等视为同级）。
        返回 True 表示不一致（diverged），False 表示一致。
        """
        nous_blocks = nous_verdict == "block"
        legacy_blocks = legacy_verdict == "block"
        return nous_blocks != legacy_blocks

    def _write_shadow_alert(
        self,
        tool_call: dict,
        nous_verdict: str,
        legacy_verdict: str,
        gate_result: Optional[GateResult],
        session_key: str,
    ) -> None:
        """将不一致 alert 追加写入 shadow_alerts.jsonl"""
        # 确保目录存在
        self.alert_log_path.parent.mkdir(parents=True, exist_ok=True)

        alert = {
            "ts": time.time(),
            "session_key": session_key,
            "tool_name": tool_call.get("tool_name") or tool_call.get("name", ""),
            "nous_verdict": nous_verdict,
            "legacy_verdict": legacy_verdict,
            "tool_call_summary": _summarize_tool_call(tool_call),
            "proof_trace": gate_result.proof_trace.to_dict() if gate_result else {},
        }

        try:
            with open(self.alert_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert, ensure_ascii=False) + "\n")
            logger.warning(
                "[gateway_hook] SHADOW ALERT: nous=%s legacy=%s tool=%s",
                nous_verdict,
                legacy_verdict,
                alert["tool_name"],
            )
        except Exception as e:
            logger.error("[gateway_hook] 写 shadow alert 失败: %s", e)

    # ── after_tool_call（M7.1a）──────────────────────────────────────────

    def after_tool_call(
        self,
        tool_call: dict,
        result: Any,
        session_key: Optional[str] = None,
    ) -> dict[str, int]:
        """
        在工具调用执行完成后运行 auto_extract，从结果中提取实体/关系。

        Args:
            tool_call:   工具调用 dict（同 before_tool_call 的输入）
            result:      工具执行结果（任意类型）
            session_key: 日志会话标识（可选）

        Returns:
            {"extracted": N}  其中 N 是写入 KG 的条目数
        """
        if not self.auto_extract_enabled:
            return {"extracted": 0}

        if self.db is None:
            logger.debug("[after_tool_call] no db, skip extract")
            return {"extracted": 0}

        if self.llm_fn is None:
            logger.debug("[after_tool_call] no llm_fn, skip extract")
            return {"extracted": 0}

        tool_name = tool_call.get("tool_name") or tool_call.get("name", "unknown")
        params = tool_call.get("params") or tool_call.get("arguments") or {}

        try:
            from nous.auto_extract import extract_from_tool_call

            # extract_from_tool_call 是 async，用 asyncio 运行
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if loop and loop.is_running():
                # 已有事件循环 — 创建 task（调用方需 await）
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    extract_result = pool.submit(
                        asyncio.run,
                        extract_from_tool_call(
                            tool_name=tool_name,
                            params=params,
                            result=result,
                            db=self.db,
                            llm_fn=self.llm_fn,
                        )
                    ).result(timeout=30)
            else:
                extract_result = asyncio.run(
                    extract_from_tool_call(
                        tool_name=tool_name,
                        params=params,
                        result=result,
                        db=self.db,
                        llm_fn=self.llm_fn,
                    )
                )

            # 记录提取日志
            extracted_count = extract_result.get("extracted", 0)
            if extracted_count > 0:
                self._write_extract_log(tool_name, extracted_count, session_key)

            return extract_result

        except Exception as exc:
            logger.warning("[after_tool_call] extract failed for %s: %s", tool_name, exc)
            return {"extracted": 0}

    def _write_extract_log(
        self,
        tool_name: str,
        extracted_count: int,
        session_key: Optional[str],
    ) -> None:
        """记录提取日志到 extract_log.jsonl"""
        self.extract_log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.time(),
            "tool_name": tool_name,
            "extracted": extracted_count,
            "session_key": session_key or "",
        }
        try:
            with open(self.extract_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("[gateway_hook] 写 extract_log 失败: %s", e)


# ── 辅助函数 ──────────────────────────────────────────────────────────────


def _summarize_tool_call(tool_call: dict, max_len: int = 100) -> str:
    """将 tool_call 摘要成不超过 max_len 字符的字符串"""
    try:
        s = json.dumps(tool_call, ensure_ascii=False)
    except Exception:
        s = str(tool_call)
    return s[:max_len] + ("..." if len(s) > max_len else "")
