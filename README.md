# Personal AI Employee (Digital FTE)

A local-first autonomous AI agent that works as a full-time digital employee, powered by Claude Code and Obsidian. Built for the Personal AI Employee Hackathon (Hackathon 0).

## What This Is

The Digital FTE is an AI system that monitors Gmail, WhatsApp, LinkedIn, and your local filesystem — triages incoming items, applies configurable business rules, and processes them through a structured pipeline — all without sending your data to external cloud storage.

It follows the **Perception → Reasoning → Action** architecture:
- **Perception**: Watchers detect events (files, emails, WhatsApp messages, LinkedIn notifications)
- **Reasoning**: Claude Code reads the vault, applies handbook rules, and decides what to do
- **Action**: Agent Skills execute decisions — auto-reply, escalate for approval, draft, archive

All state is stored as markdown files in an Obsidian vault, making the system fully transparent and auditable.

## Tier Structure

The project is built incrementally across tiers. Each tier is a standalone subdirectory.

| Tier | Directory | Focus | Status |
|------|-----------|-------|--------|
| **Bronze** | `level-bronze/` | Foundation — filesystem watcher, 3 agent skills, dashboard | ✅ Complete |
| **Silver** | `level-silver/` | Expansion — Gmail + WhatsApp + LinkedIn watchers, MCP email, HITL approvals, PM2 | ✅ Complete |
| **Gold** | `level-gold/` _(planned)_ | Autonomy — multi-step reasoning, proactive actions, self-scheduling | Planned |
| **Platinum** | `level-platinum/` _(planned)_ | Intelligence — learning from history, self-improvement | Planned |

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

Drop any file into `AI_Employee_Vault/Drop_Box/` and open Claude Code to use the skills:
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

## Tech Stack

| Layer | Bronze | Silver |
|-------|--------|--------|
| Language | Python 3.13+ via `uv` | Python 3.13+ · Node.js v18+ |
| Watchers | watchdog (filesystem) | watchdog · Gmail API · Baileys (WhatsApp) · Playwright (LinkedIn) |
| Orchestration | Manual (Claude Code on-demand) | PM2 + orchestrator.py (autonomous) |
| AI Actions | Claude Code Agent Skills | Claude Code Agent Skills + MCP email server |
| State | Obsidian vault (markdown + YAML) | Obsidian vault (markdown + YAML) |
| Scheduling | — | Windows Task Scheduler |
| Logging | JSON Lines | JSON Lines |

## Key Principles

1. **Local-First**: All data stays on your machine. No cloud storage.
2. **File-Based Communication**: Agents communicate through markdown files with YAML frontmatter.
3. **Human-in-the-Loop**: The human always has final say. HITL approval gates every sensitive action.
4. **Observability**: Every action is logged. `Dashboard.md` shows live system state.
5. **Incremental Progression**: Each tier builds on the last. Bronze works standalone; Silver extends it.

## License

Hackathon project — Personal AI Employee Hackathon (Hackathon 0).
