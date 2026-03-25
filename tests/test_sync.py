"""测试 M1.3 增量同步 (IncrementalSync)"""
import os
import sys
import time
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from nous.db import NousDB
from nous.sync import IncrementalSync

from _paths import ENTITIES_ROOT


@pytest.fixture
def db():
    _db = NousDB(":memory:")
    yield _db
    _db.close()


@pytest.fixture
def tmp_entities(tmp_path):
    entities = tmp_path / "entities"
    people = entities / "people"
    people.mkdir(parents=True)

    (people / "alice.md").write_text(
        "---\ntype: person\ncreated_at: 2026-01-01\n---\n# Alice\n",
        encoding="utf-8",
    )
    (people / "bob.md").write_text(
        "---\ntype: person\ncreated_at: 2026-01-01\n---\n# Bob\n",
        encoding="utf-8",
    )
    return entities


class TestFirstSync:
    def test_imports_all_files_on_first_run(self, db, tmp_entities):
        sync = IncrementalSync(db, str(tmp_entities))
        result = sync.run()

        assert result["total_files"] == 2
        assert result["changed"] == 2
        assert result["unchanged"] == 0
        assert result["errors"] == []
        assert db.count_entities() == 2

    def test_entities_actually_in_db(self, db, tmp_entities):
        sync = IncrementalSync(db, str(tmp_entities))
        sync.run()

        rows = db.query("?[id] := *entity{id}")
        ids = [r["id"] for r in rows]
        assert any("alice" in i for i in ids)
        assert any("bob" in i for i in ids)


class TestNoChange:
    def test_second_run_returns_changed_zero(self, db, tmp_entities):
        sync = IncrementalSync(db, str(tmp_entities))
        sync.run()

        result = sync.run()

        assert result["changed"] == 0
        assert result["unchanged"] == 2
        assert result["errors"] == []

    def test_db_count_stable_after_no_change(self, db, tmp_entities):
        sync = IncrementalSync(db, str(tmp_entities))
        sync.run()
        count_before = db.count_entities()

        sync.run()
        count_after = db.count_entities()

        assert count_before == count_after


class TestModifiedFile:
    def test_only_modified_file_reimported(self, db, tmp_entities):
        sync = IncrementalSync(db, str(tmp_entities))
        sync.run()

        time.sleep(0.02)

        alice = tmp_entities / "people" / "alice.md"
        alice.write_text(
            "---\ntype: person\ncreated_at: 2026-01-01\n---\n# Alice Updated\n",
            encoding="utf-8",
        )

        result = sync.run()

        assert result["changed"] == 1
        assert result["unchanged"] == 1
        assert result["total_files"] == 2

    def test_modified_content_reflected_in_db(self, db, tmp_entities):
        sync = IncrementalSync(db, str(tmp_entities))
        sync.run()

        time.sleep(0.02)

        alice = tmp_entities / "people" / "alice.md"
        alice.write_text(
            "---\ntype: person\ncreated_at: 2026-01-01\n---\n# Alice New Name\n",
            encoding="utf-8",
        )
        sync.run()

        rows = db.query(
            '?[props] := *entity{id: "entity:person:alice", props}'
        )
        assert len(rows) == 1
        name = rows[0]["props"].get("name", "")
        assert "Alice New Name" in name


class TestNewFile:
    def test_new_file_detected(self, db, tmp_entities):
        sync = IncrementalSync(db, str(tmp_entities))
        sync.run()

        charlie = tmp_entities / "people" / "charlie.md"
        charlie.write_text(
            "---\ntype: person\ncreated_at: 2026-01-01\n---\n# Charlie\n",
            encoding="utf-8",
        )

        result = sync.run()

        assert result["total_files"] == 3
        assert result["changed"] == 1
        assert result["unchanged"] == 2
        assert db.count_entities() == 3


class TestReturnSchema:
    def test_result_has_required_keys(self, db, tmp_entities):
        sync = IncrementalSync(db, str(tmp_entities))
        result = sync.run()

        assert "total_files" in result
        assert "changed" in result
        assert "unchanged" in result
        assert "errors" in result
        assert isinstance(result["errors"], list)

    def test_total_equals_changed_plus_unchanged_plus_errors(self, db, tmp_entities):
        sync = IncrementalSync(db, str(tmp_entities))
        result = sync.run()

        assert result["total_files"] == (
            result["changed"] + result["unchanged"] + len(result["errors"])
        )

    def test_empty_dir_returns_zeros(self, db, tmp_path):
        empty = tmp_path / "entities"
        empty.mkdir()

        sync = IncrementalSync(db, str(empty))
        result = sync.run()

        assert result["total_files"] == 0
        assert result["changed"] == 0
        assert result["unchanged"] == 0
        assert result["errors"] == []


@pytest.mark.skipif(not ENTITIES_ROOT.exists(), reason="entities dir not found (CI)")
class TestPerformance:
    def test_no_change_under_200ms(self, db):
        sync = IncrementalSync(db, str(ENTITIES_ROOT))
        first = sync.run()
        assert first["changed"] >= 10, f"真实目录同步数量异常: {first}"

        start = time.perf_counter()
        result = sync.run()
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result["changed"] == 0, f"无变更时 changed 应为 0，实际: {result['changed']}"
        assert elapsed_ms < 200, f"增量同步耗时 {elapsed_ms:.1f}ms，超过 200ms 限制"

    def test_idempotent_multiple_runs(self, db, tmp_entities):
        sync = IncrementalSync(db, str(tmp_entities))
        sync.run()
        count_1 = db.count_entities()

        sync.run()
        sync.run()
        count_3 = db.count_entities()

        assert count_1 == count_3
