#!/usr/bin/env bash
# launch-baseline-l1-rerun.sh — relaunch baseline + l1 with JSON crash patch.
#
# After D2 §4.X added, codex r4 flagged "missing GLM-only baseline" as a
# reviewer-attack vector. This script relaunches the two screens that
# crashed on JSON decode (since patched in run_eval_adaptive_llm.py).
#
# baseline: agent only (GLM-4.6, no Nous) → control
# l1:       agent + L1 Datalog only        → minimal Nous
# l1_4 already complete (95.9%, 75.0%)

set -euo pipefail

HERMES_ENV="${HERMES_ENV:-.env}"
[[ -f "$HERMES_ENV" ]] && { set -a; source "$HERMES_ENV"; set +a; }

[[ -z "${ZAI_API_KEY:-}" ]] && { echo "[FATAL] ZAI_API_KEY missing"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

OUTDIR="$SCRIPT_DIR/results-fullmatrix"
LOGDIR="$SCRIPT_DIR/logs-fullmatrix-rerun"
mkdir -p "$OUTDIR" "$LOGDIR"

launch() {
  local name="$1" mode="$2" out="$3" log="$4"
  screen -dmS "$name" bash -c "
    set -e
    cd '$SCRIPT_DIR'
    uv run --project ../agentdojo python run_eval_adaptive_llm.py \
      --agent-llm glm \
      --attack important_instructions \
      --suites banking slack travel workspace \
      --benchmark-version v1 \
      --logdir '$LOGDIR/$mode' \
      --force-rerun \
      --modes $mode \
      --out '$out' \
      2>&1 | tee $log
    echo '[done $name] '\$(date)
  "
}

echo "[launch] baseline + l1 reruns starting $(date)"

launch nous-baseline-rerun baseline "$OUTDIR/baseline-glm-fullmatrix.json" /tmp/baseline-rerun.log
sleep 2
launch nous-l1-rerun       l1       "$OUTDIR/l1-glm-fullmatrix.json"       /tmp/l1-rerun.log

screen -ls

cat <<EOF

[next] 监控:
  screen -ls
  tail -f /tmp/baseline-rerun.log
  tail -f /tmp/l1-rerun.log

[ETA]
  ~14h each (parallel; matches l1_4 wall time which finished after ~5h)
  Should be done by ~5/29 23:00, well before D4 freeze 5/1
EOF
