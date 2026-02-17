<!--
  Sync Impact Report
  ==================
  Version change: 0.0.0 (template) → 1.0.0
  Modified principles: All new (template placeholders replaced)
  Added sections:
    - 8 Core Principles (I–VIII)
    - Technology Stack & Environment
    - Development Workflow
    - Governance
  Removed sections: None (template placeholders replaced)
  Templates requiring updates:
    - .specify/templates/plan-template.md — ✅ compatible (Constitution Check section will reference these principles)
    - .specify/templates/spec-template.md — ✅ compatible (no structural conflicts)
    - .specify/templates/tasks-template.md — ✅ compatible (phase structure maps to tier progression)
  Follow-up TODOs: None
-->

# Personal AI Employee (FTE) Constitution

## Core Principles

### I. Local-First & Privacy-Centric

All data MUST reside locally in the Obsidian vault by default. The vault
is the single source of truth for state, tasks, logs, and plans. Secrets
(API keys, tokens, credentials) MUST never be stored in the vault or
committed to Git; use environment variables and `.env` files (added to
`.gitignore` immediately). Sensitive actions (banking, payments) MUST
always require human approval via the HITL pattern before execution.

### II. Perception → Reasoning → Action Pipeline

The system follows a strict three-layer architecture:
- **Perception (Watchers):** Lightweight Python scripts using `watchdog`,
  Gmail API, or Playwright that monitor external sources and write
  `.md` files with YAML frontmatter into `/Needs_Action`.
- **Reasoning (Claude Code):** Reads `/Needs_Action`, creates plans in
  `/Plans`, and writes approval requests to `/Pending_Approval`.
- **Action (MCP Servers):** Node.js MCP servers execute approved external
  actions (send email, post social media, make payments).

No layer may bypass another. Watchers MUST NOT take actions directly.
Claude MUST NOT send external communications without an MCP server.

### III. File-Based Communication

Agents communicate exclusively by writing markdown files into vault
folders. The canonical folder contract is:
- `/Inbox` — raw incoming items
- `/Needs_Action` — watcher-produced items awaiting Claude reasoning
- `/Plans` — Claude-generated action plans with checkboxes
- `/Pending_Approval` — items requiring human sign-off
- `/Approved` — human-approved items ready for MCP execution
- `/Done` — completed items (audit trail)
- `/Logs` — structured JSON/markdown logs of all actions

The claim-by-move rule applies: the first agent to move a file from
`/Needs_Action` to `/In_Progress/<agent>/` owns it.

### IV. Human-in-the-Loop (NON-NEGOTIABLE)

Every sensitive action MUST produce an approval request file in
`/Pending_Approval` before execution. The human approves by moving the
file to `/Approved`. Actions that always require approval:
- Payments to new payees or amounts > $100
- Emails to new contacts or bulk sends
- Social media DMs and replies
- File operations outside the vault
- Any irreversible action

Auto-approve thresholds (email replies to known contacts, scheduled
social posts, recurring payments < $50) MUST be explicitly configured
in `Company_Handbook.md`.

### V. Agent Skills Architecture

All AI functionality MUST be implemented as Claude Code Agent Skills
(slash commands). Each skill is a self-contained, testable unit. Skills
are defined in `.claude/commands/` and follow the naming convention
`<domain>.<action>.md`. New capabilities are added as new skills, not
as monolithic scripts.

### VI. Observability & Audit Logging

Every action the AI takes MUST be logged with: timestamp, action_type,
actor, target, parameters, approval_status, and result. Logs are stored
in `/Logs/YYYY-MM-DD.json` and retained for a minimum of 90 days.
`Dashboard.md` MUST reflect current system status and recent activity.
The system MUST support `DRY_RUN` mode (via environment variable) that
logs intended actions without executing them.

### VII. Incremental Tier Progression

Development follows the hackathon tier structure. Each tier MUST be
fully functional before advancing:
1. **Bronze:** Vault + Dashboard + Company_Handbook + 1 watcher +
   folder structure + basic Agent Skills
2. **Silver:** + 2 watchers + LinkedIn posting + reasoning loop +
   1 MCP server + HITL workflow + scheduling
3. **Gold:** + cross-domain integration + Odoo accounting + social
   media + CEO Briefing + Ralph Wiggum loop + error recovery
4. **Platinum:** + cloud VM 24/7 + cloud/local work-zone split +
   vault sync

Never skip a tier. Each tier MUST pass its acceptance criteria before
the next tier begins.

### VIII. Resilience & Graceful Degradation

Watchers are long-running daemon processes and MUST handle transient
failures (network timeouts, API rate limits) with exponential backoff
retry. When a component fails, the system MUST degrade gracefully:
- Gmail API down: queue outgoing emails locally
- Claude unavailable: watchers continue collecting into `/Needs_Action`
- MCP server down: log the intended action for retry

Process management (PM2 or a custom Python watchdog) MUST ensure
watchers auto-restart on crash.

## Technology Stack & Environment

**Runtime environment:** Windows 11 with WSL2 (Ubuntu). Development and
Git operations run in WSL bash. Obsidian vault lives on the Windows
filesystem and is accessible from both Windows and WSL via
`/mnt/c/...` or direct Windows paths.

**Cross-environment rules:**
- Python scripts and watchers: run in WSL or Windows, managed by `uv`
- MCP servers (Node.js): run in WSL or Windows, use `npm`/`npx`
- Claude Code: runs in terminal (WSL bash preferred)
- Obsidian: runs on Windows natively, reads the vault directory
- File paths in code MUST use `pathlib.Path` for cross-platform safety
- Shell scripts MUST use bash (not PowerShell); use WSL if on Windows
- Git operations MUST use Unix-style line endings (`core.autocrlf=input`)

**Stack:**
- **Python:** 3.12+ managed by `uv` (not pip/venv)
- **Node.js:** v24+ LTS for MCP servers
- **Obsidian:** v1.10.6+ for vault GUI
- **Claude Code:** active subscription, primary reasoning engine
- **Key libraries:** watchdog, google-api-python-client, playwright
- **Version control:** Git + GitHub

## Development Workflow

**Branching:** `main` is the stable branch. Feature work happens on
`<tier>/<feature-name>` branches (e.g., `bronze/filesystem-watcher`).

**Spec-Driven Development (SDD) flow:**
1. `/sp.specify` — write the feature spec
2. `/sp.plan` — create the implementation plan
3. `/sp.tasks` — generate testable tasks
4. Implement tasks incrementally, smallest viable diff
5. `/sp.git.commit_pr` — commit and create PR

**Watcher development cycle:**
1. Create the watcher class extending `BaseWatcher`
2. Implement `check_for_updates()` and `create_action_file()`
3. Test with a file drop into the monitored folder
4. Verify the `.md` file appears in `/Needs_Action` with correct
   YAML frontmatter
5. Verify the log entry appears in `/Logs`

**Testing:** Watchers are tested by dropping test files and verifying
output in `/Needs_Action`. MCP servers are tested with dry-run mode.
Integration tests verify the full Perception → Reasoning → Action
pipeline.

## Governance

This constitution is the authoritative source for all development
decisions in the Personal AI Employee project. All code, skills, and
configurations MUST comply with these principles.

**Amendment process:**
1. Propose the change via `/sp.constitution` with rationale
2. Document the version bump (MAJOR for principle removal/redefinition,
   MINOR for additions, PATCH for clarifications)
3. Update all dependent artifacts (CLAUDE.md, templates, skills)

**Compliance verification:**
- Every PR MUST be checked against the constitution principles
- Complexity MUST be justified; prefer the simplest approach
- Use `CLAUDE.md` for runtime development guidance

**Version**: 1.0.0 | **Ratified**: 2026-02-16 | **Last Amended**: 2026-02-16
