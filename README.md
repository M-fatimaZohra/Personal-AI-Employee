# Personal AI Employee (Digital FTE)

A local-first autonomous AI agent that works as a full-time digital employee, powered by Claude Code and Obsidian. Built for the Personal AI Employee Hackathon (Hackathon 0).

## What This Is

The Digital FTE is an autonomous AI system that acts as a full-time employee — monitoring Gmail, WhatsApp, LinkedIn, Facebook, Instagram, Twitter, and your local filesystem; managing business finances via Odoo; and running weekly CEO briefings. Everything runs locally on your machine. No cloud storage, no external data leakage.

It follows the **Perception → Reasoning → Action** architecture:
- **Perception**: 7 watchers detect events (files, emails, WhatsApp messages, LinkedIn/Facebook/Instagram/Twitter notifications, Odoo financial health)
- **Reasoning**: Claude Code reads the vault, applies Company Handbook rules, and decides what to do
- **Action**: 15 Agent Skills execute decisions — auto-reply, create invoices, schedule social posts, escalate for HITL approval

All state is stored as markdown files with YAML frontmatter in an Obsidian vault, making every decision transparent and auditable. Sensitive actions (financial, legal, new contacts) always require explicit human approval via file-move in Obsidian before execution.

## Tier Structure

The project is built incrementally across tiers. Each tier is a standalone subdirectory.

| Tier | Directory | Focus | Status |
|------|-----------|-------|--------|
| **Bronze** | `level-bronze/` | Foundation — filesystem watcher, 3 agent skills, dashboard | ✅ Complete |
| **Silver** | `level-silver/` | Expansion — Gmail + WhatsApp + LinkedIn watchers, MCP email, HITL approvals, PM2 | ✅ Complete |
| **Gold** | `level-gold/` | Autonomy — Odoo accounting, social media (FB/IG/TW), multi-domain workflows, CEO briefing, circuit breakers | ✅ Complete |
| **Platinum** | `level-platinum/` | Distribution — 24/7 cloud agent on Azure VM, vault sync over SSH, draft-only cloud mode, Odoo on cloud | ✅ Complete |

## Project Structure

```
fte-Autonomus-employ/
├── level-bronze/               # Bronze tier — filesystem watcher + 3 skills
│   ├── AI_Employee_Vault/      # Obsidian vault (the agent's state bus)
│   ├── .claude/skills/         # Agent Skills
│   ├── *.py                    # Watcher + utilities
│   └── tests/
│
├── level-silver/               # Silver tier — multi-channel + orchestrator + HITL
│   ├── AI_Employee_Vault/      # Obsidian vault (4 watchers feed here)
│   ├── .claude/skills/         # 10 Agent Skills
│   ├── mcp-email-server/       # Node.js MCP server for Gmail send/draft/search
│   ├── schedules/              # Windows Task Scheduler batch scripts
│   ├── *.py / *.js             # Python + Node.js watchers + orchestrator
│   └── tests/
│
├── level-gold/                 # Gold tier — Odoo, social media, multi-domain, CEO briefing
│   ├── AI_Employee_Vault/      # Obsidian vault (7 watchers feed here)
│   ├── .claude/skills/         # 15 Agent Skills
│   ├── mcp-email-server/       # Node.js MCP server — Gmail send/draft/search
│   ├── mcp-odoo-server/        # Node.js MCP server — Odoo JSON-RPC (invoice/partner/finance)
│   ├── schedules/              # 5 Windows Task Scheduler batch scripts
│   ├── media/                  # Images for Instagram posts
│   ├── docker-compose.yml      # Odoo 19 Community + PostgreSQL 15
│   ├── ecosystem.config.cjs    # PM2 config (2 processes)
│   ├── *.py / *.js             # 20 Python modules + Node.js WhatsApp watcher
│   └── tests/                  # 9 test files (pytest + Node.js)
│
├── level-platinum/             # Platinum tier — distributed cloud + local AI employee
│   ├── cloud/                  # Runs on Azure VM (24/7): Gmail watcher, orchestrator (draft-only)
│   ├── local/                  # Runs on laptop: all 7 watchers, approval execution
│   ├── shared/                 # Shared code + 16 Agent Skills (used by both agents)
│   ├── AI_Employee_Vault/      # Single shared vault (synced via Git over SSH every 2 min)
│   ├── scripts/                # VM setup, vault sync, secret transfer automation
│   ├── schedules/              # Windows Task Scheduler batch scripts
│   ├── docs/                   # Architecture, Odoo setup, lessons learned
│   └── tests/                  # Pytest + Node.js test suite
│
├── specs/                      # Spec-Driven Development artifacts
│   ├── 001-bronze-tier/        # Bronze spec, plan, tasks
│   └── 002-silver-tier/        # Silver spec, plan, tasks
│
├── history/                    # Prompt History Records (dev audit trail)
│   └── prompts/
│       ├── constitution/
│       ├── 001-bronze-tier/    # Bronze PHRs (committed)
│       └── 002-silver-tier/    # Silver PHRs (gitignored — contain live test data)
│
├── .specify/                   # SpecKit Plus templates and scripts
│   └── memory/constitution.md  # Project principles
└── CLAUDE.md                   # Agent development rules
```

## Quick Start

### Bronze Tier

```bash
cd level-bronze
uv sync
uv run python run_watchers.py
```

Drop any file into `AI_Employee_Vault/Drop_Box/` and use the skills:
`/fte-triage` · `/fte-process` · `/fte-status`

See [level-bronze/README.md](level-bronze/README.md) for full details.

### Silver Tier

```bash
cd level-silver
uv sync
cp .env.example .env    # Fill in credentials
pm2 start ecosystem.config.js
```

Gmail, WhatsApp, and LinkedIn events are automatically detected, triaged, and routed through the HITL approval workflow. See [level-silver/QUICKSTART.md](level-silver/QUICKSTART.md) for the full setup guide.

### Gold Tier

```bash
cd level-gold
uv sync
uv run playwright install chromium
cp .env.example .env                           # Fill in all credentials
docker compose up -d                           # Start Odoo
cd mcp-email-server && npm install && cd ..
cd mcp-odoo-server && npm install && cd ..
npm install                                    # WhatsApp deps
pm2 start ecosystem.config.cjs                # Start orchestrator + WhatsApp watcher
```

First-time authentication (one-off):

```bash
uv run python gmail_watcher.py --auth-only                     # Gmail OAuth
node whatsapp_watcher.js --setup                               # WhatsApp QR scan
LI_HEADLESS=false uv run python facebook_watcher.py --setup    # Facebook login
LI_HEADLESS=false uv run python instagram_watcher.py --setup   # Instagram login
LI_HEADLESS=false uv run python twitter_watcher.py --setup     # Twitter login
LI_HEADLESS=false uv run python linkedin_watcher.py --setup    # LinkedIn login
```

See [level-gold/QUICKSTART.md](level-gold/QUICKSTART.md) for the full 11-step guide, [docs/odoo-setup.md](level-gold/docs/odoo-setup.md) for Odoo, and [docs/social-media-setup.md](level-gold/docs/social-media-setup.md) for social platform sessions.

### Platinum Tier

The Platinum tier splits the system into two agents that communicate exclusively through a Git-synced Obsidian vault over SSH.

**Cloud Agent** (Azure VM, 24/7):
```bash
# On the Azure VM
pm2 start ecosystem.config.cjs     # Start cloud orchestrator (draft-only mode)
```

**Local Agent** (Windows laptop):
```bash
cd level-platinum/local
uv sync
cp .env.example .env               # Fill in credentials
pm2 start ecosystem.config.cjs    # Start local orchestrator + all watchers
```

**Vault Sync** runs automatically every 2 minutes via cron (VM) and Windows Task Scheduler (local). The Cloud Agent writes `Needs_Action/email/EMAIL_*.md` files which sync to the local agent, which claims them, drafts replies using Claude skills, and sends via MCP after human approval.

See [level-platinum/README.md](level-platinum/README.md) for the full deployment guide, security model, and architecture.

## Tech Stack

| Layer | Bronze | Silver | Gold | Platinum |
|-------|--------|--------|------|----------|
| Language | Python 3.13+ via `uv` | Python 3.13+ · Node.js v20+ | Python 3.13+ · Node.js v20+ | Python 3.13+ · Node.js v20+ |
| Watchers | watchdog (filesystem) | watchdog · Gmail API · Baileys · Playwright (LI) | + Playwright (FB/IG/TW) | Cloud: Gmail only · Local: all 7 |
| Orchestration | Manual | PM2 + orchestrator.py | PM2 + orchestrator.py (enhanced) | PM2 on VM (cloud) + PM2 on laptop (local) |
| AI Actions | Claude Code Skills | Skills + MCP email server | Skills + MCP email + MCP Odoo | 16 skills (shared) + MCP email + MCP Odoo |
| Accounting | — | — | Odoo 19 Community (Docker, local) | Odoo 19 Community (Docker, Azure VM 24/7) |
| Social Media | — | LinkedIn only | LinkedIn + Facebook + Instagram + Twitter | Local only (cloud IPs = bot detection) |
| State | Obsidian vault | Obsidian vault | Obsidian vault | Shared vault — Git over SSH every 2 min |
| Scheduling | — | Windows Task Scheduler (3) | Windows Task Scheduler (5) | Cron (VM) + Task Scheduler (local) |
| Error Recovery | — | Exponential backoff | CircuitBreaker + backoff | CircuitBreaker + backoff + graceful degradation |
| Logging | JSON Lines | JSON Lines | JSON Lines + 90-day retention | JSON Lines (both agents, separate log files) |
| Deployment | Local only | Local only | Local only | Azure VM D2s_v6 (2 vCPU, 8GB, East Asia) |
| Security | — | HITL approvals | HITL + secrets isolation | Draft-only cloud mode · secrets never synced · atomic claim-by-move |

## Key Principles

1. **Local-First**: All sensitive data stays on your machine. Secrets, sessions, and credentials never leave the local environment.
2. **File-Based Communication**: Agents communicate through markdown files with YAML frontmatter in an Obsidian vault — the vault is the state bus.
3. **Human-in-the-Loop**: The human always has final say. HITL approval gates every sensitive action (financial, legal, external communications).
4. **Observability**: Every action is logged. `Dashboard.md` shows live system state across both agents.
5. **Draft-Only Cloud**: The Cloud Agent can perceive and reason, but **never executes irreversible actions** (no email sends, no social posts, no invoice commits). All execution is local-only.
6. **Atomic Claim-by-Move**: `os.rename()` is POSIX-atomic — prevents double-processing when both cloud and local agents scan the same `Needs_Action/` folder simultaneously.
7. **Incremental Progression**: Each tier builds on the last. Bronze works standalone; Platinum is the full distributed production system.

## License

Hackathon project — Personal AI Employee Hackathon (Hackathon 0).
