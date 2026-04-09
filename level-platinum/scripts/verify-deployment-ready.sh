#!/bin/bash
# verify-deployment-ready.sh — Pre-deployment verification for Platinum Tier
# Run this script BEFORE starting deployment to catch any issues early
#
# Usage: bash scripts/verify-deployment-ready.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
WARN=0

echo "=========================================="
echo "Platinum Tier Pre-Deployment Verification"
echo "=========================================="
echo ""

# Configuration
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AZURE_SECRETS_DIR="$PROJECT_ROOT/.azure-secrets"
VAULT_DIR="$PROJECT_ROOT/AI_Employee_Vault"

# Helper functions
pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL++))
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARN++))
}

# Test 1: Check Azure secrets
echo "[1/15] Checking Azure secrets..."
if [ -f "$AZURE_SECRETS_DIR/ai-employee-key.pem" ]; then
    pass "ai-employee-key.pem exists"

    # Check permissions (skip on Windows - Git Bash stat is unreliable)
    if command -v stat &> /dev/null && [ "$(uname -s)" != "MINGW"* ] && [ "$(uname -s)" != "MSYS"* ]; then
        PERMS=$(stat -c %a "$AZURE_SECRETS_DIR/ai-employee-key.pem" 2>/dev/null || echo "unknown")
        if [ "$PERMS" = "400" ]; then
            pass "PEM key has correct permissions (400)"
        elif [ "$PERMS" != "unknown" ]; then
            warn "PEM key permissions are $PERMS (should be 400)"
        fi
    else
        warn "Skipping permission check on Windows (ensure PEM is secure)"
    fi
else
    fail "ai-employee-key.pem not found in .azure-secrets/"
fi

if [ -f "$AZURE_SECRETS_DIR/vm-ip.txt" ]; then
    VM_IP=$(cat "$AZURE_SECRETS_DIR/vm-ip.txt" | tr -d '[:space:]')
    if [ -n "$VM_IP" ]; then
        pass "vm-ip.txt exists and contains: $VM_IP"
    else
        fail "vm-ip.txt is empty"
    fi
else
    fail "vm-ip.txt not found in .azure-secrets/"
fi

# Test 2: Check directory structure
echo ""
echo "[2/15] Checking directory structure..."
for dir in cloud local shared scripts AI_Employee_Vault; do
    if [ -d "$PROJECT_ROOT/$dir" ]; then
        pass "$dir/ directory exists"
    else
        fail "$dir/ directory missing"
    fi
done

# Test 3: Check cloud configuration
echo ""
echo "[3/15] Checking cloud configuration..."
if [ -f "$PROJECT_ROOT/cloud/.env" ]; then
    pass "cloud/.env exists"

    if grep -q "CLOUD_DRAFT_ONLY=true" "$PROJECT_ROOT/cloud/.env"; then
        pass "CLOUD_DRAFT_ONLY=true (security layer 1)"
    else
        fail "CLOUD_DRAFT_ONLY not set to true in cloud/.env"
    fi

    if grep -q "DRY_RUN=true" "$PROJECT_ROOT/cloud/.env"; then
        pass "DRY_RUN=true (security layer 6)"
    else
        warn "DRY_RUN=false in cloud/.env (consider setting to true for safety)"
    fi
else
    fail "cloud/.env missing"
fi

if [ -f "$PROJECT_ROOT/cloud/orchestrator.py" ]; then
    pass "cloud/orchestrator.py exists"
else
    fail "cloud/orchestrator.py missing"
fi

if [ -f "$PROJECT_ROOT/cloud/ecosystem.config.cjs" ]; then
    pass "cloud/ecosystem.config.cjs exists"
else
    fail "cloud/ecosystem.config.cjs missing"
fi

# Test 4: Check local configuration
echo ""
echo "[4/15] Checking local configuration..."
if [ -f "$PROJECT_ROOT/local/.env" ]; then
    pass "local/.env exists"
else
    fail "local/.env missing (copy from level-gold/.env)"
fi

if [ -f "$PROJECT_ROOT/local/orchestrator.py" ]; then
    pass "local/orchestrator.py exists"

    # Check for sys.path fix
    if grep -q "sys.path.insert.*shared" "$PROJECT_ROOT/local/orchestrator.py"; then
        pass "local orchestrator has sys.path fix for shared imports"
    else
        fail "local orchestrator missing sys.path fix"
    fi
else
    fail "local/orchestrator.py missing"
fi

if [ -f "$PROJECT_ROOT/local/ecosystem.config.cjs" ]; then
    pass "local/ecosystem.config.cjs exists"

    # Check if updated for Platinum
    if grep -q "platinum-local-orchestrator" "$PROJECT_ROOT/local/ecosystem.config.cjs"; then
        pass "local ecosystem.config.cjs updated for Platinum"
    else
        warn "local ecosystem.config.cjs still references gold-orchestrator"
    fi
else
    fail "local/ecosystem.config.cjs missing"
fi

# Test 5: Check shared utilities
echo ""
echo "[5/15] Checking shared utilities..."
for file in base_watcher.py logger.py backoff.py id_tracker.py; do
    if [ -f "$PROJECT_ROOT/shared/$file" ]; then
        pass "shared/$file exists"
    else
        fail "shared/$file missing"
    fi
done

# Test 6: Check skills directory
echo ""
echo "[6/15] Checking skills access..."
if [ -d "$PROJECT_ROOT/shared/.claude/skills" ]; then
    SKILL_COUNT=$(ls -1 "$PROJECT_ROOT/shared/.claude/skills" | wc -l)
    pass "shared/.claude/skills exists ($SKILL_COUNT skills)"
else
    fail "shared/.claude/skills missing"
fi

if [ -L "$PROJECT_ROOT/cloud/.claude" ] || [ -d "$PROJECT_ROOT/cloud/.claude" ]; then
    pass "cloud/.claude exists (symlink or directory)"
else
    fail "cloud/.claude missing (skills won't be accessible)"
fi

if [ -L "$PROJECT_ROOT/local/.claude" ] || [ -d "$PROJECT_ROOT/local/.claude" ]; then
    pass "local/.claude exists (symlink or directory)"
else
    fail "local/.claude missing (skills won't be accessible)"
fi

# Test 7: Check vault structure
echo ""
echo "[7/15] Checking vault structure..."
for dir in Needs_Action Pending_Approval Approved Rejected Done Plans Updates; do
    if [ -d "$VAULT_DIR/$dir" ]; then
        pass "AI_Employee_Vault/$dir/ exists"
    else
        warn "AI_Employee_Vault/$dir/ missing (will be created on first run)"
    fi
done

if [ -d "$VAULT_DIR/In_Progress/cloud" ]; then
    pass "AI_Employee_Vault/In_Progress/cloud/ exists"
else
    warn "AI_Employee_Vault/In_Progress/cloud/ missing (will be created on first run)"
fi

if [ -d "$VAULT_DIR/In_Progress/local" ]; then
    pass "AI_Employee_Vault/In_Progress/local/ exists"
else
    warn "AI_Employee_Vault/In_Progress/local/ missing (will be created on first run)"
fi

# Test 8: Check deployment scripts
echo ""
echo "[8/15] Checking deployment scripts..."
for script in setup_vm.sh vault_sync.sh transfer_secrets.sh vault-sync-setup.sh; do
    if [ -f "$PROJECT_ROOT/scripts/$script" ]; then
        pass "scripts/$script exists"

        # Check if executable
        if [ -x "$PROJECT_ROOT/scripts/$script" ]; then
            pass "scripts/$script is executable"
        else
            warn "scripts/$script not executable (run: chmod +x scripts/$script)"
        fi

        # Check for correct PEM filename
        if grep -q "ai-employee-key.pem" "$PROJECT_ROOT/scripts/$script" 2>/dev/null; then
            pass "scripts/$script uses correct PEM filename"
        elif grep -q "azure-ai.pem" "$PROJECT_ROOT/scripts/$script" 2>/dev/null; then
            fail "scripts/$script still references old PEM filename (azure-ai.pem)"
        fi
    else
        fail "scripts/$script missing"
    fi
done

# Test 9: Check vault paths in orchestrators
echo ""
echo "[9/15] Checking vault paths..."
if grep -q "parent\.parent.*AI_Employee_Vault" "$PROJECT_ROOT/cloud/orchestrator.py" 2>/dev/null; then
    pass "cloud orchestrator uses correct vault path (parent.parent)"
else
    fail "cloud orchestrator has incorrect vault path"
fi

if grep -q "parent\.parent.*AI_Employee_Vault" "$PROJECT_ROOT/local/orchestrator.py" 2>/dev/null; then
    pass "local orchestrator uses correct vault path (parent.parent)"
else
    fail "local orchestrator has incorrect vault path"
fi

# Test 10: Check MCP servers
echo ""
echo "[10/15] Checking MCP servers..."
for dir in mcp-email-server mcp-odoo-server; do
    if [ -d "$PROJECT_ROOT/cloud/$dir" ]; then
        pass "cloud/$dir/ exists"
    else
        fail "cloud/$dir/ missing"
    fi

    if [ -d "$PROJECT_ROOT/local/$dir" ]; then
        pass "local/$dir/ exists"
    else
        fail "local/$dir/ missing"
    fi
done

# Test 11: Check Python environment
echo ""
echo "[11/15] Checking Python environment..."
if command -v uv &> /dev/null; then
    pass "uv is installed"
else
    fail "uv not found (install from: https://docs.astral.sh/uv/)"
fi

if command -v python &> /dev/null || command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python --version 2>&1 || python3 --version 2>&1)
    pass "Python installed: $PYTHON_VERSION"
else
    fail "Python not found"
fi

# Test 12: Check Node.js environment
echo ""
echo "[12/15] Checking Node.js environment..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    pass "Node.js installed: $NODE_VERSION"
else
    fail "Node.js not found (required for MCP servers and WhatsApp)"
fi

if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    pass "npm installed: $NPM_VERSION"
else
    fail "npm not found"
fi

# Test 13: Check PM2
echo ""
echo "[13/15] Checking PM2..."
if command -v pm2 &> /dev/null; then
    PM2_VERSION=$(pm2 --version)
    pass "PM2 installed: $PM2_VERSION"
else
    warn "PM2 not found (install: npm install -g pm2)"
fi

# Test 14: Test SSH connectivity (if VM IP exists)
echo ""
echo "[14/15] Testing SSH connectivity to VM..."
if [ -f "$AZURE_SECRETS_DIR/vm-ip.txt" ] && [ -f "$AZURE_SECRETS_DIR/ai-employee-key.pem" ]; then
    VM_IP=$(cat "$AZURE_SECRETS_DIR/vm-ip.txt" | tr -d '[:space:]')
    SSH_KEY="$AZURE_SECRETS_DIR/ai-employee-key.pem"

    if timeout 10 ssh -i "$SSH_KEY" -o ConnectTimeout=5 -o StrictHostKeyChecking=no ubuntu@$VM_IP "echo 'SSH OK'" &> /dev/null; then
        pass "SSH connection to VM successful"
    else
        warn "Cannot connect to VM (VM may be stopped or IP incorrect)"
    fi
else
    warn "Skipping SSH test (VM IP or PEM key missing)"
fi

# Test 15: Check documentation
echo ""
echo "[15/15] Checking documentation..."
for doc in README.md DEPLOYMENT_GUIDE.md FINAL_CHECKLIST.md; do
    if [ -f "$PROJECT_ROOT/$doc" ]; then
        pass "$doc exists"

        # Check for old PEM filename references
        if grep -q "azure-ai\.pem" "$PROJECT_ROOT/$doc" 2>/dev/null; then
            fail "$doc still references old PEM filename (azure-ai.pem)"
        else
            pass "$doc uses correct PEM filename"
        fi
    else
        warn "$doc missing"
    fi
done

# Summary
echo ""
echo "=========================================="
echo "Verification Summary"
echo "=========================================="
echo -e "${GREEN}Passed:${NC} $PASS"
echo -e "${YELLOW}Warnings:${NC} $WARN"
echo -e "${RED}Failed:${NC} $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✓ All critical checks passed!${NC}"
    echo ""
    echo "You are ready to deploy. Next steps:"
    echo "  1. Start your Azure VM in Azure Portal"
    echo "  2. Follow DEPLOYMENT_GUIDE.md steps 1-9"
    echo "  3. Estimated time: 90 minutes"
    echo ""
    exit 0
else
    echo -e "${RED}✗ $FAIL critical issues found.${NC}"
    echo ""
    echo "Please fix the failed checks before deploying."
    echo "See DEPLOYMENT_GUIDE.md for detailed instructions."
    echo ""
    exit 1
fi
