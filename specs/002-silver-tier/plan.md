# Implementation Plan: Silver Tier — Functional Assistant

**Branch**: `002-silver-tier` | **Date**: 2026-02-18 | **Spec**: [specs/002-silver-tier/spec.md](spec.md)
**Input**: Feature specification from `/specs/002-silver-tier/spec.md`
**Working Directory**: `/level-silver` (copy of `/level-bronze` + Silver extensions)
**Agent Name**: `silver-fte`

---

## Summary

Silver tier transforms the on-demand Bronze agent into a **fully autonomous** communication assistant. Four watchers (Filesystem, Gmail, WhatsApp, LinkedIn) run concurrently via PM2 (survive reboots and crashes), feeding into a unified `/Needs_Action` vault. An **Orchestrator** (`orchestrator.py`) automatically invokes the correct Claude skill when action files arrive — the user never types a command.

A **Tiered Approval System** governs all outbound actions: low-sensitivity messages (greetings, acknowledgments, basic replies) auto-execute immediately; high-sensitivity actions (financial, legal, client commitments) write to `/Pending_Approval` for human review — the **only manual step** in the pipeline. LinkedIn posts always pass through HITL first, then auto-post via Playwright with **randomized jitter timing** and **human behavior simulation** to avoid bot detection.

A **Ralph Wiggum stop hook** (`.claude/hooks/stop.py`) ensures multi-step tasks complete before Claude exits. A Claude reasoning loop creates structured `Plan.md` files for complex tasks. One MCP server (Email) gives Claude the ability to send emails after approval. **A secondary LinkedIn account is recommended for initial deployment** to protect the primary profile during testing. Everything runs locally at $0 cost.

---

## Technical Context

**Language/Version**: Python 3.13+ via `uv` (watchers, orchestrator) + Node.js v24+ (MCP server + WhatsApp watcher)
**Primary Dependencies**:
- Python: `google-auth`, `google-auth-oauthlib`, `google-api-python-client`, `playwright` (LinkedIn only), `watchdog`, `python-dotenv`
- Node.js (MCP email server): `@modelcontextprotocol/sdk`, `googleapis`, `dotenv`
- Node.js (WhatsApp watcher): `@whiskeysockets/baileys`, `pino`, `qrcode-terminal`, `chokidar`, `dotenv`, `fs-extra` — ESM (`"type": "module"`)
**Storage**: Local filesystem only — `.env` for secrets, `.json` files for ID tracking
**Testing**: `pytest` (Python watchers), manual integration test via vault
**Target Platform**: Windows 11, Python 3.13, Node.js v24+
**Performance Goals**: Gmail polling every 2 min, WhatsApp event-driven via Baileys WebSocket (keyword-gated, real-time), LinkedIn 30-min minimum interval, approval detection within 30 seconds
**Constraints**: $0 cost, all secrets in `.env`, all actions require human approval before execution, WhatsApp/LinkedIn personal-use only (ToS safeguards: read-only, rate-limited, keyword-gated)

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Local-First & Privacy-Centric | PASS | All data stays on local machine. No cloud storage. Gmail content stored in vault only. |
| II. Perception → Reasoning → Action | PASS | Gmail/WhatsApp/LinkedIn/FS watchers → Skills → MCP actions |
| III. File-Based Communication | PASS | All inter-agent state via `.md` files with YAML frontmatter |
| IV. Human-in-the-Loop | PASS | MANDATORY — every external action requires user approval. No exceptions. |
| V. Agent Skills Architecture | PASS | 10 skills total (3 Bronze enhanced + 7 new Silver) |
| VI. Observability & Audit Logging | PASS | JSON Lines logging for all actions, DRY_RUN support |
| VII. Incremental Tier Progression | PASS | Bronze preserved in `/level-bronze`, Silver extends in `/level-silver` |
| VIII. Resilience & Graceful Degradation | PASS | Exponential backoff for all APIs, one watcher failure doesn't crash others |

---

## Credentials Required

### 1. Gmail API — OAuth 2.0 (Free)

**What it is**: Allows the Gmail Watcher and Email MCP to read and send emails on your behalf.

**How to get it (step-by-step)**:
```
1. Go to https://console.cloud.google.com
2. Create a new project → Name it "personal-ai-employee"
3. APIs & Services → Enable APIs → search "Gmail API" → Enable
4. APIs & Services → Credentials → Create Credentials → OAuth client ID
5. Application type: Desktop app → Name: "silver-fte"
6. Download the JSON → save as level-silver/.secrets/gmail_credentials.json
7. First run: python gmail_watcher.py → browser opens → log in with Gmail → approve
8. Token auto-saved to level-silver/.secrets/gmail_token.json
```

**Files generated**:
| File | Contains | Gitignored |
|------|----------|------------|
| `.secrets/gmail_credentials.json` | Client ID + Client Secret from Google | YES |
| `.secrets/gmail_token.json` | Access token + Refresh token (auto-generated on first run) | YES |

**Cost**: Free. Gmail API free tier = 15,000 queries/day. At 2-min polling = 720 queries/day. Well within limits.

---

### 2. MCP Server Secret (Self-Generated)

**What it is**: A shared secret between Claude Code and the Email MCP server to prevent unauthorized calls.

**How to set it up**:
```bash
# Generate a random secret (run once)
python -c "import secrets; print(secrets.token_hex(32))"
# Copy the output → paste into .env as MCP_SERVER_SECRET=...
```

**Cost**: $0. Self-generated, no external service.

---

## Secrets: Complete `.gitignore` Reference

### What MUST NEVER reach GitHub

| File/Pattern | Contains | Why Critical |
|---|---|---|
| `level-silver/.env` | All API keys, bot tokens, MCP secrets | Direct credential exposure |
| `level-silver/.secrets/gmail_credentials.json` | Google OAuth Client ID + Secret | Can be used to impersonate your app |
| `level-silver/.secrets/gmail_token.json` | Access + Refresh tokens for your Gmail | Full Gmail account access |
| `level-silver/.secrets/` | Entire secrets directory | Catch-all for any future credential files |
| `level-silver/AI_Employee_Vault/Logs/*.json` | Email content, message content, user data | Privacy — logs contain real email/message text |
| `level-silver/AI_Employee_Vault/Done/*.md` | Processed emails, messages | Privacy — real communication data |
| `level-silver/AI_Employee_Vault/Needs_Action/*.md` | Unprocessed emails, messages | Privacy — real communication data |
| `level-silver/AI_Employee_Vault/Pending_Approval/*.md` | Approval requests with full content | Privacy — contains email drafts |
| `level-silver/AI_Employee_Vault/Plans/*.md` | Reasoning plans with private content | Privacy |
| `level-silver/.venv/` | Python virtual environment | Binary bloat |
| `level-silver/mcp-email-server/node_modules/` | Node.js dependencies | Binary bloat |
| `level-silver/*.pyc`, `__pycache__/` | Compiled Python | Build artifact |
| `.obsidian/workspace.json` | User-specific workspace state | User-specific |

### Root-level `.gitignore` additions

```gitignore
# Silver tier secrets (NEVER PUSH)
level-silver/.env
level-silver/.env.*
level-silver/.secrets/
level-silver/.secrets/gmail_credentials.json
level-silver/.secrets/gmail_token.json

# Silver vault data (privacy — contains real emails and messages)
level-silver/AI_Employee_Vault/Logs/*.json
level-silver/AI_Employee_Vault/Done/*.md
level-silver/AI_Employee_Vault/Needs_Action/*.md
level-silver/AI_Employee_Vault/Pending_Approval/*.md
level-silver/AI_Employee_Vault/Approved/*.md
level-silver/AI_Employee_Vault/Rejected/*.md
level-silver/AI_Employee_Vault/Plans/*.md

# Node.js
level-silver/mcp-email-server/node_modules/
level-silver/mcp-email-server/.env
```

### Template committed to git (safe)

```
level-silver/.env.example   ← committed, shows required vars with placeholder values
```

---

## Environment Variables — `.env.example`

```dotenv
# ══════════════════════════════════════════════
# Silver FTE — Environment Variables Template
# Copy to .env and fill in real values
# NEVER commit .env to git
# ══════════════════════════════════════════════

# ─── Gmail ───────────────────────────────────
# Path to OAuth credentials JSON from Google Cloud Console
GMAIL_CREDENTIALS_PATH=.secrets/gmail_credentials.json
# Path where the OAuth token is saved after first login
GMAIL_TOKEN_PATH=.secrets/gmail_token.json
# Gmail label/query to monitor (default: important unread)
GMAIL_QUERY=is:unread is:important

# ─── MCP Email Server ────────────────────────
# Port the MCP server listens on
MCP_SERVER_PORT=3001
# Shared secret between Claude Code and MCP server
MCP_SERVER_SECRET=generate_with_python_secrets_token_hex_32

# ─── LinkedIn ─────────────────────────────────
# Playwright session directory — use burner account path during testing
LINKEDIN_SESSION_DIR=.secrets/linkedin_burner_session
# Posting window (24h format) — post time randomized within this range
POST_WINDOW_START=09:00
POST_WINDOW_END=18:00

# ─── Behaviour ───────────────────────────────
# Set to "true" to log all actions without executing them
DRY_RUN=false
# Polling interval for Gmail watcher (seconds)
GMAIL_POLL_INTERVAL=120
# Approval file expiration (seconds, default 24h)
APPROVAL_EXPIRY_SECONDS=86400
# Orchestrator heartbeat interval (seconds)
ORCHESTRATOR_HEARTBEAT=30
```

---

## Installation Guide

### Prerequisites Check

```bash
# Verify Python 3.13+
python --version           # should be 3.13.x

# Verify Node.js v24+
node --version             # should be v24.x.x

# Verify uv
uv --version

# Verify git
git --version
```

### Step 1: Copy Bronze to Silver

```bash
# From repo root
cp -r level-bronze level-silver
cd level-silver

# Rename project in pyproject.toml
# Change: name = "bronze-fte"  →  name = "silver-fte"
# Change: description = "Bronze tier..."  →  "Silver tier..."

# Reinitialise uv environment for new project name
uv sync
```

### Step 2: Install Python dependencies

```bash
cd level-silver

# Core new dependencies
uv add google-auth google-auth-oauthlib google-api-python-client
uv add playwright python-dotenv

# Install Playwright browsers (first time only)
uv run playwright install chromium

# Dev dependencies (already present from Bronze)
# pytest already installed
```

### Step 3: Create secrets directory

```bash
mkdir -p level-silver/.secrets
echo "*" > level-silver/.secrets/.gitignore   # ignore everything inside
```

### Step 4: Set up environment file

```bash
cp level-silver/.env.example level-silver/.env
# Open .env in your editor and fill in real values
```

### Step 5: First-time Gmail OAuth

```bash
cd level-silver
# This opens a browser window — log in with your Gmail account and approve
uv run python gmail_watcher.py --auth-only
# Token saved to .secrets/gmail_token.json
```

### Step 6: Set up WhatsApp and LinkedIn sessions

```bash
cd level-silver

# Install WhatsApp watcher Node.js dependencies
npm install --prefix whatsapp_watcher   # or: cd whatsapp && npm install

# WhatsApp — first-time QR scan (session saved via LocalAuth, no re-scan on restart)
node whatsapp_watcher.js --setup

# LinkedIn — log in on first run (use burner account; session saved to LINKEDIN_SESSION_DIR)
uv run python linkedin_watcher.py --setup
# → Set LINKEDIN_SESSION_DIR=.secrets/linkedin_burner_session in .env first
```

### Step 7: Install and configure MCP Email server

```bash
cd level-silver/mcp-email-server
npm install
# Configure Claude Code to use the MCP server:
# Add to ~/.config/claude-code/mcp.json (or Windows equivalent):
# {
#   "mcpServers": {
#     "email": {
#       "command": "node",
#       "args": ["<absolute-path>/level-silver/mcp-email-server/index.js"],
#       "env": { "MCP_SERVER_SECRET": "<your_secret>" }
#     }
#   }
# }
```

### Step 8: Register scheduled tasks (Windows Task Scheduler)

```bash
cd level-silver/schedules
# Register all scheduled tasks (run as Administrator)
schtasks /create /tn "SilverFTE-GmailPoller" /tr "level-silver\schedules\gmail_poll.bat" /sc minute /mo 2
schtasks /create /tn "SilverFTE-MorningBriefing" /tr "level-silver\schedules\morning_briefing.bat" /sc daily /st 08:00
schtasks /create /tn "SilverFTE-WeeklyReview" /tr "level-silver\schedules\weekly_review.bat" /sc weekly /d SUN /st 09:00
```

---

## Full Flow: How Silver Tier Works

### Flow 1 — Incoming Email (Gmail)

```
[External world]                [Perception]               [Vault]
  Someone emails you   →→→   Gmail Watcher polls          EMAIL_abc123.md
  (every 120 seconds)         Gmail API (free)             created in
                              Detects unread+important     /Needs_Action/
                              Reads subject, body, from      ↓
                              Deduplicates by message_id   Dashboard.md
                              Removes from "unread"        updated
                                                           Log entry written

[Reasoning — you invoke /fte-gmail-triage]
  Reads EMAIL_abc123.md
  Reads Company_Handbook.md rules
  Classifies: type=email, priority=high (client), category=client_request
  Updates frontmatter with classification
  Writes PLAN_reply_abc123.md to /Plans:
    - [x] Read and understand email
    - [ ] Draft reply (requires-approval: true)
    - [ ] Send reply via MCP (requires-approval: true)

[Tiered Approval — /fte-gmail-reply runs Sensitivity Classifier]
  Reads email content + Company_Handbook.md rules

  DIRECT path (auto-send, no HITL):
    Patterns: simple ack, meeting confirm, "received", "thanks", FYI reply
    → Drafts reply → calls MCP send_email directly → logs to /Done

  SENSITIVE path (HITL required):
    Keywords: financial, legal, client commitment, contract, invoice, external
    → Drafts reply → writes APPROVAL_email_reply_abc123.md to /Pending_Approval/:
    ---
    type: email_reply
    to: client@company.com
    subject: Re: Invoice Request
    expires_at: 2026-02-19T08:00:00
    status: pending
    ---
    [Full draft email content for you to review]

[YOU — review in Obsidian]
  Open Pending_Approval/ in Obsidian
  Read the draft email
  Option A: Move file to /Approved/   ← you are happy with it
  Option B: Move file to /Rejected/   ← you want to change it
  Option C: Edit the file, then move to /Approved/

[Action — Approval Watcher detects your move]
  Sees file in /Approved/
  Reads approval file: action_type=email_reply
  Calls Email MCP: send_email(to, subject, body)
  MCP sends email via Gmail API
  Moves approval file to /Done/ with status=sent
  Updates Dashboard + writes log entry
```

---

### Flow 2 — WhatsApp Message (Tiered Approval)

```
[External world]               [Perception]               [Vault]
  Contact messages you →→→  WhatsApp Watcher             WHATSAPP_<chat>.md
  via WhatsApp              (Baileys, event-driven WebSocket) created in
  "urgent: invoice due"      sock.ev.on('messages.upsert') /Needs_Action/
                             Filters by WA_URGENT_KEYWORDS   ↓
                             Deduplicates by Baileys key ID Dashboard updated

[Reasoning — Orchestrator auto-invokes /fte-triage]
  Claude reads message + Company_Handbook.md
  Runs Sensitivity Classifier:

  ┌─ ROUTINE (low-risk message) ───────────────────────────────────────┐
  │  Patterns: "hello", "thanks", "yes", "got it", "will do"           │
  │  → fte-whatsapp-reply drafts reply                                  │
  │  → Writes APPROVAL_WA_*.md directly to /Approved/                  │
  │  → chokidar detects → sock.sendMessage() (zero HITL)               │
  │  → Logs to /Archive + Dashboard updated                             │
  └────────────────────────────────────────────────────────────────────┘

  ┌─ SENSITIVE (high-risk message) ────────────────────────────────────┐
  │  Keywords: invoice, payment, contract, deal, legal, confidential    │
  │  → fte-whatsapp-reply drafts reply                                  │
  │  → Writes APPROVAL_WA_*.md to /Pending_Approval                    │
  │  → User reviews in Obsidian, moves to /Approved or /Rejected        │
  │  → chokidar detects /Approved → 2s composing presence              │
  │  → sock.sendMessage() → moves file to /Archive                     │
  └────────────────────────────────────────────────────────────────────┘
```

---

### Flow 3 — LinkedIn Post (HITL-gated Playwright auto-post with jitter)

```
[Scheduled — Weekly Sunday 9 AM or on-demand]
  Task Scheduler runs weekly_review.bat
    → Triggers /fte-linkedin-draft skill

[Reasoning]
  Claude reads Business_Goals.md
  Claude reads Done/ for recent wins + Dashboard for activity stats
  Drafts a professional LinkedIn post (150-300 words, 3-5 hashtags)
  Writes LINKEDIN_DRAFT_2026-02-18.md to /Plans/ for HITL review:
    ---
    type: linkedin_post
    status: draft
    created_at: 2026-02-18
    hashtags: [#AI, #Productivity, #Automation]
    ---
    [Full post content]

[HITL — YOU review in Obsidian]
  Read the draft, edit if needed
  Move to /Approved/ when satisfied  ← the ONLY manual step

[Jitter Scheduling — ApprovalWatcher detects /Approved]
  Reads approval file: type=linkedin_post
  Does NOT post immediately — picks a random post time:
    post_at = random time within POST_WINDOW_START–POST_WINDOW_END
              (default: 09:00–18:00, never same minute two weeks in a row)
  Writes: .state/linkedin_scheduled.json {"post_at": "14:37", "file": "..."}
  Dashboard shows: "LinkedIn post scheduled for 2:37 PM"

[Orchestrator tick detects scheduled time]
  When now >= post_at:
    Session health check: if login page visible → alert Dashboard + abort
    Human behavior simulation:
      1. Navigate to feed (not post dialog directly)
      2. Browse + scroll for 15–45 random seconds
      3. Click "Start a post" with mouse-movement overshoot
      4. Type content character-by-character (60–130ms/char + micro-pauses)
      5. Proofread pause: 4–10 random seconds
      6. Click "Post"
    Move file to /Done/ with status=posted
    Delete scheduler state file

[Account Safety]
  Use LINKEDIN_SESSION_DIR env var to switch between burner and primary session
  Burner account recommended for initial deployment
```

---

### Flow 4 — Morning Briefing (Scheduled)

```
[08:00 AM — Task Scheduler]
  Runs morning_briefing.bat →  uv run python run_briefing.py
  Script invokes /fte-briefing skill

[Reasoning]
  Claude reads overnight EMAIL_*.md files in Needs_Action
  Claude reads Pending_Approval/ count
  Claude reads recent Logs entries
  Claude reads Plans/ for in-progress tasks
  Writes BRIEFING_2026-02-18.md to /Plans/:
    # Morning Briefing — 2026-02-18
    ## Overnight Activity
    - 3 new emails (2 high priority)
    ## Pending Approvals
    - 1 email reply waiting for your approval
    ## Active Plans
    - PLAN_invoice_client_a: step 2/4
    ## Suggested Actions
    1. Review APPROVAL_email_reply_abc123.md
    2. Check EMAIL_def456.md (marked urgent)

[You open Obsidian at 8 AM → briefing is waiting]
```

---

## Autonomy Architecture

### The Three Autonomy Engines

Silver tier is fully autonomous from perception to draft. The user's **only** intentional action is moving files in Obsidian to approve or reject. Everything else is machine-driven by three complementary systems:

| Engine | File | Role |
|--------|------|------|
| **Orchestrator** | `orchestrator.py` | Watches `/Needs_Action`, dispatches skills automatically |
| **Ralph Wiggum Stop Hook** | `.claude/hooks/stop.py` | Prevents Claude from exiting mid-task |
| **PM2 Process Manager** | `ecosystem.config.cjs` | Keeps watchers + orchestrator alive forever |

---

### 1. orchestrator.py — The Autonomy Engine

The Hackathon specification calls for a "Master Python Orchestrator that handles the timing and folder watching." This is what makes skills autonomous — the user never types a skill command.

**How it works:**

```
Email arrives
    → GmailWatcher creates EMAIL_abc.md in /Needs_Action
    → Orchestrator detects new file (watchdog on /Needs_Action)
    → Orchestrator runs: claude --print "/fte-gmail-triage EMAIL_abc.md"
    → Claude reads email, writes APPROVAL_*.md to /Pending_Approval
    → [User reviews in Obsidian — HITL gate — the ONLY manual step]
    → User moves to /Approved
    → ApprovalWatcher detects → triggers MCP send
    → Everything moves to /Done
```

**Skill routing logic:**

```python
# orchestrator.py — dispatch table
SKILL_ROUTING = {
    "EMAIL_":          "fte-gmail-triage",     # Gmail → specialized email triage + tiered approval
    "WHATSAPP_":       "fte-triage",           # WhatsApp → general triage (reply via fte-whatsapp-reply)
    "LINKEDIN_NOTIF_": "fte-triage",           # LinkedIn notifications → general triage
    "FILE_":           "fte-triage",           # Filesystem drops → general triage
}

def on_new_action_file(filepath: Path) -> None:
    for prefix, skill in SKILL_ROUTING.items():
        if filepath.name.startswith(prefix):
            subprocess.Popen([
                "claude", "--print",
                f"/{skill} {filepath.name}",
            ], cwd=str(filepath.parent.parent))
            return
```

Skills are **prompts, not daemons**. The Orchestrator is what automatically invokes them.

---

### 2. Ralph Wiggum Stop Hook — Task Persistence

From the Hackathon specification: *"a Stop hook that intercepts Claude's exit and feeds the prompt back."* This ensures multi-step tasks (e.g. draft + approve + send) run to completion:

```
Claude starts processing EMAIL_abc.md
Claude drafts reply → writes APPROVAL_*.md
Claude tries to exit
Stop hook checks: Is EMAIL_abc.md status = done? → NO
Stop hook re-injects prompt → Claude continues
Eventually EMAIL_abc.md moves to /Done → Stop hook allows exit
```

File: `level-silver/.claude/hooks/stop.py`

---

### 3. PM2 Process Manager — Process Immortality

From the Hackathon specification: *"Scripts terminate if SSH closes / crash on unhandled exceptions."*

```bash
pm2 start ecosystem.config.cjs   # start all processes
pm2 save                         # persist process list
pm2 startup                      # survive reboots
```

`ecosystem.config.cjs` manages:
- `run_watchers.py` — all 3 watchers in one process
- `orchestrator.py` — the autonomy engine

---

### Complete Autonomous Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  ALWAYS-ON PROCESSES (PM2 managed)                            │
│                                                               │
│  run_watchers.py                 orchestrator.py              │
│  ├── FilesystemWatcher           └── Watches /Needs_Action    │
│  ├── GmailWatcher (2min)             Calls: claude --print    │
│  ├── WhatsAppWatcher (whatsapp-web.js) "/<skill> <file>"      │
│  └── LinkedInWatcher (30min min)     + checks /Plans + /Appr │
└──────────────────────────────────────────────────────────────┘
           │                               │
           ▼                               ▼
┌──────────────────────┐      ┌──────────────────────────────┐
│  /Needs_Action/      │      │  Claude Code (auto-run)       │
│  EMAIL_abc.md        │─────▶│  EMAIL_  → fte-gmail-triage   │
│  WHATSAPP_xyz.md     │      │  WHATSAPP_ → fte-triage       │
│  LINKEDIN_NOTIF_.md  │      │  LINKEDIN_ → fte-triage       │
│  FILE_doc.md         │      │  FILE_  → fte-triage          │
└──────────────────────┘      └──────────┬─────────────────┘
                                         │
                          ┌──────────────▼──────────────────┐
                          │  Sensitivity Classifier          │
                          │  DIRECT → auto-execute now       │
                          │  SENSITIVE → /Pending_Approval   │
                          └──────┬────────────┬─────────────┘
                                 │            │
                    ┌────────────▼──┐  ┌──────▼───────────────┐
                    │  MCP / Playwright│  │  /Pending_Approval/  │
                    │  (auto-execute) │  │  APPROVAL_*.md       │◀─ Only human
                    │  → /Done        │  └──────┬───────────────┘   touchpoint
                    └────────────────┘         │ User moves to /Approved
                                               ▼
                                    ┌──────────────────────────┐
                                    │  ApprovalWatcher          │
                                    │  email → MCP send_email   │
                                    │  whatsapp → client.sendMessage()  │
                                    │  linkedin → Playwright    │
                                    │            + jitter delay │
                                    │  → Moves to /Done         │
                                    └──────────────────────────┘
```

---

### Revised Build Priority (Autonomy-First)

| # | What | Why |
|---|------|-----|
| 1 | `id_tracker.py` + `backoff.py` ✅ | Phase 2 foundation |
| 2 | `approval_watcher.py` | Closes the HITL loop |
| 3 | `orchestrator.py` | THE autonomy engine — auto-invokes skills |
| 4 | All 10 Agent Skills | The reasoning layer the orchestrator calls |
| 5 | Ralph Wiggum stop hook | Multi-step task persistence |
| 6 | PM2 setup + `whatsapp_watcher.js` + `linkedin_watcher.py` | Additional channels (hackathon requirement) + process immortality |
| 7 | MCP email server | The "hands" for sending |

---

## Silver Tier File Structure

```
level-silver/
├── pyproject.toml                    # name=silver-fte, python>=3.13
├── .env                              # GITIGNORED — all secrets
├── .env.example                      # COMMITTED — template with placeholders
├── .gitignore                        # Secrets + vault data + venv
├── .python-version                   # 3.13
├── README.md                         # Setup and usage guide
├── .secrets/                         # GITIGNORED entirely
│   ├── .gitignore                    # "*" (ignore all files inside)
│   ├── gmail_credentials.json        # From Google Cloud Console (OAuth client secret)
│   ├── gmail_token.json              # Auto-generated on first auth run
│   ├── whatsapp_session/             # Baileys session dir (auto-created by useMultiFileAuthState)
│   └── linkedin_session/             # Playwright persistent session (burner account)
│
├── run_watchers.py                   # Entry point — starts ALL 4 watchers in threads
├── orchestrator.py                   # Autonomy engine; watchdog on /Needs_Action, auto-invokes skills
├── base_watcher.py                   # (Bronze) Abstract base — unchanged
├── logger.py                         # (Bronze) JSON Lines logger — unchanged
├── dashboard_updater.py              # UPDATED — 4 watcher statuses + approvals + plans counts
│
├── filesystem_watcher.py             # (Bronze) Drop_Box watcher — unchanged
├── gmail_watcher.py                  # Gmail API polling watcher (every 2 min)
├── whatsapp_watcher.js               # WhatsApp watcher (Node.js, whatsapp-web.js, event-driven, receives + sends)
├── linkedin_watcher.py               # LinkedIn notifications watcher via Playwright (30-min min interval)
├── approval_watcher.py               # Monitors /Approved and /Rejected, triggers MCP actions
├── id_tracker.py                     # Persistent deduplication — JSON file in .state/
├── backoff.py                        # Exponential backoff retry decorator for all API calls
│
├── ecosystem.config.cjs               # PM2 config — silver-orchestrator + whatsapp-watcher (process immortality); .cjs required for ESM package
├── .state/                           # GITIGNORED — machine-specific runtime state
│   ├── processed_ids.json            # Deduplication IDs (Gmail, WhatsApp, LinkedIn)
│   └── linkedin_scheduled.json       # Jitter scheduler: {"post_at":"14:37","file":"LINKEDIN_DRAFT_*.md"}
│
├── .claude/
│   ├── hooks/
│   │   └── stop.py                   # Ralph Wiggum stop hook — re-injects prompt until task reaches /Done
│   └── skills/
│       ├── fte-triage/SKILL.md          # UPDATED — handles WHATSAPP_* + LINKEDIN_NOTIF_* + FILE_*
│       ├── fte-status/SKILL.md          # UPDATED — 4 watchers + approval + plans + scheduled post
│       ├── fte-process/SKILL.md         # UPDATED — handles email/whatsapp/social/file items
│       ├── fte-gmail-triage/SKILL.md    # Classify emails, set priority, run sensitivity classifier
│       ├── fte-gmail-reply/SKILL.md     # TIERED — DIRECT auto-send or SENSITIVE → /Pending_Approval
│       ├── fte-whatsapp-reply/SKILL.md  # NEW — TIERED: DIRECT auto-reply or SENSITIVE → /Pending_Approval
│       ├── fte-plan/SKILL.md            # Decompose complex tasks into PLAN_*.md in /Plans
│       ├── fte-approve/SKILL.md         # Process approved items from /Approved (MCP or Playwright)
│       ├── fte-linkedin-draft/SKILL.md  # Draft LinkedIn posts → /Plans for HITL review
│       └── fte-briefing/SKILL.md        # Morning/weekly briefing → BRIEFING_*.md in /Plans
│
├── mcp-email-server/                 # Node.js MCP server ("hands" for email)
│   ├── package.json                  # type:module, deps: @modelcontextprotocol/sdk, googleapis, dotenv
│   ├── index.js                      # MCP server entry — startup validation + 3 tools registered
│   └── tools/
│       ├── gmail_auth.js             # Shared OAuth2 client factory + RFC 2822 builder
│       ├── send_email.js             # send_email — HITL-gated (checks /Approved file exists)
│       ├── draft_email.js            # draft_email — creates Gmail draft, no approval needed
│       └── search_emails.js          # search_emails — parallel metadata fetch
│
├── schedules/                        # Windows Task Scheduler one-shot scripts
│   ├── gmail_poll.bat                # Runs gmail_watcher.py --once
│   ├── morning_briefing.bat          # Triggers fte-briefing skill via Claude CLI
│   ├── weekly_review.bat             # Triggers fte-linkedin-draft skill
│   └── README.md                     # schtasks registration commands
│
├── AI_Employee_Vault/
│   ├── Dashboard.md                  # COMMITTED — auto-updated; 4 watchers + HITL queue
│   ├── Company_Handbook.md           # COMMITTED — agent rules, email/social tone, approval thresholds
│   ├── Business_Goals.md             # GITIGNORED — revenue targets, active projects, LinkedIn themes
│   ├── Drop_Box/                     # (Bronze) GITIGNORED — filesystem drops land here
│   ├── Inbox/                        # (Bronze) reserved for future integrations
│   ├── Needs_Action/                 # GITIGNORED — EMAIL_*, WHATSAPP_*, LINKEDIN_NOTIF_*, FILE_*
│   ├── Plans/                        # GITIGNORED — PLAN_*, LINKEDIN_DRAFT_*, BRIEFING_*
│   ├── Pending_Approval/             # GITIGNORED — APPROVAL_* awaiting user review in Obsidian
│   ├── Approved/                     # GITIGNORED — user moves file here to trigger execution
│   ├── Rejected/                     # GITIGNORED — user moves file here to cancel action
│   ├── Done/                         # GITIGNORED — all completed/expired/rejected items
│   └── Logs/                         # GITIGNORED — JSON Lines daily audit logs (YYYY-MM-DD.json)
│
└── tests/
    ├── test_filesystem_watcher.py    # (Bronze) 3 tests — unchanged
    ├── test_gmail_watcher.py         # Mock Gmail API — fetch, dedup, action file creation
    ├── test_approval_watcher.py      # Approval detection, expiration, validation
    ├── test_id_tracker.py            # Persistent ID storage, dedup across restarts
    └── test_mcp_server.js            # MCP server auth, send_email HITL gate, DRY_RUN
```

### Gitignore Strategy

```
# Root .gitignore — vault rule (most important)
level-silver/AI_Employee_Vault/*                    # ignore all contents
!level-silver/AI_Employee_Vault/Company_Handbook.md # KEEP — agent rules config
!level-silver/AI_Employee_Vault/Dashboard.md        # KEEP — system status template
```

All other vault subdirectories (Done, Logs, Needs_Action, Pending_Approval, Approved, Rejected, Plans, Drop_Box, Business_Goals.md) are gitignored automatically via the `*` wildcard. The two negation exceptions are committed so the project bootstraps without manual vault setup.

---

## Key Design Decisions

### Decision 1: Tiered Approval — Sensitive vs. Direct Actions

Outbound actions are classified by risk before execution. Low-risk **direct** actions auto-execute immediately. High-risk **sensitive** actions always route through `/Pending_Approval` for human review. The classifier lives inside each reply skill and reads `Company_Handbook.md` rules.

| Channel | DIRECT (auto-execute) | SENSITIVE (HITL required) |
|---------|----------------------|--------------------------|
| Gmail | Ack, meeting confirm, "received", FYI reply | Financial, legal, client commitment, external stakeholder |
| WhatsApp | Greeting, "thanks", "yes/no", basic social | Invoice, payment, deal, contract, urgent business |
| LinkedIn | N/A — always HITL first, then Playwright posts | Every post (reviewed in Obsidian before auto-posting) |

**Sensitive-path approval file schema:**
```yaml
---
type: email_reply | linkedin_post | whatsapp_reply
action_id: <uuid>
to: recipient@email.com        # For email/WhatsApp actions
subject: Re: Invoice            # For email actions
sensitivity: sensitive          # sensitive | direct
status: pending                 # pending | approved | rejected | expired
created_at: 2026-02-18T08:00:00Z
expires_at: 2026-02-19T08:00:00Z
requested_by: fte-gmail-reply
---

## Action Preview

[Full content for user to review — complete email body, full post text, etc.]

## Why This Action

[Claude's reasoning + sensitivity classification rationale]

## Rules Applied

- Company Handbook Rule 2: respond within 24 hours
- Sensitivity: HIGH — client communication with financial implications
```

When in doubt, the classifier defaults to `sensitive`. False positives (unnecessary approvals) are safer than false negatives (auto-sending a sensitive message).

**Approval file schema:**
```yaml
---
type: email_reply | linkedin_post | whatsapp_reply
action_id: <uuid>
to: recipient@email.com        # For email actions
subject: Re: Invoice            # For email actions
status: pending                 # pending | approved | rejected | expired
created_at: 2026-02-18T08:00:00Z
expires_at: 2026-02-19T08:00:00Z
requested_by: fte-gmail-reply
---

## Action Preview

[Full content for user to review — complete email body, full post text, etc.]

## Why This Action

[Claude's reasoning for this action]

## Rules Applied

- Company Handbook Rule 2: respond within 24 hours
- Priority: high (client communication)
```

### Decision 2: WhatsApp via Baileys (@whiskeysockets/baileys); LinkedIn via Playwright (Hackathon Requirement)

The hackathon spec (Hackathoncontext.md) explicitly names WhatsApp and LinkedIn as the required watchers for Silver tier.

**WhatsApp** (`whatsapp_watcher.js` — Node.js ESM):
- `@whiskeysockets/baileys` — pure WebSocket implementation of WhatsApp multi-device protocol; no browser, no CDP, no Puppeteer
- WhatsApp treats it as a real linked device (indistinguishable from WhatsApp Desktop)
- Session persistence via `useMultiFileAuthState('.secrets/whatsapp_session/')` — no QR re-scan on restart
- Event-driven: `sock.ev.on('messages.upsert', ...)` — no polling
- QR rendered in terminal via `qrcode-terminal` (manual handler; `printQRInTerminal` is deprecated in installed version)
- `--setup` CLI flag: exits automatically after `connection === 'open'`, session saved
- Single process handles both **receiving** (writes `WHATSAPP_*.md`) **and sending** (`sock.sendMessage()`)
- chokidar watches `/Approved/` for `APPROVAL_WA_*.md` to auto-send approved replies
- Stealth: sends 2-second composing presence before every reply
- JID normalization: `normalizeJid()` converts legacy `@c.us` to `@s.whatsapp.net`
- Graceful shutdown: `process.on('SIGINT'/'SIGTERM', async () => { await sock.end(); process.exit(0) })` — prevents session corruption
- Tiered approval: ROUTINE replies write directly to `/Approved/` (auto-send); SENSITIVE routes to `/Pending_Approval`
- ToS safeguards: No proactive or mass messaging; auto-replies for ROUTINE classified messages only
- `ecosystem.config.cjs` (renamed from `.js` — required because package uses `"type": "module"` ESM)

**LinkedIn** (`linkedin_watcher.py`):
- Playwright `launch_persistent_context` on `linkedin.com/notifications/`
- 30-minute **minimum** interval for reading notifications — never polls faster
- Reads only your own notifications (mentions, comments)
- **Session health check on every open**: if login page detected → alert Dashboard + abort immediately (prevents typing into wrong fields, a major bot-detection signal)
- `generate_post_draft()` writes `LINKEDIN_DRAFT_<date>.md` to `/Plans` for HITL review
- **Auto-posts after user approval**: when user moves draft to `/Approved`, Playwright posts with jitter delay and human behavior simulation (see Decision 10)
- Session directory configurable via `LINKEDIN_SESSION_DIR` env var — enables burner/primary account switching

WhatsApp watcher (`whatsapp_watcher.js`) is event-driven — keyword-gated, deduplication via Baileys message key ID (persisted to `.state/wa_processed_ids.json`), HITL-gated replies sent via `sock.sendMessage()` from the same Node.js process.

### Decision 3: Gmail API Not Gmail SMTP

We use the Gmail API (OAuth 2.0) not SMTP/IMAP for reading emails because:
- OAuth is more secure (no password in config, revocable)
- API provides structured data (labels, thread IDs, deduplication)
- SMTP/IMAP would require "Less Secure Apps" enabled (deprecated by Google)

For sending, the Email MCP uses the Gmail API `send` endpoint (via the same OAuth token).

### Decision 4: ID Tracking via JSON File

Processed Gmail message IDs, WhatsApp chat IDs, and LinkedIn notification IDs are stored in `level-silver/.state/processed_ids.json`. This file:
- Is gitignored (contains no secrets, but is machine-specific state)
- Persists across watcher restarts (prevents duplicate processing)
- Is separate from the vault (not markdown, not user-visible)

### Decision 5: LinkedIn Posts via HITL-Gated Playwright (No Official API)

LinkedIn's free API does not allow posting for personal accounts. Rather than requiring manual copy-paste, the approved draft is posted via Playwright automation after user HITL approval. This fully satisfies the hackathon requirement ("Automatically Post on LinkedIn") while keeping the human as the quality gate.

**Why Playwright over copy-paste:**
- Fully closes the automation loop — user's only action is moving a file in Obsidian
- The HITL review step (moving to `/Approved`) is the quality gate, not posting mechanics
- Playwright already runs for the LinkedIn watcher, so no new dependency is added

**Safeguards to prevent ToS violations:**
- No proactive/autonomous posting; all posts are HITL-triggered and jitter-delayed
- Jitter delay: post time randomized within a configurable window (default 09:00–18:00)
- Human behavior simulation: feed browsing, character-by-character typing, random pauses (see Decision 10)
- Session health check: abort if login page detected (prevents bot-pattern behavior on expired sessions)
- Frequency cap: maximum 1 post per day enforced via `scheduler_state.json`
- Burner account: use `LINKEDIN_SESSION_DIR` to point to a secondary account during testing (see Decision 10)

### Decision 6: MCP Server Security

The Email MCP server validates every incoming request against `MCP_SERVER_SECRET`. Requests without a valid secret are rejected with a 401 error and logged. This prevents Claude from sending emails without the MCP server being properly configured.

### Decision 7: Orchestrator as Autonomy Engine (not daemon skills)

Skills are stateless prompts, not always-on processes. Making each skill a daemon would require managing 10 separate processes, each consuming memory, with independent crash/restart logic. Instead, a single `orchestrator.py` uses watchdog to monitor `/Needs_Action` and dispatches skills on-demand via `subprocess.Popen(["claude", "--print", "/<skill> <file>"])`. This means:
- Skills remain simple SKILL.md files — no Python daemon code needed
- The orchestrator is the only process with filesystem intelligence
- Adding a new skill requires only adding one line to `SKILL_ROUTING`
- Claude Code handles all AI reasoning; the orchestrator only handles routing

The Ralph Wiggum stop hook complements this: since `claude --print` exits after each skill run, the hook intercepts the exit signal, checks whether the triggered file has reached `/Done`, and re-injects the prompt if the task is still in progress. This gives Claude persistence across what would otherwise be disconnected single-shot invocations.

### Decision 8: PM2 over Windows Task Scheduler for Process Management

Windows Task Scheduler can start processes on a schedule but does not restart crashed processes or persist across SSH disconnects. PM2 (Node.js process manager, cross-platform) provides:
- Automatic restart on crash with configurable backoff
- Log aggregation (`pm2 logs`)
- Startup persistence (`pm2 startup` generates OS-level init script)
- Process monitoring (`pm2 monit`)

Both `run_watchers.py` and `orchestrator.py` are registered in `ecosystem.config.cjs`. Task Scheduler `.bat` scripts are retained for scheduled one-shot tasks (morning briefing, weekly review) where PM2 scheduling is not needed.

### Decision 9: Sensitivity Classifier — Tiered Approval

Each reply skill (`fte-gmail-reply`, `fte-whatsapp-reply`) classifies the message against `Company_Handbook.md` and routes:
- **DIRECT**: greeting, ack, simple yes/no, social — auto-executes via MCP or Playwright
- **SENSITIVE**: invoice, payment, contract, legal, external stakeholder — writes to `/Pending_Approval`
- **Ambiguity rule**: default to `SENSITIVE` when uncertain
- Decision logged to action file frontmatter as `sensitivity: direct|sensitive` + `sensitivity_reason`

### Decision 10: LinkedIn Safety — Jitter, Human Simulation, Burner Account

- **Jitter**: post time randomized within `POST_WINDOW_START`–`POST_WINDOW_END` (default 09:00–18:00), persisted to `.state/linkedin_scheduled.json`; 23h minimum gap between posts
- **Human simulation**: navigate to feed first → scroll → character-by-character typing → proofread pause → post. This human behavior simulation is the primary mitigation against account restriction, as it makes automated posting indistinguishable from manual user activity.
- **Session health check**: if login page detected on open → alert Dashboard + abort (prevents bot fingerprinting on expired sessions)
- **Burner account**: `LINKEDIN_SESSION_DIR` env var switches between test and primary session directories; validate on burner for ≥2 weeks before graduating to primary account

---

## Data Models

### `EMAIL_<gmail_id>.md` — Gmail Action File
```yaml
---
type: email
message_id: msg_abc123xyz
thread_id: thread_def456
from: client@company.com
to: you@gmail.com
subject: Invoice Request for Project Alpha
received_at: 2026-02-18T07:42:00Z
status: needs_action
priority: high
labels: [IMPORTANT, UNREAD]
has_attachments: false
source: Gmail
processed_by: null
---

[Email body text here]
```

### `WHATSAPP_<jid>_<datestamp>.md` — WhatsApp Action File
```yaml
---
type: whatsapp_message
chat_id: "1234567890@s.whatsapp.net"
chat_name: "ContactName"
message_id: "BAILEYS_MSG_KEY_ID"
date: "2026-02-18T07:50:00.000Z"
status: needs_action
priority: high
keywords_matched: ["urgent", "invoice"]
source: WhatsApp
processed_by: null
---

[Message text here]
```

Note: `chat_id` is the full Baileys JID (`@s.whatsapp.net`). `chat_name` is `pushName` (contact's display name) or the number prefix. JIDs ending in `@g.us` (groups) and `status@broadcast` are silently skipped.

### `LINKEDIN_NOTIF_<notif_id>.md` — LinkedIn Notification File
```yaml
---
type: linkedin_notification
notif_id: ln_abc123
notification_type: mention
from_user: Jane Doe
date: 2026-02-18T09:00:00Z
status: needs_action
priority: normal
source: LinkedIn
processed_by: null
---

[Notification text here]
```

### `APPROVAL_<action_id>.md` — HITL Approval File
```yaml
---
type: email_reply
action_id: a1b2c3d4
to: client@company.com
subject: Re: Invoice Request
status: pending
created_at: 2026-02-18T08:05:00Z
expires_at: 2026-02-19T08:05:00Z
requested_by: fte-gmail-reply
trigger_file: EMAIL_msg_abc123xyz.md
---

## Draft Content (Review Before Approving)

[Full email body that Claude drafted]

## Claude's Reasoning

Responding to invoice request from client. Using professional tone per Handbook Rule 1.
```

### `PLAN_<task_id>.md` — Reasoning Plan File
```yaml
---
type: plan
plan_id: p9q8r7
trigger_file: EMAIL_msg_abc123xyz.md
status: in_progress
created_at: 2026-02-18T08:00:00Z
completed_at: null
---

## Steps

- [x] Read and classify incoming email
- [x] Identify required action: send invoice + reply
- [ ] Draft email reply (requires_approval: true)
- [ ] Draft invoice document
- [ ] Send email reply via MCP (requires_approval: true)
- [ ] Log completion
```

---

## Constitution Principle Compliance

| Principle | Implementation |
|-----------|---------------|
| Local-First | All data in local vault. Gmail/WhatsApp/LinkedIn content stored locally only. Nothing leaves the machine without approval. |
| Perception → Reasoning → Action | Gmail/WhatsApp/LinkedIn/FS Watchers → Skills (triage, plan, draft) → Approval Watcher → MCP |
| File-Based Communication | YAML frontmatter on all action files. Approval moves = user signal. |
| HITL (non-negotiable) | Every external action writes to `/Pending_Approval`. No bypass. No auto-approve. |
| Agent Skills Architecture | 10 skills total in `.claude/skills/`. All AI logic in SKILL.md files. |
| Observability | JSON Lines logging for all watcher events, approval events, MCP calls. |
| Incremental Progression | Bronze in `/level-bronze` untouched. Silver extends in `/level-silver`. |
| Resilience | Exponential backoff for Gmail. WhatsApp uses Baileys with `connection.update` auto-reconnect on network drops; logs out cleanly on `DisconnectReason.loggedOut`. LinkedIn uses Playwright with graceful skip on session failure. One watcher crash doesn't stop others. |

---

## Risks & Mitigations

| Risk | Likelihood | Blast Radius | Mitigation |
|------|-----------|-------------|------------|
| Gmail OAuth token expires | Medium | Gmail watcher stops | Auto-refresh via `google-auth` library. If refresh fails, log auth error + alert Dashboard. |
| WhatsApp/LinkedIn session expires | Medium | Watcher skips gracefully | WhatsApp: Baileys `connection.update` event auto-reconnects on network drops; on `DisconnectReason.loggedOut`, logs error and exits — user reruns `node whatsapp_watcher.js --setup`. LinkedIn: Playwright persistent context; on expiry logs warning and skips. Other watchers continue. |
| WhatsApp/LinkedIn ToS violation | Low | Account action by platform | Safeguards in place: read-only, keyword-gated, rate-limited, personal-use only. No mass messaging, no auto-posting. |
| User approves wrong action | Low | Unintended email sent | Approval file shows complete preview including recipient and full content. Expiry gives time to reject. |
| Vault data git-pushed accidentally | Low | Private emails on GitHub | Comprehensive `.gitignore` + CI check (if added). All vault data patterns gitignored. |
| MCP server not running | Medium | Email sending fails | Approval watcher logs MCP failure, sets file status=failed, notifies via Dashboard. |
| Orchestrator spawns duplicate skill processes | Medium | Duplicate action files, log noise | Orchestrator maintains an in-memory set of files currently being processed; skips dispatch if file is already in-flight. |
| `claude` CLI not on PATH when orchestrator spawns subprocess | Medium | Skills never invoked | `ecosystem.config.cjs` sets explicit PATH; orchestrator startup validates `claude --version` before watching. |
| Stop hook re-injects prompt indefinitely (infinite loop) | Low | Claude never exits | Hook checks max re-injection count (configurable, default 5). After limit, logs critical and exits. |
| PM2 not installed / process list lost after OS update | Low | Watchers don't auto-start | `pm2 save` + `pm2 startup` documented in QUICKSTART. Recovery: `pm2 resurrect`. |
