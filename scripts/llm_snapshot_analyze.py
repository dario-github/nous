"""Analyze the LLM trace snapshot for §8 motivating example.

Computes summary stats: answer distribution, reasoning length stats, lexical
diversity (proxy for variety of natural-language reasoning styles), and a
crude pairwise reasoning-similarity histogram via word-set Jaccard.
"""
from __future__ import annotations
import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "paper" / "llm-snapshot" / "raw-traces.json"
OUT = ROOT / "paper" / "llm-snapshot" / "summary.json"

with RAW.open() as fh:
    traces = json.load(fh)

n = len(traces)
answers = [t["answer"] for t in traces]
ans_counter = Counter(answers)

reasoning_lengths = [len(t["reasoning"].split()) for t in traces]

def tokenize(s: str) -> set[str]:
    return {w.strip(".,").lower() for w in s.split() if w.strip(".,")}

token_sets = [tokenize(t["reasoning"]) for t in traces]
all_tokens = sorted({tk for ts in token_sets for tk in ts})

# pairwise Jaccard similarity
import itertools
jaccards = []
for a, b in itertools.combinations(token_sets, 2):
    inter = len(a & b)
    union = len(a | b)
    jaccards.append(inter / union if union else 0)

summary = {
    "n_traces": n,
    "answer_distribution": dict(ans_counter),
    "answer_mode": ans_counter.most_common(1)[0][0],
    "answer_mode_rate": ans_counter.most_common(1)[0][1] / n,
    "answer_correct_rate_assuming_6": ans_counter.get(6, 0) / n,
    "reasoning_length_words": {
        "min": min(reasoning_lengths),
        "max": max(reasoning_lengths),
        "mean": round(statistics.mean(reasoning_lengths), 1),
        "stdev": round(statistics.stdev(reasoning_lengths), 1) if n > 1 else 0,
    },
    "vocab_total_unique": len(all_tokens),
    "tokens_per_trace_mean": round(statistics.mean(len(s) for s in token_sets), 1),
    "pairwise_jaccard_word_set": {
        "mean": round(statistics.mean(jaccards), 3),
        "min": round(min(jaccards), 3),
        "max": round(max(jaccards), 3),
        "stdev": round(statistics.stdev(jaccards), 3),
    },
}

OUT.write_text(json.dumps(summary, indent=2))
for k, v in summary.items():
    print(f"{k}: {v}")
