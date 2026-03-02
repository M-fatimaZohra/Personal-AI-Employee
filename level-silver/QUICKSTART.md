# Quick Start — Silver Tier

> **Repo structure**: The root directory is `fte-Autonomus-employ/`. Each tier lives in its own subdirectory — `level-bronze/`, `level-silver/`, etc. This guide covers `level-silver/` only.

## Prerequisites

- Python 3.13+ with [`uv`](https://docs.astral.sh/uv/) installed
- Node.js v18+ and npm
- [PM2](https://pm2.keymetrics.io/) — `npm install -g pm2`
- Claude Code CLI — `npm install -g @anthropic-ai/claude-code`
- A Google account with Gmail API enabled (see step 3)
- A WhatsApp account for the bot (can be your own; QR login)
- A LinkedIn account (burner recommended for first run)

---

## Step 1 — Clone and enter the tier

```bash
git clone <repo-url>
cd fte-Autonomus-employ/level-silver
```

## Step 2 — Install dependencies

```bash
uv sync                              # Python dependencies
uv run playwright install chromium  # Playwright browser (LinkedIn)
cd mcp-email-server && npm install && cd ..  # MCP email server
```

## Step 3 — Create your environment file

```bash
cp .env.example .env
```

Open `.env` and fill in every value. Required fields:

| Variable | Where to get it |
|----------|----------------|
| `GMAIL_CREDENTIALS_PATH` | Path to your `gmail_credentials.json` (from Google Cloud Console) |
| `GMAIL_TOKEN_PATH` | Path where OAuth token will be saved (auto-created on first auth) |
| `LINKEDIN_SESSION_DIR` | Path where Playwright will save the LinkedIn session |
| `POST_WINDOW_START` | Earliest LinkedIn post time e.g. `09:00` |
| `POST_WINDOW_END` | Latest LinkedIn post time e.g. `18:00` |

## Step 4 — Add your Gmail credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → Create a project → Enable Gmail API
2. Create OAuth 2.0 credentials (Desktop app) → Download `credentials.json`
3. Save it to `.secrets/gmail_credentials.json`

```bash
mkdir -p .secrets
# copy your credentials.json here as gmail_credentials.json
```

## Step 5 — Authenticate services (first time only)

```bash
# Gmail — opens browser for OAuth consent
uv run python gmail_watcher.py --auth-only

# WhatsApp — shows QR code in terminal, scan with your phone
node whatsapp_watcher.js --setup

# LinkedIn — opens Playwright browser, log in manually, then close
uv run python linkedin_watcher.py --setup
```

Sessions are saved in `.secrets/` and reused on subsequent runs.

## Step 6 — Configure the MCP email server

Copy `.env` values into `mcp-email-server/.env` (or symlink):

```bash
cp .env mcp-email-server/.env
```

Register it with Claude Code (add to your global `~/.claude/claude_desktop_config.json` or `settings.json`):

```json
{
  "mcpServers": {
    "email": {
      "command": "node",
      "args": ["mcp-email-server/index.js"],
      "cwd": "/absolute/path/to/level-silver"
    }
  }
}
```

## Step 7 — Edit the vault config files

Open `AI_Employee_Vault/` in Obsidian (or any editor):

- **`Company_Handbook.md`** — Set your approval thresholds, tone rules, auto-reply policies
- **`FAQ_Context.md`** — Add your services, pricing, business hours, and escalation triggers

Skills read these files before drafting any reply. Fill them in before going live.

## Step 8 — Start everything

```bash
pm2 start ecosystem.config.js   # Starts orchestrator.py + whatsapp_watcher.js
pm2 save                         # Persist process list across reboots
pm2 startup                      # Register PM2 as a startup service
```

## Step 9 — Register scheduled tasks (Windows)

```bash
cd schedules

# Gmail polling every 2 minutes
schtasks /create /tn "SilverFTE-GmailPoller" /tr "%CD%\gmail_poll.bat" /sc minute /mo 2

# Morning briefing daily at 08:00
schtasks /create /tn "SilverFTE-MorningBriefing" /tr "%CD%\morning_briefing.bat" /sc daily /st 08:00

# Weekly LinkedIn draft every Sunday at 09:00
schtasks /create /tn "SilverFTE-WeeklyReview" /tr "%CD%\weekly_review.bat" /sc weekly /d SUN /st 09:00
```

## Step 10 — Verify

```bash
pm2 logs          # Watch live logs — should see heartbeat ticks
pm2 monit         # Process monitor dashboard

uv run pytest tests/ -v   # Run all tests
```

Open `AI_Employee_Vault/Dashboard.md` in Obsidian — all 4 watchers should show **Online**.

---

## Day-to-Day Usage

| Action | What happens |
|--------|-------------|
| Email arrives in Gmail | `gmail_watcher` → `Needs_Action/` → orchestrator → skill classifies → auto-reply or `Pending_Approval/` |
| WhatsApp message received | `whatsapp_watcher` → `Needs_Action/` → orchestrator → skill classifies → auto-reply or `Pending_Approval/` |
| File dropped in `Drop_Box/` | `filesystem_watcher` → `Needs_Action/` → orchestrator → skill processes |
| Item in `Pending_Approval/` | You review in Obsidian → move to `Approved/` or `Rejected/` → `approval_watcher` executes |

## DRY_RUN Mode

Test everything without sending real emails or WhatsApp messages:

```bash
# In .env:
DRY_RUN=true
```

All actions are logged but never executed. Switch to `DRY_RUN=false` when ready to go live.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| WhatsApp QR not scanning | Run `node whatsapp_watcher.js --setup` again; delete `.secrets/whatsapp_session/` first if session is corrupted |
| Gmail auth fails | Delete `.secrets/gmail_token.json` and re-run `--auth-only` |
| LinkedIn session expired | Run `linkedin_watcher.py --setup` again to re-authenticate |
| Orchestrator not dispatching | Check `pm2 logs orchestrator` — look for `no_skills_dispatched` or `skill_timeout` entries |
| Email not sending | Verify MCP server is registered in Claude Code settings and `DRY_RUN=false` |
