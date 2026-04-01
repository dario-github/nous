#!/usr/bin/env python3
"""Biomorphic Memory Adapter for LongMemEval benchmark.

Architecture:
  Haystack sessions → Graph (nodes=sessions, edges=temporal+semantic)
  Query → BM25+embedding anchors → Spreading Activation → PPR → top-K sessions
  Retrieved sessions + question → GPT-4o CoT → answer

Usage:
  python3 biomorphic_longmemeval.py --data data/longmemeval_s_cleaned.json \
    --out results/biomorphic_v1.jsonl --limit 5 --top_k 8
"""
import json, time, math, argparse, os, sys
import numpy as np
from collections import defaultdict
from tqdm import tqdm

# ── Embedding + LLM ──────────────────────────────────────────────────
from sentence_transformers import SentenceTransformer, util as st_util
from openai import OpenAI

EMB_MODEL = None  # lazy init
LLM_CLIENT = None

def get_emb_model():
    global EMB_MODEL
    if EMB_MODEL is None:
        EMB_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    return EMB_MODEL

def get_llm():
    global LLM_CLIENT
    if LLM_CLIENT is None:
        LLM_CLIENT = OpenAI()
    return LLM_CLIENT

def callgpt(messages, model="gpt-4o", max_tokens=512, temperature=0.0):
    resp = get_llm().chat.completions.create(
        model=model, messages=messages, temperature=temperature, max_tokens=max_tokens
    )
    return resp.choices[0].message.content


# ── Graph Construction ────────────────────────────────────────────────

def flatten_session_text(session: list[dict], date: str) -> str:
    """Flatten a session into a single text block with date prefix."""
    lines = [f"[Date: {date}]"]
    for turn in session:
        role = turn.get("role", "unknown")
        content = turn.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def build_graph(haystack_sessions, haystack_dates, haystack_session_ids,
                cosine_threshold=0.35, temporal_weight=0.8, semantic_weight_scale=1.0):
    """Build a biomorphic graph from haystack sessions.

    Returns: dict with nodes, edges, embeddings, texts, session_id_map.
    """
    model = get_emb_model()

    # Build nodes
    nodes = []
    texts = []
    for i, (sess, date, sid) in enumerate(zip(
            haystack_sessions, haystack_dates, haystack_session_ids)):
        text = flatten_session_text(sess, date)
        nodes.append({
            "idx": i,
            "session_id": sid,
            "date": date,
            "num_turns": len(sess),
        })
        texts.append(text)

    # Compute embeddings
    embeddings = model.encode(texts, convert_to_tensor=False, show_progress_bar=False)
    embeddings = np.array(embeddings)

    n = len(nodes)
    edges = []

    # Temporal edges (consecutive sessions)
    for i in range(n - 1):
        edges.append({"from": i, "to": i + 1, "type": "temporal",
                       "weight": temporal_weight})
        edges.append({"from": i + 1, "to": i, "type": "temporal",
                       "weight": temporal_weight * 0.5})

    # Semantic edges (cosine similarity)
    if n > 1:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        normed = embeddings / norms
        sim_matrix = normed @ normed.T

        for i in range(n):
            for j in range(i + 1, n):
                sim = float(sim_matrix[i, j])
                if sim > cosine_threshold:
                    w = sim * semantic_weight_scale
                    edges.append({"from": i, "to": j, "type": "semantic", "weight": w})
                    edges.append({"from": j, "to": i, "type": "semantic", "weight": w})

    # PageRank
    pagerank = compute_pagerank(n, edges)

    return {
        "nodes": nodes,
        "edges": edges,
        "embeddings": embeddings,
        "texts": texts,
        "pagerank": pagerank,
        "n": n,
    }


def compute_pagerank(n, edges, alpha=0.85, iterations=20):
    """Simple PageRank on graph."""
    pr = np.ones(n) / n
    # Build adjacency
    adj = defaultdict(list)  # src -> [(tgt, weight)]
    out_weight = defaultdict(float)
    for e in edges:
        src, tgt, w = e["from"], e["to"], e["weight"]
        adj[src].append((tgt, w))
        out_weight[src] += w

    for _ in range(iterations):
        new_pr = np.ones(n) * (1 - alpha) / n
        for src in range(n):
            if out_weight[src] > 0:
                for tgt, w in adj[src]:
                    new_pr[tgt] += alpha * pr[src] * w / out_weight[src]
        pr = new_pr
    return pr


# ── Retrieval: SA + PPR ──────────────────────────────────────────────

def retrieve_sessions(graph, question: str, question_date: str,
                      top_k=8, sa_alpha=0.6, ppr_weight=0.15, decay_rate=0.02):
    """Retrieve top-K sessions using biomorphic memory retrieval.

    1. BM25 + embedding → anchor nodes
    2. Spreading activation (1-hop)
    3. Temporal decay (newer = stronger for knowledge-update)
    4. PPR boost
    5. Combine → top-K
    """
    model = get_emb_model()
    n = graph["n"]
    embeddings = graph["embeddings"]
    texts = graph["texts"]
    nodes = graph["nodes"]
    edges = graph["edges"]
    pagerank = graph["pagerank"]

    # Step 1: Anchor scoring via embedding similarity
    q_emb = model.encode(question, convert_to_tensor=False)
    q_emb = np.array(q_emb)

    # Cosine similarity to all nodes
    norms_corpus = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms_corpus = np.where(norms_corpus == 0, 1, norms_corpus)
    norm_q = np.linalg.norm(q_emb)
    if norm_q == 0:
        norm_q = 1
    sim_scores = (embeddings @ q_emb) / (norms_corpus.flatten() * norm_q)

    # Step 2: Spreading Activation
    activation = np.zeros(n)
    # Top anchors
    anchor_k = min(10, n)
    anchor_indices = np.argsort(sim_scores)[-anchor_k:][::-1]
    for idx in anchor_indices:
        activation[idx] = max(activation[idx], sim_scores[idx])

    # Build adjacency for activation spread
    adj = defaultdict(list)
    for e in edges:
        adj[e["from"]].append((e["to"], e["weight"]))

    # 1-hop spread
    spread = np.zeros(n)
    for src in range(n):
        if activation[src] > 0:
            for tgt, w in adj[src]:
                spread[tgt] += activation[src] * w * sa_alpha
    activation = np.maximum(activation, spread)

    # Step 3: Temporal decay (recency boost for knowledge-update questions)
    # Newer sessions get slight boost
    recency = np.linspace(0, 1, n)  # 0=oldest, 1=newest
    temporal_boost = 1.0 + recency * 0.1  # max 10% boost for newest

    # Step 4: Combine scores
    # final = semantic * (1 + activation_bonus) * temporal * (1 + pr_bonus)
    sem_score = np.clip(sim_scores, 0, 1)
    act_score = np.clip(activation, 0, 1)
    pr_score = pagerank / (pagerank.max() + 1e-8)

    final_score = (
        0.5 * sem_score +
        0.3 * act_score +
        ppr_weight * pr_score +
        0.05 * temporal_boost
    )

    # Get top-K session indices
    top_indices = np.argsort(final_score)[-top_k:][::-1]
    # Sort by temporal order for context coherence
    top_indices = sorted(top_indices, key=lambda i: i)

    return top_indices, final_score


# ── Answer Generation ─────────────────────────────────────────────────

ANSWER_PROMPT = """You are a helpful assistant with access to a user's past chat history.
Using the conversation sessions below, answer the question as accurately and concisely as possible.
Think step by step: first identify which sessions contain relevant information, then synthesize your answer.

If the question cannot be answered from the provided sessions, say "I don't have enough information to answer this question."

Chat History Sessions:
{sessions}

Question (asked on {question_date}): {question}

Think step by step, then give your final answer."""


def generate_answer(graph, retrieved_indices, question, question_date, model="gpt-4o"):
    """Generate answer from retrieved sessions using GPT-4o with CoT."""
    sessions_text = []
    for idx in retrieved_indices:
        sessions_text.append(graph["texts"][idx])
    sessions_block = "\n\n---\n\n".join(sessions_text)

    prompt = ANSWER_PROMPT.format(
        sessions=sessions_block,
        question=question,
        question_date=question_date,
    )

    answer = callgpt(
        [{"role": "user", "content": prompt}],
        model=model, max_tokens=256, temperature=0.0,
    )
    return answer.strip()


# ── NDCG Session Scoring (EmergenceMem technique) ────────────────────

def retrieve_sessions_ndcg(graph, question: str, question_date: str,
                           top_k=8, top_turns=50, sa_alpha=0.6):
    """Hybrid: match at turn level, score sessions by NDCG, boost with SA.

    This combines EmergenceMem's NDCG insight with our graph-based SA.
    """
    model = get_emb_model()
    nodes = graph["nodes"]
    n = graph["n"]
    embeddings = graph["embeddings"]
    edges = graph["edges"]
    pagerank = graph["pagerank"]

    # Step 1: Turn-level matching
    all_turns = []
    turn_to_session = []  # maps turn index → session index
    for i, node in enumerate(nodes):
        session_text = graph["texts"][i]
        turns = session_text.split("\n")
        for t in turns:
            if t.strip():
                all_turns.append(t)
                turn_to_session.append(i)

    if not all_turns:
        return list(range(min(top_k, n))), np.ones(n) / n

    turn_embeddings = model.encode(all_turns, convert_to_tensor=False,
                                    show_progress_bar=False)
    turn_embeddings = np.array(turn_embeddings)

    q_emb = model.encode(question, convert_to_tensor=False)
    q_emb = np.array(q_emb)

    # Cosine sim
    t_norms = np.linalg.norm(turn_embeddings, axis=1, keepdims=True)
    t_norms = np.where(t_norms == 0, 1, t_norms)
    q_norm = max(np.linalg.norm(q_emb), 1e-8)
    turn_sims = (turn_embeddings @ q_emb) / (t_norms.flatten() * q_norm)

    # Top turns
    k = min(top_turns, len(all_turns))
    top_turn_indices = np.argsort(turn_sims)[-k:][::-1]

    # Step 2: NDCG session scoring
    session_scores = np.zeros(n)
    for rank, tidx in enumerate(top_turn_indices):
        sid = turn_to_session[tidx]
        # NDCG: 1/log2(rank+2)
        session_scores[sid] += 1.0 / math.log2(rank + 2)

    # Step 3: SA boost from top sessions
    anchor_k = min(10, n)
    anchors = np.argsort(session_scores)[-anchor_k:][::-1]
    activation = np.zeros(n)
    for idx in anchors:
        activation[idx] = session_scores[idx]

    adj = defaultdict(list)
    for e in edges:
        adj[e["from"]].append((e["to"], e["weight"]))

    spread = np.zeros(n)
    for src in range(n):
        if activation[src] > 0:
            for tgt, w in adj[src]:
                spread[tgt] += activation[src] * w * sa_alpha
    activation = np.maximum(activation, spread)

    # Step 4: Combine
    pr_score = pagerank / (pagerank.max() + 1e-8)
    recency = np.linspace(0, 1, n)

    # Normalize session_scores
    ss_max = session_scores.max() + 1e-8
    final = (
        0.45 * (session_scores / ss_max) +
        0.30 * (activation / (activation.max() + 1e-8)) +
        0.15 * pr_score +
        0.05 * recency +
        0.05  # base
    )

    top_indices = np.argsort(final)[-top_k:][::-1]
    top_indices = sorted(top_indices, key=lambda i: i)

    return top_indices, final


# ── Evaluation ────────────────────────────────────────────────────────

def get_anscheck_prompt(task, question, answer, response, abstention=False):
    """LongMemEval evaluation prompts (from official repo)."""
    if not abstention:
        if task in ['single-session-user', 'single-session-assistant', 'multi-session']:
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the information required by the answer, answer no. \n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
        elif task == 'temporal-reasoning':
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the information required by the answer, answer no. In addition, do not penalize off-by-one errors for the number of days. If the question asks for the number of days/weeks/months, etc., and the model makes off-by-one errors (e.g., predicting 19 days when the answer is 18), the model's response is still correct. \n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
        elif task == 'knowledge-update':
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response contains some previous information along with an updated answer, the response should be considered as correct as long as the updated answer is the required answer.\n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
        elif task == 'single-session-preference':
            template = "I will give you a question, a rubric for desired personalized response, and a response from a model. Please answer yes if the response satisfies the desired response. Otherwise, answer no. The model does not need to reflect all the points in the rubric. The response is correct as long as it recalls and utilizes the user's personal information correctly.\n\nQuestion: {}\n\nRubric: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
        else:
            raise NotImplementedError(f"Unknown task: {task}")
        return template.format(question, answer, response)
    else:
        template = "I will give you an unanswerable question, an explanation, and a response from a model. Please answer yes if the model correctly identifies the question as unanswerable. The model could say that the information is incomplete, or some other information is given but the asked information is not.\n\nQuestion: {}\n\nExplanation: {}\n\nModel Response: {}\n\nDoes the model correctly identify the question as unanswerable? Answer yes or no only."
        return template.format(question, answer, response)


def evaluate_single(question_id, question_type, question, answer, hypothesis):
    """Evaluate a single hypothesis using GPT-4o judge."""
    abstention = question_id.endswith("_abs")
    prompt = get_anscheck_prompt(question_type, question, answer, hypothesis, abstention)
    eval_resp = callgpt([{"role": "user", "content": prompt}],
                        model="gpt-4o", max_tokens=10)
    return "yes" in eval_resp.lower()


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to longmemeval_s_cleaned.json")
    parser.add_argument("--out", required=True, help="Output JSONL path")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of questions (0=all)")
    parser.add_argument("--top_k", type=int, default=8, help="Number of sessions to retrieve")
    parser.add_argument("--method", default="ndcg", choices=["session", "ndcg"],
                        help="Retrieval method: session-level or NDCG turn-to-session")
    parser.add_argument("--cosine_threshold", type=float, default=0.35)
    parser.add_argument("--sa_alpha", type=float, default=0.6)
    parser.add_argument("--skip_eval", action="store_true", help="Skip GPT-4o evaluation")
    parser.add_argument("--answer_model", default="gpt-4o")
    args = parser.parse_args()

    print(f"Loading data from {args.data}...")
    data = json.load(open(args.data))
    if args.limit > 0:
        data = data[:args.limit]
    print(f"  {len(data)} questions loaded")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    results = []
    correct = 0
    total = 0
    type_stats = defaultdict(lambda: {"correct": 0, "total": 0})

    haystack_times = []
    query_times = []

    for item in tqdm(data, desc="Processing"):
        qid = item["question_id"]
        qtype = item["question_type"]
        question = item["question"]
        answer = item["answer"]
        qdate = item["question_date"]

        # Build graph
        t0 = time.perf_counter()
        graph = build_graph(
            item["haystack_sessions"],
            item["haystack_dates"],
            item["haystack_session_ids"],
            cosine_threshold=args.cosine_threshold,
        )
        haystack_times.append(time.perf_counter() - t0)

        # Retrieve
        t0 = time.perf_counter()
        if args.method == "ndcg":
            indices, scores = retrieve_sessions_ndcg(
                graph, question, qdate,
                top_k=args.top_k, sa_alpha=args.sa_alpha,
            )
        else:
            indices, scores = retrieve_sessions(
                graph, question, qdate,
                top_k=args.top_k, sa_alpha=args.sa_alpha,
            )

        # Generate answer
        hypothesis = generate_answer(graph, indices, question, qdate,
                                      model=args.answer_model)
        query_times.append(time.perf_counter() - t0)

        # Evaluate
        label = None
        if not args.skip_eval:
            label = evaluate_single(qid, qtype, question, answer, hypothesis)
            if label:
                correct += 1
                type_stats[qtype]["correct"] += 1
            type_stats[qtype]["total"] += 1
            total += 1

        entry = {
            "question_id": qid,
            "question_type": qtype,
            "hypothesis": hypothesis,
            "label": label,
            "retrieved_sessions": [int(i) for i in indices],
        }
        results.append(entry)

        # Write incrementally
        with open(args.out, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Progress
        if total > 0 and total % 10 == 0:
            print(f"  [{total}] acc={correct/total:.3f} "
                  f"haystack={np.median(haystack_times):.2f}s "
                  f"query={np.median(query_times):.2f}s")

    # Final report
    print("\n" + "="*60)
    if total > 0:
        print(f"Overall Accuracy: {correct/total:.4f} ({correct}/{total})")
    print(f"Haystack time (median): {np.median(haystack_times):.3f}s")
    print(f"Query time (median): {np.median(query_times):.3f}s")
    print("\nPer-category breakdown:")
    for t in sorted(type_stats.keys()):
        s = type_stats[t]
        acc = s["correct"] / s["total"] if s["total"] > 0 else 0
        print(f"  {t:<30}: {acc:.2%} ({s['correct']}/{s['total']})")

    # Save summary
    summary = {
        "total": total, "correct": correct,
        "accuracy": correct / total if total > 0 else 0,
        "haystack_time_median": float(np.median(haystack_times)),
        "query_time_median": float(np.median(query_times)),
        "per_type": {t: type_stats[t] for t in type_stats},
        "config": vars(args),
    }
    with open(args.out + ".summary.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {args.out}")


if __name__ == "__main__":
    main()
