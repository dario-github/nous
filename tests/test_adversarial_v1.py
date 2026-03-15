"""Adversarial regression tests (Loop 28) — datalog-only layer.

Note: These tests run without the semantic gate (no API calls).
The full benchmark with semantic gate is run via scripts/run_challenge_benchmark.py.

Datalog-only tests verify:
1. Benign adversarial cases are NEVER blocked by rules alone (FP prevention)
2. Harmful cases are documented as known evasion gaps (xfail)
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
from nous.gate import gate
from nous.triviality_filter import TrivialityConfig

CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"
ADV_PATH = Path(__file__).parent.parent / "data" / "challenge" / "adversarial_v1.json"


def _load_adversarial():
    if not ADV_PATH.exists():
        pytest.skip("adversarial_v1.json not found")
    with open(ADV_PATH) as f:
        return json.load(f)


def _run_gate_datalog_only(scenario: dict) -> bool:
    """Run gate WITHOUT semantic gate (datalog + triviality only)."""
    tcs = scenario_to_tool_calls(scenario)
    prompt = scenario.get("prompt", "")
    for tc in tcs:
        tc["params"]["content"] = prompt
        tc["params"]["full_prompt"] = prompt

    triv = TrivialityConfig()
    for tc in tcs:
        result = gate(tc, constraints_dir=CONSTRAINTS_DIR, triviality_config=triv)
        if result.verdict.action in ("block", "confirm"):
            return True
    return False


# === All harmful adversarial cases — xfail at datalog layer ===
# These require semantic gate (LLM intent analysis) to catch.
# xfail documents the gap; XPASS means datalog rules improved.

_ALL_HARMFUL_IDS = [f"adv-h{i:02d}" for i in range(1, 16)]


@pytest.mark.parametrize("case_id", _ALL_HARMFUL_IDS)
@pytest.mark.xfail(reason="Adversarial evasion: requires semantic gate for detection", strict=False)
def test_adversarial_harmful_xfail(case_id):
    """Harmful adversarial cases that evade datalog rules."""
    data = _load_adversarial()
    case = next((h for h in data["harmful"] if h["id"] == case_id), None)
    if case is None:
        pytest.skip(f"{case_id} not found")
    assert _run_gate_datalog_only(case) is True, f"{case_id} should be blocked"


# === Benign adversarial cases — HARD regression test ===
# These must NEVER be blocked by the FULL pipeline.
# Some may be blocked by datalog alone (marked as known_datalog_fp) — the
# semantic gate correctly overrides these. This tests datalog behavior only.

_ALL_BENIGN_IDS = [f"adv-b{i:02d}" for i in range(1, 16)]
# Benign cases blocked by datalog but correctly allowed by semantic gate
_KNOWN_DATALOG_FP = {"adv-b06", "adv-b15"}  # Weapons-category: legal gun shop, museum archive


@pytest.mark.parametrize("case_id", _ALL_BENIGN_IDS)
def test_adversarial_benign_never_blocked(case_id):
    """Benign adversarial cases must never be blocked by datalog rules."""
    data = _load_adversarial()
    case = next((b for b in data["benign"] if b["id"] == case_id), None)
    if case is None:
        pytest.skip(f"{case_id} not found")

    blocked = _run_gate_datalog_only(case)

    if case_id in _KNOWN_DATALOG_FP:
        if blocked:
            pytest.xfail(f"{case_id}: known datalog FP (semantic gate correctly overrides)")
        # If NOT blocked, great — datalog improved!
        return

    assert blocked is False, f"{case_id} is benign and must not be blocked"
