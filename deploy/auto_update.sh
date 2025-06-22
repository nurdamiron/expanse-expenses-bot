#!/bin/bash
# Auto-update script for production deployment

# Configuration
REPO_DIR="/home/ubuntu/expanse-telegram-bot"
BOT_SERVICE="expanse-bot"
BRANCH="main"
LOG_FILE="/var/log/expanse-bot-update.log"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Check for updates
cd "$REPO_DIR" || exit 1

# Fetch latest changes
git fetch origin "$BRANCH" >> "$LOG_FILE" 2>&1

# Check if update is needed
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" = "$REMOTE" ]; then
    log "No updates available"
    exit 0
fi

log "Updates detected. Starting update process..."

# Pull latest changes
git pull origin "$BRANCH" >> "$LOG_FILE" 2>&1

# Check if requirements changed
if git diff HEAD~ HEAD --name-only | grep -q "requirements.txt"; then
    log "Requirements changed. Installing new dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt >> "$LOG_FILE" 2>&1
fi

# Check if database schema changed
if git diff HEAD~ HEAD --name-only | grep -q "database/"; then
    log "Database changes detected. Please run migrations manually!"
    # Send notification to admin
fi

# Graceful restart with zero downtime
log "Restarting bot service..."
sudo systemctl reload "$BOT_SERVICE" >> "$LOG_FILE" 2>&1

# Verify bot is running
sleep 5
if systemctl is-active --quiet "$BOT_SERVICE"; then
    log "Bot successfully restarted"
else
    log "ERROR: Bot failed to restart!"
    sudo systemctl status "$BOT_SERVICE" >> "$LOG_FILE" 2>&1
fi