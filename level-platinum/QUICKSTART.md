# Platinum Tier — Quick Reference

> **Note**: Platinum tier is a distributed system (Cloud VM + Local laptop). For full deployment instructions, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## Architecture Overview

Platinum splits the Gold tier into two agents:
- **Cloud Agent** (Azure VM, 24/7): Gmail monitoring, draft-only mode
- **Local Agent** (Laptop): All 7 watchers, approval execution, MCP actions

Communication happens via Git-synced Obsidian vault over SSH (every 2 minutes).

## Prerequisites

Same as Gold tier, plus:
- Azure VM (D2s_v6 or similar, 2 vCPU, 8GB RAM)
- SSH key for VM access
- Git installed on both cloud and local

## Quick Commands

### Cloud Agent (on Azure VM)
```bash
# Start cloud orchestrator
pm2 start ecosystem.config.cjs

# Check status
pm2 logs platinum-cloud-orchestrator
pm2 monit

# Vault sync (runs via cron every 2 min)
cd ~/cloud && bash scripts/vault_sync.sh
```

### Local Agent (on laptop)
```bash
cd level-platinum/local

# Start local orchestrator + all watchers
pm2 start ecosystem.config.cjs

# Check status
pm2 logs
pm2 monit

# Manual vault sync
cd .. && bash scripts/vault_sync.sh
```

## Full Setup

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for:
1. VM provisioning and hardening
2. Vault sync setup (bare Git repo over SSH)
3. Secret transfer (Gmail credentials)
4. PM2 + cron configuration
5. Demo gate testing

---

**For Gold tier quick start** (single-machine setup), see `../level-gold/QUICKSTART.md`.
```

Sessions saved to `.secrets/` and reused automatically on subsequent runs.

## Step 7 — Register MCP servers with Claude Code

Add to your global `~/.claude/settings.json` (or user settings in Claude Code):

```json
{
  "mcpServers": {
    "email": {
      "command": "node",
      "args": ["mcp-email-server/index.js"],
      "cwd": "<absolute-path-to-level-gold>"
    },
    "odoo": {
      "command": "node",
      "args": ["mcp-odoo-server/index.js"],
      "cwd": "<absolute-path-to-level-gold>"
    }
  }
}
```

Verify with `/fte-status` in Claude Code — both MCP servers should show as registered.

## Step 8 — Configure vault files

Open `AI_Employee_Vault/` in Obsidian (or any editor):

- **`Company_Handbook.md`** — Approval thresholds, tone rules, auto-reply policies
- **`FAQ_Context.md`** — Your services, pricing, business hours, escalation triggers
- **`Business_Goals.md`** — Revenue targets, Q-goals, LinkedIn post themes (used by CEO briefing)

## Step 9 — Start everything via PM2

```bash
pm2 start ecosystem.config.cjs
pm2 save       # Persist across reboots
pm2 startup    # Register as startup service — run the generated command as Admin
```

## Step 10 — Register scheduled tasks (Windows)

```bash
cd schedules
register_tasks.bat    # Registers all 5 schtasks entries at once
```

Or manually:

```cmd
set GOLD=<absolute-path-to-level-gold>

schtasks /create /tn "GoldFTE-GmailPoller"       /tr "%GOLD%\schedules\gmail_poll.bat"        /sc minute /mo 2
schtasks /create /tn "GoldFTE-MorningBriefing"   /tr "%GOLD%\schedules\morning_briefing.bat"  /sc daily  /st 08:00
schtasks /create /tn "GoldFTE-DailySocial"        /tr "%GOLD%\schedules\daily_social.bat"      /sc daily  /st 12:00
schtasks /create /tn "GoldFTE-WeeklyReview"       /tr "%GOLD%\schedules\weekly_review.bat"     /sc weekly /d SUN /st 09:00
schtasks /create /tn "GoldFTE-WeeklyAudit"        /tr "%GOLD%\schedules\weekly_audit.bat"      /sc weekly /d SUN /st 18:00
```

## Step 11 — Verify

```bash
pm2 logs          # Should see orchestrator heartbeat ticks every 10s
pm2 monit         # Process dashboard

uv run pytest tests/ -v   # Run all unit tests
```

Open `AI_Employee_Vault/Dashboard.md` in Obsidian — all 7 watchers should show **Online**, Odoo should show **✅ reachable**.

---

## Day-to-Day Usage

| Trigger | What happens |
|---------|-------------|
| Email arrives in Gmail | `gmail_watcher` → `Needs_Action/` → orchestrator → `fte-gmail-triage` → auto-reply or `Pending_Approval/` |
| WhatsApp message | `whatsapp_watcher.js` → `Needs_Action/` → orchestrator → `fte-whatsapp-reply` → auto or HITL |
| Facebook notification | `facebook_watcher` → `Needs_Action/` → orchestrator → `fte-triage` |
| File in `Drop_Box/` | `filesystem_watcher` → `Needs_Action/` → orchestrator → `fte-process` |
| Item in `Pending_Approval/` | Review in Obsidian → move to `Approved/` → orchestrator → `fte-approve` → MCP executes |
| Social post approved | Move to `Approved/` → orchestrator routes to scheduler → posts at jitter time |
| Daily 08:00 | Task Scheduler → `morning_briefing.bat` → `/fte-briefing` → `Plans/BRIEFING_*.md` |
| Sunday 18:00 | Task Scheduler → `weekly_audit.bat` → `/fte-audit` → `Plans/CEO_BRIEFING_*.md` |

## DRY_RUN Mode

Test everything without sending real emails, messages, or social posts:

```bash
# In .env:
DRY_RUN=true
```

All actions are logged to `Logs/YYYY-MM-DD.json` but never executed. Switch to `DRY_RUN=false` when ready to go live.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| WhatsApp QR not scanning | Delete `.secrets/whatsapp_session/` then re-run setup |
| Gmail auth fails | Delete `.secrets/gmail_token.json`, re-run `--auth-only` |
| Social session expired | Re-run `--setup` for that platform with `LI_HEADLESS=false` |
| Odoo unreachable | Run `docker compose up -d`, verify `ODOO_URL` + `ODOO_API_KEY` in `.env` |
| MCP permission denied | Check `.claude/settings.local.json` — all 7 MCP tools must be in `allow` list |
| Orchestrator not dispatching | `pm2 logs gold-orchestrator` — look for `skill_timeout` or `no_skills_dispatched` |
| Social post not firing at scheduled time | Check `.state/{platform}_scheduled.json` — verify `post_at` and `post_date` |
| Circuit breaker stuck open | Wait 15 min for half-open probe, or restart orchestrator after fixing underlying service |
