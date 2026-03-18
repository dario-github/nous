"""Loop 44: Semantic Gate repeat=3 多数投票测试。"""
import pytest
from src.nous.semantic_gate import SemanticGateConfig, semantic_gate


# ── Mock Providers ────────────────────────────────────────────────────────────

def _make_fixed_provider(action: str, confidence: float = 0.85):
    """每次都返回相同结果的 provider。"""
    def provider(prompt: str, timeout_ms: int, model: str) -> str:
        return f'{{"action": "{action}", "reason": "test", "confidence": {confidence}}}'
    return provider


def _make_alternating_provider(responses: list[str]):
    """轮流返回不同结果的 provider（模拟随机性）。"""
    state = {"i": 0}
    def provider(prompt: str, timeout_ms: int, model: str) -> str:
        r = responses[state["i"] % len(responses)]
        state["i"] += 1
        return r
    return provider


def _make_failing_provider(fail_after: int):
    """前 N 次成功，之后抛出异常。"""
    state = {"calls": 0}
    def provider(prompt: str, timeout_ms: int, model: str) -> str:
        state["calls"] += 1
        if state["calls"] > fail_after:
            raise RuntimeError("provider timeout")
        return '{"action": "allow", "reason": "test", "confidence": 0.8}'
    return provider


# ── 单次调用（repeat=1，原有行为）─────────────────────────────────────────────

def test_single_call_allow():
    """repeat=1 时 allow 结果正确传递。"""
    cfg = SemanticGateConfig(
        enabled=True, mode="active",
        provider=_make_fixed_provider("allow"),
        repeat=1,
    )
    result = semantic_gate({"name": "read_file", "content": "test"}, {}, "allow", config=cfg)
    assert result is not None
    assert result["action"] == "allow"


def test_single_call_block():
    """repeat=1 时 block 结果正确传递。"""
    cfg = SemanticGateConfig(
        enabled=True, mode="active",
        provider=_make_fixed_provider("block", 0.95),
        repeat=1,
    )
    result = semantic_gate({"name": "exec", "content": "rm -rf /"}, {}, "block", config=cfg)
    assert result is not None
    assert result["action"] == "block"
    assert result["confidence"] == 0.95


# ── 多数投票（repeat=3）──────────────────────────────────────────────────────

def test_majority_vote_unanimous():
    """3/3 一致 block → block，置信度为均值。"""
    cfg = SemanticGateConfig(
        enabled=True, mode="active",
        provider=_make_fixed_provider("block", 0.90),
        repeat=3,
    )
    result = semantic_gate({"name": "exec", "content": "malware"}, {}, "allow", config=cfg)
    assert result is not None
    assert result["action"] == "block"
    assert abs(result["confidence"] - 0.90) < 0.001


def test_majority_vote_2_1_block():
    """2 block + 1 allow → block（多数方）。"""
    responses = [
        '{"action": "block", "reason": "harmful", "confidence": 0.92}',
        '{"action": "allow", "reason": "benign", "confidence": 0.60}',
        '{"action": "block", "reason": "harmful", "confidence": 0.88}',
    ]
    cfg = SemanticGateConfig(
        enabled=True, mode="active",
        provider=_make_alternating_provider(responses),
        repeat=3,
    )
    result = semantic_gate({"name": "exec", "content": "test"}, {}, "allow", config=cfg)
    assert result is not None
    assert result["action"] == "block"
    # 置信度 = (0.92 + 0.88) / 2 = 0.90
    assert abs(result["confidence"] - 0.90) < 0.001


def test_majority_vote_2_1_allow():
    """2 allow + 1 block → allow（多数方）。"""
    responses = [
        '{"action": "allow", "reason": "safe", "confidence": 0.85}',
        '{"action": "block", "reason": "suspicious", "confidence": 0.75}',
        '{"action": "allow", "reason": "safe", "confidence": 0.80}',
    ]
    cfg = SemanticGateConfig(
        enabled=True, mode="active",
        provider=_make_alternating_provider(responses),
        repeat=3,
    )
    result = semantic_gate({"name": "read_file", "content": "logs"}, {}, "allow", config=cfg)
    assert result is not None
    assert result["action"] == "allow"
    # 置信度 = (0.85 + 0.80) / 2 = 0.825
    assert abs(result["confidence"] - 0.825) < 0.001


def test_majority_vote_partial_failure():
    """1 成功 + 2 失败 → 使用唯一成功结果（不报错）。"""
    cfg = SemanticGateConfig(
        enabled=True, mode="active",
        provider=_make_failing_provider(fail_after=1),
        repeat=3,
    )
    result = semantic_gate({"name": "read_file", "content": "ok"}, {}, "allow", config=cfg)
    assert result is not None
    assert result["action"] == "allow"


def test_majority_vote_all_fail_open():
    """全部失败 → FAIL_OPEN (None)，不中断 pipeline。"""
    def always_fail(prompt, timeout_ms, model):
        raise RuntimeError("network error")

    cfg = SemanticGateConfig(
        enabled=True, mode="active",
        provider=always_fail,
        repeat=3,
    )
    result = semantic_gate({"name": "exec", "content": "test"}, {}, "allow", config=cfg)
    assert result is None  # FAIL_OPEN


def test_majority_vote_latency_accumulates():
    """repeat=3 时 latency_ms 应大于单次调用（串行调用）。"""
    import time
    call_count = {"n": 0}
    def slow_provider(prompt, timeout_ms, model):
        call_count["n"] += 1
        time.sleep(0.01)
        return '{"action": "allow", "reason": "ok", "confidence": 0.8}'

    cfg = SemanticGateConfig(
        enabled=True, mode="active",
        provider=slow_provider,
        repeat=3,
    )
    result = semantic_gate({"name": "read_file", "content": "test"}, {}, "allow", config=cfg)
    assert result is not None
    assert call_count["n"] == 3
    assert result["latency_ms"] >= 20  # 至少 3×10ms


# ── config repeat 字段默认值 ──────────────────────────────────────────────────

def test_config_default_repeat():
    """SemanticGateConfig 默认 repeat=1。"""
    cfg = SemanticGateConfig()
    assert cfg.repeat == 1


def test_config_repeat_3():
    """repeat=3 可以正确构造。"""
    cfg = SemanticGateConfig(repeat=3)
    assert cfg.repeat == 3
