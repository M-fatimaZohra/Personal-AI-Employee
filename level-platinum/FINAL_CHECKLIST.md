# Platinum Tier — Final Deployment Checklist

**Date**: 2026-03-18
**Status**: ✅ Phase 1 Complete — All Code Ready
**Branch**: `004-platinum-tier`

---

## ✅ Implementation Complete

### Core Architecture
- [x] Cloud orchestrator (draft-only mode, 5 layers of protection)
- [x] Local orchestrator (claim-by-move, dashboard merge)
- [x] Claim-by-move pattern (atomic os.rename() in both agents)
- [x] Dashboard single-writer (cloud → Updates/, local merges)
- [x] Cloud dashboard_updater.py (writes to Updates/cloud_status.md)

### Deployment Scripts
- [x] setup_vm.sh (VM provisioning, hardening)
- [x] vault_sync.sh (Git sync every 2 min)
- [x] transfer_secrets.sh (Gmail credentials to VM)
- [x] vault-sync-setup.sh (Initialize bare Git repo)

### Configuration
- [x] cloud/.env (CLOUD_DRAFT_ONLY=true, DRY_RUN=true)
- [x] local/.env (copied from Gold tier)
- [x] cloud/ecosystem.config.cjs (PM2 config, cloud only)
- [x] Vault .gitignore (excludes secrets)

### Documentation
- [x] DEPLOYMENT_GUIDE.md (step-by-step instructions)
- [x] README.md (architecture overview)
- [x] Platinum_Tier_Progress_Report.md (implementation status)
- [x] FINAL_CHECKLIST.md (this file)

### Test Gmail Account
- [x] Created: dedicated AI agent Gmail account
- [x] OAuth credentials downloaded
- [x] OAuth token generated
- [x] Authentication tested successfully

---

## 🚀 Ready for Deployment

### Prerequisites (User Actions Required)

1. **Azure VM**
   - [ ] Start VM in Azure Portal
   - [ ] Note public IP address
   - [ ] Verify SSH port 22 is open

2. **Local Secrets**
   - [ ] Move .pem key to `.azure-secrets/ai-employee-key.pem`
   - [ ] Run: `chmod 400 .azure-secrets/ai-employee-key.pem` (Git Bash)
   - [ ] Create `.azure-secrets/vm-ip.txt` with VM public IP

3. **Verify Files Exist**
   - [ ] `cloud/.env` exists with CLOUD_DRAFT_ONLY=true
   - [ ] `local/.env` exists (copied from Gold)
   - [ ] `scripts/setup_vm.sh` exists
   - [ ] `scripts/vault_sync.sh` exists
   - [ ] `scripts/transfer_secrets.sh` exists
   - [ ] `scripts/vault-sync-setup.sh` exists

---

## 📋 Deployment Sequence

Follow [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) steps 1-9:

1. **Prepare Local Secrets** (5 min)
2. **Start Azure VM** (1 min)
3. **Run VM Setup Script** (20 min)
4. **Transfer Test Gmail Credentials** (5 min)
5. **Set Up Vault Sync** (15 min)
6. **Deploy Cloud Agent Code** (10 min)
7. **Start Cloud Agent** (5 min)
8. **Set Up Vault Sync Cron** (10 min)
9. **Test Platinum Demo Gate** (10 min)

**Total Time**: ~90 minutes

---

## 🎯 Platinum Demo Gate Test

**Objective**: Prove cloud agent monitors Gmail 24/7 while laptop is off.

**Steps**:
1. Shut down local laptop completely
2. Send test email to your dedicated AI agent Gmail account
3. Wait 3 minutes (cloud polls every 2 min)
4. Start laptop
5. Wait 2 minutes (vault sync pulls from VM)
6. Open Obsidian → Pending_Approval/
7. Verify draft appears with cloud agent timestamp
8. Move draft to Approved/
9. Verify email sent via business Gmail (local agent)

**Success Criteria**:
- ✅ Draft created while laptop was off
- ✅ Draft synced to laptop via Git
- ✅ Local agent executed approved action
- ✅ Email sent from business Gmail (not test account)

---

## 🔒 Security Verification

Before starting deployment, verify:

- [ ] Test Gmail on cloud, business Gmail on local
- [ ] .pem key has 400 permissions
- [ ] .env files never committed to Git
- [ ] Vault .gitignore excludes secrets
- [ ] CLOUD_DRAFT_ONLY=true in cloud/.env
- [ ] SEND_ALLOWED=false in cloud MCP email server
- [ ] SSH password auth disabled on VM
- [ ] Only ports 22 + 8069 open on Azure NSG

---

## 💰 Cost Management

**Azure VM (D2s_v6, East Asia)**:
- ~$0.096/hour = $2.30/day
- 7-day demo: ~$16-18
- **Action**: Stop VM when not testing

**Monitoring**:
```bash
# Check VM status
az vm get-instance-view --name fte-agent-vm --resource-group fte-rg --query instanceView.statuses[1].displayStatus

# Stop VM (preserve credits)
az vm stop --name fte-agent-vm --resource-group fte-rg

# Start VM (when testing)
az vm start --name fte-agent-vm --resource-group fte-rg
```

---

## 📊 What Changed from Gold Tier

| Component | Gold Tier | Platinum Tier |
|-----------|-----------|---------------|
| **Deployment** | Single machine | Cloud (Azure) + Local (laptop) |
| **Gmail** | Local only | Cloud 24/7 + Local |
| **Execution** | Local only | Local only (cloud drafts only) |
| **Social Media** | Local only | Local only (unchanged) |
| **Dashboard** | Single file | Cloud writes Updates/, local merges |
| **File Processing** | Single agent | Claim-by-move (prevents double processing) |
| **Sync** | N/A | Git over SSH (every 2 min) |
| **Security** | Business Gmail local | Test Gmail cloud, business local |

---

## ✨ Key Features

1. **24/7 Gmail Monitoring**: Cloud agent never sleeps
2. **Zero Execution Risk**: Cloud agent CANNOT send emails (5 layers of protection)
3. **Laptop Independence**: Drafts created while laptop is off
4. **Atomic Claiming**: No double processing via os.rename()
5. **Conflict-Free Dashboard**: Single-writer pattern
6. **Private Sync**: Git over SSH (no GitHub, no public repos)
7. **Credential Isolation**: Test account on cloud, business account local
8. **Bot Detection Avoidance**: Social media stays local (Azure IPs flagged)

---

## 🎓 Hackathon Submission

**Tier**: Platinum (Distributed Architecture)
**Demo**: Email monitoring while laptop is off
**Innovation**: Claim-by-move + dashboard single-writer + draft-only security
**Cost**: ~$16-18 for 7-day demo period

**Judging Criteria**:
- ✅ Technical complexity (distributed agents, Git sync, atomic claiming)
- ✅ Security (5-layer draft-only protection, credential isolation)
- ✅ Practical value (24/7 monitoring, laptop independence)
- ✅ Cost efficiency (stop VM when not testing)

---

**Next Step**: Follow DEPLOYMENT_GUIDE.md to deploy to Azure VM and test the Platinum demo gate.
