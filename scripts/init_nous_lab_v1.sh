#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <project-slug>"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_SLUG="$1"
LAB_DIR="$ROOT_DIR/docs/lab"
TEMPLATE_DIR="$LAB_DIR/templates"
PROJECT_DIR="$LAB_DIR/projects/$PROJECT_SLUG"

mkdir -p "$PROJECT_DIR"

copy_template() {
  local src="$1"
  local dst="$2"
  if [[ ! -f "$dst" ]]; then
    cp "$src" "$dst"
  fi
}

copy_template "$TEMPLATE_DIR/PROJECT_CHARTER.template.md" "$PROJECT_DIR/PROJECT_CHARTER.md"
copy_template "$TEMPLATE_DIR/EVIDENCE_LEDGER.template.md" "$PROJECT_DIR/EVIDENCE_LEDGER.md"
copy_template "$TEMPLATE_DIR/HYPOTHESIS_PACK.template.md" "$PROJECT_DIR/HYPOTHESIS_PACK.md"
copy_template "$TEMPLATE_DIR/EXPERIMENT_PACK.template.md" "$PROJECT_DIR/EXPERIMENT_PACK.md"
copy_template "$TEMPLATE_DIR/REVIEW_MEMO.template.md" "$PROJECT_DIR/REVIEW_MEMO.md"
copy_template "$TEMPLATE_DIR/LEARNING_RECORD.template.md" "$PROJECT_DIR/LEARNING_RECORD.md"
copy_template "$TEMPLATE_DIR/WEEKLY_RESEARCH_PACKET.template.md" "$PROJECT_DIR/WEEKLY_RESEARCH_PACKET.md"

STATE_FILE="$PROJECT_DIR/STATE.yaml"
if [[ ! -f "$STATE_FILE" ]]; then
  cat > "$STATE_FILE" <<STATEEOF
project: $PROJECT_SLUG
status: draft
owner: pending
conductor: pending
phase: charter
current_gate: problem
next_required_artifact: PROJECT_CHARTER.md
STATEEOF
fi

echo "Initialized Nous Lab project at: $PROJECT_DIR"
echo "Next step: fill PROJECT_CHARTER.md and move through gates."
