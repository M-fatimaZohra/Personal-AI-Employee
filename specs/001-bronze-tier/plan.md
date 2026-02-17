# Implementation Plan: Bronze Tier — Personal AI Employee Foundation

**Branch**: `001-bronze-tier` | **Date**: 2026-02-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-bronze-tier/spec.md`
**Agent Name**: `bronze-fte` (the Bronze-phase AI Employee agent)

## Summary

Build the foundational "Personal AI Employee" system: a filesystem
watcher (Python/watchdog) that monitors a `Drop_Box` folder and creates
action files in the Obsidian vault, a live Dashboard, three Claude Code
Agent Skills implementing the Reusable Intelligence (RI) pattern, a
Company Handbook for runtime behavior rules, and structured audit
logging. All work lives in the `/level-bronze` directory.

## Technical Context

**Language/Version**: Python 3.12+ managed by `uv`
**Primary Dependencies**: watchdog (filesystem events), pathlib (paths)
**Storage**: Local filesystem (Obsidian vault markdown + JSON logs)
**Testing**: Manual drop-test + pytest for watcher unit tests
**Target Platform**: Windows 11 + WSL2 (Ubuntu), cross-platform via pathlib
**Project Type**: Single project — Python watchers + Claude Code Agent Skills
**Performance Goals**: File detection within 10 seconds, dashboard update within 30 seconds
**Constraints**: Local-first, no external services required for Bronze, offline-capable
**Scale/Scope**: Single user, 1 watcher, 3 Agent Skills, ~10 files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Local-First & Privacy-Centric | PASS | All data in local vault; no secrets needed for Bronze |
| II. Perception → Reasoning → Action | PASS | Watcher (perception) → Skills (reasoning) → vault writes (action) |
| III. File-Based Communication | PASS | All agent communication via markdown files in vault folders |
| IV. Human-in-the-Loop | PASS | Bronze is on-demand; HITL deferred to Silver (no auto-actions) |
| V. Agent Skills Architecture | PASS | 3 RI skills: `/fte.triage`, `/fte.status`, `/fte.process` |
| VI. Observability & Audit Logging | PASS | Structured logs in `/Logs`, DRY_RUN support |
| VII. Incremental Tier Progression | PASS | Bronze only; no Silver/Gold features |
| VIII. Resilience & Graceful Degradation | PASS | Watcher handles FileNotFoundError, auto-creates folders |

All gates pass. No violations.

## Architecture & Tech Stack

### Three-Layer Architecture (Bronze Scope)

```
┌─────────────────────────────────────────────────────────┐
│                    USER (Obsidian)                       │
│  Dashboard.md │ Company_Handbook.md │ /Needs_Action/*   │
└───────┬───────────────────┬───────────────────┬─────────┘
        │ reads             │ reads             │ reads
        ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│              REASONING LAYER (Claude Code)               │
│  /fte.triage  │  /fte.status  │  /fte.process           │
│  (Agent Skills — Reusable Intelligence Units)           │
└───────┬───────────────────┬───────────────────┬─────────┘
        │ writes            │ writes            │ writes
        ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│                 OBSIDIAN VAULT (Local)                   │
│  /Needs_Action  /Done  /Logs  Dashboard.md              │
└───────▲─────────────────────────────────────────────────┘
        │ writes action files
┌───────┴─────────────────────────────────────────────────┐
│              PERCEPTION LAYER (Python)                   │
│  FilesystemWatcher (watchdog) → monitors /Drop_Box      │
│  run_watchers.py (entry point)                          │
└─────────────────────────────────────────────────────────┘
```

### Agent Name: `bronze-fte`

The Bronze-phase agent is called `bronze-fte`. It encompasses:
- The Python watcher process (filesystem perception)
- The 3 Claude Code Agent Skills (reasoning)
- The vault folder structure (state bus)

## Project Structure

### Documentation (this feature)

```text
specs/001-bronze-tier/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── action-file-schema.md
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (`/level-bronze` directory)

```text
level-bronze/
├── pyproject.toml                # uv project: watchdog dependency
├── run_watchers.py               # Entry point: start all watchers
├── base_watcher.py               # ABC: BaseWatcher interface
├── filesystem_watcher.py         # Watchdog-based Drop_Box monitor
├── dashboard_updater.py          # Reads vault state, writes Dashboard.md
├── logger.py                     # Structured JSON logging to /Logs
│
├── AI_Employee_Vault/            # Obsidian vault root
│   ├── Dashboard.md              # System status + recent activity + pending tasks
│   ├── Company_Handbook.md       # User-editable behavioral rules
│   ├── Drop_Box/                 # User drops files here (monitored)
│   ├── Inbox/                    # Raw incoming items
│   ├── Needs_Action/             # Watcher-produced action files
│   ├── Done/                     # Completed items (audit trail)
│   └── Logs/                     # Structured JSON logs (YYYY-MM-DD.json)
│
├── tests/
│   ├── test_filesystem_watcher.py
│   ├── test_dashboard_updater.py
│   └── test_logger.py
│
└── .claude/
    └── commands/                 # Agent Skills (RI Units)
        ├── fte.triage.md         # Classify /Needs_Action items, update Dashboard
        ├── fte.status.md         # Report system health
        └── fte.process.md        # Move item through pipeline to /Done
```

**Structure Decision**: Single project in `/level-bronze` with Python
source files at root level (no `src/` nesting — this is a small
hackathon project, not a library). Agent Skills live in
`level-bronze/.claude/commands/` so they are scoped to the Bronze
working directory.

## Complexity Tracking

No constitution violations. No complexity justification needed.

## Key Design Decisions

### 1. Action File Format (YAML Frontmatter)

Every file produced by a watcher uses this format:

```yaml
---
type: file_drop          # file_drop | email | message | task
original_name: invoice.txt
dropped_at: 2026-02-16T10:30:00Z
status: needs_action     # needs_action | in_progress | done | rejected
priority: normal         # low | normal | high | urgent
source: Drop_Box
processed_by: null       # skill name that last processed this
---

[Original file content or binary placeholder here]
```

### 2. Dashboard.md Structure

```markdown
# AI Employee Dashboard

## System Status
- Filesystem Watcher: 🟢 Online | Last check: <timestamp>

## Pending Tasks (X items)
| ID | Type | Name | Priority | Created |
|----|------|------|----------|---------|

## Recent Activity (last 10)
| Timestamp | Action | Actor | Details |
|-----------|--------|-------|---------|
```

### 3. Log Entry Format (`/Logs/YYYY-MM-DD.json`)

Each line is a JSON object (JSON Lines format):

```json
{"timestamp":"2026-02-16T10:30:00Z","action":"file_processed","actor":"FilesystemWatcher","source":"Drop_Box/invoice.txt","destination":"Needs_Action/FILE_invoice.md","result":"success"}
```

### 4. Agent Skill RI Pattern

Each `.claude/commands/fte.<name>.md` skill follows:

```markdown
Read the vault state:
1. List all files in AI_Employee_Vault/Needs_Action/
2. Parse YAML frontmatter from each file
3. Read Company_Handbook.md for applicable rules

Reason and act:
4. [Skill-specific logic]

Write outputs:
5. Update affected files (frontmatter status changes)
6. Update Dashboard.md with current state
7. Log the action to /Logs/YYYY-MM-DD.json
```

### 5. DRY_RUN Mode

When `DRY_RUN=true` environment variable is set:
- Watcher logs "would move file X to Y" but does not move
- Skills log "would update Dashboard" but do not write
- All intended actions are captured in `/Logs` with `"dry_run": true`
