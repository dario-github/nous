"""Tests for AgentHarm benchmark loader."""
import sys
import json
from pathlib import Path
from unittest.mock import patch

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))


class TestLoader:
    def test_normalize_full_fields(self):
        from nous.benchmarks.agentharm.loader import _normalize_example
        raw = {"id": "t1", "prompt": "Do bad thing.",
               "target_functions": ["create_ransomware", "send_email"],
               "category": "Cyberattack", "name": "Bad Thing"}
        r = _normalize_example(raw)
        assert r["id"] == "t1"
        assert r["prompt"] == "Do bad thing."
        assert r["target_functions"] == ["create_ransomware", "send_email"]
        assert r["category"] == "Cyberattack"
        assert r["name"] == "Bad Thing"

    def test_normalize_string_functions(self):
        from nous.benchmarks.agentharm.loader import _normalize_example
        raw = {"id": "t2", "prompt": "Test",
               "target_functions": "create_ransomware, send_email, post_on_x",
               "category": "Mixed", "name": "Test"}
        r = _normalize_example(raw)
        assert r["target_functions"] == ["create_ransomware", "send_email", "post_on_x"]

    def test_normalize_missing_fields(self):
        from nous.benchmarks.agentharm.loader import _normalize_example
        r = _normalize_example({"id": "minimal"})
        assert r["id"] == "minimal"
        assert r["prompt"] == ""
        assert r["target_functions"] == []
        assert r["category"] == "unknown"
        assert r["name"] == ""

    def test_load_from_cache_hit(self, tmp_path):
        cache_dir = tmp_path / "data" / "agentharm"
        cache_dir.mkdir(parents=True)
        sample = [{"id": "h_001", "prompt": "test",
                   "target_functions": ["create_ransomware"],
                   "category": "Cyberattack", "name": "Test"}]
        (cache_dir / "harmful.json").write_text(json.dumps(sample))
        with patch("nous.benchmarks.agentharm.loader._CACHE_DIR", cache_dir):
            from nous.benchmarks.agentharm.loader import _load_from_cache
            result = _load_from_cache("harmful")
        assert result is not None
        assert len(result) == 1
        assert result[0]["id"] == "h_001"

    def test_load_from_cache_miss(self, tmp_path):
        with patch("nous.benchmarks.agentharm.loader._CACHE_DIR", tmp_path):
            from nous.benchmarks.agentharm import loader
            result = loader._load_from_cache("harmful")
        assert result is None

    @patch("nous.benchmarks.agentharm.loader._load_from_hf")
    def test_load_skips_hf_with_cache(self, mock_hf, tmp_path):
        cache_dir = tmp_path / "data" / "agentharm"
        cache_dir.mkdir(parents=True)
        sample = [{"id": "h_001", "prompt": "test",
                   "target_functions": [], "category": "X", "name": "T"}]
        (cache_dir / "harmful.json").write_text(json.dumps(sample))
        with patch("nous.benchmarks.agentharm.loader._CACHE_DIR", cache_dir):
            from nous.benchmarks.agentharm import loader
            loader._load("harmful", use_cache=True)
        mock_hf.assert_not_called()
