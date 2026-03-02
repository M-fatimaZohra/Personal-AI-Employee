"""Dashboard updater — reads vault state and atomically rewrites Dashboard.md."""

import json
from datetime import datetime, timezone
from pathlib import Path


# All watcher names the Silver tier can report. Unknown watchers in watcher_status
# are also displayed but not listed here by default.
KNOWN_WATCHERS = ["FilesystemWatcher", "GmailWatcher", "WhatsAppWatcher", "LinkedInWatcher", "ApprovalWatcher"]


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from a markdown file."""
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
    """Return the most recent log entries across today's and yesterday's files."""
    entries: list[dict] = []
    log_files = sorted(logs_path.glob("*.json"), reverse=True)
    for log_file in log_files[:2]:
        try:
            lines = log_file.read_text(encoding="utf-8").strip().splitlines()
            for line in reversed(lines):
                if line.strip():
                    entries.append(json.loads(line))
                if len(entries) >= limit:
                    break
        except (json.JSONDecodeError, OSError):
            continue
        if len(entries) >= limit:
            break
    return entries[:limit]


def _count_md_files(folder: Path) -> int:
    """Count .md files in a vault folder (returns 0 if folder missing)."""
    if not folder.exists():
        return 0
    return sum(1 for f in folder.glob("*.md"))


def update_dashboard(
    vault_path: str | Path,
    watcher_status: dict | None = None,
) -> Path:
    """Scan vault state and atomically rewrite Dashboard.md.

    Shows:
        - System status for all 5 watchers (Filesystem, Gmail, WhatsApp, LinkedIn, Approval)
        - Pending Tasks table (Needs_Action items, sorted by priority)
        - Pending Approvals count (Pending_Approval/)
        - Plans count (Plans/)
        - Recent Activity log (last 10 entries)

    Args:
        vault_path:     Path to the AI_Employee_Vault directory.
        watcher_status: Dict like {"GmailWatcher": "Online"}.
                        Omitted watchers default to "Offline".

    Returns:
        Path to the written Dashboard.md file.
    """
    vault = Path(vault_path)
    needs_action = vault / "Needs_Action"
    pending_approval = vault / "Pending_Approval"
    plans = vault / "Plans"
    logs_path = vault / "Logs"
    dashboard_path = vault / "Dashboard.md"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # -----------------------------------------------------------------------
    # System Status — all known watchers, unknown ones from watcher_status dict
    # -----------------------------------------------------------------------
    merged_status: dict[str, str] = {w: "Offline" for w in KNOWN_WATCHERS}
    if watcher_status:
        merged_status.update(watcher_status)

    status_lines = []
    for name, state in merged_status.items():
        icon = "🟢" if state.startswith("Online") else "🔴"
        status_lines.append(f"- **{name}**: {icon} {state} — {now_str}")

    # -----------------------------------------------------------------------
    # Pending Tasks (Needs_Action)
    # -----------------------------------------------------------------------
    priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    pending_items: list[dict] = []

    if needs_action.exists():
        for md_file in sorted(needs_action.glob("*.md")):
            try:
                text = md_file.read_text(encoding="utf-8")
                fm = _parse_frontmatter(text)
                item_type = fm.get("type", "unknown")

                # Display name differs by type
                if item_type == "email":
                    display = fm.get("subject", md_file.name)[:60]
                    from_field = fm.get("from", "")
                    display = f"{display} ← {from_field[:30]}" if from_field else display
                elif item_type == "whatsapp_message":
                    chat = fm.get("chat_name", "unknown chat")
                    snippet = fm.get("snippet", "")[:40]
                    display = f"{chat}: {snippet}" if snippet else chat
                elif item_type == "linkedin_notification":
                    notif_type = fm.get("notif_type", "notification")
                    actor = fm.get("actor_name", "someone")
                    display = f"{notif_type} from {actor}"[:60]
                else:
                    display = fm.get("original_name", md_file.name)

                pending_items.append({
                    "id": md_file.stem,
                    "type": item_type,
                    "name": display,
                    "priority": fm.get("priority", "normal"),
                    "created": fm.get("dropped_at", fm.get("created_at", "unknown"))[:19],
                })
            except OSError:
                continue

    pending_items.sort(
        key=lambda x: (priority_order.get(x["priority"], 2), x["created"])
    )

    pending_table = "| ID | Type | Item | Priority | Received |\n"
    pending_table += "|----|------|------|----------|----------|\n"
    for item in pending_items:
        pending_table += (
            f"| `{item['id']}` | {item['type']} | {item['name']} "
            f"| **{item['priority']}** | {item['created']} |\n"
        )
    if not pending_items:
        pending_table += "| — | — | ✅ All clear — nothing pending | — | — |\n"

    # -----------------------------------------------------------------------
    # Approval queue and Plans counts
    # -----------------------------------------------------------------------
    approval_count = _count_md_files(pending_approval)
    plans_count = _count_md_files(plans)

    approval_note = (
        f"⚠️ **{approval_count} item(s) awaiting your approval** in `Pending_Approval/`"
        if approval_count > 0
        else "✅ No pending approvals"
    )
    plans_note = (
        f"📋 **{plans_count} active plan(s)** in `Plans/`"
        if plans_count > 0
        else "📋 No active plans"
    )

    # -----------------------------------------------------------------------
    # Recent Activity log
    # -----------------------------------------------------------------------
    log_entries = _read_recent_logs(logs_path)
    activity_table = "| Timestamp | Action | Actor | Details |\n"
    activity_table += "|-----------|--------|-------|---------|\n"
    for entry in log_entries:
        ts = entry.get("timestamp", "")[:19].replace("T", " ")
        action = entry.get("action", "")
        actor = entry.get("actor", "")
        details = entry.get("details", "") or entry.get("source", "")
        result = entry.get("result", "")
        result_icon = "✅" if result == "success" else ("🔄" if result == "dry_run" else "❌")
        activity_table += (
            f"| {ts} | {result_icon} {action} | {actor} | {details[:60]} |\n"
        )
    if not log_entries:
        activity_table += "| — | — | No recent activity | — |\n"

    # -----------------------------------------------------------------------
    # Compose Dashboard
    # -----------------------------------------------------------------------
    content = f"""# AI Employee Dashboard

## System Status
{chr(10).join(status_lines)}

## Inbox ({len(pending_items)} item{"s" if len(pending_items) != 1 else ""} pending)
{pending_table}
## HITL Queue
{approval_note}
{plans_note}

## Recent Activity (last 10 events)
{activity_table}
---
*Last updated: {now_str} — auto-generated by silver-fte*
"""

    # Atomic write: temp file → rename (prevents Obsidian from reading partial writes)
    # Falls back to direct write on Windows if Obsidian has the file locked (PermissionError)
    tmp_path = dashboard_path.with_suffix(".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    try:
        tmp_path.replace(dashboard_path)
    except PermissionError:
        # Obsidian has Dashboard.md locked — write directly instead of crashing
        try:
            dashboard_path.write_text(content, encoding="utf-8")
        except PermissionError:
            pass  # Dashboard update skipped — Obsidian lock held; will retry next tick
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    return dashboard_path
