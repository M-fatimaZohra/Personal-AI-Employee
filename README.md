# Personal AI Employee (Digital FTE)

A local-first autonomous AI agent that works as a full-time digital employee, powered by Claude Code and Obsidian. Built for the Personal AI Employee Hackathon (Hackathon 0).

## What This Is

The Digital FTE is an AI system that monitors your local filesystem, triages incoming files, applies configurable business rules, and processes items through a structured pipeline — all without sending your data to external services.

It follows the **Perception - Reasoning - Action** architecture:
- **Perception**: Python watchers detect events (new files, emails, messages)
- **Reasoning**: Claude Code reads the vault, applies handbook rules, and decides what to do
- **Action**: Agent Skills execute decisions (classify, process, archive, flag for review)

All state is stored as markdown files in an Obsidian vault, making the system fully transparent and auditable.

## Tier Structure

The project is built incrementally across four tiers:

| Tier | Focus | Status |
|------|-------|--------|
| **Bronze** | Foundation — filesystem watcher, 3 agent skills, dashboard, handbook | Complete |
| **Silver** | Expansion — Gmail/WhatsApp watchers, MCP servers, human-in-the-loop approvals | Planned |
| **Gold** | Autonomy — multi-step task execution, stop hooks, autonomous loops | Planned |
| **Platinum** | Intelligence — learning from past actions, proactive suggestions, self-improvement | Planned |

## Quick Start (Bronze Tier)

```bash
cd level-bronze
uv sync                           # Install dependencies (Python 3.13+)
uv run python run_watchers.py     # Start the filesystem watcher
```

Drop any file into `level-bronze/AI_Employee_Vault/Drop_Box/` and watch it get processed.

Then open Claude Code in `level-bronze/` and use the agent skills:
- `/fte-triage` — Classify and prioritize pending items
- `/fte-process` — Process an item through the pipeline
- `/fte-status` — Check system health

See [level-bronze/README.md](level-bronze/README.md) for full usage instructions.

## Project Structure

```
fte-Autonomus-employ/
├── level-bronze/               # Bronze tier implementation (active)
│   ├── AI_Employee_Vault/      # Obsidian vault — the agent's "brain"
│   ├── .claude/skills/         # Agent Skills (Reusable Intelligence)
│   ├── *.py                    # Python watcher + utilities
│   └── tests/                  # Unit tests
├── specs/                      # Specification documents
│   └── 001-bronze-tier/        # Bronze tier spec, plan, tasks
├── history/                    # Prompt History Records (audit trail)
├── .specify/                   # SpecKit Plus templates and scripts
│   └── memory/constitution.md  # Project principles
└── CLAUDE.md                   # Agent development rules
```

## Tech Stack

- **Python 3.13+** managed by `uv`
- **watchdog** for filesystem event monitoring
- **Claude Code** Agent Skills for AI reasoning
- **Obsidian** vault for transparent state management
- **JSON Lines** for structured audit logging

## Key Principles

1. **Local-First**: All data stays on your machine. No cloud APIs for storage.
2. **File-Based Communication**: Agents communicate through markdown files with YAML frontmatter.
3. **Human-in-the-Loop**: The human always has final say. Bronze tier is on-demand; Silver adds approval workflows.
4. **Observability**: Every action is logged. Dashboard.md shows live system state.
5. **Incremental Progression**: Each tier builds on the last. Bronze works standalone.

## Environment

- Windows 11 + WSL2
- Python 3.13+ via `uv`
- Claude Code CLI

## License

Hackathon project — Personal AI Employee Hackathon (Hackathon 0).
