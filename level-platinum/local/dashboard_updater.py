"""Dashboard updater — reads vault state and atomically rewrites Dashboard.md."""

import json
from datetime import datetime, timezone
from pathlib import Path


# All watcher names the Gold tier can report.
KNOWN_WATCHERS = [
    "FilesystemWatcher", "GmailWatcher", "WhatsAppWatcher",
    "LinkedInWatcher", "FacebookWatcher", "InstagramWatcher",
    "TwitterWatcher", "ApprovalWatcher",
]


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
    """Count .md files in a vault folder recursively (returns 0 if folder missing)."""
    if not folder.exists():
        return 0
    return sum(1 for f in folder.glob("**/*.md"))


def _count_social_files(folder: Path, prefix: str) -> int:
    """Count social media action files with a given prefix in a vault folder."""
    if not folder.exists():
        return 0
    return sum(1 for f in folder.glob(f"{prefix}*.md"))


def update_dashboard(
    vault_path: str | Path,
    watcher_status: dict | None = None,
    service_health: dict | None = None,
    odoo_summary: dict | None = None,
) -> Path:
    """Scan vault state and atomically rewrite Dashboard.md.

    Shows:
        - System status for all 6 watchers (+ SocialMediaWatcher)
        - Service Health table (Odoo, social media circuit breaker states)
        - Odoo financial snapshot (if provided)
        - Pending Tasks table (Needs_Action items, sorted by priority)
        - Pending Approvals count (Pending_Approval/)
        - Plans count (Plans/)
        - Recent Activity log (last 10 entries)

    Args:
        vault_path:     Path to the AI_Employee_Vault directory.
        watcher_status: Dict like {"GmailWatcher": "Online"}.
                        Omitted watchers default to "Offline".
        service_health: Dict of CircuitBreaker.status dicts keyed by service name.
                        e.g. {"odoo": {"circuit_state": "open", "failure_count": 3, ...}}
        odoo_summary:   Dict with keys: revenue, expenses, outstanding_count, outstanding_total,
                        overdue_count, overdue_total (all optional).

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
        # Platinum Tier — scan domain subdirectories recursively
        for md_file in sorted(needs_action.glob("**/*.md")):
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
    # Service Health (circuit breakers — Gold Tier)
    # -----------------------------------------------------------------------
    service_health_lines: list[str] = []
    if service_health:
        for svc_name, status in service_health.items():
            state = status.get("circuit_state", "unknown")
            failures = status.get("failure_count", 0)
            retry_in = status.get("retry_in_seconds")
            if state == "closed":
                icon = "🟢"
                detail = "Online"
            elif state == "open":
                icon = "🔴"
                retry_str = f", retry in {retry_in:.0f}s" if retry_in else ""
                detail = f"Degraded (circuit open, {failures} failure(s){retry_str})"
            else:  # half_open
                icon = "🟡"
                detail = "Probing (half-open)"
            service_health_lines.append(f"- **{svc_name}**: {icon} {detail}")

    # -----------------------------------------------------------------------
    # Odoo financial snapshot
    # -----------------------------------------------------------------------
    odoo_lines: list[str] = []
    if odoo_summary:
        revenue = odoo_summary.get("revenue", "N/A")
        expenses = odoo_summary.get("expenses", "N/A")
        out_count = odoo_summary.get("outstanding_count", 0)
        out_total = odoo_summary.get("outstanding_total", "N/A")
        ov_count = odoo_summary.get("overdue_count", 0)
        ov_total = odoo_summary.get("overdue_total", "N/A")
        odoo_lines = [
            f"- 💰 Revenue (this month): **{revenue}**",
            f"- 💸 Expenses (this month): **{expenses}**",
            f"- 📄 Outstanding invoices: **{out_count}** totalling **{out_total}**",
            f"- ⚠️ Overdue invoices: **{ov_count}** totalling **{ov_total}**",
        ]

    # -----------------------------------------------------------------------
    # Social Media Engagement (posts published)
    # -----------------------------------------------------------------------
    done = vault / "Done"
    fb_posts = _count_social_files(done, "SOCIAL_FB_")
    ig_posts = _count_social_files(done, "SOCIAL_IG_")
    twitter_posts = _count_social_files(done, "TWITTER_")
    total_social = fb_posts + ig_posts + twitter_posts

    social_lines: list[str] = []
    if total_social > 0:
        social_lines = [
            f"- 📘 Facebook: **{fb_posts}** post{'s' if fb_posts != 1 else ''}",
            f"- 📷 Instagram: **{ig_posts}** post{'s' if ig_posts != 1 else ''}",
            f"- 🐦 Twitter: **{twitter_posts}** tweet{'s' if twitter_posts != 1 else ''}",
            f"- 📊 Total: **{total_social}** published",
        ]

    # -----------------------------------------------------------------------
    # Cloud Agent Status (Platinum Tier)
    # -----------------------------------------------------------------------
    cloud_status_lines: list[str] = []
    cloud_status_file = vault / "Updates" / "cloud_status.md"
    if cloud_status_file.exists():
        try:
            cloud_text = cloud_status_file.read_text(encoding="utf-8")
            cloud_fm = _parse_frontmatter(cloud_text)
            cloud_updated = cloud_fm.get("last_updated", "unknown")[:19].replace("T", " ")
            cloud_gmail = cloud_fm.get("gmail_status", "unknown")
            cloud_needs = cloud_fm.get("needs_action_count", "0")
            cloud_progress = cloud_fm.get("in_progress_count", "0")
            cloud_pending = cloud_fm.get("pending_approval_count", "0")

            gmail_icon = "🟢" if cloud_gmail == "online" else "🔴"
            cloud_status_lines = [
                f"**Last Updated:** {cloud_updated}",
                f"- Gmail: {gmail_icon} {cloud_gmail}",
                f"- Needs_Action: {cloud_needs}",
                f"- In_Progress/cloud: {cloud_progress}",
                f"- Pending_Approval: {cloud_pending}",
            ]
        except Exception:
            cloud_status_lines = ["⚠️ Cloud status unavailable"]

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

    # CEO briefing notification — detect most recent unread CEO_BRIEFING_*.md
    ceo_briefing_note = ""
    if plans.exists():
        ceo_files = sorted(plans.glob("CEO_BRIEFING_*.md"), reverse=True)
        if ceo_files:
            latest = ceo_files[0]
            ceo_briefing_note = (
                f"\n📊 **CEO Briefing ready**: `Plans/{latest.name}` — open in Obsidian"
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
    service_health_section = (
        "\n## Service Health\n" + "\n".join(service_health_lines) + "\n"
        if service_health_lines
        else ""
    )
    odoo_section = (
        "\n## Odoo Financial Snapshot\n" + "\n".join(odoo_lines) + "\n"
        if odoo_lines
        else ""
    )
    social_section = (
        "\n## Social Media Engagement\n" + "\n".join(social_lines) + "\n"
        if social_lines
        else ""
    )
    cloud_section = (
        "\n## Cloud Agent\n" + "\n".join(cloud_status_lines) + "\n"
        if cloud_status_lines
        else ""
    )

    content = f"""# AI Employee Dashboard

## System Status
{chr(10).join(status_lines)}
{service_health_section}{cloud_section}{odoo_section}{social_section}
## Inbox ({len(pending_items)} item{"s" if len(pending_items) != 1 else ""} pending)
{pending_table}
## HITL Queue
{approval_note}
{plans_note}{ceo_briefing_note}

## Recent Activity (last 10 events)
{activity_table}
---
*Last updated: {now_str} — auto-generated by platinum-fte*
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
