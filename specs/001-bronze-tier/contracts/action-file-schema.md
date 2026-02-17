# Contract: Action File Schema

**Version**: 1.0 | **Date**: 2026-02-16

## Purpose

Defines the contract between Watchers (producers) and Agent Skills
(consumers) for files in `/Needs_Action`.

## Format

All action files are Markdown with YAML frontmatter.

### Required Frontmatter Fields

| Field | Type | Values | Producer |
|-------|------|--------|----------|
| `type` | string | `file_drop`, `email`, `message`, `task` | Watcher |
| `original_name` | string | Original filename | Watcher |
| `dropped_at` | string | ISO 8601 datetime | Watcher |
| `status` | string | `needs_action` (initial) | Watcher |
| `source` | string | Source identifier | Watcher |

### Optional Frontmatter Fields

| Field | Type | Values | Producer |
|-------|------|--------|----------|
| `priority` | string | `low`, `normal`, `high`, `urgent` | Skill |
| `processed_by` | string | Skill name | Skill |
| `processed_at` | string | ISO 8601 datetime | Skill |
| `tags` | list | User-defined labels | Skill |

### Body

- Text files: original content verbatim
- Binary files: `[Binary file: <original_name>]`

## File Naming

- Pattern: `FILE_<stem>.md` (filesystem watcher)
- Future: `EMAIL_<id>.md`, `MSG_<id>.md` (Silver tier)
- Duplicates: append `_2`, `_3`, etc.

## Status Lifecycle

```
[Watcher creates] → needs_action
[Skill claims]    → in_progress
[Skill completes] → done (moved to /Done)
[Skill rejects]   → rejected (stays in /Needs_Action with reason)
```

## Consumers

- `/fte.triage`: reads all `needs_action` items, classifies, updates priority
- `/fte.process`: reads a specific item, reasons about it, moves to `/Done`
- `/fte.status`: counts items by status for system health report
