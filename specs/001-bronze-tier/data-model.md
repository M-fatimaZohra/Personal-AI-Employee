# Data Model: Bronze Tier

**Branch**: `001-bronze-tier` | **Date**: 2026-02-16

## Entities

### ActionFile

Represents a detected item in the vault awaiting processing.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | enum | yes | `file_drop`, `email`, `message`, `task` |
| original_name | string | yes | Original filename before renaming |
| dropped_at | ISO 8601 datetime | yes | When the item was detected |
| status | enum | yes | `needs_action`, `in_progress`, `done`, `rejected` |
| priority | enum | no | `low`, `normal` (default), `high`, `urgent` |
| source | string | yes | Origin folder/source (e.g., `Drop_Box`) |
| processed_by | string | no | Skill name that last processed this item |

**State transitions**:
```
needs_action → in_progress → done
needs_action → rejected
```

**File naming**: `FILE_<original_stem>.md` (e.g., `FILE_invoice.md`)
**Duplicate handling**: Append `_2`, `_3`, etc. if name exists.

### LogEntry

Represents a single audit log record.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| timestamp | ISO 8601 datetime | yes | When the action occurred |
| action | string | yes | Action type (e.g., `file_processed`, `skill_executed`) |
| actor | string | yes | Who performed it (e.g., `FilesystemWatcher`, `fte.triage`) |
| source | string | no | Input path or source identifier |
| destination | string | no | Output path or destination identifier |
| result | enum | yes | `success`, `warning`, `error` |
| dry_run | boolean | no | `true` if DRY_RUN mode was active |
| details | string | no | Additional context or error message |

**Storage**: One JSON object per line in `/Logs/YYYY-MM-DD.json`.

### DashboardState

Derived view (not stored separately — computed from vault state).

| Section | Source | Update Trigger |
|---------|--------|----------------|
| System Status | Watcher heartbeat | Watcher start/stop |
| Pending Tasks | Scan `/Needs_Action` | Any file change |
| Recent Activity | Read last 10 log entries | Any log append |

## Relationships

```
Drop_Box --[watcher]--> Needs_Action (ActionFile created)
Needs_Action --[skill]--> Done (status: done)
Needs_Action --[skill]--> Needs_Action (status: rejected)
Any action --[logger]--> Logs (LogEntry appended)
Vault state --[updater]--> Dashboard.md (rewritten)
```
