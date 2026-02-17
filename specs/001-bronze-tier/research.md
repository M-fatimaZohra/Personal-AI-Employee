# Research: Bronze Tier

**Branch**: `001-bronze-tier` | **Date**: 2026-02-16

## R1: Filesystem Watching on Windows + WSL

**Decision**: Use Python `watchdog` library with the `Observer` class.
**Rationale**: watchdog provides cross-platform filesystem event
monitoring. On Windows it uses ReadDirectoryChangesW; on WSL/Linux it
uses inotify. Both are efficient and non-polling.
**Alternatives considered**:
- `os.scandir` polling loop: simpler but wastes CPU and has latency
- `inotify` directly: Linux-only, not cross-platform
- Windows `FileSystemWatcher` via ctypes: complex, Windows-only

## R2: YAML Frontmatter Parsing

**Decision**: Use Python `re` module to split frontmatter, no heavy
YAML dependency needed for Bronze.
**Rationale**: Action files have simple key-value frontmatter. A regex
split on `---` delimiters + line-by-line parsing is sufficient. Full
YAML parsing (PyYAML) can be added in Silver if needed.
**Alternatives considered**:
- PyYAML: adds dependency, overkill for simple key-value pairs
- python-frontmatter: nice API but another dependency
- Manual split: chosen — zero dependencies, adequate for Bronze

## R3: Structured Logging Format

**Decision**: JSON Lines (one JSON object per line) in daily log files.
**Rationale**: JSON Lines is grep-friendly, appendable, and parseable
by any language. Daily rotation (`YYYY-MM-DD.json`) keeps files small.
**Alternatives considered**:
- Markdown log entries: human-readable but hard to parse programmatically
- SQLite: powerful but overkill for Bronze, adds complexity
- Python `logging` module with JSON formatter: good for app logs but
  we need structured audit logs in the vault, not stderr

## R4: Agent Skills Implementation

**Decision**: Claude Code slash commands as `.md` files in
`.claude/commands/`.
**Rationale**: This is the hackathon-mandated approach. Skills are
markdown files containing instructions for Claude. They are the
Reusable Intelligence (RI) unit — portable, composable, version-
controlled.
**Alternatives considered**:
- Python scripts called by Claude: not RI-portable, couples to runtime
- MCP server tools: Silver/Gold scope, too heavy for Bronze
- Hooks: not user-invocable, wrong abstraction layer

## R5: Dashboard Update Strategy

**Decision**: Watcher calls a `dashboard_updater.py` module after each
file operation. The updater scans vault state and rewrites Dashboard.md.
**Rationale**: Scanning `/Needs_Action` and `/Done` on each event
ensures the dashboard is always consistent with vault state, even if
files are manually moved.
**Alternatives considered**:
- Incremental append: fast but drifts from reality if files are
  manually moved or deleted
- Obsidian Dataview plugin: nice but couples to Obsidian, not portable
- Separate dashboard watcher: unnecessary complexity for Bronze
