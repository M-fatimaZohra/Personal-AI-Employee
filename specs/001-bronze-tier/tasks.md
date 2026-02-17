# Tasks: Bronze Tier — Personal AI Employee Foundation

**Input**: Design documents from `/specs/001-bronze-tier/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/action-file-schema.md, quickstart.md
**Working Directory**: `/level-bronze`
**Agent Name**: `bronze-fte`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create the `/level-bronze` directory structure, initialize `uv` project, and establish the vault folder hierarchy.

- [X] T001 Create `/level-bronze` directory and initialize `uv` project with `pyproject.toml` (name: `bronze-fte`, dependencies: `watchdog`)
- [X] T002 Create vault folder structure: `level-bronze/AI_Employee_Vault/` with subdirectories `Drop_Box/`, `Inbox/`, `Needs_Action/`, `Done/`, `Logs/`
- [X] T003 [P] Create `level-bronze/.claude/commands/` directory for Agent Skills
- [X] T004 [P] Create `level-bronze/tests/` directory with empty `__init__.py`

**Checkpoint**: `uv sync` succeeds, all directories exist.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure modules that ALL user stories depend on.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Implement structured logger in `level-bronze/logger.py` — write JSON Lines entries to `AI_Employee_Vault/Logs/YYYY-MM-DD.json` with fields: timestamp, action, actor, source, destination, result, dry_run, details. Support `DRY_RUN` env var.
- [X] T006 [P] Implement `BaseWatcher` abstract base class in `level-bronze/base_watcher.py` — `__init__(vault_path, check_interval)`, abstract methods `check_for_updates() -> list` and `create_action_file(item) -> Path`. Include vault path helpers (inbox, needs_action, done, logs). Auto-create missing vault folders in `__init__`.
- [X] T007 [P] Implement dashboard updater in `level-bronze/dashboard_updater.py` — `update_dashboard(vault_path)` function that scans `/Needs_Action` (parse YAML frontmatter), reads last 10 log entries from `/Logs`, and writes `Dashboard.md` with System Status, Pending Tasks table, and Recent Activity table. Use atomic write (temp file + rename).

**Checkpoint**: `logger.py`, `base_watcher.py`, `dashboard_updater.py` all importable. Logger writes valid JSON Lines. Dashboard updater produces valid markdown.

---

## Phase 3: User Story 1 — Drop a File, Get It Triaged (Priority: P1)

**Goal**: A file dropped into `Drop_Box` is detected, renamed with `FILE_` prefix, given YAML frontmatter, and placed in `/Needs_Action` within 10 seconds.

**Independent Test**: Drop `test.txt` into `Drop_Box`, verify `FILE_test.md` appears in `/Needs_Action` with correct frontmatter.

### Implementation for User Story 1

- [X] T008 [US1] Implement `FilesystemWatcher` in `level-bronze/filesystem_watcher.py` — extends `BaseWatcher`, uses watchdog `Observer` + `FileSystemEventHandler`. On file created in `Drop_Box`: call `create_action_file(path)`.
- [X] T009 [US1] Implement `create_action_file(item)` in `FilesystemWatcher` — read file content (text) or write `[Binary file: <name>]` placeholder (binary). Write `FILE_<stem>.md` to `/Needs_Action` with YAML frontmatter (type: file_drop, original_name, dropped_at, status: needs_action, priority: normal, source: Drop_Box). Handle duplicate names by appending `_2`, `_3`, etc.
- [X] T010 [US1] Implement `start()` and `stop()` methods in `FilesystemWatcher` — process existing files in `Drop_Box` on start, then launch watchdog observer. Log start/stop events via `logger.py`.
- [X] T011 [US1] Call `dashboard_updater.update_dashboard()` after each file is processed in `FilesystemWatcher.create_action_file()`.
- [X] T012 [US1] Implement `run_watchers.py` entry point in `level-bronze/run_watchers.py` — instantiate `FilesystemWatcher`, register SIGINT/SIGTERM handlers for graceful shutdown, run main loop with `time.sleep(1)`.

**Checkpoint**: Drop a file into `Drop_Box` → appears in `/Needs_Action` as `FILE_<name>.md` with valid frontmatter. Dashboard.md updated. Log entry written.

---

## Phase 4: User Story 2 — Dashboard Shows System Status (Priority: P1)

**Goal**: `Dashboard.md` displays watcher status, pending task table, and recent activity table. Updates automatically when watcher processes items.

**Independent Test**: Start watcher, drop 3 files, open `Dashboard.md` — see all 3 in Pending Tasks and 3 entries in Recent Activity.

### Implementation for User Story 2

- [X] T013 [US2] Create initial `level-bronze/AI_Employee_Vault/Dashboard.md` with template sections: System Status (Filesystem Watcher: Offline), Pending Tasks (empty table), Recent Activity (empty table).
- [X] T014 [US2] Add watcher heartbeat to `dashboard_updater.py` — accept optional `watcher_status` dict parameter. When `FilesystemWatcher.start()` is called, update Dashboard with watcher online status and timestamp. When `stop()` is called, update to offline.
- [X] T015 [US2] Ensure `update_dashboard()` lists items in Pending Tasks table with columns: ID (filename), Type (from frontmatter), Name (original_name), Priority, Created (dropped_at). Sort by priority descending, then by date.

**Checkpoint**: Dashboard.md shows watcher as Online, lists pending items in table, shows recent log activity.

---

## Phase 5: User Story 3 — Agent Skills as Reusable Intelligence (Priority: P1)

**Goal**: Three Claude Code Agent Skills (`/fte.triage`, `/fte.status`, `/fte.process`) are implemented as RI units in `.claude/commands/`.

**Independent Test**: Place 2 test files in `/Needs_Action`, invoke `/fte.triage` from Claude Code, verify Dashboard updated with classified items.

### Implementation for User Story 3

- [X] T016 [P] [US3] Create `/fte.triage` skill in `level-bronze/.claude/commands/fte.triage.md` — instructions for Claude to: read all files in `AI_Employee_Vault/Needs_Action/`, parse YAML frontmatter, classify items by type, read `Company_Handbook.md` for rules, update priority based on rules, rewrite `Dashboard.md` Pending Tasks section grouped by type. Log the triage action.
- [X] T017 [P] [US3] Create `/fte.status` skill in `level-bronze/.claude/commands/fte.status.md` — instructions for Claude to: count files in each vault folder (Needs_Action, Done, Inbox), read last log entry timestamp, check if watcher process is indicated as running in Dashboard.md, output a system health summary to the user and update Dashboard.md System Status section.
- [X] T018 [P] [US3] Create `/fte.process` skill in `level-bronze/.claude/commands/fte.process.md` — instructions for Claude to: list items in `AI_Employee_Vault/Needs_Action/`, let user pick one (or process oldest), read the file content and frontmatter, read `Company_Handbook.md` for applicable rules, reason about what action to take, update frontmatter (status: done, processed_by: fte.process), move file to `AI_Employee_Vault/Done/`, update Dashboard.md, log the action.

**Checkpoint**: All 3 skills invocable from Claude Code in `/level-bronze`. `/fte.triage` classifies and updates dashboard. `/fte.status` reports health. `/fte.process` moves items to Done.

---

## Phase 6: User Story 4 — Company Handbook Governs Behavior (Priority: P2)

**Goal**: `Company_Handbook.md` contains user-editable rules that Agent Skills read and apply during reasoning.

**Independent Test**: Add rule "Flag files with .exe extension as high priority", drop an `.exe`, run `/fte.triage`, verify priority is set to high.

### Implementation for User Story 4

- [X] T019 [US4] Create `level-bronze/AI_Employee_Vault/Company_Handbook.md` with initial rules: "1. Always be polite and professional.", "2. Process all incoming files within the defined check interval.", "3. Log every action taken for auditability.", "4. Never modify original files — always copy or move.", "5. Flag ambiguous items for human review in /Needs_Action."
- [X] T020 [US4] Update `/fte.triage` skill (`level-bronze/.claude/commands/fte.triage.md`) to include explicit instruction: "Read `AI_Employee_Vault/Company_Handbook.md` and apply each rule when classifying items. If a rule matches an item, note the rule number in the item's frontmatter as `handbook_rule: <number>`."
- [X] T021 [US4] Update `/fte.process` skill (`level-bronze/.claude/commands/fte.process.md`) to include explicit instruction: "Before processing, read `Company_Handbook.md` and verify the proposed action does not violate any rule. If it does, set status to `rejected` with reason."

**Checkpoint**: Handbook rules influence triage priority and process decisions. Rule references appear in frontmatter.

---

## Phase 7: User Story 5 — Audit Logging for All Actions (Priority: P2)

**Goal**: Every watcher and skill action produces a structured JSON log entry in `/Logs/YYYY-MM-DD.json`.

**Independent Test**: Run full pipeline (drop → watcher → triage skill → process skill), check log file has entries for all 4 actions.

### Implementation for User Story 5

- [X] T022 [US5] Add logging calls to `FilesystemWatcher` — log `file_detected` on watchdog event, `file_processed` after action file creation, `file_error` on any exception. Each call uses `logger.py` with correct actor/source/destination fields.
- [X] T023 [US5] Add logging calls to `dashboard_updater.py` — log `dashboard_updated` after each rewrite with details showing pending count and activity count.
- [X] T024 [US5] Update all 3 Agent Skills to include logging instruction: "After completing the action, append a JSON log entry to `AI_Employee_Vault/Logs/YYYY-MM-DD.json` with fields: timestamp, action (`skill_executed`), actor (`fte.<name>`), source, destination, result."
- [X] T025 [US5] Implement `DRY_RUN` support in `logger.py` — when `DRY_RUN=true` env var is set, add `"dry_run": true` to all log entries. In `filesystem_watcher.py`, skip file moves but still log intended actions.

**Checkpoint**: Log file contains entries for every watcher event, dashboard update, and skill execution. DRY_RUN mode logs without moving.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, documentation, and validation.

- [X] T026 [P] Create `level-bronze/.gitignore` — exclude `.venv/`, `__pycache__/`, `*.pyc`, `AI_Employee_Vault/Logs/*.json` (optional: keep logs out of git)
- [X] T027 [P] Validate quickstart flow end-to-end: clone → `uv sync` → `uv run python run_watchers.py` → drop file → check Needs_Action → run `/fte.triage` → run `/fte.process` → check Done
- [X] T028 Update `level-bronze/pyproject.toml` with correct metadata, scripts entry point, and pytest dependency for test running
- [X] T029 [P] Create a sample test file `level-bronze/tests/test_filesystem_watcher.py` — test that `create_action_file` produces correct frontmatter, handles duplicates, handles binary files

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1 File Drop)**: Depends on Phase 2 — core perception pipeline
- **Phase 4 (US2 Dashboard)**: Depends on Phase 2 + T011 from US1 (dashboard updater already called)
- **Phase 5 (US3 Agent Skills)**: Depends on Phase 2 — can start after Phase 2, parallel with US1/US2
- **Phase 6 (US4 Handbook)**: Depends on T016-T018 (skills must exist to update)
- **Phase 7 (US5 Logging)**: Depends on T005 (logger), T008 (watcher), T016-T018 (skills)
- **Phase 8 (Polish)**: Depends on all previous phases

### User Story Dependencies

- **US1 (File Drop)**: After Phase 2 — no other story dependencies
- **US2 (Dashboard)**: After Phase 2 — integrates with US1 outputs
- **US3 (Agent Skills)**: After Phase 2 — can proceed independently
- **US4 (Handbook)**: After US3 (modifies skills)
- **US5 (Logging)**: After US1 + US3 (adds logging to both)

### Parallel Opportunities

```
After Phase 2 completes:
  ├── US1 (T008-T012) — filesystem watcher
  ├── US3 (T016-T018) — agent skills [P] all three in parallel
  └── US2 (T013-T015) — dashboard (can overlap with US1)

After US1 + US3:
  ├── US4 (T019-T021) — handbook rules
  └── US5 (T022-T025) — logging integration
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (logger, base_watcher, dashboard_updater)
3. Complete Phase 3: US1 — filesystem watcher
4. **STOP AND VALIDATE**: Drop a file, verify it appears in `/Needs_Action`
5. This alone is a working Bronze demo

### Incremental Delivery

1. Setup + Foundational → infrastructure ready
2. US1 (File Drop) → working perception layer (MVP!)
3. US2 (Dashboard) → visible system state
4. US3 (Agent Skills) → RI units operational
5. US4 (Handbook) → configurable behavior
6. US5 (Logging) → full observability
7. Polish → production-ready Bronze tier

---

## Task Summary

| Phase | Story | Tasks | Parallel |
|-------|-------|-------|----------|
| Setup | — | T001–T004 | T003, T004 |
| Foundational | — | T005–T007 | T006, T007 |
| US1 File Drop | P1 | T008–T012 | — |
| US2 Dashboard | P1 | T013–T015 | — |
| US3 Agent Skills | P1 | T016–T018 | T016, T017, T018 |
| US4 Handbook | P2 | T019–T021 | — |
| US5 Logging | P2 | T022–T025 | — |
| Polish | — | T026–T029 | T026, T027, T029 |
| **Total** | | **29 tasks** | **11 parallelizable** |
