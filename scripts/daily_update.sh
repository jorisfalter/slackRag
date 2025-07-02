#!/bin/bash

# Daily Slack Bot Database Update Script
# This script runs the incremental update and logs the results

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/daily_update_$(date +%Y%m%d).log"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "🚀 Starting daily Slack bot database update"
log "Project directory: $PROJECT_DIR"

# Change to project directory
cd "$PROJECT_DIR" || {
    log "❌ Failed to change to project directory: $PROJECT_DIR"
    exit 1
}

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    log "📦 Activating virtual environment"
    source venv/bin/activate
elif [ -d ".venv" ]; then
    log "📦 Activating virtual environment"
    source .venv/bin/activate
else
    log "⚠️  No virtual environment found, using system Python"
fi

# Run the incremental update
log "🔄 Running incremental update..."
python slack_export/incremental_update.py 2>&1 | tee -a "$LOG_FILE"

# Check exit status
if [ $? -eq 0 ]; then
    log "✅ Daily update completed successfully"
else
    log "❌ Daily update failed with exit code $?"
    exit 1
fi

# Clean up old log files (keep last 7 days)
log "🧹 Cleaning up old log files..."
find "$LOG_DIR" -name "daily_update_*.log" -mtime +7 -delete

log "🎉 Daily update process finished" 