#!/bin/bash
# vault-sync-setup.sh — Initialize vault sync between local machine and Azure VM
# Run this script ONCE from your local machine after VM setup is complete
#
# Prerequisites:
#   - Azure VM is running
#   - setup_vm.sh has been executed on VM
#   - transfer_secrets.sh has been executed
#   - .azure-secrets/ai-employee-key.pem exists locally
#   - .azure-secrets/vm-ip.txt exists locally
#
# Usage: bash scripts/vault-sync-setup.sh

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AZURE_SECRETS_DIR="$PROJECT_ROOT/.azure-secrets"
VAULT_DIR="$PROJECT_ROOT/AI_Employee_Vault"

# Read VM IP from file
if [ ! -f "$AZURE_SECRETS_DIR/vm-ip.txt" ]; then
    echo "ERROR: VM IP file not found: $AZURE_SECRETS_DIR/vm-ip.txt"
    exit 1
fi

VM_IP=$(cat "$AZURE_SECRETS_DIR/vm-ip.txt" | tr -d '[:space:]')
SSH_KEY="$AZURE_SECRETS_DIR/ai-employee-key.pem"
VM_USER="ubuntu"

echo "=========================================="
echo "Vault Sync Setup"
echo "=========================================="
echo ""
echo "VM IP: $VM_IP"
echo "Vault: $VAULT_DIR"
echo ""

# Step 1: Create bare Git repo on VM
echo "[1/6] Creating bare Git repository on Azure VM..."
ssh -i "$SSH_KEY" "$VM_USER@$VM_IP" << 'ENDSSH'
mkdir -p ~/vault-sync.git
cd ~/vault-sync.git
git init --bare
git config --local receive.denyCurrentBranch ignore
echo "Bare Git repo created at ~/vault-sync.git"
ENDSSH

echo "[OK] Bare repo created on VM"

# Step 2: Configure Git user on VM
echo "[2/6] Configuring Git user on VM..."
ssh -i "$SSH_KEY" "$VM_USER@$VM_IP" << 'ENDSSH'
git config --global user.email "cloud-agent@fte.local"
git config --global user.name "Cloud Agent"
echo "Git user configured"
ENDSSH

echo "[OK] Git user configured on VM"

# Step 3: Initialize local vault as Git repo
echo "[3/6] Initializing local vault as Git repository..."
cd "$VAULT_DIR"

if [ -d ".git" ]; then
    echo "Vault is already a Git repo — skipping init"
else
    git init
    echo "[OK] Git repo initialized"
fi

# Step 4: Create vault .gitignore
echo "[4/6] Creating vault .gitignore..."
cat > .gitignore << 'EOF'
# Secrets (NEVER sync)
.env
.env.*
.secrets/
*.pem
*.key
gmail_credentials.json
gmail_token.json
whatsapp_session/
facebook_session/
instagram_session/
twitter_session/
linkedin_session/

# Runtime state (machine-specific)
.state/

# Logs (too large, not needed for sync)
Logs/
Archive/

# Drop_Box (local filesystem only)
Drop_Box/
EOF

echo "[OK] .gitignore created"

# Step 5: Add VM as remote origin
echo "[5/6] Adding Azure VM as remote origin..."
if git remote | grep -q "^origin$"; then
    echo "Remote 'origin' already exists — updating URL"
    git remote set-url origin "$VM_USER@$VM_IP:~/vault-sync.git"
else
    git remote add origin "$VM_USER@$VM_IP:~/vault-sync.git"
fi

echo "[OK] Remote origin configured"

# Step 6: Initial commit and push
echo "[6/6] Creating initial commit and pushing to VM..."

# Configure local Git user if not set
if [ -z "$(git config user.email)" ]; then
    git config user.email "local-agent@fte.local"
    git config user.name "Local Agent"
fi

# Stage files
git add -A

# Commit
if git diff --cached --quiet; then
    echo "No changes to commit"
else
    git commit -m "Initial vault sync setup - $(date -Iseconds)"
    echo "[OK] Initial commit created"
fi

# Push to VM
GIT_SSH_COMMAND="ssh -i $SSH_KEY -o StrictHostKeyChecking=no" git push -u origin main

echo "[OK] Pushed to VM"

echo ""
echo "=========================================="
echo "Vault Sync Setup Complete!"
echo "=========================================="
echo ""
echo "Git repository structure:"
echo "  Local:  $VAULT_DIR/.git"
echo "  Remote: $VM_USER@$VM_IP:~/vault-sync.git"
echo ""
echo "What syncs:"
echo "  ✓ Needs_Action/"
echo "  ✓ Pending_Approval/"
echo "  ✓ Approved/"
echo "  ✓ Plans/"
echo "  ✓ Done/"
echo "  ✓ In_Progress/"
echo "  ✓ Updates/"
echo "  ✓ Dashboard.md"
echo "  ✓ Company_Handbook.md"
echo ""
echo "What NEVER syncs (security):"
echo "  ✗ .env, .secrets/, *.pem, *.key"
echo "  ✗ .state/ (machine-specific)"
echo "  ✗ Logs/ (too large)"
echo "  ✗ Drop_Box/ (local only)"
echo ""
echo "Next steps:"
echo "  1. Set up cron job for vault_sync.sh (every 2 minutes)"
echo "  2. Deploy cloud agent code to VM"
echo "  3. Start cloud orchestrator via PM2"
echo "  4. Test: send email while laptop off → draft appears"
echo ""
