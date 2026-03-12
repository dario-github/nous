"""Nous — 增量同步 (M1.3)

IncrementalSync: 比较文件 mtime 与 DB updated_at，只重新解析有变更的 MD 文件。
"""
import os
from pathlib import Path

from nous.db import NousDB
from nous.parser import (
    parse_entity_file,
    build_slug_to_id_map,
    _infer_etype,
    _make_entity_id,
    _SKIP_STEMS,
)

_MTIME_TOLERANCE = 0.001

class IncrementalSync:
    """增量同步：只处理有变更的 MD 文件"""

    def __init__(self, db: NousDB, entities_dir: str = "memory/entities"):
        self.db = db
        self.entities_dir = Path(entities_dir)

    def run(self) -> dict:
        errors: list[str] = []
        changed = 0
        unchanged = 0

        md_files = [
            f for f in sorted(self.entities_dir.rglob("*.md"))
            if f.stem not in _SKIP_STEMS
        ]
        total_files = len(md_files)

        if total_files == 0:
            return {
                "total_files": 0,
                "changed": 0,
                "unchanged": 0,
                "errors": errors,
            }

        db_updated: dict[str, float] = {}
        try:
            rows = self.db.query("?[id, updated_at] := *entity{id, updated_at}")
            for row in rows:
                db_updated[row["id"]] = float(row["updated_at"])
        except Exception as e:
            errors.append(f"DB batch query failed: {e}")
            return {
                "total_files": total_files,
                "changed": 0,
                "unchanged": 0,
                "errors": errors,
            }

        slug_to_id: dict[str, str] | None = None
        to_update: list[tuple[Path, float]] = []

        for md_file in md_files:
            mtime = os.path.getmtime(md_file)
            etype = _infer_etype(md_file)
            entity_id = _make_entity_id(etype, md_file.stem)

            if entity_id not in db_updated or mtime > db_updated[entity_id] + _MTIME_TOLERANCE:
                to_update.append((md_file, mtime))
            else:
                unchanged += 1

        if to_update:
            slug_to_id = build_slug_to_id_map(self.entities_dir)

            for md_file, mtime in to_update:
                try:
                    entity, relations = parse_entity_file(md_file, slug_to_id)
                    
                    # Update timestamp
                    entity.updated_at = mtime
                    
                    self.db.upsert_entities([entity])
                    self.db.upsert_relations(relations)
                    changed += 1
                except Exception as e:
                    errors.append(f"SKIP {md_file}: {e}")

        return {
            "total_files": total_files,
            "changed": changed,
            "unchanged": unchanged,
            "errors": errors,
        }

# 兼容 M1.4 的测试: 提供 sync_entities 别名或包装函数
def sync_entities(db: NousDB, entities_root: Path) -> dict:
    """向下兼容 M1.4 test_query.py 的 sync_entities 接口"""
    sync = IncrementalSync(db, str(entities_root))
    return sync.run()
