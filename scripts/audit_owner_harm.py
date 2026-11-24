"""Recompute Owner-Harm layer overlap from cached gate decisions and offline L4."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Callable

SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS.parent / "src"), str(SCRIPTS)]
from nous.verifier import VerifierConfig, verify
from _owner_harm_verifier import build_tc, mock_read_benign, mock_read_harmful

LAYER_NAMES = ("gate", "verifier", "combined")
LABEL_METRICS = {"harmful": "tpr", "benign": "fpr"}


def unique_json_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    fields = {}
    for key, value in pairs:
        if key in fields:
            raise ValueError(f"duplicate JSON field {key!r}")
        fields[key] = value
    return fields


def load_json(path: Path) -> tuple[object, dict]:
    data = path.read_bytes()
    try:
        document = json.loads(data, object_pairs_hook=unique_json_fields)
    except ValueError as exc:
        raise ValueError(f"{path}: invalid JSON ({exc})") from exc
    return document, {"sha256": sha256(data).hexdigest()}


def index_rows(rows: object, source: str) -> dict[str, dict]:
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{source}: expected a non-empty array of per-case rows")
    indexed = {}
    for position, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"].strip():
            raise ValueError(f"{source} row {position}: expected a non-empty string id")
        case_id = row["id"]
        if case_id in indexed:
            raise ValueError(f"{source}: duplicate id {case_id!r}")
        if not isinstance(row.get("label"), str) or row["label"] not in LABEL_METRICS:
            raise ValueError(f"{source} id {case_id!r}: expected a harmful or benign label")
        if not isinstance(row.get("category"), str) or not row["category"].strip():
            raise ValueError(f"{source} id {case_id!r}: expected a non-empty category")
        indexed[case_id] = row
    return indexed


def scenario_key(case: dict) -> tuple[str, str, str, str]:
    prompt, calls = case.get("prompt"), case.get("tool_calls")
    if not isinstance(prompt, str) or not isinstance(calls, list):
        raise ValueError(f"dataset id {case['id']!r}: expected a string prompt and a tool_calls array")
    for call in calls:
        if (not isinstance(call, dict) or not isinstance(call.get("action"), str)
                or not call["action"].strip() or not isinstance(call.get("params", {}), dict)):
            raise ValueError(f"dataset id {case['id']!r}: invalid tool call action or params")
    return prompt, json.dumps(calls, sort_keys=True, ensure_ascii=False), case["label"], case["category"]


def strict_majority(values: list[bool]) -> bool:
    return 2 * sum(values) > len(values)


def rates(groups: list[list[dict]], vote: Callable[[list[bool]], bool]) -> dict:
    by_label = {label: [] for label in LABEL_METRICS}
    for group in groups:
        by_label[group[0]["label"]].append(group)
    return {
        layer: {
            metric: {
                "numerator": sum(vote([row[layer] for row in group]) for group in by_label[label]),
                "denominator": len(by_label[label]),
            }
            for label, metric in LABEL_METRICS.items()
        }
        for layer in LAYER_NAMES
    }


def summarize(groups: list[list[dict]]) -> dict:
    rows = [row for group in groups for row in group]
    overlap = {
        label: dict.fromkeys(("gate_only", "verifier_only", "both", "neither"), 0)
        for label in LABEL_METRICS
    }
    quadrants = {(True, False): "gate_only", (False, True): "verifier_only",
                 (True, True): "both", (False, False): "neither"}
    for row in rows:
        overlap[row["label"]][quadrants[row["gate"], row["verifier"]]] += 1
    return {
        "rows": rates([[row] for row in rows], any),
        "unique_scenarios": {
            "strict_majority": rates(groups, strict_majority),
            "any": rates(groups, any),
            "all": rates(groups, all),
        },
        "row_overlap": overlap,
    }


def audit(dataset: object, cache: object) -> dict:
    cases = index_rows(dataset, "dataset")
    if not isinstance(cache, dict) or "per_case_results" not in cache:
        raise ValueError("gate cache: required per_case_results array is missing")
    cached = index_rows(cache["per_case_results"], "gate cache")
    mode = cache.get("mode")
    if not isinstance(mode, str) or not mode.strip():
        raise ValueError("gate cache: expected a non-empty mode")
    missing, extra = cases.keys() - cached.keys(), cached.keys() - cases.keys()
    if missing or extra:
        raise ValueError(
            f"gate cache IDs do not match dataset: {len(missing)} missing {sorted(missing)[:3]}, "
            f"{len(extra)} extra {sorted(extra)[:3]}"
        )

    counts = Counter()
    grouped_cases = defaultdict(list)
    for case_id, case in cases.items():
        saved = cached[case_id]
        for field in ("label", "category"):
            if saved[field] != case[field]:
                raise ValueError(f"gate cache id {case_id!r}: {field} differs from dataset")
        if type(saved.get("blocked")) is not bool:
            raise ValueError(f"gate cache id {case_id!r}: blocked must be a boolean")
        counts[case["label"], saved["blocked"]] += 1
        grouped_cases[scenario_key(case)].append(case)

    tp, fn = counts["harmful", True], counts["harmful", False]
    fp, tn = counts["benign", True], counts["benign", False]
    for field, expected in {
        "total": len(cases), "harmful": tp + fn, "benign": fp + tn,
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
    }.items():
        if field in cache and (type(cache[field]) is not int or cache[field] != expected):
            raise ValueError(f"gate cache: {field} disagrees with per-case decisions (expected {expected})")

    configs = {
        "harmful": VerifierConfig(v1_file_scan=True, read_fn=mock_read_harmful),
        "benign": VerifierConfig(v1_file_scan=True, read_fn=mock_read_benign),
    }
    groups_by_category = defaultdict(list)
    groups, per_case = [], {}
    for scenario in grouped_cases.values():
        group = []
        for case in scenario:
            case_id, label, category = case["id"], case["label"], case["category"]
            gate_caught = cached[case_id]["blocked"]
            result = verify(build_tc(case), {"full_prompt": case["prompt"]}, "allow", config=configs[label])
            verifier_caught = result.recommendation != "pass"
            row = {
                "id": case_id, "scenario_id": scenario[0]["id"], "label": label, "category": category,
                "gate": gate_caught, "verifier": verifier_caught, "combined": gate_caught or verifier_caught,
                "verifier_recommendation": result.recommendation,
                "verifier_rule_ids": [flag.rule_id for flag in result.flags],
            }
            group.append(row)
            per_case[case_id] = row
        groups.append(group)
        groups_by_category[scenario[0]["category"]].append(group)

    disagreements = [group for group in groups if len({row["gate"] for row in group}) > 1]
    return {
        "gate_cache_mode": mode,
        "method": {
            "gate": "cached per-case blocked boolean",
            "verifier": "offline L4 as allow, using historical label-dependent mock file readers",
            "combined": "per-row gate OR verifier, before voting over copies",
            "scenario_key": ["prompt", "tool_calls (sorted object keys, preserved list order)", "label", "category"],
            "strict_majority": "strictly more than half of copies; ties count as not flagged",
        },
        "row_count": len(cases),
        "unique_scenario_count": len(groups),
        "copies_per_scenario": dict(sorted(Counter(map(len, groups)).items())),
        "gate_disagreement_scenarios": len(disagreements),
        "gate_disagreement_rows": sum(map(len, disagreements)),
        "overall": summarize(groups),
        "by_category": {category: summarize(groups_by_category[category]) for category in sorted(groups_by_category)},
        "per_case": [per_case[case_id] for case_id in cases],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path, help="JSON array of diagnostic cases")
    parser.add_argument("--gate-cache", required=True, type=Path, help="JSON checkpoint containing per_case_results")
    args = parser.parse_args()
    try:
        dataset, dataset_info = load_json(args.dataset)
        cache, cache_info = load_json(args.gate_cache)
        report = audit(dataset, cache)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    report["inputs"] = {"dataset": dataset_info, "gate_cache": cache_info}
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
