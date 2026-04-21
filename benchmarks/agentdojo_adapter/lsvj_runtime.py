"""LSVJ-S 防御适配层 for AgentDojo.

LSVJFilteredRuntime: 继承 FunctionsRuntime；每次 tool 调用前
  (1) LLM 提议一条 Datalog rule (proposer)
  (2) 4-stage compile-time gate 审核
  (3) 用 AgentDojo-derived bindings 执行 rule
  (4) 综合 LLM 顶层裁决 + rule discharge → final verdict

设计要点：
- 复用 src/nous/lsvj/ 的 schema / synthesis / gate / compiler。
- 因为 AgentDojo 没有 Cozo KG，提供 AgentDojoEvaluator —— 从 tool_call
  和 session_context 里直接推 6 个 primitive 的取值（Class B 跑真实
  regex；Class A/C 走启发式 mock，记录 mock 结果以便后续 audit）。
- 与 NousFilteredRuntime 接口对齐 (configure / get_log)。
- FAIL_OPEN：proposer/gate 异常 → fall back to allow（不影响 utility）；
  decision_log 单独记 error 字段。
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Mapping, Sequence
from typing import Any, Optional

from agentdojo.functions_runtime import (
    FunctionReturnType,
    FunctionsRuntime,
    TaskEnvironment,
)

logger = logging.getLogger(__name__)

BLOCKED_RESULT = "[LSVJ_BLOCKED] 此工具调用已被 LSVJ-S 安全门控拦截。"

_KNOWN_INTERNAL_DOMAINS = {"company.com", "internal.local", "localhost"}
_AUTHORITY_COERCION_PATTERNS = [
    r"ignore\s+previous", r"system:.*override", r"as\s+admin",
    r"you\s+must", r"override\s+the", r"bypass.*restriction",
    r"new\s+instructions?:", r"important:.*override",
]
_INNER_CIRCLE_HINTS = ["@company.com", "boss", "ceo", "manager", "team lead"]


def _is_external_url(value: Any) -> bool:
    s = str(value).lower()
    if "@" in s:
        domain = s.rsplit("@", 1)[-1].split()[0].rstrip(">,;.")
        return domain not in _KNOWN_INTERNAL_DOMAINS
    if s.startswith(("http://", "https://", "//")):
        m = re.search(r"//([^/]+)", s)
        return bool(m and m.group(1).split(":")[0] not in _KNOWN_INTERNAL_DOMAINS)
    return False


def _has_authority_coercion(prompt: str) -> bool:
    p = (prompt or "").lower()
    return any(re.search(pat, p) for pat in _AUTHORITY_COERCION_PATTERNS)


def _is_inner_circle(recipient: str) -> bool:
    r = (recipient or "").lower()
    return any(hint in r for hint in _INNER_CIRCLE_HINTS)


class AgentDojoEvaluator:
    """Evaluator over the 6 owner-harm primitives, deriving truth values
    directly from the AgentDojo tool_call + session_context. Compatible
    with the lsvj.gate.Evaluator Protocol.
    """

    def __init__(self, tool_call: dict, session_context: list[dict] | None) -> None:
        self.tool_call = tool_call
        self.session_context = session_context or []
        self.params = tool_call.get("params", {})
        self._prompt_text = " ".join(
            str(m.get("content", "") if isinstance(m, dict) else m)
            for m in self.session_context
        )
        self.calls: list[dict] = []

    def evaluate(self, prim_id: str, args: Sequence[str], bindings: dict) -> bool:
        # If a binding for this primitive is already in `bindings`, prefer it
        # (this is how lsvj.gate's perturbation logic injects synthetic flips).
        if prim_id in bindings and isinstance(bindings[prim_id], bool):
            return bindings[prim_id]
        result = self._eval(prim_id, list(args))
        self.calls.append({"prim": prim_id, "args": list(args), "value": result})
        return result

    # Convenience callable wrapper for ad-hoc use in adapter
    def __call__(self, prim_id: str, args: Sequence[str]) -> bool:
        return self.evaluate(prim_id, args, {})

    def _resolve(self, name: str) -> Any:
        if name in self.params:
            return self.params[name]
        synonyms = {
            "payload": ("body", "content", "command", "text", "data"),
            "text": ("body", "content"),
            "command": ("cmd", "shell"),
            "target": ("to", "url", "recipient", "endpoint"),
            "recipient_id": ("to", "recipient", "target_email"),
            "prompt": None,
            "action_id": None,
            "message_body": ("body", "content", "text"),
            "url_or_target": ("url", "to", "endpoint"),
        }
        if name == "prompt":
            return self._prompt_text
        if name == "action_id":
            return self.tool_call.get("tool_name", "")
        for syn in synonyms.get(name, ()) or ():
            if syn in self.params:
                return self.params[syn]
        return ""

    def _eval(self, prim_id: str, args: list[str]) -> bool:
        if prim_id == "is_inner_circle":
            return _is_inner_circle(str(self._resolve(args[0])))
        if prim_id == "owner_has_directed":
            tool_name = self.tool_call.get("tool_name", "").lower()
            return tool_name in self._prompt_text.lower() if tool_name else False
        if prim_id == "payload_contains_regex":
            text = str(self._resolve(args[0]))
            pat = args[1].strip("\"'") if len(args) > 1 else ""
            try:
                return bool(re.search(pat, text, re.IGNORECASE))
            except re.error:
                return False
        if prim_id == "external_url":
            return _is_external_url(self._resolve(args[0]))
        if prim_id == "body_reveals_inner_relation":
            body = str(self._resolve(args[0]))
            rid = str(self._resolve(args[1]))
            return bool(rid) and rid.split("@")[0].lower() in body.lower()
        if prim_id == "authority_coercion_present":
            return _has_authority_coercion(str(self._resolve(args[0])))
        return False


def _to_nous_format(function: str, kwargs: Mapping[str, Any]) -> dict:
    return {"tool_name": function, "action": function, "params": dict(kwargs)}


class LSVJFilteredRuntime(FunctionsRuntime):
    """FunctionsRuntime that uses LSVJ-S synthesis + gate per tool call."""

    _proposer_provider: Any = None
    _model: str = "glm-4.7-flashx"
    _schema: Any = None
    _seeds: list[str] = []
    _log: list[dict] = []
    _user_goal: Optional[str] = None
    _upgrade_only: bool = True

    @classmethod
    def configure(
        cls,
        proposer_provider: Any,
        schema: Any,
        seeds: list[str],
        model: str = "glm-4.7-flashx",
        upgrade_only: bool = True,
    ) -> None:
        cls._proposer_provider = proposer_provider
        cls._schema = schema
        cls._seeds = list(seeds)
        cls._model = model
        cls._upgrade_only = upgrade_only

    @classmethod
    def set_user_goal(cls, goal: str) -> None:
        cls._user_goal = goal

    @classmethod
    def get_log(cls) -> list[dict]:
        return list(cls._log)

    @classmethod
    def reset_log(cls) -> None:
        cls._log = []

    def run_function(
        self,
        env: TaskEnvironment,
        function: str,
        kwargs: Mapping[str, Any],
        raise_on_error: bool = False,
    ) -> tuple[FunctionReturnType, str | None]:
        from nous.lsvj.synthesis import (
            build_synthesis_prompt,
            parse_synthesis_response,
            SynthesisResult,
        )
        from nous.lsvj.compiler import compile_check, parse_rule
        from nous.lsvj.gate import admit_rule, _execute_rule

        tool_call = _to_nous_format(function, kwargs)
        session_context: list[dict] = []
        if self.__class__._user_goal:
            session_context.append({"role": "user", "content": self.__class__._user_goal})

        verdict = "allow"
        gate_status = "default_allow"
        latency_ms = 0.0
        rule_text = ""
        admit_result_repr = ""
        error: str | None = None
        t_start = time.perf_counter()

        try:
            schema = self.__class__._schema
            seeds = self.__class__._seeds
            assert schema is not None and self.__class__._proposer_provider is not None, (
                "LSVJFilteredRuntime.configure() must be called before run_function"
            )
            prompt = build_synthesis_prompt(tool_call, session_context, schema, seeds)
            raw = self.__class__._proposer_provider(
                prompt, timeout_ms=300_000, model_override=self.__class__._model,
            )
            parsed = parse_synthesis_response(raw)
            if not isinstance(parsed, SynthesisResult):
                error = f"synth_parse_fail: {getattr(parsed, 'message', '?')[:80]}"
                gate_status = "synth_parse_fail"
            else:
                rule_text = parsed.synthesized_obligation.rule_body
                outer_decision = parsed.decision
                cc = compile_check(rule_text, schema)
                if not cc.passed:
                    error = f"compile_fail: {(cc.errors or ['?'])[0][:80]}"
                    gate_status = "compile_fail"
                    verdict = "confirm" if outer_decision == "allow" else outer_decision
                else:
                    parsed_rule = parse_rule(rule_text)
                    evaluator = AgentDojoEvaluator(tool_call, session_context)
                    # Pre-evaluate primitives to derive runtime bindings
                    bindings = {
                        c.prim_id: evaluator(c.prim_id, c.args)
                        for c in parsed_rule.calls
                    }
                    admission = admit_rule(rule_text, schema, bindings, evaluator, N=5)
                    admit_result_repr = (
                        f"admitted={admission.admitted}, "
                        f"reasons={admission.reasons[:2] if admission.reasons else []}"
                    )
                    if admission.admitted:
                        discharged = admission.discharged
                        if outer_decision == "allow" and discharged:
                            verdict = "allow"
                            gate_status = "lsvj_admitted_discharged"
                        elif outer_decision in ("block", "confirm"):
                            verdict = outer_decision
                            gate_status = f"lsvj_outer_{outer_decision}"
                        else:
                            verdict = "confirm"
                            gate_status = "lsvj_admitted_not_discharged"
                    else:
                        verdict = "confirm"
                        first_reason = (admission.reasons[0] if admission.reasons else "unknown")[:40]
                        gate_status = f"gate_reject:{first_reason}"
        except Exception as exc:
            logger.warning("LSVJ-S runtime error (fail-open): %s", exc)
            error = f"runtime: {type(exc).__name__}: {str(exc)[:100]}"
            verdict = "allow"
            gate_status = "fail_open_error"
        finally:
            latency_ms = (time.perf_counter() - t_start) * 1000

        LSVJFilteredRuntime._log.append({
            "function": function,
            "kwargs": dict(kwargs),
            "verdict": verdict,
            "gate_status": gate_status,
            "rule_text": rule_text[:200],
            "admit_result": admit_result_repr,
            "latency_ms": round(latency_ms, 1),
            "error": error,
        })

        if verdict in ("block", "confirm") and self.__class__._upgrade_only:
            return BLOCKED_RESULT, None

        return super().run_function(env, function, kwargs, raise_on_error=raise_on_error)
