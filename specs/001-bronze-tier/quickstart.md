# Quickstart: Bronze Tier

**Branch**: `001-bronze-tier` | **Date**: 2026-02-16

## Prerequisites

- Python 3.12+ installed
- `uv` package manager installed (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Claude Code installed and configured (`npm install -g @anthropic/claude-code`)
- Obsidian installed (optional — any markdown viewer works)

## Setup

```bash
# Clone and enter the project
cd level-bronze

# Install dependencies
uv sync

# Verify
uv run python -c "from watchdog.observers import Observer; print('OK')"
```

## Run the Watcher

```bash
# Start the filesystem watcher
uv run python run_watchers.py

# In DRY_RUN mode (no file moves, only logging)
DRY_RUN=true uv run python run_watchers.py
```

## Test It

1. Open a second terminal
2. Copy or create a file in `AI_Employee_Vault/Drop_Box/`:
   ```bash
   echo "Test content" > AI_Employee_Vault/Drop_Box/test.txt
   ```
3. Watch the watcher terminal — it should log the detection
4. Check `AI_Employee_Vault/Needs_Action/` for `FILE_test.md`
5. Check `AI_Employee_Vault/Logs/` for today's log file
6. Open `AI_Employee_Vault/Dashboard.md` in Obsidian

## Use Agent Skills

```bash
# From the level-bronze directory, run Claude Code
claude

# Then invoke skills:
# /fte.triage   — classify all items in /Needs_Action
# /fte.status   — report system health
# /fte.process  — process a specific item to /Done
```

## Folder Structure After Setup

```
AI_Employee_Vault/
├── Dashboard.md
├── Company_Handbook.md
├── Drop_Box/          ← drop files here
├── Inbox/
├── Needs_Action/      ← watcher writes here
├── Done/              ← processed items end here
└── Logs/              ← JSON Lines audit logs
```
