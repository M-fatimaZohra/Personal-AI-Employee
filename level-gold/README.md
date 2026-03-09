# Gold Tier — Autonomous Business AI Employee

The Gold tier adds **Odoo accounting integration**, **Facebook, Instagram, and Twitter automation**, **multi-domain cross-platform workflows**, a **weekly CEO briefing**, and full **error recovery with circuit breakers** on top of the Silver foundation.

## Architecture

```
External World              Watchers (Perception)              Vault (State Bus)
─────────────────────────────────────────────────────────────────────────────────
Gmail inbox       ──→  gmail_watcher.py        ──→  Needs_Action/EMAIL_*.md
WhatsApp msg      ──→  whatsapp_watcher.js     ──→  Needs_Action/WHATSAPP_*.md
LinkedIn notif    ──→  linkedin_watcher.py     ──→  Needs_Action/LINKEDIN_NOTIF_*.md
Facebook notif    ──→  facebook_watcher.py     ──→  Needs_Action/SOCIAL_FB_*.md
Instagram notif   ──→  instagram_watcher.py    ──→  Needs_Action/SOCIAL_IG_*.md
Twitter mention   ──→  twitter_watcher.py      ──→  Needs_Action/TWITTER_*.md
Drop_Box/         ──→  filesystem_watcher.py   ──→  Needs_Action/FILE_*.md
                                                            │
                              orchestrator.py ─────────────┘  (heartbeat every 10s)
                                     │
                     ┌───────────────┴──────────────────┐
                     ▼                                   ▼
              ROUTINE item                         SENSITIVE item
          auto-write to Approved/              → Pending_Approval/
                     │                             │ (user reviews in Obsidian)
                     │                             │ moves to Approved/ or Rejected/
                     └─────────────────────────────┘
                                     │
                          approval_watcher.py
                                     │
                  ┌──────────────────┼──────────────────┐
                  ▼                  ▼                   ▼
           MCP email server    MCP Odoo server    Playwright posters
          (send/draft/search)  (invoice/partner)  (FB/IG/TW/LI)
                  └──────────────────┴──────────────────┘
                                     │
                                   Done/
```

**7 Watchers** detect events → **Orchestrator** dispatches Claude skills → **Tiered HITL approval** routes ROUTINE items directly, SENSITIVE items through human review → **2 MCP servers + Playwright** execute actions.

## File Structure

```
level-gold/
│
│── Core Orchestration
├── orchestrator.py              # Central autonomy engine — 10s heartbeat, skill dispatch,
│                                #   plan awareness (Ralph Wiggum), social schedulers,
│                                #   Odoo health check, dashboard sync, SIGINT shutdown
├── approval_watcher.py          # Watchdog on Approved/ + Rejected/ — validates frontmatter,
│                                #   routes social posts, leaves other approvals for orchestrator
│
│── Perception (Watchers)
├── gmail_watcher.py             # Gmail API OAuth polling (every 2 min) → EMAIL_*.md
├── whatsapp_watcher.js          # Baileys WebSocket (Node.js, event-driven) → WHATSAPP_*.md
│                                #   chokidar watches Approved/APPROVAL_WA_*.md → sendMessage()
├── linkedin_watcher.py          # Playwright, 30-min interval → LINKEDIN_NOTIF_*.md
├── facebook_watcher.py          # Playwright, 30-min interval → SOCIAL_FB_*.md
├── instagram_watcher.py         # Playwright, 30-min interval → SOCIAL_IG_*.md
├── twitter_watcher.py           # Playwright, 30-min interval → TWITTER_*.md
├── filesystem_watcher.py        # Watchdog Drop_Box monitor (from Bronze) → FILE_*.md
│
│── Action (Posters / Schedulers)
├── linkedin_poster.py           # Playwright LinkedIn poster + JitterScheduler
│                                #   (randomised post time within POST_WINDOW, 23h gap)
├── facebook_poster.py           # Playwright Facebook poster + FacebookScheduler
├── instagram_poster.py          # Playwright Instagram poster + InstagramScheduler
│                                #   (media tracking: get_next_media, mark_used, auto-pause)
├── twitter_poster.py            # Playwright Twitter/X poster + TwitterScheduler (280 char)
│
│── Utilities
├── base_watcher.py              # Abstract BaseWatcher class (from Bronze)
├── dashboard_updater.py         # Atomic Dashboard.md writer (temp-file + rename)
├── id_tracker.py                # Persistent deduplication — .state/processed_ids.json
├── backoff.py                   # Exponential backoff decorator + CircuitBreaker state machine
│                                #   (closed → open after N failures → half_open → closed)
├── logger.py                    # JSON Lines structured logger → Logs/YYYY-MM-DD.json
├── attachment_extractor.py      # PDF/text extraction from email attachments → ATTACHMENT_*.md
├── log_archive.py               # 90-day log retention — moves old logs to Logs/Archive/
│
│── Helper Scripts (one-off utilities, not in PM2)
├── complete_approval.py         # CLI helper: mark approval as executed + move to Done/
├── execute_facebook_post.py     # CLI helper: fire a Facebook post directly from file
├── extract_and_post.py          # CLI helper: extract attachment + create action file
├── run_watchers.py              # Legacy entry point (superseded by orchestrator.py)
│
│── MCP Servers (Node.js, stdio transport)
├── mcp-email-server/
│   ├── index.js                 # MCP server entry — startup validation, 3 tools registered
│   └── tools/
│       ├── gmail_auth.js        # Shared OAuth2 client factory + RFC 2822 builder
│       ├── send_email.js        # send_email — HITL-gated (checks Approved/ file exists)
│       ├── draft_email.js       # draft_email — creates Gmail draft, no approval needed
│       └── search_emails.js    # search_emails — parallel metadata fetch
│
├── mcp-odoo-server/
│   ├── index.js                 # MCP server entry — Odoo JSON-RPC, 4 tools registered
│   └── tools/
│       ├── odoo_auth.js         # JSON-RPC bearer token connection + validation
│       ├── get_financial_summary.js  # Read: monthly P&L + outstanding/overdue invoices
│       ├── list_transactions.js      # Read: search invoices/bills by date, type, partner
│       ├── create_invoice.js         # Write (HITL-gated): create + post customer invoice
│       └── create_partner.js         # Write (HITL-gated): create customer or vendor
│
│── Agent Skills (Claude Code)
├── .claude/
│   ├── settings.json            # Project-level Claude Code config
│   ├── settings.local.json      # MCP tool permissions (gitignored)
│   ├── hooks/
│   │   └── stop.py              # Ralph Wiggum stop hook — re-injects prompt until
│   │                            #   task reaches /Done (multi-step task persistence)
│   └── skills/
│       ├── fte-triage/          # Classify all Needs_Action item types, update priority
│       ├── fte-gmail-triage/    # Classify emails as ROUTINE/SENSITIVE, set priority
│       ├── fte-gmail-reply/     # Draft email replies — DIRECT auto-send or HITL
│       ├── fte-whatsapp-reply/  # Draft WhatsApp replies — ROUTINE auto or SENSITIVE HITL
│       ├── fte-approve/         # Execute approved items via MCP (email, Odoo)
│       ├── fte-linkedin-draft/  # Draft LinkedIn posts based on Business_Goals.md
│       ├── fte-social-post/     # Draft and route FB/IG/TW posts to schedulers
│       ├── fte-social-summary/  # Aggregate social media engagement metrics
│       ├── fte-odoo-audit/      # Financial audit via Odoo MCP — P&L, outstanding invoices
│       ├── fte-audit/           # CEO Weekly Briefing — finance + ops + social + goals
│       ├── fte-briefing/        # Daily morning briefing — emails + plans + Odoo snapshot
│       ├── fte-plan/            # Decompose complex tasks into PLAN_*.md with checkboxes
│       ├── fte-extract-attachment/ # Process ATTACHMENT_EXTRACT_*.md — extract + suggest action
│       ├── fte-status/          # System health report — 7 watchers + approvals + schedules
│       └── fte-process/         # Process Drop_Box file-drop items through pipeline
│
│── Process Management
├── ecosystem.config.cjs         # PM2 config — 2 processes:
│                                #   gold-orchestrator (Python, manages all watcher threads)
│                                #   whatsapp-watcher (Node.js, Baileys WebSocket)
│
│── Scheduled Tasks (Windows Task Scheduler)
├── schedules/
│   ├── gmail_poll.bat           # Every 2 min — single-shot Gmail poll (PM2 fallback)
│   ├── morning_briefing.bat     # Daily 08:00 — triggers /fte-briefing via ccr code
│   ├── daily_social.bat         # Daily 12:00 — triggers /fte-social-post via ccr code
│   ├── weekly_review.bat        # Sunday 09:00 — triggers /fte-linkedin-draft via ccr code
│   ├── weekly_audit.bat         # Sunday 18:00 — triggers /fte-audit (CEO briefing)
│   ├── register_tasks.bat       # One-off: registers all schtasks entries
│   └── README.md                # schtasks registration commands + troubleshooting
│
│── Vault (Obsidian State Bus)
├── AI_Employee_Vault/
│   ├── Dashboard.md             # Live system status (committed, auto-updated every 10s)
│   ├── Company_Handbook.md      # Agent behavior rules — approval thresholds, tone (committed)
│   ├── FAQ_Context.md           # Services, pricing, hours, escalation triggers (gitignored)
│   ├── Business_Goals.md        # Revenue targets, KPIs, LinkedIn themes (gitignored)
│   ├── Drop_Box/                # Filesystem drops land here (gitignored)
│   ├── Inbox/                   # Reserved for future integrations (gitignored)
│   ├── Needs_Action/            # All incoming items (gitignored)
│   ├── Pending_Approval/        # Awaiting HITL review in Obsidian (gitignored)
│   ├── Approved/                # User-approved actions (gitignored)
│   ├── Rejected/                # User-rejected actions (gitignored)
│   ├── Plans/                   # PLAN_*.md, CEO_BRIEFING_*.md, BRIEFING_*.md (gitignored)
│   ├── Done/                    # Completed items — purged after 24h (gitignored)
│   ├── Archive/                 # Archived done items (kept indefinitely) (gitignored)
│   └── Logs/                    # Daily JSON Lines audit logs YYYY-MM-DD.json (gitignored)
│
│── Infrastructure
├── docker-compose.yml           # Odoo 19 Community + PostgreSQL 15 (local Docker)
├── media/
│   └── sky.png                  # Sample image for Instagram posts
├── wa_setup.bat                 # Windows helper: first-time WhatsApp QR scan setup
│
│── Tests
├── tests/
│   ├── conftest.py              # Pytest fixtures and shared test setup
│   ├── test_filesystem_watcher.py  # Drop_Box monitoring (3 tests)
│   ├── test_gmail_watcher.py    # Gmail API fetch, dedup, action file creation
│   ├── test_approval_watcher.py # Approval detection, routing, expiration
│   ├── test_id_tracker.py       # Persistent ID storage + dedup across restarts
│   ├── test_linkedin_watcher.py # LinkedIn notification fetching
│   ├── test_orchestrator.py     # Skill routing, plan awareness, health checks
│   ├── test_backoff.py          # CircuitBreaker state transitions (12 tests — all passing)
│   └── test_mcp_server.js       # MCP email server auth, send_email HITL gate, DRY_RUN
│
│── Configuration
├── pyproject.toml               # uv project config (gold-fte, Python 3.13+)
├── package.json                 # Node.js deps (whatsapp-web.js, chokidar, dotenv)
├── .env.example                 # Committed secrets template — copy to .env and fill
├── .env                         # Gitignored — actual secrets
├── .python-version              # 3.13
├── .gitignore                   # Secrets + vault data + sessions + node_modules
│
│── Documentation
├── README.md                    # This file
├── QUICKSTART.md                # Step-by-step setup guide
├── PM2.md                       # PM2 management commands reference
├── SECURITY.md                  # What is gitignored and why, secrets checklist
└── GOLD_TIER_TEST_CHECKLIST.md  # Test matrix with pass/fail status
```

## Setup

See [QUICKSTART.md](QUICKSTART.md) for step-by-step setup after cloning.

## Agent Skills

| Skill | Trigger | Effect |
|-------|---------|--------|
| `/fte-triage` | Manual / orchestrator | Classify + prioritize all Needs_Action items |
| `/fte-gmail-triage <file>` | Auto (orchestrator) | Classify email, set ROUTINE/SENSITIVE |
| `/fte-gmail-reply <file>` | Auto (orchestrator) | Draft email reply — auto-send or HITL |
| `/fte-whatsapp-reply <file>` | Auto (orchestrator) | Draft WhatsApp reply — auto or HITL |
| `/fte-approve <file>` | Auto (orchestrator) | Execute approved action via MCP |
| `/fte-plan <task>` | Auto (orchestrator) | Decompose task into PLAN_*.md |
| `/fte-social-post <platform>` | Manual / scheduled | Draft social post → Pending_Approval/ |
| `/fte-social-summary` | Manual | Aggregate social engagement from Done/ |
| `/fte-odoo-audit` | Manual | Financial snapshot from Odoo MCP |
| `/fte-briefing` | Daily 08:00 | Morning briefing → Plans/BRIEFING_*.md |
| `/fte-audit [date]` | Sunday 18:00 | CEO Weekly Briefing → Plans/CEO_BRIEFING_*.md |
| `/fte-extract-attachment <file>` | Auto (orchestrator) | Process email attachment |
| `/fte-linkedin-draft` | Sunday 09:00 | Draft LinkedIn post → Plans/ |
| `/fte-status` | On-demand | System health — 7 watchers + approvals + schedules |
| `/fte-process <file>` | Auto (orchestrator) | Process Drop_Box file-drop item |

## MCP Servers

### mcp-email-server (Gmail)
| Tool | Gate | Description |
|------|------|-------------|
| `send_email` | HITL required | Send via Gmail API — approval file must exist in Approved/ |
| `draft_email` | None | Create Gmail draft only |
| `search_emails` | None | Search Gmail by query string |

### mcp-odoo-server (Odoo Community)
| Tool | Gate | Description |
|------|------|-------------|
| `get_financial_summary` | None | Monthly P&L + outstanding/overdue invoices |
| `list_transactions` | None | Search invoices/bills by date, type, partner |
| `create_invoice` | HITL required | Create + post customer invoice |
| `create_partner` | HITL required | Create customer or vendor record |

## Key Patterns

- **CircuitBreaker**: Wraps all Odoo + social API calls — opens after 3 failures, half-open probe after 15 min, closes on recovery. Logged as `circuit_opened` / `circuit_half_open` / `circuit_closed`.
- **Jitter scheduling**: Social posts randomized within `POST_WINDOW_START`–`POST_WINDOW_END` (default 09:00–18:00), 23h minimum gap enforced between posts.
- **Human simulation**: Playwright browses feed before posting, types character-by-character at 60–130ms/char, pauses 4–10s to proofread.
- **Ralph Wiggum loop**: `stop.py` hook re-injects PLAN_*.md prompts until all steps are checked complete. Bypassed for automated orchestrator dispatches via `FTE_AUTOMATED_DISPATCH=1`.
- **DRY_RUN mode**: `DRY_RUN=true` in `.env` — all actions logged but never executed. Safe for testing.
- **Atomic writes**: Dashboard.md updated via temp-file + rename — prevents Obsidian corruption.
- **Deduplication**: `id_tracker.py` persists processed IDs in `.state/` — survives PM2 restarts.
- **24h Done/ cleanup**: Orchestrator purges files from Done/ older than 24h (Archive/ subdirectory preserved).

## Running

```bash
cd level-gold

# Install dependencies
uv sync
uv run playwright install chromium
cd mcp-email-server && npm install && cd ..
cd mcp-odoo-server && npm install && cd ..

# Start Odoo (first time)
docker compose up -d

# Start all processes via PM2
pm2 start ecosystem.config.cjs
pm2 save       # Persist across reboots
pm2 startup    # Register as Windows service (run generated command as Admin)

# Monitor
pm2 logs       # Live log stream
pm2 monit      # Interactive process dashboard

# Tests
uv run pytest tests/ -v
```
