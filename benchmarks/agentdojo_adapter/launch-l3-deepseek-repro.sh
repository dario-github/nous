#!/usr/bin/env bash
# launch-l3-deepseek-repro.sh — D2/D3 of NeurIPS 6-day sprint.
#
# Reproducibility-locked rerun of L1+L3+L4 on AgentDojo for v2 paper §4.2.
# Replaces legacy qwen-turbo-via-relay path that no longer reproduces.
# Codex r2b plan e-1 substituted gpt-5-mini → deepseek-v4-pro per Yan's
# boundary that GPT-5.x can only go via codex CLI (not API).
#
# Locked parameters (do NOT edit during run):
#   - L3 model: deepseek-v4-pro (thinking enabled, max_tokens=2500)
#   - L3 temperature: 0.0
#   - L3 repeat: 1 (rely on temp=0 determinism; 2nd pass post-launch if needed)
#   - Agent LLM: GLM-4.6 (same as legacy run for comparability)
#   - Attack: important_instructions
#   - Suites: banking, slack, travel, workspace
#   - Benchmark version: v1

set -euo pipefail

HERMES_ENV="${HERMES_ENV:-.env}"
if [[ -f "$HERMES_ENV" ]]; then
  set -a; source "$HERMES_ENV"; set +a
fi

# DeepSeek key from chmod-600 file (factory falls back to this automatically,
# but exporting also lets ZAI_API_KEY-style ps-leak audit see it's not on cmdline)
DEEPSEEK_KEY_FILE="$HOME/.openclaw/.deepseek-api-key"
if [[ ! -f "$DEEPSEEK_KEY_FILE" ]]; then
  echo "[FATAL] DeepSeek key file missing: $DEEPSEEK_KEY_FILE"; exit 1
fi
export DEEPSEEK_API_KEY="$(cat "$DEEPSEEK_KEY_FILE")"

if [[ -z "${ZAI_API_KEY:-}" ]]; then
  echo "[FATAL] ZAI_API_KEY 未导出 (agent LLM = GLM-4.6 needs it)"; exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

OUTDIR="$SCRIPT_DIR/results-l3-repro"
LOGDIR="$SCRIPT_DIR/logs-l3-repro"
mkdir -p "$OUTDIR" "$LOGDIR"

OUT_JSON="$OUTDIR/l1_3_4_deepseek-glm-fullmatrix.json"
LOG_FILE="/tmp/l3-deepseek-repro.log"

echo "[launch] L3 reproducibility rerun starting $(date)"
echo "[launch] L3 model: deepseek-v4-pro (thinking enabled, repeat=5)"
echo "[launch] Agent: GLM-4.6, attack: important_instructions"
echo "[launch] Output: $OUT_JSON"
echo "[launch] Log:    $LOG_FILE"

screen -dmS nous-l3-deepseek bash -c "
  set -e
  cd '$SCRIPT_DIR'
  uv run --project ../agentdojo python run_eval_adaptive_llm.py \
    --agent-llm glm \
    --attack important_instructions \
    --suites banking slack travel workspace \
    --benchmark-version v1 \
    --logdir '$LOGDIR' \
    --force-rerun \
    --modes l1_3_4_deepseek \
    --out '$OUT_JSON' \
    2>&1 | tee $LOG_FILE
  echo '[done nous-l3-deepseek] '\$(date)
"

sleep 2
screen -ls | grep nous-l3-deepseek || { echo "[FATAL] screen failed to start"; exit 1; }

cat <<EOF

[next] 监控:
  screen -ls
  screen -r nous-l3-deepseek          # 接入进度
  tail -f $LOG_FILE

[ETA]
  L3 仅在 L1 miss 时触发
  预计 ~3000-5000 L3 calls × repeat=1 = 同样规模 LLM calls
  deepseek-v4-pro thinking ~30s/call → ~25-40h sequential
  适配 D2 起跑 → D3 末出结果 → D4 freeze
  ⚠️ 若 25h+ 不够时间，备选：
    - 改用 deepseek-v4-flash (non-thinking, ~5s/call) → ~5-7h
    - 缩 suites 到 banking + workspace 两个

[abort]:
  screen -X -S nous-l3-deepseek quit

[D4 freeze]:
  python3 -c "
import json
d = json.load(open('$OUT_JSON'))
s = list(d['results_by_mode'].values())[0]['summary']
print(f'l1_3_4_deepseek: sec={s[\"security\"][\"defended\"]}/{s[\"security\"][\"total\"]} ({100*s[\"security\"][\"rate\"]:.1f}%)')
print(f'                   util={s[\"utility\"][\"passed\"]}/{s[\"utility\"][\"total\"]}')
"
EOF
