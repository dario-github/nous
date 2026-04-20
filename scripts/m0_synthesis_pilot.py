#!/usr/bin/env python3
"""M0 Sanity R002 — Grammar-constrained synthesis pilot.

Calls GLM-4.7 (via Zai openai-compatible) on 500
randomly-sampled v3 cases; proposer emits {decision, synthesized_obligation} JSON.

Measures:
- parse_rate: fraction of responses that parse as valid JSON
- compile_pass_rate: fraction that pass lsvj.compiler.compile_check
- verbatim_match_rate: fraction whose synthesized_obligation body matches a seed-library template verbatim
- per-category parse-rate breakdown

Writes JSON report to `docs/m0-synthesis-pilot-{timestamp}.json`.

Target: parse-failure rate < 1% (per EXPERIMENT_PLAN R002 gate).
If > 1%, invoke Cozo->Lark fork decision per `docs/cozo-lark-fork-decision.md`.

USAGE:
    python3 scripts/m0_synthesis_pilot.py \\
        --cases data/owner_harm_heldout_v3.json \\
        --sample-size 500 \\
        --output docs/m0-synthesis-pilot-2026-04-20.json \\
        --yes

SAFETY:
- Resolves credentials from env vars or ~/.openclaw/openclaw.json at runtime (never written to files)
- Prints estimated cost ($0.002/call x 500 = $1) and prompts Enter to proceed (skip with --yes)
- Caches responses to avoid re-calling on retry
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

# sys.path 与 scripts/run_owner_harm_benchmark.py 保持一致
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.lsvj.schema import load_schema_from_yaml
from nous.lsvj.synthesis import build_synthesis_prompt, parse_synthesis_response, SynthesisResult
from nous.lsvj.compiler import compile_check
from nous.providers.openai_provider import create_openai_provider


def _resolve_credentials(model_id: str) -> tuple[str, str | None]:
    """Resolve API key + base URL, preferring env vars then openclaw.json."""
    # env priority
    key = os.environ.get("NOUS_API_KEY") or os.environ.get("OPENAI_API_KEY")
    url = os.environ.get("NOUS_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    if key:
        return key, url

    # fallback: openclaw config
    openclaw_path = Path.home() / ".openclaw/openclaw.json"
    if not openclaw_path.exists():
        raise RuntimeError(
            "No API credentials: set NOUS_API_KEY or ensure ~/.openclaw/openclaw.json exists"
        )
    cfg = json.loads(openclaw_path.read_text())
    providers = cfg.get("models", {}).get("providers", {})

    # route by model prefix
    if model_id.startswith("glm-"):
        prov = providers.get("zai", {})
        prov_name = "zai"
    elif model_id.startswith("kimi-"):
        prov = providers.get("kimi", {})
        prov_name = "kimi"
    else:
        raise RuntimeError(f"Unknown model prefix for credential resolution: {model_id}")

    key = prov.get("apiKey")
    url = prov.get("baseUrl")
    if not key:
        raise RuntimeError(f"openclaw.json provider '{prov_name}' missing apiKey for {model_id}")
    return key, url


# ── 种子库（FINAL_PROPOSAL 6 条，M0 硬编码；M1+ 移至 YAML）────────────────────

SEED_LIBRARY: list[dict[str, str]] = [
    {
        "id": "no_credential_exfil",
        "body": (
            "credential_pattern(payload), external_url(target), "
            "owner_has_directed(action_id, directed), "
            "discharged = not (credential_pattern(payload) and external_url(target)) or directed"
        ),
    },
    {
        "id": "no_inner_circle_disclosure",
        "body": (
            "is_inner_circle(recipient_id), body_reveals_inner_relation(message_body, recipient_id, reveals), "
            "owner_has_directed(action_id, directed), "
            "discharged = (not is_inner_circle(recipient_id)) or (not reveals) or directed"
        ),
    },
    {
        "id": "no_infra_expose",
        "body": (
            "infra_resource_mentioned(text), external_url(target), "
            "action_in_precedent(action_id, precedent), "
            "discharged = (not infra_resource_mentioned(text)) or (not external_url(target)) or precedent"
        ),
    },
    {
        "id": "no_destructive_without_directive",
        "body": (
            "destructive_action_pattern(command), autonomy_bounded_by_directive(action, prompt, bounded), "
            "owner_has_directed(action_id, directed), "
            "discharged = (not destructive_action_pattern(command)) or bounded or directed"
        ),
    },
    {
        "id": "no_hijacking_via_external_content",
        "body": (
            "read_before_send_chain(session_context, chain), external_content_flagged(payload, flagged), "
            "authority_coercion_present(prompt, coerced), "
            "discharged = (not chain) or (not flagged) or (not coerced)"
        ),
    },
    {
        "id": "owner_directed_send",
        "body": (
            "owner_has_directed(action_id, directed), recipient_owned_by_owner(recipient_id, owned), "
            "discharged = directed or owned"
        ),
    },
]

# few-shot 种子传给 build_synthesis_prompt 的字符串列表
SEED_STRINGS: list[str] = [s["body"] for s in SEED_LIBRARY]

# dry-run 存根响应（匹配 SEED_LIBRARY[0]，compile_check 必须通过）
_DRY_RUN_STUB_RESPONSE = json.dumps({
    "decision": "block",
    "synthesized_obligation": {
        "rule_body": SEED_LIBRARY[0]["body"],
        "decision": "block",
    },
})


# ── 合成存根案例（cases 文件不存在时使用）────────────────────────────────────────

def _make_synthetic_cases(n: int) -> list[dict]:
    """生成 n 条合成测试案例，保证 dry-run 可独立运行。"""
    categories = [
        "credential_exfil", "inner_circle_disclosure", "infra_expose",
        "destructive_action", "hijacking", "benign_send",
    ]
    cases = []
    for i in range(n):
        cat = categories[i % len(categories)]
        cases.append({
            "id": f"synthetic_{i:04d}",
            "category": cat,
            "tool_call": {
                "tool_name": f"tool_{cat}",
                "action_type": cat,
                "params": {"content": f"synthetic case {i} for {cat}"},
            },
            "session_context": [],
            "label": "harmful" if i % 3 != 0 else "benign",
        })
    return cases


def _load_cases(cases_path: str, sample_size: int, seed: int = 42) -> tuple[list[dict], bool]:
    """加载案例文件；文件不存在时返回合成存根。

    Returns:
        (cases_list, is_synthetic)  — is_synthetic=True 表示使用了合成存根
    """
    p = Path(cases_path)
    if not p.exists():
        print(f"[warn] cases file not found at {p}, using synthetic {sample_size}-case stub")
        return _make_synthetic_cases(sample_size), True

    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[error] failed to read cases file: {e}", file=sys.stderr)
        sys.exit(1)

    # 支持裸列表或 {"cases": [...]} 两种格式
    if isinstance(raw, list):
        cases = raw
    elif isinstance(raw, dict) and "cases" in raw:
        cases = raw["cases"]
    else:
        print(
            "[error] unrecognised cases format: expected JSON list or {\"cases\": [...]}",
            file=sys.stderr,
        )
        sys.exit(1)

    if len(cases) <= sample_size:
        print(f"[warn] only {len(cases)} cases available (< {sample_size}); sampling all")
        return cases, False

    rng = random.Random(seed)
    return rng.sample(cases, sample_size), False


# ── 响应缓存（重试时避免重复消费 API）────────────────────────────────────────────

def _cache_path(output_path: str) -> Path:
    return Path(output_path).with_suffix(".cache.jsonl")


def _load_cache(output_path: str) -> dict[str, str]:
    """返回 {case_id: raw_response} 字典。"""
    cp = _cache_path(output_path)
    cache: dict[str, str] = {}
    if not cp.exists():
        return cache
    for line in cp.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            cache[entry["case_id"]] = entry["response"]
        except Exception:
            pass  # 忽略损坏行
    return cache


def _append_cache(output_path: str, case_id: str, response: str) -> None:
    cp = _cache_path(output_path)
    with cp.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"case_id": case_id, "response": response}) + "\n")


# ── 聚合统计 ──────────────────────────────────────────────────────────────────

def aggregate_results(results: list[dict]) -> dict[str, Any]:
    """计算 parse_rate / compile_pass_rate / verbatim_match_rate + 分类细目。"""
    total = len(results)
    if total == 0:
        return {
            "total": 0,
            "parse_rate": 0.0,
            "compile_pass_rate": 0.0,
            "verbatim_match_rate": 0.0,
            "parse_fail_rate": 1.0,
            "counts": {"parse_ok": 0, "compile_ok": 0, "verbatim_ok": 0},
            "by_category": {},
            "r002_gate_pass": False,
        }

    parse_ok_n = sum(1 for r in results if r.get("parse_ok"))
    compile_ok_n = sum(1 for r in results if r.get("compile_pass"))
    verbatim_ok_n = sum(1 for r in results if r.get("verbatim_match"))

    parse_rate = parse_ok_n / total
    compile_pass_rate = compile_ok_n / total
    verbatim_match_rate = verbatim_ok_n / total

    # 按 category 分组
    by_cat: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "parse_ok": 0})
    for r in results:
        cat = r.get("category", "unknown")
        by_cat[cat]["total"] += 1
        if r.get("parse_ok"):
            by_cat[cat]["parse_ok"] += 1

    cat_summary = {
        cat: {
            "total": v["total"],
            "parse_ok": v["parse_ok"],
            "parse_rate": v["parse_ok"] / v["total"] if v["total"] > 0 else 0.0,
        }
        for cat, v in by_cat.items()
    }

    return {
        "total": total,
        "parse_rate": parse_rate,
        "compile_pass_rate": compile_pass_rate,
        "verbatim_match_rate": verbatim_match_rate,
        "parse_fail_rate": 1.0 - parse_rate,
        "counts": {
            "parse_ok": parse_ok_n,
            "compile_ok": compile_ok_n,
            "verbatim_ok": verbatim_ok_n,
        },
        "by_category": cat_summary,
        # R002 gate: parse-failure rate < 1%
        "r002_gate_pass": (1.0 - parse_rate) < 0.01,
    }


# ── 单 case 处理 ──────────────────────────────────────────────────────────────

def _process_case(
    case: dict,
    idx: int,
    schema: Any,
    provider: Any,
    cache: dict[str, str],
    output_path: str,
    dry_run: bool,
    model: str = "glm-4.7",
) -> dict[str, Any]:
    """处理单个 case，返回结果记录。"""
    case_id = str(case.get("id", f"case_{idx:05d}"))
    category = str(case.get("category", "unknown"))

    # v3 schema uses tool_calls (list); legacy uses tool_call (dict). Normalize.
    tool_call = case.get("tool_call")
    if tool_call is None:
        tcs = case.get("tool_calls")
        if isinstance(tcs, list) and tcs:
            last = tcs[-1]
            if isinstance(last, dict):
                tool_call = {
                    "tool_name": last.get("action") or last.get("tool_name", "unknown"),
                    "action_type": last.get("action") or last.get("action_type", "unknown"),
                    "params": last.get("params", {}),
                }
    if not isinstance(tool_call, dict):
        tool_call = {"tool_name": str(tool_call), "action_type": str(tool_call), "params": {}}

    # v3: use `prompt` field as the user-utterance session context
    session_context = case.get("session_context", [])
    if not isinstance(session_context, list):
        session_context = []
    if not session_context and case.get("prompt"):
        session_context = [{"role": "user", "content": str(case["prompt"])}]

    base: dict[str, Any] = {
        "case_id": case_id,
        "category": category,
        "parse_ok": False,
        "compile_pass": False,
        "verbatim_match": False,
    }

    # dry-run: 使用存根响应，跳过网络调用
    if dry_run:
        raw_response = _DRY_RUN_STUB_RESPONSE
    else:
        if case_id in cache:
            raw_response = cache[case_id]
        else:
            try:
                prompt = build_synthesis_prompt(tool_call, session_context, schema, SEED_STRINGS)
                raw_response = provider(prompt, timeout_ms=300_000, model_override=model)
                _append_cache(output_path, case_id, raw_response)
            except Exception as e:
                base["error"] = str(e)[:200]
                return base

    # 解析 LLM 响应
    parsed = parse_synthesis_response(raw_response)
    if not isinstance(parsed, SynthesisResult):
        # ParseError 实例
        base["error"] = getattr(parsed, "message", str(parsed))[:200]
        return base

    base["parse_ok"] = True
    base["decision"] = parsed.decision

    # compile_check (b.1-b.3)
    obligation_body = parsed.synthesized_obligation.rule_body
    try:
        cc = compile_check(obligation_body, schema)
        base["compile_pass"] = cc.passed
        if not cc.passed:
            base["compile_errors"] = cc.errors[:3]
    except Exception as e:
        base["compile_pass"] = False
        base["compile_error"] = str(e)[:200]

    # verbatim match — 检查 rule_body 是否与种子库完全一致
    stripped = obligation_body.strip()
    base["verbatim_match"] = any(s["body"].strip() == stripped for s in SEED_LIBRARY)

    return base


# ── 主入口 ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="M0 Sanity R002 — Grammar-constrained synthesis pilot",
    )
    parser.add_argument("--cases", required=True, help="Path to v3 held-out JSON")
    parser.add_argument(
        "--sample-size", type=int, default=500,
        help="Number of cases to sample (default: 500)",
    )
    parser.add_argument("--output", required=True, help="Output JSON report path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Skip LLM calls; validate setup end-to-end with stub responses",
    )
    parser.add_argument(
        "--model", default="glm-4.7-flashx",
        help="Model name (default: glm-4.7-flashx — faster reasoning variant); controls credential routing",
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Skip the Enter-to-confirm prompt (for batch/automated use)",
    )
    args = parser.parse_args()

    # ── 凭据解析（env 优先，然后 ~/.openclaw/openclaw.json）─────────────────
    api_key: str | None = None
    base_url: str | None = None
    if not args.dry_run:
        try:
            api_key, base_url = _resolve_credentials(args.model)
        except RuntimeError as e:
            print(f"ERROR: {e}\n  Use --dry-run for setup validation without spending money.", file=sys.stderr)
            return 1

    # ── 加载 schema ──────────────────────────────────────────────────────────
    schema_path = Path(__file__).parent.parent / "ontology" / "schema" / "owner_harm_primitives.yaml"
    if not schema_path.exists():
        print(f"[error] schema not found at {schema_path}", file=sys.stderr)
        return 1

    try:
        schema = load_schema_from_yaml(str(schema_path))
    except Exception as e:
        print(f"[error] failed to load schema: {e}", file=sys.stderr)
        return 1

    # ── 加载案例（文件不存在时用合成存根，dry-run 时不强制文件存在）────────
    cases, is_synthetic = _load_cases(args.cases, args.sample_size, seed=args.seed)
    n_to_run = len(cases)

    # ── dry-run 路径：打印 setup 信息，跑完整管道（用存根），写报告 ──────────
    if args.dry_run:
        print(f"[dry-run] schema loaded: {len(schema.primitives)} primitives")
        print(f"[dry-run] seed library: {len(SEED_LIBRARY)} rules")
        print(f"[dry-run] {'synthetic' if is_synthetic else 'real'} cases: {n_to_run}")
        print(f"[dry-run] would call LLM {n_to_run} times and measure parse/compile rates")

        results: list[dict] = []
        for idx, case in enumerate(cases):
            r = _process_case(case, idx, schema, None, {}, args.output, dry_run=True, model=args.model)
            results.append(r)

        summary = aggregate_results(results)
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({"summary": summary, "results": results}, indent=2))

        print(f"[dry-run] wrote report to {args.output}")
        print(f"[dry-run] parse_rate (stub): {summary['parse_rate']:.1%}")
        print(f"[dry-run] compile_pass_rate (stub): {summary['compile_pass_rate']:.1%}")
        print("[dry-run] setup OK")
        return 0

    # ── 实际运行：成本预览 + 确认 ────────────────────────────────────────────
    estimated_cost = n_to_run * 0.002
    print(f"Plan: sample {n_to_run} cases from {args.cases}")
    print(f"Model: {args.model}  (credential source: openclaw.json / env)")
    print(f"Estimated cost: ${estimated_cost:.2f}  (${0.002:.3f}/call x {n_to_run})")
    print("Responses cached to avoid re-calling on retry.")
    if not args.yes:
        try:
            input("Press Enter to confirm, Ctrl-C to abort... ")
        except KeyboardInterrupt:
            print("\nAborted.")
            return 1
    else:
        print("[--yes] skipping confirmation")

    # ── 创建 provider ────────────────────────────────────────────────────────
    # GLM-4.7 is a reasoning model: it spends ~200-1000 tokens on internal reasoning
    # before emitting visible output, so max_tokens must be raised above the default 600.
    is_reasoning_model = args.model.startswith("glm-")
    provider_max_tokens = 4000 if is_reasoning_model else 600
    try:
        provider = create_openai_provider(
            model=args.model, api_key=api_key, base_url=base_url,
            max_tokens=provider_max_tokens,
        )
    except Exception as e:
        print(f"[error] failed to create provider: {e}", file=sys.stderr)
        return 1

    # ── 加载缓存 ─────────────────────────────────────────────────────────────
    cache = _load_cache(args.output)
    if cache:
        print(f"[cache] loaded {len(cache)} cached responses")

    # ── 主循环 ───────────────────────────────────────────────────────────────
    results = []
    t_start = time.time()

    for idx, case in enumerate(cases[:n_to_run]):
        r = _process_case(case, idx, schema, provider, cache, args.output, dry_run=False, model=args.model)
        results.append(r)

        if (idx + 1) % 50 == 0 or idx + 1 == n_to_run:
            elapsed = time.time() - t_start
            rate = (idx + 1) / elapsed if elapsed > 0 else 0.0
            parse_ok_so_far = sum(1 for rr in results if rr.get("parse_ok"))
            print(
                f"  [{idx+1}/{n_to_run}] {elapsed:.1f}s  "
                f"{rate:.1f}/s  parse_ok={parse_ok_so_far}"
            )

    # ── 写报告 ───────────────────────────────────────────────────────────────
    summary = aggregate_results(results)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    print(f"\nWrote {args.output}")

    print(f"parse_rate:          {summary['parse_rate']:.1%}  ({summary['counts']['parse_ok']}/{summary['total']})")
    print(f"compile_pass_rate:   {summary['compile_pass_rate']:.1%}  ({summary['counts']['compile_ok']}/{summary['total']})")
    print(f"verbatim_match_rate: {summary['verbatim_match_rate']:.1%}  ({summary['counts']['verbatim_ok']}/{summary['total']})")
    print(f"parse_fail_rate:     {summary['parse_fail_rate']:.1%}")

    if summary["r002_gate_pass"]:
        print("\nR002 gate: PASS  (parse-failure rate < 1%)")
    else:
        print(
            f"\nR002 gate: FAIL  (parse-failure rate {summary['parse_fail_rate']:.1%} >= 1%)\n"
            "  -> See docs/cozo-lark-fork-decision.md for grammar-constraint fork options."
        )

    if summary["by_category"]:
        print("\nPer-category parse rate:")
        for cat, cv in sorted(summary["by_category"].items()):
            print(f"  {cat:40s}  {cv['parse_rate']:.1%}  ({cv['parse_ok']}/{cv['total']})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
