"""Tests for M11.2 — 概率边权重 + 时序衰减"""
import math
import time

import pytest

from nous.edge_weight import (
    effective_confidence,
    record_access,
    set_decay_half_life,
    rank_relations_by_effective_confidence,
    DEFAULT_HALF_LIFE_SECS,
    ACCESS_BOOST_MAX,
)


class TestEffectiveConfidence:
    """衰减计算测试"""

    def test_no_decay_at_creation(self):
        """刚创建的边，有效置信度 ≈ 基础置信度"""
        now = time.time()
        ec = effective_confidence(1.0, created_at=now, now=now)
        assert ec == pytest.approx(1.0, abs=0.01)

    def test_half_decay_at_half_life(self):
        """经过一个半衰期，置信度 ≈ 0.5"""
        now = time.time()
        created = now - DEFAULT_HALF_LIFE_SECS  # 90 天前
        ec = effective_confidence(1.0, created_at=created, now=now)
        assert ec == pytest.approx(0.5, abs=0.01)

    def test_quarter_at_two_half_lives(self):
        """经过两个半衰期，置信度 ≈ 0.25"""
        now = time.time()
        created = now - 2 * DEFAULT_HALF_LIFE_SECS
        ec = effective_confidence(1.0, created_at=created, now=now)
        assert ec == pytest.approx(0.25, abs=0.01)

    def test_base_confidence_scales(self):
        """基础置信度影响衰减后的值"""
        now = time.time()
        created = now - DEFAULT_HALF_LIFE_SECS
        ec = effective_confidence(0.8, created_at=created, now=now)
        assert ec == pytest.approx(0.4, abs=0.01)

    def test_custom_half_life(self):
        """自定义半衰期"""
        now = time.time()
        half_life_7d = 7 * 86400
        created = now - half_life_7d  # 7 天前
        props = {"decay_half_life": half_life_7d}
        ec = effective_confidence(1.0, created_at=created, props=props, now=now)
        assert ec == pytest.approx(0.5, abs=0.01)

    def test_clamp_to_1(self):
        """boost 不应让置信度超过 1.0"""
        now = time.time()
        props = {"last_accessed": now}  # 刚被访问
        ec = effective_confidence(1.0, created_at=now, props=props, now=now)
        assert ec <= 1.0

    def test_very_old_near_zero(self):
        """非常老的边，有效置信度趋近于 0"""
        now = time.time()
        created = now - 365 * 86400 * 3  # 3 年前
        ec = effective_confidence(1.0, created_at=created, now=now)
        assert ec < 0.01


class TestAccessBoost:
    """访问 boost 测试"""

    def test_recent_access_boosts(self):
        """最近被访问的边有 boost"""
        now = time.time()
        created = now - DEFAULT_HALF_LIFE_SECS  # 90 天前 → base ≈ 0.5
        ec_no_access = effective_confidence(1.0, created_at=created, now=now)
        ec_with_access = effective_confidence(
            1.0, created_at=created,
            props={"last_accessed": now},
            now=now
        )
        assert ec_with_access > ec_no_access
        assert ec_with_access - ec_no_access == pytest.approx(ACCESS_BOOST_MAX, abs=0.02)

    def test_old_access_no_boost(self):
        """8 天前的访问不再有 boost"""
        now = time.time()
        created = now - DEFAULT_HALF_LIFE_SECS
        ec_no = effective_confidence(1.0, created_at=created, now=now)
        ec_old = effective_confidence(
            1.0, created_at=created,
            props={"last_accessed": now - 8 * 86400},
            now=now
        )
        assert ec_old == pytest.approx(ec_no, abs=0.01)


class TestRecordAccess:
    """record_access 测试"""

    def test_sets_last_accessed(self):
        """记录访问时间"""
        props = record_access({})
        assert "last_accessed" in props
        assert props["access_count"] == 1

    def test_increments_count(self):
        """多次访问累加"""
        props = record_access({"access_count": 5})
        assert props["access_count"] == 6

    def test_does_not_mutate_original(self):
        """不修改原 props"""
        original = {"foo": "bar"}
        new = record_access(original)
        assert "last_accessed" not in original
        assert "foo" in new


class TestSetDecayHalfLife:
    """set_decay_half_life 测试"""

    def test_sets_in_seconds(self):
        """天 → 秒"""
        props = set_decay_half_life({}, 30)
        assert props["decay_half_life"] == 30 * 86400


class TestRanking:
    """rank_relations_by_effective_confidence 测试"""

    def test_sorts_descending(self):
        """按有效置信度降序"""
        now = time.time()
        rels = [
            {"confidence": 0.5, "created_at": now, "props": {}},
            {"confidence": 1.0, "created_at": now, "props": {}},
            {"confidence": 0.8, "created_at": now, "props": {}},
        ]
        ranked = rank_relations_by_effective_confidence(rels, now=now)
        scores = [r["effective_confidence"] for r in ranked]
        assert scores == sorted(scores, reverse=True)
        assert scores[0] == pytest.approx(1.0, abs=0.01)

    def test_old_low_ranked(self):
        """老的边排后面"""
        now = time.time()
        rels = [
            {"confidence": 1.0, "created_at": now - 365 * 86400, "props": {}},  # 老
            {"confidence": 0.7, "created_at": now, "props": {}},  # 新但低 confidence
        ]
        ranked = rank_relations_by_effective_confidence(rels, now=now)
        # 新的 0.7 应该高于衰减后的老 1.0
        assert ranked[0]["confidence"] == 0.7
