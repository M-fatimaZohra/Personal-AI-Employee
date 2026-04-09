# Platinum Tier Deployment Guide

**Date**: 2026-03-18
**Status**: Phase 1 Complete — Ready for VM Deployment
**Branch**: `004-platinum-tier`

---

## ✅ What's Complete

### 1. Directory Structure
```
level-platinum/
├── cloud/                          # Deploy to Azure VM
│   ├── orchestrator.py             # ✅ Draft-only mode (simplified)
│   ├── gmail_watcher.py            # ✅ Copied from Gold
│   ├── dashboard_updater.py        # ✅ Copied (needs Updates/ modification)
│   ├── mcp-email-server/           # ✅ Copied
│   ├── mcp-odoo-server/            # ✅ Copied
│   ├── .env                        # ✅ CLOUD_DRAFT_ONLY=true
│   ├── pyproject.toml              # ✅ Copied
│   └── ecosystem.config.cjs        # ✅ Copied (needs modification)
│
├── local/                          # Runs on laptop
│   ├── orchestrator.py             # 🔄 Partially modified (claim-by-move added to __init__)
│   ├── (all watchers)              # ✅ All 7 watchers copied
│   ├── (all posters)               # ✅ All 4 posters copied
│   ├── mcp-email-server/           # ✅ Copied
│   ├── mcp-odoo-server/            # ✅ Copied
│   └── .env                        # ⚠️ Needs creation (copy from Gold)
│
├── shared/                         # Used by both
│   ├── base_watcher.py             # ✅ Copied
│   ├── logger.py                   # ✅ Copied
│   ├── backoff.py                  # ✅ Copied
│   ├── id_tracker.py               # ✅ Copied
│   └── .claude/skills/             # ✅ All 16 skills copied
│
├── scripts/                        # Deployment automation
│   ├── setup_vm.sh                 # ✅ Created
│   ├── vault_sync.sh               # ✅ Created
│   └── transfer_secrets.sh         # ✅ Created
│
├── AI_Employee_Vault/
│   ├── In_Progress/cloud/          # ✅ Created
│   ├── In_Progress/local/          # ✅ Created
│   └── Updates/                    # ✅ Created
│
└── .azure-secrets/                 # ⚠️ Needs your .pem + IP
    ├── ai-employee-key.pem         # ⚠️ You need to move here
    └── vm-ip.txt                   # ⚠️ You need to create
```

### 2. Test Gmail Account
✅ Created: new email
✅ OAuth credentials downloaded
✅ OAuth token generated
✅ Authentication tested successfully

### 3. Azure VM
✅ Provisioned: D2s_v6 (2 vCPU, 8GB RAM, East Asia)
✅ SSH tested successfully
✅ Ports 22 + 8069 open
⏸️ VM stopped to preserve credits

---

## 🔄 What's Remaining

### Critical Path (Must Complete for Demo)

| Task | Status | Time | Description |
|------|--------|------|-------------|
| Finish local orchestrator modifications | 🔄 | 30 min | Add claim-by-move to scan loop, integrate dashboard merge |
| Create cloud ecosystem.config.cjs | ⚠️ | 10 min | PM2 config for cloud (gmail watcher only) |
| Create local .env | ⚠️ | 5 min | Copy from Gold tier |
| Create vault-sync-setup.sh | ⚠️ | 15 min | Initialize bare Git repo on VM |
| Modify cloud dashboard_updater.py | ⚠️ | 15 min | Write to Updates/ instead of Dashboard.md |
| Test deployment | ⚠️ | 2 hours | Full end-to-end test |

---

## 🚀 Deployment Steps (When Ready)

### Step 1: Prepare Local Secrets (5 minutes)
```bash
cd level-platinum

# Move your .pem key
mv ~/Downloads/your-key.pem .azure-secrets/ai-employee-key.pem
chmod 400 .azure-secrets/ai-employee-key.pem

# Save VM IP
echo "YOUR_VM_PUBLIC_IP" > .azure-secrets/vm-ip.txt

# Create local .env (copy from Gold)
cp ../level-gold/.env local/.env
```

### Step 2: Start Azure VM (1 minute)
- Go to Azure Portal → Virtual Machines → fte-agent-vm
- Click "Start"
- Wait ~60 seconds

### Step 3: Run VM Setup Script (20 minutes)
```bash
# Copy setup script to VM
scp -i .azure-secrets/ai-employee-key.pem scripts/setup_vm.sh ubuntu@$(cat .azure-secrets/vm-ip.txt):~/

# SSH into VM
ssh -i .azure-secrets/ai-employee-key.pem ubuntu@$(cat .azure-secrets/vm-ip.txt)

# Run setup
bash setup_vm.sh

# Log out and back in (for Docker group)
exit
ssh -i .azure-secrets/ai-employee-key.pem ubuntu@$(cat .azure-secrets/vm-ip.txt)
```

### Step 4: Transfer Test Gmail Credentials (5 minutes)
```bash
# From local machine
cd level-platinum
bash scripts/transfer_secrets.sh
```

### Step 5: Set Up Vault Sync (15 minutes)
```bash
# SSH into VM
ssh -i .azure-secrets/ai-employee-key.pem ubuntu@$(cat .azure-secrets/vm-ip.txt)

# Create bare Git repo
mkdir -p ~/vault-sync.git
cd ~/vault-sync.git
git init --bare

# Exit VM
exit

# On local machine, initialize vault as Git repo
cd level-platinum/AI_Employee_Vault
git init
git remote add origin ubuntu@YOUR_VM_IP:~/vault-sync.git

# Create .gitignore for vault
cat > .gitignore << 'EOF'
.env
.env.*
.secrets/
*.pem
*.key
.state/
Logs/
Archive/
Drop_Box/
EOF

# Initial commit and push
git add -A
git commit -m "Initial vault sync setup"
git push -u origin main
```

### Step 6: Deploy Cloud Agent Code (10 minutes)
```bash
# Copy cloud directory to VM
cd level-platinum
scp -i .azure-secrets/ai-employee-key.pem -r cloud/ ubuntu@$(cat .azure-secrets/vm-ip.txt):~/

# SSH into VM
ssh -i .azure-secrets/ai-employee-key.pem ubuntu@$(cat .azure-secrets/vm-ip.txt)

# Install Python dependencies
cd ~/cloud
uv sync

# Install MCP server dependencies
cd mcp-email-server && npm install && cd ..
cd mcp-odoo-server && npm install && cd ..
```

### Step 7: Start Cloud Agent (5 minutes)
```bash
# On VM
cd ~/cloud
pm2 start ecosystem.config.cjs
pm2 save
pm2 startup  # Run the generated command as instructed
```

### Step 8: Set Up Vault Sync Cron (10 minutes)
```bash
# On VM
crontab -e

# Add this line:
*/2 * * * * cd ~/cloud && bash scripts/vault_sync.sh >> logs/vault_sync.log 2>&1

# On local machine
crontab -e

# Add this line:
*/2 * * * * cd /path/to/level-platinum && bash scripts/vault_sync.sh >> logs/vault_sync.log 2>&1
```

### Step 9: Test Platinum Demo Gate (10 minutes)
1. Shut down local laptop
2. Send test email to your dedicated AI agent Gmail account
3. Wait 3 minutes
4. Start laptop
5. Check Obsidian — draft should appear in Pending_Approval/
6. Move to Approved/
7. Verify email sent

---

## 🔒 Security Checklist

Before deployment, verify:

- [ ] Test Gmail account used (not business account)
- [ ] .pem key has 400 permissions
- [ ] .env files never committed to Git
- [ ] Vault .gitignore excludes .secrets/, .env, .state/
- [ ] CLOUD_DRAFT_ONLY=true in cloud/.env
- [ ] SEND_ALLOWED=false in cloud MCP email server
- [ ] SSH password auth disabled on VM
- [ ] Only ports 22 + 8069 open on Azure NSG

---

## 📊 Current Progress

**Phase 1: Foundation** — 80% complete
- ✅ Directory structure
- ✅ Deployment scripts
- ✅ Cloud orchestrator (draft-only)
- 🔄 Local orchestrator (partial)
- ⚠️ Vault sync setup (script ready, not deployed)

**Estimated time to demo-ready:** 3-4 hours

---

## ⚠️ Known Issues

1. **Local orchestrator** — claim-by-move logic added to __init__ but not integrated into scan loop yet
2. **Cloud dashboard_updater.py** — still writes to Dashboard.md, needs to write to Updates/
3. **Ecosystem configs** — need separate cloud/local versions (cloud has no social watchers)
4. **Local .env** — needs to be created (copy from Gold)

---

## 💡 Next Actions

**For you:**
1. Move .pem key to `.azure-secrets/ai-employee-key.pem`
2. Create `.azure-secrets/vm-ip.txt` with your VM public IP
3. Create `local/.env` (copy from `level-gold/.env`)

**For me (when you say "continue"):**
1. Finish local orchestrator claim-by-move integration
2. Modify cloud dashboard_updater.py for Updates/ writing
3. Create separate ecosystem.config.cjs for cloud/local
4. Create vault-sync-setup.sh script
5. Create comprehensive test checklist

---

## 📝 Notes

- VM currently stopped to preserve Azure credits
- Test Gmail authentication verified working
- Business Gmail credentials remain in level-gold (safe)
- All deployment scripts ready for use
- Estimated Azure cost: ~$18-20 for full hackathon demo period

---

**Status:** Ready for final code modifications, then deployment.
