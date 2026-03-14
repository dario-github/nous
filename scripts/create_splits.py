#!/usr/bin/env python3
"""Create train/val/test splits for AgentHarm benchmark.

Stratified by category, random_state=42, ratio 60/20/20.
Output: data/splits/{train,val,test}.json
Each file contains {"harmful": [...], "benign": [...]} with scenario dicts.

Once generated, splits are FROZEN — never regenerate.
"""
import json
import random
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.benchmarks.agentharm.loader import load_harmful, load_benign

SEED = 42
SPLITS_DIR = Path(__file__).parent.parent / "data" / "splits"
RATIOS = {"train": 0.6, "val": 0.2, "test": 0.2}


def stratified_split(scenarios: list[dict], seed: int = SEED) -> dict[str, list[dict]]:
    """Split scenarios into train/val/test, stratified by category."""
    by_cat = defaultdict(list)
    for s in scenarios:
        by_cat[s["category"]].append(s)

    splits = {"train": [], "val": [], "test": []}
    rng = random.Random(seed)

    for cat in sorted(by_cat.keys()):
        items = by_cat[cat]
        rng.shuffle(items)
        n = len(items)
        n_train = round(n * RATIOS["train"])
        n_val = round(n * RATIOS["val"])
        # rest goes to test
        splits["train"].extend(items[:n_train])
        splits["val"].extend(items[n_train : n_train + n_val])
        splits["test"].extend(items[n_train + n_val :])

    return splits


def verify_splits(h_splits, b_splits):
    """Verify split integrity."""
    for kind, label in [(h_splits, "harmful"), (b_splits, "benign")]:
        total = sum(len(kind[s]) for s in kind)
        print(f"\n{label}: {total} total")
        for split_name in ["train", "val", "test"]:
            items = kind[split_name]
            cats = defaultdict(int)
            for s in items:
                cats[s["category"]] += 1
            print(f"  {split_name}: {len(items)} — {dict(sorted(cats.items()))}")

    # Check no overlap
    for label, splits in [("harmful", h_splits), ("benign", b_splits)]:
        train_ids = {s["id"] for s in splits["train"]}
        val_ids = {s["id"] for s in splits["val"]}
        test_ids = {s["id"] for s in splits["test"]}
        assert train_ids.isdisjoint(val_ids), f"{label} train/val overlap!"
        assert train_ids.isdisjoint(test_ids), f"{label} train/test overlap!"
        assert val_ids.isdisjoint(test_ids), f"{label} val/test overlap!"
        total_ids = len(train_ids) + len(val_ids) + len(test_ids)
        print(f"  {label}: no overlap ✓ ({total_ids} unique ids)")


def main():
    harmful = load_harmful()
    benign = load_benign()

    print(f"Loaded: {len(harmful)} harmful, {len(benign)} benign")

    h_splits = stratified_split(harmful)
    b_splits = stratified_split(benign)

    verify_splits(h_splits, b_splits)

    # Save
    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    for split_name in ["train", "val", "test"]:
        out = {
            "harmful": h_splits[split_name],
            "benign": b_splits[split_name],
            "metadata": {
                "seed": SEED,
                "ratios": RATIOS,
                "split": split_name,
                "n_harmful": len(h_splits[split_name]),
                "n_benign": len(b_splits[split_name]),
            },
        }
        path = SPLITS_DIR / f"{split_name}.json"
        with open(path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\nSaved: {path} ({out['metadata']['n_harmful']}h + {out['metadata']['n_benign']}b)")

    print("\n✅ Splits created. DO NOT regenerate — these are frozen.")


if __name__ == "__main__":
    main()
