#!/usr/bin/env python3
"""Nous — 每日增量同步脚本 (M1.6)

用法：
    python3 nous/scripts/daily_sync.py [--force] [--db PATH]

默认 DB 路径：./nous.db
默认 entities 目录：memory/entities
"""
import argparse
import json
import sys
import time
from pathlib import Path

# 确保 nous 包可导入
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.db import NousDB
from nous.sync import IncrementalSync


def main():
    parser = argparse.ArgumentParser(description="Nous daily incremental sync")
    parser.add_argument("--force", action="store_true", help="Force full resync")
    parser.add_argument(
        "--db",
        default=str(Path(os.environ.get("NOUS_DB", "nous.db"))),
        help="DB file path",
    )
    parser.add_argument(
        "--entities",
        default=str(Path(os.environ.get("ENTITIES_DIR", "entities"))),
        help="Entities directory",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    start = time.perf_counter()

    db = NousDB(args.db)
    try:
        sync = IncrementalSync(db, args.entities)

        if args.force:
            # Force: 删除所有 entity 重建
            # 简单做法：直接跑，因为 mtime 总是会比 0 大
            # 用一个 trick: 把所有 DB updated_at 置 0
            try:
                db.db.run(
                    "?[id, etype, labels, props, metadata, confidence, source, "
                    "created_at, updated_at] := "
                    "*entity{id, etype, labels, props, metadata, confidence, "
                    "source, created_at}, updated_at = 0.0 "
                    ":put entity {id => etype, labels, props, metadata, "
                    "confidence, source, created_at, updated_at}"
                )
            except Exception:
                pass

        result = sync.run()
        elapsed_ms = (time.perf_counter() - start) * 1000

        result["elapsed_ms"] = round(elapsed_ms, 1)
        result["db_entities"] = db.count_entities()
        result["db_relations"] = db.count_relations()

        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"📊 Nous Sync: {result['changed']} changed, "
                  f"{result['unchanged']} unchanged, "
                  f"{len(result['errors'])} errors "
                  f"({elapsed_ms:.0f}ms)")
            print(f"   DB: {result['db_entities']} entities, "
                  f"{result['db_relations']} relations")
            if result["errors"]:
                for err in result["errors"]:
                    print(f"   ⚠️ {err}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
