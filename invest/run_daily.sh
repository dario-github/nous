#!/bin/bash
# Nous Invest - Daily Loop Cron Wrapper
# Add to crontab: 0 18 * * mon-fri /Users/yan/clawd-agents/research/nous-invest/run_daily.sh

PROJECT_DIR="/Users/yan/clawd-agents/research/nous-invest"
LOG_FILE="$PROJECT_DIR/logs/cron_run_$(date +%Y%m%d_%H%M%S).log"

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

# Log header
echo "========================================" >> "$LOG_FILE"
echo "Nous Invest Daily Loop - $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Change to project directory
cd "$PROJECT_DIR" || exit 1

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "✅ Virtual environment activated" >> "$LOG_FILE"
else
    echo "⚠️ Virtual environment not found, using system Python" >> "$LOG_FILE"
fi

# Run the daily loop
echo "🚀 Starting daily loop..." >> "$LOG_FILE"
python daily_loop.py 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

# Log completion
echo "" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "Completed at $(date) with exit code $EXIT_CODE" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Cleanup old logs (keep last 30 days)
find "$PROJECT_DIR/logs" -name "cron_run_*.log" -mtime +30 -delete 2>/dev/null

exit $EXIT_CODE
