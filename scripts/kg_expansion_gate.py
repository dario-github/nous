#!/usr/bin/env python3
"""KG Expansion Gate — validate KG changes don't regress benchmark metrics.

Usage:
  # Dry run: show what would be added
  python3 scripts/kg_expansion_gate.py preview entities.json

  # Expand + validate: add entities/relations, run val benchmark, rollback if FPR rises
  python3 scripts/kg_expansion_gate.py apply entities.json

  # Just validate current state
  python3 scripts/kg_expansion_gate.py validate

entities.json format:
{
  "entities": [{"id": "...", "etype": "...", "props": {...}}],
  "relations": [{"from_id": "...", "to_id": "...", "rtype": "...", "props": {...}}]
}
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "nous.db"
BACKUP_PATH = PROJECT_ROOT / "nous.db.bak"
DOCS_DIR = PROJECT_ROOT / "docs"

sys.path.insert(0, str(PROJECT_ROOT / "src"))


def backup_db():
    """Backup the current database."""
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"[backup] {DB_PATH} → {BACKUP_PATH}")


def restore_db():
    """Restore database from backup."""
    if BACKUP_PATH.exists():
        shutil.copy2(BACKUP_PATH, DB_PATH)
        print(f"[restore] {BACKUP_PATH} → {DB_PATH}")


def run_val_benchmark() -> dict:
    """Run val split benchmark, return results dict."""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "run_split_benchmark.py"), "val"],
        capture_output=True, text=True, timeout=300,
        cwd=str(PROJECT_ROOT),
        env={**__import__("os").environ, "PYTHONPATH": str(PROJECT_ROOT / "src")},
    )
    if result.returncode != 0:
        print(f"[error] Benchmark failed:\n{result.stderr[-500:]}")
        return None

    results_path = DOCS_DIR / "split-results-val.json"
    if not results_path.exists():
        print("[error] No results file generated")
        return None

    with open(results_path) as f:
        return json.load(f)


def apply_expansion(expansion_file: str):
    """Apply entities and relations from expansion file to DB."""
    from nous.db import NousDB

    with open(expansion_file) as f:
        data = json.load(f)

    db = NousDB()
    entities = data.get("entities", [])
    relations = data.get("relations", [])

    if entities:
        from nous.db import Entity
        ent_objs = [Entity(
            id=e["id"],
            etype=e["etype"],
            props=e.get("props", {}),
            confidence=e.get("confidence", 0.9),
        ) for e in entities]
        db.upsert_entities(ent_objs)
        print(f"[apply] Upserted {len(ent_objs)} entities")

    if relations:
        from nous.db import Relation
        rel_objs = [Relation(
            from_id=r["from_id"],
            to_id=r["to_id"],
            rtype=r["rtype"],
            props=r.get("props", {}),
            confidence=r.get("confidence", 0.9),
        ) for r in relations]
        db.upsert_relations(rel_objs)
        print(f"[apply] Upserted {len(rel_objs)} relations")

    db.close()
    return len(entities), len(relations)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1]

    if action == "validate":
        print("[validate] Running val benchmark on current DB...")
        results = run_val_benchmark()
        if results:
            o = results["overall"]
            fps = results.get("false_positives", [])
            print(f"\n[result] TPR={o['tpr']}% FPR={o['fpr']}% FPs={len(fps)}")
            for fp in fps:
                print(f"  FP: {fp['id']} [{fp['category']}]")
        return

    if len(sys.argv) < 3:
        print("Need expansion file path")
        sys.exit(1)

    expansion_file = sys.argv[2]
    if not Path(expansion_file).exists():
        print(f"File not found: {expansion_file}")
        sys.exit(1)

    with open(expansion_file) as f:
        data = json.load(f)

    if action == "preview":
        ents = data.get("entities", [])
        rels = data.get("relations", [])
        print(f"[preview] {len(ents)} entities, {len(rels)} relations")
        for e in ents:
            print(f"  + Entity: {e['id']} [{e['etype']}] {e.get('props', {}).get('name', '')}")
        for r in rels:
            print(f"  + Relation: {r['from_id']} --{r['rtype']}--> {r['to_id']}")
        return

    if action == "apply":
        # Step 1: Baseline
        print("[step 1] Running baseline val benchmark...")
        baseline = run_val_benchmark()
        if not baseline:
            print("[abort] Baseline benchmark failed")
            sys.exit(1)

        baseline_fpr = baseline["overall"]["fpr"]
        baseline_tpr = baseline["overall"]["tpr"]
        baseline_fps = len(baseline.get("false_positives", []))
        print(f"[baseline] TPR={baseline_tpr}% FPR={baseline_fpr}% FPs={baseline_fps}")

        # Step 2: Backup + Apply
        backup_db()
        n_ents, n_rels = apply_expansion(expansion_file)

        # Step 3: Post-expansion benchmark
        print(f"\n[step 3] Running post-expansion val benchmark...")
        post = run_val_benchmark()
        if not post:
            print("[abort] Post benchmark failed, restoring DB")
            restore_db()
            sys.exit(1)

        post_fpr = post["overall"]["fpr"]
        post_tpr = post["overall"]["tpr"]
        post_fps = len(post.get("false_positives", []))
        print(f"[post] TPR={post_tpr}% FPR={post_fpr}% FPs={post_fps}")

        # Step 4: Decision
        fpr_delta = post_fpr - baseline_fpr
        tpr_delta = post_tpr - baseline_tpr

        print(f"\n[delta] FPR: {baseline_fpr}% → {post_fpr}% ({fpr_delta:+.1f}%)")
        print(f"[delta] TPR: {baseline_tpr}% → {post_tpr}% ({tpr_delta:+.1f}%)")

        if post_fpr > baseline_fpr:
            print(f"\n[ROLLBACK] FPR increased! Rolling back...")
            restore_db()
            print("[rollback] DB restored to pre-expansion state")

            # Log the failure
            log = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "expansion_file": expansion_file,
                "entities_attempted": n_ents,
                "relations_attempted": n_rels,
                "baseline_fpr": baseline_fpr,
                "post_fpr": post_fpr,
                "new_fps": [fp for fp in post.get("false_positives", [])
                           if fp not in baseline.get("false_positives", [])],
                "action": "rollback",
            }
            log_path = PROJECT_ROOT / "logs" / "kg_expansion_log.jsonl"
            log_path.parent.mkdir(exist_ok=True)
            with open(log_path, "a") as f:
                f.write(json.dumps(log) + "\n")
            sys.exit(1)

        elif post_tpr < baseline_tpr:
            print(f"\n[ROLLBACK] TPR decreased! Rolling back...")
            restore_db()
            sys.exit(1)

        else:
            print(f"\n[COMMIT] FPR maintained/improved, TPR maintained. Expansion committed!")
            # Clean backup
            if BACKUP_PATH.exists():
                BACKUP_PATH.unlink()

            log = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "expansion_file": expansion_file,
                "entities_added": n_ents,
                "relations_added": n_rels,
                "baseline_fpr": baseline_fpr,
                "post_fpr": post_fpr,
                "fpr_delta": fpr_delta,
                "action": "commit",
            }
            log_path = PROJECT_ROOT / "logs" / "kg_expansion_log.jsonl"
            log_path.parent.mkdir(exist_ok=True)
            with open(log_path, "a") as f:
                f.write(json.dumps(log) + "\n")


if __name__ == "__main__":
    main()
