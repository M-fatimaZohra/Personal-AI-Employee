# Quick Start — Gold Tier

> **Repo structure**: Root is `fte-Autonomus-employ/`. This guide covers `level-gold/` only.
> Gold tier extends Silver — if running Silver alongside, they share Gmail OAuth credentials but use separate PM2 processes.

## Prerequisites

- Python 3.13+ with [`uv`](https://docs.astral.sh/uv/)
- Node.js v20+ and npm
- [PM2](https://pm2.keymetrics.io/) — `npm install -g pm2`
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — for Odoo
- Claude Code CLI or CCR — `npm install -g @anthropic-ai/claude-code`
- A Google account with Gmail API enabled
- WhatsApp account (scan QR on first run)
- LinkedIn account (burner recommended)
- Facebook, Instagram, Twitter accounts (burner recommended for testing)

---

## Step 1 — Clone and enter the tier

```bash
git clone <repo-url>
cd fte-Autonomus-employ/level-gold
```

## Step 2 — Install Python + Node dependencies

```bash
uv sync                                        # Python dependencies
uv run playwright install chromium             # Playwright browser
cd mcp-email-server && npm install && cd ..    # MCP email server
cd mcp-odoo-server && npm install && cd ..     # MCP Odoo server
npm install                                    # Root Node deps (whatsapp-web.js, chokidar)
```

## Step 3 — Create your environment file

```bash
cp .env.example .env
```

Fill in every value. Key variables:

| Variable | Where to get it |
|----------|----------------|
| `GMAIL_CREDENTIALS_PATH` | Path to `gmail_credentials.json` (Google Cloud Console) |
| `GMAIL_TOKEN_PATH` | Auto-created on first auth run |
| `ODOO_URL` | `http://localhost:8069` (local Docker default) |
| `ODOO_DB` | `fte_business` (name you choose during Odoo setup) |
| `ODOO_API_KEY` | Generated in Odoo → Settings → Users → API Keys |
| `LINKEDIN_SESSION_DIR` | `.secrets/linkedin_session` |
| `FB_SESSION_DIR` | `.secrets/facebook_session` |
| `IG_SESSION_DIR` | `.secrets/instagram_session` |
| `TWITTER_SESSION_DIR` | `.secrets/twitter_session` |
| `POST_WINDOW_START` | `09:00` (earliest social post time) |
| `POST_WINDOW_END` | `18:00` (latest social post time) |

## Step 4 — Start Odoo (Docker)

```bash
docker compose up -d
```

First-time Odoo setup:
1. Open `http://localhost:8069` in browser
2. Create database — name it `fte_business` (matches `ODOO_DB` in `.env`)
3. Install **Accounting** module from Apps
4. Go to Settings → Users & Companies → Users → Administrator → API Keys → **Generate**
5. Copy the key into `.env` as `ODOO_API_KEY`

## Step 5 — Add Gmail credentials

1. [Google Cloud Console](https://console.cloud.google.com/) → Create project → Enable Gmail API
2. Credentials → OAuth 2.0 Client → Desktop app → Download JSON
3. Save as `.secrets/gmail_credentials.json`

## Step 6 — Authenticate all services (first time only)

```bash
mkdir -p .secrets

# Gmail — opens browser for OAuth consent
uv run python gmail_watcher.py --auth-only

# WhatsApp — shows QR code in terminal, scan with phone
wa_setup.bat          # Windows helper, or:
node whatsapp_watcher.js --setup

# LinkedIn — opens Playwright browser, log in manually, then close
LI_HEADLESS=false uv run python linkedin_watcher.py --setup

# Facebook — opens Playwright browser
LI_HEADLESS=false uv run python facebook_watcher.py --setup

# Instagram — opens Playwright browser
LI_HEADLESS=false uv run python instagram_watcher.py --setup

# Twitter/X — opens Playwright browser
LI_HEADLESS=false uv run python twitter_watcher.py --setup
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
