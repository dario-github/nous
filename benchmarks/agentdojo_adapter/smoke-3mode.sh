#!/usr/bin/env bash
# smoke-3mode.sh — sanity gate G1+G2+G3 before full matrix
# 3 modes × 1 banking user × 1 inj, ~3 min
set -euo pipefail
HERMES_ENV="${HERMES_ENV:-.env}"
[[ -f "$HERMES_ENV" ]] && { set -a; source "$HERMES_ENV"; set +a; }
[[ -z "${ZAI_API_KEY:-}" ]] && { echo "[FATAL] no ZAI_API_KEY"; exit 1; }
cd "$(dirname "$0")"
exec uv run --project ../agentdojo python run_eval_adaptive_llm.py \
  --agent-llm glm \
  --suites banking \
  --user-tasks user_task_0 user_task_1 user_task_2 \
  --injection-tasks injection_task_0 injection_task_1 \
  --modes baseline l1 l1_4 \
  --force-rerun \
  --out /tmp/g2-smoke.json 2>&1 | tee /tmp/g2-smoke.log
