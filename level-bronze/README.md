# Bronze Tier — Personal AI Employee Foundation

The Bronze tier implements the **Minimum Viable FTE**: a filesystem watcher that detects dropped files and three Claude Code Agent Skills that triage, process, and report on them.

## Architecture

```
You drop a file        Python Watcher (Perception)       Claude Code Skills (Reasoning + Action)
     |                        |                                    |
     v                        v                                    v
 Drop_Box/ ──> filesystem_watcher.py ──> Needs_Action/ ──> /fte-triage ──> /fte-process ──> Done/
                                              |                                                |
                                              └──── Dashboard.md (auto-updated) ───────────────┘
                                              └──── Logs/YYYY-MM-DD.json (audit trail) ────────┘
```

**Perception layer** (automated): Python + watchdog monitors `Drop_Box/` for new files.
**Reasoning + Action layer** (on-demand): Claude Code reads vault files, applies Company Handbook rules, and writes results back.

## Setup

```bash
cd level-bronze
uv sync            # Install dependencies (Python 3.13+, watchdog, pytest)
```

## Usage

### 1. Start the watcher

```bash
uv run python run_watchers.py
```

The watcher monitors `AI_Employee_Vault/Drop_Box/`. When a file appears:
- It creates an action file (`FILE_<name>.md`) with YAML frontmatter in `/Needs_Action`
- It removes the original from Drop_Box
- It updates `Dashboard.md` and writes a log entry

### 2. Drop a file

Copy or move any file into `AI_Employee_Vault/Drop_Box/`:

```bash
cp invoice.pdf AI_Employee_Vault/Drop_Box/
```

Within seconds, `FILE_invoice.md` appears in `AI_Employee_Vault/Needs_Action/` with metadata:

```yaml
---
type: file_drop
original_name: invoice.pdf
dropped_at: 2026-02-17T08:46:06+00:00
status: needs_action
priority: normal
source: Drop_Box
processed_by: null
---
```

### 3. Use Agent Skills

Open Claude Code inside `level-bronze/` and invoke:

| Skill | Purpose | Command |
|-------|---------|---------|
| **fte-triage** | Classify items, apply handbook rules, update priorities | `/fte-triage` |
| **fte-status** | Report system health (watcher status, file counts, last activity) | `/fte-status` |
| **fte-process** | Process an item — reason about it, move to Done, log | `/fte-process` |

### 4. View in Obsidian

Open `AI_Employee_Vault/` as an Obsidian vault. `Dashboard.md` shows:
- Watcher status (Online/Offline)
- Pending tasks table (items in Needs_Action)
- Recent activity log (last 10 actions)

## Company Handbook

Edit `AI_Employee_Vault/Company_Handbook.md` to change how the agent behaves. Rules are read by skills during triage and processing. Current rules include:
- Files >10MB flagged as high priority
- Executables (.exe, .bat, .sh) flagged for manual review
- Confidential filenames flagged as urgent

## DRY_RUN Mode

Run the watcher without moving files:

```bash
DRY_RUN=true uv run python run_watchers.py
```

Actions are logged but no files are moved or deleted.

## Testing

```bash
uv run pytest tests/ -v
```

Three tests validate: text file processing, binary file handling, and duplicate filename resolution.

## File Structure

```
level-bronze/
├── pyproject.toml              # Project config (python >=3.13, watchdog)
├── run_watchers.py             # Entry point
├── base_watcher.py             # Abstract base class for watchers
├── filesystem_watcher.py       # Watchdog-based Drop_Box monitor
├── dashboard_updater.py        # Atomic Dashboard.md writer
├── logger.py                   # JSON Lines structured logger
├── AI_Employee_Vault/
│   ├── Dashboard.md            # Live system status
│   ├── Company_Handbook.md     # Agent behavior rules
│   ├── Drop_Box/               # Files land here (monitored)
│   ├── Inbox/                  # Future: external integrations
│   ├── Needs_Action/           # Action files awaiting processing
│   ├── Done/                   # Completed items
│   └── Logs/                   # Daily JSON Lines audit logs
├── .claude/skills/
│   ├── fte-triage/SKILL.md     # Triage skill
│   ├── fte-status/SKILL.md     # Status skill
│   └── fte-process/SKILL.md    # Process skill
└── tests/
    └── test_filesystem_watcher.py
```
