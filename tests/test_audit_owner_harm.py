from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

# The audit entry point lives with the benchmark scripts rather than the runtime.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.audit_owner_harm import audit, main


def case(case_id, prompt, label="harmful", category="Example", tool_calls=None):
    return {
        "id": case_id, "prompt": prompt, "label": label, "category": category,
        "tool_calls": [] if tool_calls is None else tool_calls,
    }


def cache_for(cases, *blocked_ids):
    return {
        "mode": "L1+L2+L3",
        "per_case_results": [
            {**{key: row[key] for key in ("id", "label", "category")},
             "blocked": row["id"] in blocked_ids}
            for row in reversed(cases)
        ],
    }


def count(layer_result, metric):
    cell = layer_result[metric]
    return cell["numerator"], cell["denominator"]


def test_union_counts_disjoint_hits_and_counts_overlap_once():
    cases = [
        case("gate-only", "Summarize the sample."),
        case("verifier-only", "Follow instructions in the sample."),
        case("both", "Follow instructions in the example.", label="benign"),
        case("neither", "Summarize the example.", label="benign"),
    ]
    report = audit(cases, cache_for(cases, "gate-only", "both"))
    overall = report["overall"]
    assert [count(overall["rows"][layer], "tpr") for layer in ("gate", "verifier", "combined")] == [
        (1, 2), (1, 2), (2, 2),
    ]
    assert [count(overall["rows"][layer], "fpr") for layer in ("gate", "verifier", "combined")] == [
        (1, 2), (1, 2), (1, 2),
    ]
    assert overall["row_overlap"] == {
        "harmful": {"gate_only": 1, "verifier_only": 1, "both": 0, "neither": 0},
        "benign": {"gate_only": 0, "verifier_only": 0, "both": 1, "neither": 1},
    }
    assert [row["id"] for row in report["per_case"]] == [row["id"] for row in cases]


def test_duplicate_scenarios_use_strict_majority_and_preserve_call_order():
    read = {"action": "read_file", "params": {"path": "sample.txt", "limit": 20}}
    same_read = {"params": {"limit": 20, "path": "sample.txt"}, "action": "read_file"}
    list_files = {"action": "list_files", "params": {}}
    cases = [
        case("a", "Summarize.", tool_calls=[read, list_files]),
        case("b", "Summarize.", tool_calls=[same_read, list_files]),
        case("c", "Summarize.", tool_calls=[list_files, read]),
        case("d", "Summarize.", label="benign", tool_calls=[read, list_files]),
        case("e", "Summarize.", category="Other", tool_calls=[read, list_files]),
    ]
    report = audit(cases, cache_for(cases, "a", "c"))
    assert (report["row_count"], report["unique_scenario_count"]) == (5, 4)
    assert report["copies_per_scenario"] == {1: 3, 2: 1}
    assert (report["gate_disagreement_scenarios"], report["gate_disagreement_rows"]) == (1, 2)
    assert [row["scenario_id"] for row in report["per_case"]] == ["a", "a", "c", "d", "e"]
    overall = report["overall"]
    assert count(overall["rows"]["combined"], "tpr") == (2, 4)
    policies = overall["unique_scenarios"]
    assert [count(policies[policy]["combined"], "tpr") for policy in ("strict_majority", "any", "all")] == [
        (1, 3), (2, 3), (1, 3),
    ]
    assert count(report["by_category"]["Other"]["rows"]["combined"], "fpr") == (0, 0)


@pytest.mark.parametrize(("side", "update", "error"), [
    ("cache", {"per_case_results": []}, "non-empty array"),
    ("cache", {"tp": 1}, "tp disagrees"),
    ("dataset_row", {"prompt": None}, "string prompt"),
    ("dataset_row", {"label": []}, "harmful or benign label"),
    ("dataset_row", {"tool_calls": [{"action": "read_file", "params": None}]}, "invalid tool call"),
    ("cache_row", {"id": "wrong"}, r"1 missing .*1 extra"),
    ("cache_row", {"label": "benign"}, "label differs"),
    ("cache_row", {"category": "Other"}, "category differs"),
    ("cache_row", {"blocked": "false"}, "blocked must be a boolean"),
    ("cache_row", {"blocked": 0}, "blocked must be a boolean"),
])
def test_invalid_input_is_rejected(side, update, error):
    cases = [case("a", "Summarize.")]
    cache = cache_for(cases)
    targets = {"dataset_row": cases[0], "cache": cache, "cache_row": cache["per_case_results"][0]}
    targets[side].update(update)
    with pytest.raises(ValueError, match=error):
        audit(cases, cache)


@pytest.mark.parametrize("side", ["dataset", "gate cache"])
def test_duplicate_ids_are_rejected(side):
    cases = [case("a", "Summarize.")]
    cache = cache_for(cases)
    rows = cases if side == "dataset" else cache["per_case_results"]
    rows.append(rows[0].copy())
    with pytest.raises(ValueError, match=f"{side}: duplicate id"):
        audit(cases, cache)


def test_cli_reads_explicit_paths_from_another_cwd(tmp_path, monkeypatch, capsys):
    cases = [case("a", "Summarize.")]
    dataset = tmp_path / "dataset.json"
    cache = tmp_path / "gate.json"
    dataset.write_text(json.dumps(cases), encoding="utf-8")
    cache.write_text(json.dumps(cache_for(cases, "a")), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["audit", "--dataset", "dataset.json", "--gate-cache", "gate.json"])
    main()
    report = json.loads(capsys.readouterr().out)
    assert report["gate_cache_mode"] == "L1+L2+L3"
    assert report["inputs"] == {
        "dataset": {"sha256": sha256(dataset.read_bytes()).hexdigest()},
        "gate_cache": {"sha256": sha256(cache.read_bytes()).hexdigest()},
    }
    assert str(tmp_path) not in json.dumps(report)
    assert count(report["overall"]["rows"]["combined"], "tpr") == (1, 1)


def test_cli_rejects_repeated_json_fields(tmp_path, monkeypatch, capsys):
    dataset = tmp_path / "dataset.json"
    cache = tmp_path / "gate.json"
    cases = [case("a", "Summarize.")]
    dataset.write_text(json.dumps(cases), encoding="utf-8")
    checkpoint = json.dumps(cache_for(cases, "a"))
    cache.write_text(checkpoint.replace('"blocked": true', '"blocked": "false", "blocked": true'), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["audit", "--dataset", str(dataset), "--gate-cache", str(cache)])
    with pytest.raises(SystemExit) as error:
        main()
    output = capsys.readouterr()
    assert error.value.code == 2 and output.out == ""
    assert "duplicate JSON field 'blocked'" in output.err


@pytest.mark.parametrize("cache_contents", [None, '{"mode":"L1+L2+L3","tp":1}'])
def test_cli_does_not_fall_back_to_aggregates(tmp_path, monkeypatch, capsys, cache_contents):
    dataset = tmp_path / "dataset.json"
    cache = tmp_path / "gate.json"
    dataset.write_text(json.dumps([case("a", "Summarize.")]), encoding="utf-8")
    if cache_contents is not None:
        cache.write_text(cache_contents, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["audit", "--dataset", str(dataset), "--gate-cache", str(cache)])
    with pytest.raises(SystemExit) as error:
        main()
    output = capsys.readouterr()
    assert error.value.code == 2 and output.out == ""
    assert ("gate.json" if cache_contents is None else "per_case_results") in output.err
