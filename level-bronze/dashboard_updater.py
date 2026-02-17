"""Dashboard updater — reads vault state and writes Dashboard.md."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from a markdown file's text content."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip()
    return data


def _read_recent_logs(logs_path: Path, limit: int = 10) -> list[dict]:
    """Read the most recent log entries across today's and yesterday's files."""
    entries = []
    log_files = sorted(logs_path.glob("*.json"), reverse=True)
    for log_file in log_files[:2]:
        try:
            for line in reversed(log_file.read_text(encoding="utf-8").strip().splitlines()):
                if line.strip():
                    entries.append(json.loads(line))
                if len(entries) >= limit:
                    break
        except (json.JSONDecodeError, OSError):
            continue
        if len(entries) >= limit:
            break
    return entries[:limit]


def update_dashboard(
    vault_path: str | Path,
    watcher_status: dict | None = None,
) -> Path:
    """Scan vault state and rewrite Dashboard.md.

    Args:
        vault_path: Path to the AI_Employee_Vault directory.
        watcher_status: Optional dict like {"FilesystemWatcher": "Online"}.

    Returns:
        Path to the written Dashboard.md file.
    """
    vault = Path(vault_path)
    needs_action = vault / "Needs_Action"
    logs_path = vault / "Logs"
    dashboard_path = vault / "Dashboard.md"

    # --- System Status ---
    status_lines = []
    if watcher_status:
        for name, state in watcher_status.items():
            icon = "🟢" if state == "Online" else "🔴"
            status_lines.append(
                f"- {name}: {icon} {state} | Last check: "
                f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
    else:
        status_lines.append("- No watchers reporting")

    # --- Pending Tasks ---
    pending_items = []
    if needs_action.exists():
        for md_file in sorted(needs_action.glob("*.md")):
            try:
                text = md_file.read_text(encoding="utf-8")
                fm = _parse_frontmatter(text)
                pending_items.append({
                    "id": md_file.stem,
                    "type": fm.get("type", "unknown"),
                    "name": fm.get("original_name", md_file.name),
                    "priority": fm.get("priority", "normal"),
                    "created": fm.get("dropped_at", "unknown"),
                })
            except OSError:
                continue

    # Sort: priority (urgent > high > normal > low), then date
    priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    pending_items.sort(key=lambda x: (priority_order.get(x["priority"], 2), x["created"]))

    pending_table = "| ID | Type | Name | Priority | Created |\n"
    pending_table += "|----|------|------|----------|---------|\n"
    for item in pending_items:
        pending_table += (
            f"| {item['id']} | {item['type']} | {item['name']} "
            f"| {item['priority']} | {item['created']} |\n"
        )
    if not pending_items:
        pending_table += "| — | — | No pending items | — | — |\n"

    # --- Recent Activity ---
    log_entries = _read_recent_logs(logs_path)
    activity_table = "| Timestamp | Action | Actor | Details |\n"
    activity_table += "|-----------|--------|-------|---------|\n"
    for entry in log_entries:
        ts = entry.get("timestamp", "")[:19].replace("T", " ")
        action = entry.get("action", "")
        actor = entry.get("actor", "")
        details = entry.get("source", "") or entry.get("details", "")
        activity_table += f"| {ts} | {action} | {actor} | {details} |\n"
    if not log_entries:
        activity_table += "| — | — | No recent activity | — |\n"

    # --- Compose Dashboard ---
    content = f"""# AI Employee Dashboard

## System Status
{chr(10).join(status_lines)}

## Pending Tasks ({len(pending_items)} items)
{pending_table}
## Recent Activity (last 10)
{activity_table}
---
*Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*
"""

    # Atomic write: write to temp, then rename
    tmp_path = dashboard_path.with_suffix(".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(dashboard_path)

    return dashboard_path
