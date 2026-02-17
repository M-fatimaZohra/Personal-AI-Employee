# Feature Specification: Bronze Tier — Personal AI Employee Foundation

**Feature Branch**: `001-bronze-tier`
**Created**: 2026-02-16
**Status**: Draft
**Input**: User description: "Create spec for bronze tier and mention agent building for RI (reusable intelligence). You will work with Agents and Skills for Bronze formation."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Drop a File, Get It Triaged (Priority: P1)

The user drops a file (text, PDF, image) into the vault's `Drop_Box`
folder. The system detects the new file within seconds, moves it to
`/Needs_Action` with a `FILE_` prefix and YAML frontmatter metadata
(type, original name, timestamp, status). The user opens Obsidian and
sees the item in `/Needs_Action` ready for Claude to reason about.

**Why this priority**: This is the minimum viable perception loop — a
working Watcher that proves the Perception → Vault pipeline functions.
Without this, no higher-tier feature can work.

**Independent Test**: Drop a `.txt` file into `Drop_Box`, wait 5
seconds, confirm the file appears in `/Needs_Action/FILE_<name>.md`
with correct frontmatter and the original content embedded.

**Acceptance Scenarios**:

1. **Given** the filesystem watcher is running, **When** a user drops
   `invoice.txt` into `Drop_Box`, **Then** a file
   `FILE_invoice.md` appears in `/Needs_Action` within 10 seconds
   with YAML frontmatter containing `type: file_drop`,
   `original_name: invoice.txt`, `dropped_at: <ISO timestamp>`, and
   `status: needs_action`.
2. **Given** the watcher is running, **When** three files are dropped
   simultaneously, **Then** all three appear in `/Needs_Action` with
   unique names and correct metadata.
3. **Given** the watcher is running, **When** a binary file (e.g.,
   `.png`) is dropped, **Then** the action file is created with a
   placeholder body `[Binary file: <name>]` instead of raw content.

---

### User Story 2 — Dashboard Shows System Status (Priority: P1)

The user opens `Dashboard.md` in Obsidian and sees the current system
status (online/offline for each watcher), a table of recent activity
(last 10 events), and a list of pending tasks in `/Needs_Action`.
The dashboard is updated automatically whenever a watcher processes
an item.

**Why this priority**: The dashboard is the user's primary interface
for understanding what the AI Employee is doing. It is a Bronze tier
requirement.

**Independent Test**: Start the watcher, drop a file, open
`Dashboard.md` and confirm the Recent Activity table has a new row
and the Pending Tasks section lists the new item.

**Acceptance Scenarios**:

1. **Given** the system is freshly started, **When** the user opens
   `Dashboard.md`, **Then** System Status shows the filesystem
   watcher as online.
2. **Given** a file was just processed, **When** the user opens
   `Dashboard.md`, **Then** Recent Activity contains an entry with
   timestamp, event type, and source file name.
3. **Given** three items are in `/Needs_Action`, **When** the user
   opens `Dashboard.md`, **Then** Pending Tasks lists all three with
   their IDs and creation timestamps.

---

### User Story 3 — Agent Skills as Reusable Intelligence (Priority: P1)

The user invokes a Claude Code slash command (Agent Skill) such as
`/fte.triage` that reads all files in `/Needs_Action`, classifies each
item by type (email, file drop, message), and writes a prioritized
summary into `Dashboard.md`. Skills are self-contained markdown command
files in `.claude/commands/` that can be reused across sessions, shared
across projects, and composed together.

**Why this priority**: The hackathon requires all AI functionality to be
implemented as Agent Skills (Reusable Intelligence). This story
establishes the RI pattern that every future tier builds on.

**Independent Test**: Place two test `.md` files in `/Needs_Action`
(one `type: file_drop`, one `type: email`), run `/fte.triage`, confirm
Dashboard.md is updated with a classified summary.

**Acceptance Scenarios**:

1. **Given** two items exist in `/Needs_Action` with different types,
   **When** the user runs `/fte.triage`, **Then** `Dashboard.md`
   Pending Tasks section is updated with both items grouped by type.
2. **Given** `/Needs_Action` is empty, **When** the user runs
   `/fte.triage`, **Then** `Dashboard.md` shows "No pending items"
   and no errors occur.
3. **Given** the skill `/fte.triage` exists in `.claude/commands/`,
   **When** a new Claude Code session starts, **Then** the skill is
   available via tab-completion and runs without additional setup.

---

### User Story 4 — Company Handbook Governs Behavior (Priority: P2)

The user edits `Company_Handbook.md` to add or modify rules (e.g.,
"Flag any file larger than 10MB for manual review"). When Claude
processes items via Agent Skills, it reads the handbook and applies
these rules to its reasoning. The handbook acts as the configurable
"personality" of the AI Employee.

**Why this priority**: The handbook is a Bronze deliverable and the
mechanism by which the user controls AI behavior without modifying code.

**Independent Test**: Add a rule "Reject files with .exe extension" to
the handbook, drop a `.exe` file, run the triage skill, and confirm the
item is flagged as rejected in its frontmatter.

**Acceptance Scenarios**:

1. **Given** the handbook contains "Flag files larger than 10MB",
   **When** a 15MB file is triaged, **Then** the triage output marks
   it as `priority: high` with a note referencing the handbook rule.
2. **Given** the handbook contains no rules about a file type,
   **When** that file type is triaged, **Then** default handling
   applies (classify and list normally).

---

### User Story 5 — Audit Logging for All Actions (Priority: P2)

Every action taken by the system (watcher detection, file move, skill
execution, dashboard update) is logged to `/Logs` with a structured
entry containing timestamp, action type, actor (watcher/skill name),
source, destination, and result.

**Why this priority**: Observability is a constitution principle and
required for trust and debugging.

**Independent Test**: Run the full pipeline (drop file → watcher
processes → skill triages → dashboard updates), then check the log
file for the day and confirm all actions are recorded.

**Acceptance Scenarios**:

1. **Given** the watcher processes a file, **When** the log file for
   today is opened, **Then** it contains an entry with
   `action: file_processed`, the original filename, and the
   destination path.
2. **Given** a skill is executed, **When** the log is checked,
   **Then** it contains an entry with `action: skill_executed`,
   skill name, items processed count, and result status.

---

### Edge Cases

- What happens when a file with the same name is dropped twice? The
  system MUST append a numeric suffix (e.g., `FILE_invoice_2.md`) to
  prevent overwrites.
- What happens when the vault folder is missing at startup? The watcher
  MUST create all required folders (`/Inbox`, `/Needs_Action`, `/Done`,
  `/Logs`, `/Drop_Box`) automatically.
- What happens when a file is deleted from `Drop_Box` before the
  watcher processes it? The watcher MUST handle `FileNotFoundError`
  gracefully and log a warning.
- What happens when `Dashboard.md` is open in Obsidian while being
  updated? Obsidian auto-reloads; the system writes atomically (write
  to temp file, then rename) to prevent corruption.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a filesystem watcher that monitors
  `Drop_Box` and creates action files in `/Needs_Action` with YAML
  frontmatter metadata.
- **FR-002**: System MUST maintain a `Dashboard.md` reflecting current
  system status, recent activity, and pending tasks.
- **FR-003**: System MUST provide a `Company_Handbook.md` where users
  define behavioral rules that Agent Skills read and apply.
- **FR-004**: System MUST implement all AI functionality as Claude Code
  Agent Skills (`.claude/commands/fte.*.md`) following the Reusable
  Intelligence (RI) pattern.
- **FR-005**: System MUST log all actions to `/Logs` with structured
  entries (timestamp, action_type, actor, source, destination, result).
- **FR-006**: System MUST auto-create the vault folder structure on
  first run if any folders are missing.
- **FR-007**: System MUST handle duplicate filenames by appending a
  numeric suffix to prevent overwrites.
- **FR-008**: System MUST provide a `run_watchers.py` entry point that
  starts all watchers and handles graceful shutdown.
- **FR-009**: Agent Skills MUST be self-contained markdown files that
  work without external dependencies beyond the vault structure.
- **FR-010**: System MUST support `DRY_RUN=true` environment variable
  that logs intended actions without moving files.

### Key Entities

- **Action File**: A markdown file in `/Needs_Action` with YAML
  frontmatter (type, original_name, dropped_at, status, priority).
  Represents a detected item awaiting reasoning.
- **Vault**: The `AI_Employee_Vault` directory — Obsidian knowledge
  base and inter-agent communication bus.
- **Agent Skill (RI Unit)**: A `.claude/commands/fte.<name>.md` file
  containing a Claude Code slash command. The fundamental unit of
  Reusable Intelligence — self-contained, composable, shareable.
- **Watcher**: A Python class extending `BaseWatcher` that monitors an
  external source and produces Action Files.
- **Dashboard**: `Dashboard.md` — single-pane-of-glass view of the AI
  Employee's state, updated by watchers and skills.
- **Handbook**: `Company_Handbook.md` — user-editable rules governing
  Agent Skill behavior at runtime.

### Bronze Agent Skills (RI Units)

The following Agent Skills MUST be delivered as part of Bronze tier:

| Skill | Command | Purpose |
|-------|---------|---------|
| Triage | `/fte.triage` | Read `/Needs_Action`, classify items by type, update Dashboard |
| Status | `/fte.status` | Report system health: watcher uptime, pending count, last activity |
| Process | `/fte.process` | Move an item through the pipeline: reason about it, update frontmatter, move to `/Done` |

Each skill follows the RI pattern:
1. Read vault state (files, frontmatter, handbook rules)
2. Reason about the inputs using Claude
3. Write outputs back to the vault (updated files, dashboard, logs)
4. Log the action taken

## Assumptions

- The Obsidian vault directory lives inside the project repository
  (can be symlinked to an external Obsidian vault later).
- Python 3.12+ is available via `uv` on the development machine.
- Claude Code is installed and configured with an active subscription.
- The filesystem watcher is the sole Bronze-tier watcher (Gmail and
  WhatsApp watchers are Silver-tier scope).
- Agent Skills run on-demand via user invocation (automated triggering
  via Ralph Wiggum loop is Gold-tier scope).
- WSL2 (Ubuntu) and Windows 11 are both available; bash is the default
  shell for scripts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A file dropped into `Drop_Box` appears in `/Needs_Action`
  with correct metadata within 10 seconds.
- **SC-002**: `Dashboard.md` reflects current vault state (pending
  items, recent activity, watcher status) and updates within 30
  seconds of any change.
- **SC-003**: At least 3 Agent Skills are delivered as RI units:
  `/fte.triage`, `/fte.status`, `/fte.process`.
- **SC-004**: Every system action produces a structured log entry;
  100% of watcher and skill actions are captured.
- **SC-005**: The system starts with `uv run python run_watchers.py`
  and shuts down gracefully on Ctrl+C.
- **SC-006**: A new user can clone the repo, run `uv sync`, start the
  watchers, and see results in Obsidian within 5 minutes.
