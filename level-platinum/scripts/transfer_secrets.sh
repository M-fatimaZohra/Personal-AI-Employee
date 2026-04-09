#!/bin/bash
# transfer_secrets.sh — Transfer Gmail credentials from local to Azure VM
# Run this script ONCE from your local machine after VM setup is complete
#
# Prerequisites:
#   - Azure VM is running
#   - setup_vm.sh has been executed on VM
#   - .azure-secrets/ai-employee-key.pem exists locally
#   - .azure-secrets/vm-ip.txt exists locally
#   - .secrets/gmail_credentials.json exists locally (test account)
#   - .secrets/gmail_token.json exists locally (test account)
#
# Usage: bash scripts/transfer_secrets.sh

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AZURE_SECRETS_DIR="$PROJECT_ROOT/.azure-secrets"
LOCAL_SECRETS_DIR="$PROJECT_ROOT/.secrets"

# Read VM IP from file
if [ ! -f "$AZURE_SECRETS_DIR/vm-ip.txt" ]; then
    echo "ERROR: VM IP file not found: $AZURE_SECRETS_DIR/vm-ip.txt"
    echo "Create it with: echo 'YOUR_VM_IP' > .azure-secrets/vm-ip.txt"
    exit 1
fi

VM_IP=$(cat "$AZURE_SECRETS_DIR/vm-ip.txt" | tr -d '[:space:]')
SSH_KEY="$AZURE_SECRETS_DIR/ai-employee-key.pem"
VM_USER="ubuntu"

# Verify SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo "ERROR: SSH key not found: $SSH_KEY"
    exit 1
fi

# Verify SSH key permissions (skip on Windows - Git Bash chmod is unreliable)
case "$(uname -s)" in
    MINGW*|MSYS*)
        echo "Skipping permission check on Windows (SSH will still work)"
        ;;
    *)
        if [ "$(stat -c %a "$SSH_KEY" 2>/dev/null || stat -f %A "$SSH_KEY" 2>/dev/null)" != "400" ]; then
            echo "Fixing SSH key permissions..."
            chmod 400 "$SSH_KEY"
        fi
        ;;
esac

# Verify Gmail credentials exist
if [ ! -f "$LOCAL_SECRETS_DIR/gmail_credentials.json" ]; then
    echo "ERROR: Gmail credentials not found: $LOCAL_SECRETS_DIR/gmail_credentials.json"
    exit 1
fi

if [ ! -f "$LOCAL_SECRETS_DIR/gmail_token.json" ]; then
    echo "ERROR: Gmail token not found: $LOCAL_SECRETS_DIR/gmail_token.json"
    echo "Run: uv run python gmail_watcher.py --auth-only"
    exit 1
fi

echo "=========================================="
echo "Transferring Secrets to Azure VM"
echo "=========================================="
echo ""
echo "VM IP: $VM_IP"
echo "SSH Key: $SSH_KEY"
echo ""

# Test SSH connection first
echo "[1/5] Testing SSH connection..."
if ssh -i "$SSH_KEY" -o ConnectTimeout=10 "$VM_USER@$VM_IP" "echo 'SSH connection successful'" > /dev/null 2>&1; then
    echo "✓ SSH connection verified"
else
    echo "ERROR: Cannot connect to VM via SSH"
    echo "Check:"
    echo "  - VM is running in Azure Portal"
    echo "  - VM IP is correct in .azure-secrets/vm-ip.txt"
    echo "  - Port 22 is open in Azure Network Security Group"
    exit 1
fi

# Create .secrets directory on VM
echo "[2/5] Creating .secrets directory on VM..."
ssh -i "$SSH_KEY" "$VM_USER@$VM_IP" "mkdir -p ~/cloud/.secrets"

# Transfer gmail_credentials.json
echo "[3/5] Transferring gmail_credentials.json..."
scp -i "$SSH_KEY" "$LOCAL_SECRETS_DIR/gmail_credentials.json" "$VM_USER@$VM_IP:~/cloud/.secrets/"
echo "✓ gmail_credentials.json transferred"

# Transfer gmail_token.json
echo "[4/5] Transferring gmail_token.json..."
scp -i "$SSH_KEY" "$LOCAL_SECRETS_DIR/gmail_token.json" "$VM_USER@$VM_IP:~/cloud/.secrets/"
echo "✓ gmail_token.json transferred"

# Set correct permissions on VM
echo "[5/5] Setting permissions on VM..."
ssh -i "$SSH_KEY" "$VM_USER@$VM_IP" "chmod 600 ~/cloud/.secrets/gmail_credentials.json ~/cloud/.secrets/gmail_token.json"
echo "✓ Permissions set"

echo ""
echo "=========================================="
echo "Transfer Complete!"
echo "=========================================="
echo ""
echo "Credentials transferred to VM:"
echo "  - ~/cloud/.secrets/gmail_credentials.json"
echo "  - ~/cloud/.secrets/gmail_token.json"
echo ""
echo "SECURITY NOTE:"
echo "  These are TEST account credentials only."
echo "  Your business Gmail credentials remain local-only."
echo ""
echo "Next steps:"
echo "  1. Run vault-sync-setup.sh to create Git repo on VM"
echo "  2. Deploy cloud agent code to VM"
echo "  3. Start cloud orchestrator via PM2"
echo ""
