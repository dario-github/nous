#!/bin/bash
# Biomorphic Memory LongMemEval Benchmark - Mac Bootstrap
set -e
WORKDIR="/Users/user/Workspace/biomorphic-benchmark"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

echo "=== Step 1: venv ==="
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ venv created"
fi
source venv/bin/activate

echo "=== Step 2: dependencies ==="
pip install --quiet openai sentence-transformers tqdm numpy 2>&1 | tail -5
echo "✅ deps installed"

echo "=== Step 3: data ==="
mkdir -p data
cd data
if [ ! -f "longmemeval_s_cleaned.json" ]; then
    echo "Downloading longmemeval_s_cleaned.json (265MB)..."
    curl -L "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json" -o longmemeval_s_cleaned.json
    echo "✅ downloaded"
fi
ls -lh *.json 2>/dev/null
cd ..

echo "=== Step 4: adapter script ==="
curl -sL "https://gist.githubusercontent.com/yanfeatherai/c438d92bff666bf15e1965c865c50beb/raw/biomorphic_longmemeval.py" -o biomorphic_longmemeval.py
echo "✅ adapter downloaded"

echo "=== Step 5: test run (5 questions, skip eval) ==="
mkdir -p results
python3 biomorphic_longmemeval.py \
    --data data/longmemeval_s_cleaned.json \
    --out results/test_5_skip.jsonl \
    --limit 5 \
    --skip_eval

echo ""
echo "=== Step 6: test run (5 questions, with eval) ==="
python3 biomorphic_longmemeval.py \
    --data data/longmemeval_s_cleaned.json \
    --out results/test_5_eval.jsonl \
    --limit 5

echo ""
echo "=== COMPLETE ==="
cat results/test_5_eval.jsonl.summary.json 2>/dev/null
