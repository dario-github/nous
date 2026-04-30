#!/usr/bin/env bash
# launch-full-matrix.sh — 3-mode overnight P1 实验（pre-reg: baseline-prereg-2026-04-28.md）
# 3 screens 并行：baseline / l1 / l1_4。l1_3_4_glm 留 follow-up，不在此次。
# Mode dispatch via run_eval_adaptive_llm.py 的 --modes 参数 + monkey-patched
# TaskSuite.run_task_with_pipeline。Wiring 已 G2 verify (2026-04-28 21:xx)。

set -euo pipefail

HERMES_ENV="${HERMES_ENV:-.env}"
if [[ -f "$HERMES_ENV" ]]; then
  set -a; source "$HERMES_ENV"; set +a
fi

if [[ -z "${ZAI_API_KEY:-}" ]]; then
  echo "[FATAL] ZAI_API_KEY 未导出"; exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SUITES=(banking slack travel workspace)  # codex §5: banking first (known G2), slack smallest for fast 2nd signal, workspace largest last
ATTACK=important_instructions
LLM=glm
COMMON_ARGS=(
  --agent-llm "$LLM"
  --attack "$ATTACK"
  --suites "${SUITES[@]}"
  --benchmark-version v1
  --logdir "$SCRIPT_DIR/logs-fullmatrix"
  --force-rerun
)

mkdir -p "$SCRIPT_DIR/logs-fullmatrix" "$SCRIPT_DIR/results-fullmatrix"

launch_screen() {
  local name="$1" modes="$2" out="$3" log="$4"
  screen -dmS "$name" bash -c "
    set -e
    cd '$SCRIPT_DIR'
    # ZAI_API_KEY 由 screen 从父 env 继承（不写入 cmdline 避免 ps 泄漏）
    uv run --project ../agentdojo python run_eval_adaptive_llm.py \
      ${COMMON_ARGS[@]} \
      --modes $modes \
      --out '$out' \
      2>&1 | tee $log
    echo '[done $name] '\$(date)
  "
}

echo "[launch] 3 screens (baseline / l1 / l1_4) in parallel..."
launch_screen nous-baseline "baseline" "$SCRIPT_DIR/results-fullmatrix/baseline-glm-fullmatrix.json" /tmp/full-matrix-baseline.log
sleep 2
launch_screen nous-l1       "l1"       "$SCRIPT_DIR/results-fullmatrix/l1-glm-fullmatrix.json"       /tmp/full-matrix-l1.log
sleep 2
launch_screen nous-l1l4     "l1_4"     "$SCRIPT_DIR/results-fullmatrix/l1_4-glm-fullmatrix.json"     /tmp/full-matrix-l1l4.log

screen -ls

cat <<EOF

[next] 监控：
  screen -ls
  screen -r nous-l1                 # 接入 l1 进度
  tail -f /tmp/full-matrix-{baseline,l1,l1l4}.log

[ETA]
  各 mode 全矩阵：~10-14h（GLM-4.6, ~3-5s/call × ~10500 calls/mode）
  3 screens 并行 → 总 wall time ~14h
  GLM coding plan dedicated resources → 无 standard 3 并发限制

[abort 全部]:
  screen -X -S nous-baseline quit
  screen -X -S nous-l1 quit
  screen -X -S nous-l1l4 quit

[results 收完后]:
  python3 -c "
import json
for m in ['baseline','l1','l1_4']:
    d = json.load(open(f'$SCRIPT_DIR/results-fullmatrix/{m}-glm-fullmatrix.json'))
    s = list(d['results_by_mode'].values())[0]['summary']
    print(f'{m}: sec={s[\"security\"][\"defended\"]}/{s[\"security\"][\"total\"]} ({100*s[\"security\"][\"rate\"]:.1f}%) util={s[\"utility\"][\"passed\"]}/{s[\"utility\"][\"total\"]}')
"
EOF
