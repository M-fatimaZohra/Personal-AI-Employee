#!/bin/bash
# vault_sync.sh — Platinum Tier vault synchronization script
# Syncs AI_Employee_Vault between local machine and Azure VM via Git over SSH
# Run this script every 2 minutes via cron on BOTH machines
#
# Usage: bash vault_sync.sh
# Cron: */2 * * * * cd /path/to/level-platinum && bash scripts/vault_sync.sh >> logs/vault_sync.log 2>&1

set -e  # Exit on any error

# Configuration
VAULT_DIR="AI_Employee_Vault"
STATE_FILE=".state/vault_sync_state.json"
LOG_PREFIX="[vault-sync]"

# Ensure we're in the right directory
cd "$(dirname "$0")/.." || exit 1

# Create state directory if it doesn't exist
mkdir -p .state

# Initialize state file if it doesn't exist
if [ ! -f "$STATE_FILE" ]; then
    echo '{"last_push":"","last_pull":"","consecutive_failures":0,"status":"ok"}' > "$STATE_FILE"
fi

# Function to update state
update_state() {
    local key=$1
    local value=$2
    python3 -c "
import json
with open('$STATE_FILE', 'r') as f:
    state = json.load(f)
state['$key'] = '$value'
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)
"
}

# Function to log with timestamp
log() {
    echo "$LOG_PREFIX $(date -Iseconds) $1"
}

# Change to vault directory
cd "$VAULT_DIR" || {
    log "ERROR: Vault directory not found: $VAULT_DIR"
    exit 1
}

# Check if git repo is initialized
if [ ! -d ".git" ]; then
    log "ERROR: Vault is not a git repository. Run vault-sync-setup.sh first."
    exit 1
fi

log "Starting vault sync..."

# Stage only shared state — local-only folders excluded by .gitignore
# NEVER sync: Approved/ Dashboard.md Rejected/ Inbox/ Drop_Box/ Logs/
# Needs_Action/whatsapp/ and Needs_Action/filesystem/ are local-only
git add -A 2>/dev/null || true

# Check if there are changes to commit
if git diff --cached --quiet; then
    log "No local changes to commit"
else
    # Commit with timestamp
    COMMIT_MSG="sync: $(date -Iseconds)"
    git commit -m "$COMMIT_MSG" || {
        log "ERROR: Commit failed"
        update_state "consecutive_failures" $(($(jq -r .consecutive_failures "$STATE_FILE") + 1))
        exit 1
    }
    log "Committed local changes"
    update_state "last_push" "$(date -Iseconds)"
fi

# Pull changes from remote (rebase to avoid merge commits)
log "Pulling remote changes..."
if git pull --rebase origin main; then
    log "Pull successful"
    update_state "last_pull" "$(date -Iseconds)"
    update_state "consecutive_failures" 0
    update_state "status" "ok"
else
    log "ERROR: Pull failed (conflict or network issue)"
    update_state "consecutive_failures" $(($(jq -r .consecutive_failures "$STATE_FILE") + 1))
    update_state "status" "degraded"

    # Abort rebase if it failed
    git rebase --abort 2>/dev/null || true

    exit 1
fi

# Push changes to remote
log "Pushing to remote..."
if git push origin main; then
    log "Push successful"
    update_state "last_push" "$(date -Iseconds)"
    update_state "status" "ok"
else
    log "ERROR: Push failed (network issue or remote ahead)"
    update_state "consecutive_failures" $(($(jq -r .consecutive_failures "$STATE_FILE") + 1))
    update_state "status" "degraded"
    exit 1
fi

log "Vault sync complete"
