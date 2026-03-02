# Silver Tier — Personal AI Employee

The Silver tier adds **multi-channel perception** (Gmail, WhatsApp, LinkedIn, filesystem), an **autonomous orchestrator**, and a **Human-in-the-Loop (HITL) approval workflow** on top of the Bronze foundation.

## Architecture

```
External World          Watchers (Perception)         Vault (State Bus)
────────────────────────────────────────────────────────────────────────
Gmail inbox     ──→  gmail_watcher.py    ──→  Needs_Action/EMAIL_*.md
WhatsApp msg    ──→  whatsapp_watcher.js ──→  Needs_Action/WHATSAPP_*.md
LinkedIn notif  ──→  linkedin_watcher.py ──→  Needs_Action/LINKEDIN_*.md
Drop_Box/       ──→  filesystem_watcher  ──→  Needs_Action/FILE_*.md
                                                       │
                             orchestrator.py ──────────┘  (watches Needs_Action)
                                    │
                    ┌───────────────┴────────────────┐
                    ▼                                ▼
             ROUTINE item                     SENSITIVE item
         auto-write to Approved/          → Pending_Approval/
                    │                          │ (user reviews in Obsidian)
                    │                          │ moves file to Approved/
                    └──────────────────────────┘
                                    │
                         approval_watcher.py
                                    │
                        MCP email server / Baileys
                                    │
                              Email sent / WA reply
                                    │
                                  Done/
```

**4 Watchers** detect events → **Orchestrator** classifies and dispatches Claude skills → **Tiered approval** routes ROUTINE items directly and SENSITIVE items through HITL → **MCP server** executes approved actions.

## File Structure

```
level-silver/
├── orchestrator.py           # Autonomy engine — watches Needs_Action, dispatches skills
├── approval_watcher.py       # Watches Approved/ and Rejected/, triggers actions
├── gmail_watcher.py          # Gmail API polling (every 2 min)
├── whatsapp_watcher.js       # WhatsApp via Baileys Node.js (event-driven)
├── linkedin_watcher.py       # LinkedIn via Playwright (30-min interval)
├── filesystem_watcher.py     # Drop_Box monitor (from Bronze)
├── dashboard_updater.py      # Updates Dashboard.md atomically
├── id_tracker.py             # Deduplication across restarts
├── backoff.py                # Exponential backoff for API calls
├── ecosystem.config.js       # PM2 process config
│
├── mcp-email-server/         # Node.js MCP server — send/draft/search email
│   ├── index.js
│   └── tools/
│
├── .claude/skills/
│   ├── fte-triage/           # Classify Needs_Action items
│   ├── fte-gmail-triage/     # Classify emails, set sensitivity
│   ├── fte-gmail-reply/      # Draft email replies (ROUTINE → auto, SENSITIVE → HITL)
│   ├── fte-whatsapp-reply/   # Draft WA replies (ROUTINE → auto, SENSITIVE → HITL)
│   ├── fte-approve/          # Execute approved items via MCP
│   ├── fte-linkedin-draft/   # Draft LinkedIn posts → Plans/
│   ├── fte-briefing/         # Morning/weekly briefing
│   ├── fte-plan/             # Decompose complex tasks into PLAN_*.md
│   ├── fte-status/           # System health report
│   └── fte-process/          # Process file-drop items
│
├── AI_Employee_Vault/
│   ├── Dashboard.md          # Live status (committed)
│   ├── Company_Handbook.md   # Agent behavior rules (committed)
│   ├── FAQ_Context.md        # Services, pricing, hours — skills read this
│   ├── Needs_Action/         # Incoming items (gitignored)
│   ├── Pending_Approval/     # Awaiting HITL review (gitignored)
│   ├── Approved/             # User-approved actions (gitignored)
│   ├── Rejected/             # User-rejected actions (gitignored)
│   ├── Plans/                # Reasoning plans, drafts (gitignored)
│   ├── Done/                 # Completed items (gitignored)
│   └── Logs/                 # Daily JSON audit logs (gitignored)
│
├── .env.example              # Secrets template (copy → .env, fill values)
└── schedules/                # Windows Task Scheduler batch scripts
```

## Setup

See [QUICKSTART.md](QUICKSTART.md) for step-by-step setup after cloning.

## Agent Skills

Open Claude Code in `level-silver/` and invoke:

| Skill | Trigger | Effect |
|-------|---------|--------|
| `/fte-triage` | After new items appear | Classify + prioritize Needs_Action |
| `/fte-gmail-triage <file>` | Auto (orchestrator) | Classify email, set ROUTINE/SENSITIVE |
| `/fte-whatsapp-reply <file>` | Auto (orchestrator) | Draft WA reply |
| `/fte-approve <file>` | Auto (approval_watcher) | Send approved email via MCP |
| `/fte-linkedin-draft` | Scheduled (Sunday 09:00) | Draft LinkedIn post → Plans/ |
| `/fte-briefing` | Scheduled (daily 08:00) | Morning briefing → Plans/ |
| `/fte-status` | On-demand | System health report |

## HITL Approval Flow

1. Orchestrator dispatches skill on new `Needs_Action/` file
2. Skill classifies item as **ROUTINE** or **SENSITIVE**
3. **ROUTINE** → skill writes directly to `Approved/` (auto-executes)
   **SENSITIVE** → skill writes to `Pending_Approval/` (waits for human)
4. User opens `Pending_Approval/` in Obsidian, reviews, moves file to `Approved/` or `Rejected/`
5. `approval_watcher.py` detects the move → triggers `fte-approve` → sends email or WA message
6. Item moves to `Done/`

## Running

```bash
cd level-silver

# Start all processes (PM2 managed)
pm2 start ecosystem.config.js
pm2 save          # Persist across reboots

# Monitor
pm2 logs          # Live logs
pm2 monit         # Process dashboard

# Run tests
uv run pytest tests/ -v
```

## Key Patterns

- **DRY_RUN mode**: Set `DRY_RUN=true` in `.env` — logs all actions without executing
- **Deduplication**: `id_tracker.py` persists processed IDs in `.state/` — survives restarts
- **Jitter scheduling**: LinkedIn posts randomized within `POST_WINDOW_START`–`POST_WINDOW_END`
- **Human simulation**: Playwright types character-by-character, browses feed before posting
- **PM2 immortality**: Processes auto-restart on crash; `SIGINT` handler prevents session corruption
