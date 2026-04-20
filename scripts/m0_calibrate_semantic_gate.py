#!/usr/bin/env python3
"""M0 Sanity R003 — N-Calibration for lsvj.gate b.4 compound stage.

Given a hand-labeled 40-rule reference set at `data/n_calibration_reference_set.json`,
runs each rule through `lsvj.gate.admit_rule` at N in {3, 5, 7} and computes:

  - false_rejection_rate  : fraction of class-(i) rules rejected by b.4-A  (target <= 10%)
  - false_admission_rate  : fraction of class-(iii) rules admitted           (target <=  2%)
  - weak_admission_rate   : fraction of class-(ii) rules admitted            (directional)

Recommends the smallest N meeting both hard targets.

No LLM calls are made -- this is pure computation over the reference set JSON.

See docs/40-rule-reference-set-protocol.md for labeling procedure and pre-registration rules.

USAGE:
    # Real run (requires data/n_calibration_reference_set.json):
    python3 scripts/m0_calibrate_semantic_gate.py \\
        --reference-set data/n_calibration_reference_set.json \\
        --output docs/m0-n-calibration-results-2026-04-19.json

    # Dry-run (synthetic 10-rule set, no file needed):
    python3 scripts/m0_calibrate_semantic_gate.py \\
        --reference-set /tmp/nonexistent.json \\
        --dry-run

PRE-REGISTRATION:
    Use --seed-offset 100 for final locked metrics (seeds 0-9 were consumed during
    labeling per the protocol). See docs/40-rule-reference-set-protocol.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

# sys.path 与 scripts/run_owner_harm_benchmark.py 保持一致
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.lsvj.gate import admit_rule
from nous.lsvj.schema import load_schema_from_yaml


# ── 目标阈值 ─────────────────────────────────────────────────────────────────

FALSE_REJECTION_TARGET = 0.10   # class-(i): false-rejection rate <= 10%
FALSE_ADMISSION_TARGET = 0.02   # class-(iii): false-admission rate <= 2%

N_VALUES = [3, 5, 7]


# ── 合成参考集（dry-run 用）───────────────────────────────────────────────────

def _make_synthetic_reference_set(schema: Any) -> list[dict]:
    """生成 10 条合成规则：3 class-i + 4 class-ii + 3 class-iii。

    规则体从 schema 中取前两个原语构造，保证 compile_check 通过。
    仅用于 dry-run 管道验证，不代表真实校准结果。
    """
    prim_ids = [p.id for p in schema.primitives]
    if not prim_ids:
        # 极端退化：用占位符（compile_check 会失败，但管道不会崩溃）
        prim_ids = ["unknown_prim_a", "unknown_prim_b"]
    # 保证至少两个 id
    if len(prim_ids) == 1:
        prim_ids = prim_ids * 2

    p0, p1 = prim_ids[0], prim_ids[1]

    # class-(i): 两个原语 AND，任意一个翻转都改变 discharged
    body_i = f"{p0}(x), {p1}(y), discharged = {p0}(x) and {p1}(y)"
    # class-(ii): 宽松合取，p0 翻转影响弱
    body_ii = f"{p0}(x), {p1}(y), discharged = not {p0}(x) or {p1}(y)"
    # class-(iii): 只依赖 p1，p0 变化对 discharged 无影响
    body_iii = f"{p0}(x), {p1}(y), discharged = {p1}(y)"

    rules: list[dict] = []
    for i in range(3):
        rules.append({
            "id": f"syn_i_{i:02d}",
            "rule_class": "i",
            "flip_rate_10seeds": 0.90,
            "rule_body": body_i,
            "compile_pass": True,
            "author_note": "synthetic class-i for dry-run",
        })
    for i in range(4):
        rules.append({
            "id": f"syn_ii_{i:02d}",
            "rule_class": "ii",
            "flip_rate_10seeds": 0.20,
            "rule_body": body_ii,
            "compile_pass": True,
            "author_note": "synthetic class-ii for dry-run",
        })
    for i in range(3):
        rules.append({
            "id": f"syn_iii_{i:02d}",
            "rule_class": "iii",
            "flip_rate_10seeds": 0.00,
            "rule_body": body_iii,
            "compile_pass": True,
            "author_note": "synthetic class-iii for dry-run",
        })
    return rules


# ── 参考集加载 ────────────────────────────────────────────────────────────────

def _load_reference_set(
    path: str,
    dry_run: bool,
    schema: Any,
) -> tuple[list[dict], bool]:
    """加载参考集 JSON；文件不存在时 dry-run 返回合成存根，否则退出。

    Returns:
        (rules, is_synthetic)
    """
    p = Path(path)
    if not p.exists():
        if dry_run:
            print(f"[warn] reference set not found at {p}, using synthetic 10-rule stub")
            return _make_synthetic_reference_set(schema), True
        print(f"[error] reference set not found at {p}", file=sys.stderr)
        print("  Run labeling procedure first (docs/40-rule-reference-set-protocol.md)",
              file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[error] failed to read reference set: {e}", file=sys.stderr)
        sys.exit(1)

    # 支持裸列表或 {"rules": [...]} 格式
    if isinstance(data, list):
        rules = data
    elif isinstance(data, dict) and "rules" in data:
        rules = data["rules"]
    else:
        print(
            '[error] unrecognised format: expected JSON list or {"rules": [...]}',
            file=sys.stderr,
        )
        sys.exit(1)

    return rules, False


# ── 单条规则评估 ──────────────────────────────────────────────────────────────

def _evaluate_rule_at_n(
    rule: dict,
    schema: Any,
    n: int,
    seed_offset: int,
) -> dict[str, Any]:
    """对单条规则在给定 N 下运行 admit_rule，返回结果记录。

    bindings={} 意味着所有原语默认返回 False（最严格的基线）。
    seed_offset: final run 请使用 100+（pre-registration 要求）。
    """
    rule_id = str(rule.get("id", "unknown"))
    rule_class = str(rule.get("rule_class", "?"))
    rule_body = str(rule.get("rule_body", ""))

    result: dict[str, Any] = {
        "rule_id": rule_id,
        "rule_class": rule_class,
        "n": n,
        "admitted": False,
        "discharged": False,
        "decisive_primitives": [],
        "reasons": [],
        "error": None,
    }

    # compile_pass=False 的规则跳过（防御性检查）
    if not rule.get("compile_pass", True):
        result["error"] = "compile_pass=False in reference set; skipped"
        return result

    if not rule_body.strip():
        result["error"] = "empty rule_body"
        return result

    try:
        ar = admit_rule(
            rule_text=rule_body,
            schema=schema,
            bindings={},        # 空绑定：全原语默认 False
            evaluator=None,     # MockEvaluator（从 bindings 读取）
            N=n,
            seed=seed_offset,
        )
        result["admitted"] = ar.admitted
        result["discharged"] = ar.discharged
        result["decisive_primitives"] = ar.decisive_primitives
        result["reasons"] = ar.reasons
    except Exception as e:
        result["error"] = str(e)[:300]

    return result


# ── 聚合统计 ──────────────────────────────────────────────────────────────────

def _admission_rate(subset: list[dict], admitted_value: bool) -> float:
    if not subset:
        return 0.0
    return sum(1 for r in subset if r.get("admitted") == admitted_value) / len(subset)


def aggregate_by_n(all_results: list[dict], n: int) -> dict[str, Any]:
    """对给定 N 值聚合三类指标。"""
    n_results = [r for r in all_results if r["n"] == n]

    class_i   = [r for r in n_results if r["rule_class"] == "i"]
    class_ii  = [r for r in n_results if r["rule_class"] == "ii"]
    class_iii = [r for r in n_results if r["rule_class"] == "iii"]

    # false-rejection: class-(i) 中 admitted=False（gate 拒绝了内容敏感规则）
    false_rejection_rate = _admission_rate(class_i, admitted_value=False)
    # false-admission: class-(iii) 中 admitted=True（gate 放行了内容不变规则）
    false_admission_rate = _admission_rate(class_iii, admitted_value=True)
    # weak-admission: class-(ii) 中 admitted=True（方向指标）
    weak_admission_rate = _admission_rate(class_ii, admitted_value=True)

    gate_pass = (
        false_rejection_rate <= FALSE_REJECTION_TARGET
        and false_admission_rate <= FALSE_ADMISSION_TARGET
    )

    errors = [r for r in n_results if r.get("error")]

    return {
        "n": n,
        "false_rejection_rate": false_rejection_rate,
        "false_admission_rate": false_admission_rate,
        "weak_admission_rate": weak_admission_rate,
        "gate_pass": gate_pass,
        "counts": {
            "class_i_total":    len(class_i),
            "class_i_admitted": sum(1 for r in class_i if r.get("admitted")),
            "class_ii_total":    len(class_ii),
            "class_ii_admitted": sum(1 for r in class_ii if r.get("admitted")),
            "class_iii_total":    len(class_iii),
            "class_iii_admitted": sum(1 for r in class_iii if r.get("admitted")),
        },
        "error_count": len(errors),
    }


def recommend_n(aggregated: dict[int, dict]) -> int | None:
    """返回满足两个硬目标的最小 N；全部不满足则返回 None。"""
    for n in sorted(aggregated.keys()):
        if aggregated[n]["gate_pass"]:
            return n
    return None


# ── 主入口 ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="M0 Sanity R003 -- N-calibration for lsvj.gate b.4 compound stage",
    )
    parser.add_argument(
        "--reference-set",
        required=True,
        help="Path to hand-labeled reference set JSON (data/n_calibration_reference_set.json)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON report path (default: docs/m0-n-calibration-results-{today}.json)",
    )
    parser.add_argument(
        "--seed-offset",
        type=int,
        default=0,
        help=(
            "Seed offset passed to admit_rule. "
            "Use 100+ for final locked metrics (pre-registration; "
            "seeds 0-9 consumed during labeling). Default: 0"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use synthetic 10-rule set; validate pipeline end-to-end without any file",
    )
    args = parser.parse_args()

    # 默认输出路径
    if args.output is None:
        today = date.today().isoformat()
        args.output = str(
            Path(__file__).parent.parent / "docs" / f"m0-n-calibration-results-{today}.json"
        )

    # ── 加载 schema ──────────────────────────────────────────────────────────
    schema_path = (
        Path(__file__).parent.parent / "ontology" / "schema" / "owner_harm_primitives.yaml"
    )
    if not schema_path.exists():
        print(f"[error] schema not found at {schema_path}", file=sys.stderr)
        return 1

    try:
        schema = load_schema_from_yaml(str(schema_path))
    except Exception as e:
        print(f"[error] failed to load schema: {e}", file=sys.stderr)
        return 1

    # ── 加载参考集 ───────────────────────────────────────────────────────────
    rules, is_synthetic = _load_reference_set(args.reference_set, args.dry_run, schema)

    # 统计类别分布
    class_counts: dict[str, int] = {"i": 0, "ii": 0, "iii": 0}
    skipped_count = 0
    for r in rules:
        rc = r.get("rule_class")
        if rc in class_counts:
            class_counts[rc] += 1
        if not r.get("compile_pass", True):
            skipped_count += 1

    if args.dry_run:
        print(f"[dry-run] schema loaded: {len(schema.primitives)} primitives")
        print(f"[dry-run] reference set: {'synthetic' if is_synthetic else 'real'} "
              f"({len(rules)} rules — "
              f"class-i={class_counts['i']}, class-ii={class_counts['ii']}, class-iii={class_counts['iii']})")
        print(f"[dry-run] N values: {N_VALUES}")
        print(f"[dry-run] seed_offset: {args.seed_offset}")
        print("[dry-run] no LLM calls -- pure computation over reference set")
    else:
        print(f"Reference set: {len(rules)} rules  "
              f"(class-i={class_counts['i']}, "
              f"class-ii={class_counts['ii']}, "
              f"class-iii={class_counts['iii']})")
        if skipped_count:
            print(f"[warn] {skipped_count} rules skipped (compile_pass=False)")

    # ── 主评估ループ（no LLM calls）──────────────────────────────────────────
    all_results: list[dict] = []
    for n in N_VALUES:
        for rule in rules:
            r = _evaluate_rule_at_n(rule, schema, n, seed_offset=args.seed_offset)
            all_results.append(r)

    # ── 聚合 ─────────────────────────────────────────────────────────────────
    aggregated: dict[int, dict] = {n: aggregate_by_n(all_results, n) for n in N_VALUES}
    rec_n = recommend_n(aggregated)

    # ── 写报告 ───────────────────────────────────────────────────────────────
    report: dict[str, Any] = {
        "created": date.today().isoformat(),
        "reference_set": args.reference_set,
        "is_synthetic": is_synthetic,
        "seed_offset": args.seed_offset,
        "n_values_tested": N_VALUES,
        "targets": {
            "false_rejection_rate_max": FALSE_REJECTION_TARGET,
            "false_admission_rate_max": FALSE_ADMISSION_TARGET,
        },
        "recommended_n": rec_n,
        "results_by_n": {str(n): aggregated[n] for n in N_VALUES},
        "rules_detail": all_results,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))

    # ── 打印汇总表 ────────────────────────────────────────────────────────────
    prefix = "[dry-run] " if args.dry_run else ""
    print(f"\n{prefix}Wrote report to {args.output}\n")
    print(f"{'N':>4}  {'false_rej':>10}  {'false_adm':>10}  {'weak_adm':>9}  {'gate':>6}")
    print("-" * 50)
    for n in N_VALUES:
        ag = aggregated[n]
        mark = "  <-- recommended" if n == rec_n else ""
        print(
            f"{n:>4}  "
            f"{ag['false_rejection_rate']:>9.1%}  "
            f"{ag['false_admission_rate']:>9.1%}  "
            f"{ag['weak_admission_rate']:>8.1%}  "
            f"{'PASS' if ag['gate_pass'] else 'FAIL':>6}"
            f"{mark}"
        )

    print()
    if rec_n is not None:
        print(f"Recommended N = {rec_n}  (smallest N meeting both hard targets)")
    else:
        print(
            "WARNING: no N in {3, 5, 7} meets both hard targets.\n"
            f"  false_rejection target : <= {FALSE_REJECTION_TARGET:.0%}\n"
            f"  false_admission target : <= {FALSE_ADMISSION_TARGET:.0%}\n"
            "  -> Document closest result and escalate before proceeding to M1."
        )

    if args.dry_run:
        print("\n[dry-run] setup OK")

    return 0


if __name__ == "__main__":
    sys.exit(main())
