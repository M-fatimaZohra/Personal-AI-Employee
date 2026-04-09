# Platinum Tier — Distributed Cloud + Local AI Employee

The Platinum tier implements a **distributed two-agent architecture**: a Cloud Agent running 24/7 on Azure VM (monitoring Gmail, drafting replies) and a Local Agent on your laptop (approving and executing all actions). Sync happens via private Git repository over SSH.

## Architecture

```
                    CLOUD AGENT (Azure VM)                    LOCAL AGENT (Laptop)
                    ═══════════════════════                   ═══════════════════
Gmail inbox  ──→  gmail_watcher.py                            All 7 watchers
                         │                                           │
                         ▼                                           ▼
                  orchestrator.py                            orchestrator.py
                  (DRAFT ONLY)                               (FULL EXECUTION)
                         │                                           │
                         ▼                                           ▼
              Needs_Action/EMAIL_*.md                    Needs_Action/ALL_*.md
                         │                                           │
                         ▼                                           ▼
              In_Progress/cloud/                         In_Progress/local/
              (claim-by-move)                            (claim-by-move)
                         │                                           │
                         ▼                                           ▼
              Pending_Approval/APPROVAL_*.md             Pending_Approval/
                         │                                           │
                         └───────────────────────────────────────────┘
                                         │
                                    (user reviews)
                                         │
                                         ▼
                                   Approved/
                                         │
                                         ▼
                              approval_watcher.py (local only)
                                         │
                         ┌───────────────┼───────────────┐
                         ▼               ▼               ▼
                   MCP email       MCP Odoo      Playwright posters
                   (local only)    (local only)  (local only)
                         └───────────────┴───────────────┘
                                         │
                                       Done/

                    ┌─────────────────────────────────────────┐
                    │   Vault Sync (every 2 minutes)          │
                    │   Git over SSH (bare repo on VM)        │
                    │   Syncs: Needs_Action/, Pending_Approval/│
                    │   NEVER syncs: .env, .secrets/, .state/  │
                    └─────────────────────────────────────────┘
```

## Key Differences from Gold Tier

| Aspect | Gold Tier | Platinum Tier |
|--------|-----------|---------------|
| **Deployment** | Single machine | Cloud (Azure VM) + Local (laptop) |
| **Gmail Monitoring** | Local only | Cloud 24/7 + Local |
| **Execution** | Local only | Local only (cloud NEVER executes) |
| **Social Media** | Local only | Local only (Azure IPs = bot detection) |
| **WhatsApp** | Local only | Local only (device-bound session) |
| **Dashboard** | Single writer | Cloud writes Updates/, local merges |
| **File Claiming** | N/A | Atomic claim-by-move (prevents double processing) |
| **Security** | Business Gmail local | Test Gmail cloud, business Gmail local |
| **Sync** | N/A | Private Git repo over SSH (every 2 min) |

## File Structure

```
level-platinum/
│
├── cloud/                           # Deploy to Azure VM
│   ├── orchestrator.py              # Draft-only mode (CLOUD_DRAFT_ONLY=true)
│   ├── gmail_watcher.py             # Gmail API polling (every 2 min)
│   ├── dashboard_updater.py         # Writes to Updates/cloud_status.md
│   ├── mcp-email-server/            # MCP server (SEND_ALLOWED=false)
│   ├── mcp-odoo-server/             # MCP server (POST_ALLOWED=false)
│   ├── .env                         # CLOUD_DRAFT_ONLY=true, DRY_RUN=true
│   ├── pyproject.toml               # Python dependencies
│   ├── ecosystem.config.cjs         # PM2 config (cloud orchestrator only)
│   └── AI_Employee_Vault/           # Git-synced vault (symlink or clone)
│
├── local/                           # Runs on laptop
│   ├── orchestrator.py              # Full execution mode + dashboard merge
│   ├── (all 7 watchers)             # Gmail, WhatsApp, LinkedIn, FB, IG, Twitter, filesystem
│   ├── (all 4 posters)              # LinkedIn, Facebook, Instagram, Twitter
│   ├── approval_watcher.py          # Monitors Approved/ and Rejected/
│   ├── mcp-email-server/            # MCP server (SEND_ALLOWED=true)
│   ├── mcp-odoo-server/             # MCP server (POST_ALLOWED=true)
│   ├── .env                         # Full execution mode (same as Gold)
│   ├── pyproject.toml               # Python dependencies
│   └── ecosystem.config.cjs         # PM2 config (all watchers + orchestrator)
│
├── shared/                          # Used by both cloud and local
│   ├── base_watcher.py              # Abstract BaseWatcher class
│   ├── logger.py                    # JSON Lines structured logger
│   ├── backoff.py                   # Exponential backoff + CircuitBreaker
│   ├── id_tracker.py                # Persistent deduplication
│   └── .claude/skills/              # All 16 agent skills
│
├── scripts/                         # Deployment automation
│   ├── setup_vm.sh                  # VM provisioning (Python, Node, PM2, Docker)
│   ├── vault_sync.sh                # Git sync script (runs every 2 min via cron)
│   ├── transfer_secrets.sh          # Copy Gmail credentials to VM via scp
│   └── vault-sync-setup.sh          # Initialize bare Git repo on VM
│
├── AI_Employee_Vault/
│   ├── Dashboard.md                 # Merged by local agent (cloud + local status)
│   ├── Company_Handbook.md          # Agent behavior rules
│   ├── FAQ_Context.md               # Business context for replies
│   ├── Business_Goals.md            # Revenue targets, LinkedIn themes
│   ├── Needs_Action/                # Incoming items (synced)
│   ├── In_Progress/
│   │   ├── cloud/                   # Cloud agent claims
│   │   └── local/                   # Local agent claims
│   ├── Pending_Approval/            # Awaiting HITL review (synced)
│   ├── Approved/                    # User-approved actions (synced)
│   ├── Rejected/                    # User-rejected actions (synced)
│   ├── Plans/                       # PLAN_*.md, briefings (synced)
│   ├── Done/                        # Completed items (synced)
│   ├── Updates/                     # Cloud writes cloud_status.md here
│   └── Logs/                        # Daily JSON Lines logs (NOT synced)
│
└── .azure-secrets/                  # GITIGNORED — your VM credentials
    ├── ai-employee-key.pem          # SSH private key (chmod 400)
    └── vm-ip.txt                    # VM public IP address
```

## Security Model

### Five Layers of Draft-Only Protection (Cloud Agent)

1. **Environment variable**: `CLOUD_DRAFT_ONLY=true` in cloud/.env
2. **Startup check**: orchestrator.py raises RuntimeError if not set
3. **MCP server flags**: `SEND_ALLOWED=false`, `POST_ALLOWED=false`
4. **DRY_RUN mode**: `DRY_RUN=true` in cloud/.env (logs actions, never executes)
5. **No execution code**: Cloud orchestrator has no approval_watcher, no posters

### What Syncs (Git over SSH)

✅ **Synced** (every 2 minutes):
- Needs_Action/
- Pending_Approval/
- Approved/
- Rejected/
- Plans/
- Done/
- Updates/
- Dashboard.md
- Company_Handbook.md

❌ **NEVER synced** (security):
- .env, .env.*
- .secrets/
- *.pem, *.key
- .state/ (machine-specific)
- Logs/ (too large)
- Drop_Box/ (local filesystem only)

### Credential Isolation

- **Cloud Agent**: Test Gmail account (dedicated AI agent account)
- **Local Agent**: Business Gmail account (your real credentials)
- **Social Media**: Local only (Azure IPs trigger bot detection)
- **WhatsApp**: Local only (device-bound session)

## Claim-by-Move Pattern

Prevents double processing when both agents scan Needs_Action/:

```python
def try_claim_file(self, filepath: Path) -> bool:
    """Atomically claim a file by moving it to In_Progress/<agent>/."""
    dest = self.in_progress_dir / filepath.name  # cloud/ or local/
    try:
        filepath.rename(dest)  # Atomic operation
        return True
    except FileNotFoundError:
        return False  # Other agent claimed it first
```

Both agents scan Needs_Action/, but only one succeeds in moving the file. The other sees FileNotFoundError and skips.

## Dashboard Single-Writer Rule

Prevents Git merge conflicts:

- **Cloud Agent**: Writes to `Updates/cloud_status.md` (Gmail status, file counts)
- **Local Agent**: Merges `Updates/cloud_status.md` into `Dashboard.md` every tick
- **Result**: Dashboard.md has single writer (local), no conflicts

## Deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for full step-by-step instructions.

**Quick Start:**
1. Move .pem key to `.azure-secrets/ai-employee-key.pem`
2. Save VM IP to `.azure-secrets/vm-ip.txt`
3. Start Azure VM
4. Run `bash scripts/setup_vm.sh` on VM
5. Run `bash scripts/transfer_secrets.sh` from local
6. Run `bash scripts/vault-sync-setup.sh` from local
7. Deploy cloud code: `scp -r cloud/ ubuntu@<ip>:~/`
8. Start cloud agent: `pm2 start ecosystem.config.cjs`
9. Set up cron: `*/2 * * * * cd ~/cloud && bash scripts/vault_sync.sh`
10. Test: send email while laptop off → draft appears → approve → send

## Platinum Demo Gate

**Scenario**: Email arrives while laptop is completely offline → Cloud Agent detects, triages, and drafts reply → vault syncs → Local Agent picks up draft on return → human approves → MCP sends email → task moves to Done/.

**Flow**:
1. Local laptop is offline
2. Email arrives at the dedicated AI agent Gmail account
3. Cloud Agent detects it within 60 seconds (Gmail polling interval)
4. Cloud Agent creates `Needs_Action/email/EMAIL_<id>.md`, claims it to `In_Progress/cloud/email/`
5. Cloud Agent dispatches `/fte-gmail-triage` skill → classifies email, sets priority
6. Draft reply created in `Pending_Approval/APPROVAL_email_<id>.md`
7. Vault sync pushes draft to `vault-sync.git` on VM (cron, every 2 min)
8. Laptop returns online → Task Scheduler runs `vault_sync.bat` → draft appears in Obsidian
9. User reviews draft in `Pending_Approval/`, moves to `Approved/`
10. Local Agent's `approval_watcher.py` detects approved file → calls `mcp__email__send_email`
11. Email sent via business Gmail account → task moved to `Done/`

**End-to-end time**: Under 10 minutes (including human review)

## Agent Skills

All 16 skills from Gold tier are available in `shared/.claude/skills/`:

- `/fte-triage` — Classify all Needs_Action items
- `/fte-gmail-triage` — Classify emails as ROUTINE/SENSITIVE
- `/fte-gmail-reply` — Draft email replies (DIRECT or HITL)
- `/fte-whatsapp-reply` — Draft WhatsApp replies
- `/fte-approve` — Execute approved actions via MCP
- `/fte-linkedin-draft` — Draft LinkedIn posts
- `/fte-social-post` — Draft social media posts
- `/fte-social-summary` — Aggregate social engagement
- `/fte-odoo-audit` — Financial snapshot from Odoo
- `/fte-audit` — CEO Weekly Briefing
- `/fte-briefing` — Daily morning briefing
- `/fte-plan` — Decompose complex tasks
- `/fte-extract-attachment` — Process email attachments
- `/fte-status` — System health report
- `/fte-process` — Process Drop_Box items

## Cost Estimate

**Azure VM (D2s_v6, East Asia):**
- ~$0.096/hour = $2.30/day = $69/month
- Hackathon demo period (7 days): ~$16-18
- Stop VM when not testing to preserve credits

**Gmail API**: Free (15GB storage, unlimited API calls)

## Monitoring

**Cloud Agent (on VM):**
```bash
ssh -i .azure-secrets/ai-employee-key.pem ubuntu@$(cat .azure-secrets/vm-ip.txt)
pm2 logs platinum-cloud-orchestrator
pm2 monit
tail -f AI_Employee_Vault/Logs/$(date +%Y-%m-%d).json
```

**Local Agent (on laptop):**
```bash
cd level-platinum/local
pm2 logs
pm2 monit
```

**Vault Sync:**
```bash
# Check sync status
cd level-platinum/AI_Employee_Vault
git status
git log --oneline -5

# Manual sync (if needed)
cd level-platinum
bash scripts/vault_sync.sh
```

## Troubleshooting

**Cloud agent not drafting replies:**
- Check PM2: `pm2 status`
- Check logs: `pm2 logs platinum-cloud-orchestrator`
- Verify CLOUD_DRAFT_ONLY=true: `cat ~/cloud/.env`
- Test Gmail auth: `cd ~/cloud && uv run python gmail_watcher.py --once`

**Vault not syncing:**
- Check cron: `crontab -l`
- Check sync logs: `cat logs/vault_sync.log`
- Manual sync: `bash scripts/vault_sync.sh`
- Verify SSH: `ssh -i .azure-secrets/ai-employee-key.pem ubuntu@$(cat .azure-secrets/vm-ip.txt) echo OK`

**Double processing (both agents claim same file):**
- Check In_Progress/cloud/ and In_Progress/local/ — should be mutually exclusive
- Verify claim-by-move logic in both orchestrators
- Check logs for FileNotFoundError (expected when other agent claims first)

**Dashboard conflicts:**
- Cloud should write to Updates/cloud_status.md only
- Local should merge Updates/ into Dashboard.md
- Never edit Dashboard.md manually on cloud

## Security Checklist

Before deployment:
- [ ] Test Gmail account used on cloud (not business account)
- [ ] .pem key has 400 permissions
- [ ] .env files never committed to Git
- [ ] Vault .gitignore excludes .secrets/, .env, .state/
- [ ] CLOUD_DRAFT_ONLY=true in cloud/.env
- [ ] SEND_ALLOWED=false in cloud MCP email server
- [ ] SSH password auth disabled on VM
- [ ] Only ports 22 + 8069 open on Azure NSG
- [ ] VM stopped when not testing (preserve credits)

## Next Steps

1. **Deploy**: Follow [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
2. **Test**: Run Platinum demo gate (email while laptop off)
3. **Monitor**: Check PM2 logs and vault sync
4. **Iterate**: Adjust polling intervals, approval thresholds as needed

---

**Status**: ✅ Deployed — Azure VM operational, bidirectional vault sync verified, Gmail monitoring active, Odoo live with HTTPS
**Branch**: `004-platinum-tier`
**Date**: 2026-04-09
