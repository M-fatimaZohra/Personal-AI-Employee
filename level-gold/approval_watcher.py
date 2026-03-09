"""Approval watcher — monitors /Approved and /Rejected for HITL user decisions."""

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Self

# ccr code is installed as ccr.CMD on Windows — requires shell to execute
_WIN32 = sys.platform == "win32"

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from backoff import retry_with_backoff
from base_watcher import BaseWatcher
from dashboard_updater import update_dashboard
from facebook_poster import FacebookScheduler
from id_tracker import IDTracker
from instagram_poster import InstagramScheduler
from linkedin_poster import JitterScheduler, extract_post_content
from logger import DRY_RUN, log_action
from twitter_poster import TwitterScheduler
# whatsapp_sender (Playwright) removed — WhatsApp sends are handled by the
# Baileys Node.js watcher (whatsapp_watcher.js) via chokidar on /Approved/.


# Action types this watcher knows how to dispatch.
KNOWN_ACTION_TYPES = {
    "email_reply", "linkedin_post", "whatsapp_reply", "social_post",
    # Odoo / invoice workflow types — dispatched to fte-approve
    "odoo_invoice", "odoo_action", "odoo_partner", "manual_review",
    # Aliases fte-plan sometimes writes — treated same as odoo_action
    "approval_request", "approval",
}

# Fields that MUST be present in frontmatter per action type.
REQUIRED_FIELDS: dict[str, list[str]] = {
    "email_reply": ["to", "subject"],
    "linkedin_post": [],
    "whatsapp_reply": ["chat_name"],
    "social_post": ["platform"],  # platform: facebook | instagram | twitter
    "odoo_invoice": [],
    "odoo_action": [],
    "odoo_partner": [],
    "manual_review": [],
    "approval_request": [],
    "approval": [],
}


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from a markdown file (simple key: value pairs)."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data: dict = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip()
    return data


def _rewrite_status(text: str, new_status: str) -> str:
    """Return file content with the `status:` field in frontmatter replaced."""
    lines = text.splitlines(keepends=True)
    new_lines: list[str] = []
    in_front = False
    replaced = False
    for i, line in enumerate(lines):
        if i == 0 and line.strip() == "---":
            in_front = True
            new_lines.append(line)
            continue
        if in_front and line.strip() == "---":
            in_front = False
            new_lines.append(line)
            continue
        if in_front and line.startswith("status:") and not replaced:
            new_lines.append(f"status: {new_status}\n")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        # Append status before closing --- if not found
        new_lines.insert(1, f"status: {new_status}\n")
    return "".join(new_lines)


def _extract_proposed_reply(text: str) -> str:
    """Extract the body of the '## Proposed Reply' section from an approval file.

    Returns the trimmed text between '## Proposed Reply' and the next '##'
    heading (or end of file), stripping blockquote markers and horizontal rules.
    Returns an empty string if the section is not found.
    """
    marker = "## Proposed Reply"
    idx = text.find(marker)
    if idx == -1:
        return ""

    body = text[idx + len(marker):]
    # Trim at the next heading
    next_heading = body.find("\n## ")
    if next_heading != -1:
        body = body[:next_heading]

    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            stripped = stripped[1:].strip()
        if stripped in ("---", "***", "___"):
            continue
        lines.append(stripped)

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Watchdog handlers
# ---------------------------------------------------------------------------

class _FolderEventHandler(FileSystemEventHandler):
    """Fires immediately when a .md file appears in /Approved or /Rejected."""

    def __init__(self, watcher: "ApprovalWatcher", decision: str) -> None:
        super().__init__()
        self.watcher = watcher
        self.decision = decision

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        time.sleep(0.3)  # let the file finish writing (Obsidian flushes in chunks)
        source = Path(event.src_path)
        if source.exists() and source.suffix == ".md":
            try:
                self.watcher.create_action_file((self.decision, source))
            except Exception as e:
                self.watcher._log_error(f"watchdog.{self.decision}", e)


# ---------------------------------------------------------------------------
# ApprovalWatcher
# ---------------------------------------------------------------------------

class ApprovalWatcher(BaseWatcher):
    """Monitors /Approved and /Rejected for user HITL decisions.

    Pipeline per file:
        1. User moves APPROVAL_*.md from /Pending_Approval to /Approved or /Rejected
           (via Obsidian drag-and-drop or file manager)
        2. Watchdog event fires within seconds; polling loop is a fallback
        3. IDTracker prevents duplicate processing if both detect the same file
        4. /Approved path:
              validate frontmatter → dispatch MCP action (with backoff) →
              move to /Done with status=executed
        5. /Rejected path:
              log rejection → move to /Done with status=rejected
        6. Expiration sweep on every poll: /Pending_Approval files past
           expires_at → /Done with status=expired

    MCP dispatch calls `fte-approve` via `claude --print` subprocess (Option B pattern),
    mirroring the orchestrator's skill dispatch. `retry_with_backoff` wraps the call.
    """

    def __init__(
        self,
        vault_path: str | Path,
        check_interval: int = 10,
    ) -> None:
        super().__init__(vault_path, check_interval)

        # ID tracker — stored next to vault in .state/ (gitignored)
        self._tracker = IDTracker(self.vault_path.parent / ".state")

        # Watchdog observer for immediate detection
        self._observer = Observer()
        self._observer.schedule(
            _FolderEventHandler(self, "approved"),
            str(self.approved),
            recursive=False,
        )
        self._observer.schedule(
            _FolderEventHandler(self, "rejected"),
            str(self.rejected),
            recursive=False,
        )

        # Note: MCP dispatch removed — orchestrator.check_approved() is sole dispatcher

    # ------------------------------------------------------------------
    # BaseWatcher interface
    # ------------------------------------------------------------------

    def check_for_updates(self) -> list[Any]:
        """Return unprocessed files in /Approved and /Rejected; sweep expirations."""
        self._sweep_expired()
        items: list[tuple[str, Path]] = []
        for folder, decision in (
            (self.approved, "approved"),
            (self.rejected, "rejected"),
        ):
            if not folder.exists():
                continue
            for f in sorted(folder.glob("*.md")):
                if f.is_file() and not self._tracker.is_processed("approvals", f.stem):
                    items.append((decision, f))
        return items

    def create_action_file(self, item: Any) -> Path:
        """Process one ``(decision, filepath)`` tuple.

        Args:
            item: ``("approved" | "rejected", Path)`` tuple.

        Returns:
            Path of the file after it has been moved to /Done.
        """
        decision, path = item
        path = Path(path)

        if not path.exists():
            return path  # already moved by a concurrent handler

        if self._tracker.is_processed("approvals", path.stem):
            return path  # dedup guard — watchdog + polling could both fire

        self._tracker.mark_processed("approvals", path.stem)

        if decision == "approved":
            return self._process_approved(path)
        return self._process_rejected(path)

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def _process_approved(self, path: Path) -> Path:
        """Validate and execute an approved action; archive to /Done."""
        # Read file
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            log_action(
                self.logs, "approval_read_error", "ApprovalWatcher",
                source=path.name, result="error", details=str(e),
            )
            return self._move_to_done(path, "read_error")

        fm = _parse_frontmatter(text)
        action_type = fm.get("type", "")

        # Validate frontmatter
        error = self._validate(fm)
        if error:
            # Write error context to the file before routing to /Rejected
            error_note = f"\n\n## Validation Error\n\n{error}\n"
            rejected_dest = self.rejected / path.name
            try:
                self.rejected.mkdir(parents=True, exist_ok=True)
                rejected_dest.write_text(text + error_note, encoding="utf-8")
                path.unlink(missing_ok=True)
            except OSError as _oe:
                # If we couldn't write to Rejected/, still remove from Approved/
                # to prevent the orchestrator re-dispatch loop.
                log_action(self.logs, "approval_rejected_write_error", "ApprovalWatcher",
                           source=path.name, result="error",
                           details=f"Could not write to Rejected/: {_oe} — deleting from Approved/ anyway")
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            log_action(
                self.logs, "approval_validation_failed", "ApprovalWatcher",
                source=path.name, result="error", details=error,
            )
            done_path = self._move_to_done(rejected_dest, "validation_failed")
            update_dashboard(self.vault_path)
            return done_path

        # DRY_RUN — log but do not execute
        if DRY_RUN:
            log_action(
                self.logs, "approval_dispatched", "ApprovalWatcher",
                source=path.name, result="dry_run",
                details=f"Would dispatch action: {action_type}",
            )
            return self._move_to_done(path, "executed_dry_run")

        # LinkedIn posts use the jitter scheduler (never immediate MCP dispatch)
        if action_type == "linkedin_post":
            return self._schedule_linkedin_post(path, text)

        # Social posts (Facebook/Instagram/Twitter) use platform-specific schedulers
        if action_type == "social_post":
            return self._schedule_social_post(path, text, fm)

        # WhatsApp replies are handled by the Baileys Node.js watcher (whatsapp_watcher.js).
        # chokidar watches /Approved/APPROVAL_WA_*.md and calls sock.sendMessage() directly.
        # Leave the file in /Approved so Baileys can pick it up — do not move or send here.
        if action_type == "whatsapp_reply":
            log_action(
                self.logs, "wa_reply_delegated", "ApprovalWatcher",
                source=path.name, result="info",
                details="Delegated to Baileys watcher (whatsapp_watcher.js) — no action here",
            )
            return path

        # All other types: mark as validated and leave in /Approved for
        # orchestrator.check_approved() to dispatch via fte-approve.
        # ApprovalWatcher is the DETECTOR only — orchestrator is the sole dispatcher.
        # This prevents double-dispatch (2 claude subprocesses for 1 approval file).
        log_action(
            self.logs, "approval_validated", "ApprovalWatcher",
            source=path.name, result="info",
            details=f"Validated type={action_type} — leaving in /Approved for orchestrator dispatch",
        )
        update_dashboard(self.vault_path)
        return path

    def _schedule_linkedin_post(self, path: Path, text: str) -> Path:
        """Route a linkedin_post approval to the JitterScheduler instead of MCP.

        Extracts the post body from the approval file, schedules it for a
        randomised time within the configured posting window (default 09:00–18:00),
        enforces a 23-hour minimum gap, and moves the approval to /Done with
        status=scheduled. The orchestrator tick fires the actual Playwright post
        when the scheduled time arrives.

        Args:
            path: Path to the approval file (already in /Approved).
            text: Full file text (frontmatter + body).

        Returns:
            Path to the archived file in /Done.
        """
        content = extract_post_content(text)
        if not content:
            log_action(
                self.logs, "linkedin_schedule_error", "ApprovalWatcher",
                source=path.name, result="error",
                details="No post content found in approval file — cannot schedule",
            )
            return self._move_to_done(path, "schedule_failed_no_content")

        schedule = JitterScheduler.schedule(path, content)
        post_at   = schedule.get("post_at", "?")
        post_date = schedule.get("post_date", "?")

        log_action(
            self.logs, "linkedin_post_scheduled", "ApprovalWatcher",
            source=path.name, result="success",
            details=f"Scheduled for {post_date} at {post_at} | chars={len(content)}",
        )

        update_dashboard(self.vault_path)
        return self._move_to_done(path, "scheduled")

    def _schedule_social_post(self, path: Path, text: str, fm: dict) -> Path:
        """Route a social_post approval to the appropriate platform scheduler.

        Extracts the post body and platform from the approval file, schedules it
        for a randomised time within the configured posting window (default 09:00–18:00),
        enforces a 23-hour minimum gap per platform, and moves the approval to /Done
        with status=scheduled. The orchestrator tick fires the actual Playwright post
        when the scheduled time arrives.

        Args:
            path: Path to the approval file (already in /Approved).
            text: Full file text (frontmatter + body).
            fm: Parsed frontmatter dict.

        Returns:
            Path to the archived file in /Done.
        """
        platform = fm.get("platform", "").lower()
        if platform not in ("facebook", "instagram", "twitter"):
            log_action(
                self.logs, "social_schedule_error", "ApprovalWatcher",
                source=path.name, result="error",
                details=f"Invalid platform '{platform}'. Must be: facebook, instagram, twitter",
            )
            return self._move_to_done(path, "schedule_failed_invalid_platform")

        # Social post approvals use "## Post Content", not "## Draft Post" (LinkedIn marker).
        # extract_post_content() falls back to full body — use the correct marker instead.
        _marker = "## Post Content"
        _idx = text.find(_marker)
        content = text[_idx + len(_marker):].split("\n## ")[0].strip() if _idx != -1 else ""
        if not content:
            log_action(
                self.logs, "social_schedule_error", "ApprovalWatcher",
                source=path.name, result="error",
                details="No '## Post Content' section found in approval file — cannot schedule",
            )
            return self._move_to_done(path, "schedule_failed_no_content")

        # Move to Done/ FIRST so the scheduler stores the correct Done/ path
        done_path = self._move_to_done(path, "scheduled")

        # Route to appropriate scheduler with the Done/ path
        if platform == "facebook":
            schedule = FacebookScheduler.schedule(done_path, content)
        elif platform == "instagram":
            # Instagram requires an image — scheduler will pick from media/ folder
            schedule = InstagramScheduler.schedule(done_path, content)
        else:  # twitter
            schedule = TwitterScheduler.schedule(done_path, content)

        post_at = schedule.get("post_at", "?")
        post_date = schedule.get("post_date", "?")

        log_action(
            self.logs, f"{platform}_post_scheduled", "ApprovalWatcher",
            source=path.name, result="success",
            details=f"Scheduled for {post_date} at {post_at} | platform={platform} | chars={len(content)}",
        )

        update_dashboard(self.vault_path)
        return done_path

    def _process_rejected(self, path: Path) -> Path:
        """Log a user rejection and archive to /Done."""
        try:
            fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        except OSError:
            fm = {}

        log_action(
            self.logs, "approval_rejected", "ApprovalWatcher",
            source=path.name, result="success",
            details=f"User rejected: {fm.get('type', 'unknown')}",
        )
        done_path = self._move_to_done(path, "rejected")
        update_dashboard(self.vault_path)
        return done_path

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self, fm: dict) -> str:
        """Return an error description if frontmatter is invalid, else empty string."""
        action_type = fm.get("type", "")
        if not action_type:
            return "Missing required field: type"
        if action_type not in KNOWN_ACTION_TYPES:
            known = ", ".join(sorted(KNOWN_ACTION_TYPES))
            return f"Unknown action type '{action_type}'. Known types: {known}"
        missing = [
            field
            for field in REQUIRED_FIELDS.get(action_type, [])
            if not fm.get(field)
        ]
        if missing:
            return f"Missing required fields for '{action_type}': {missing}"
        return ""


    # ------------------------------------------------------------------
    # Expiration sweep
    # ------------------------------------------------------------------

    def _sweep_expired(self) -> None:
        """Move past-expiry files from /Pending_Approval to /Done."""
        if not self.pending_approval.exists():
            return
        now = datetime.now(timezone.utc)
        for md_file in sorted(self.pending_approval.glob("*.md")):
            try:
                text = md_file.read_text(encoding="utf-8")
                fm = _parse_frontmatter(text)
                expires_str = fm.get("expires_at", "").strip().rstrip("Z")
                if not expires_str:
                    continue
                if "+" not in expires_str and "T" in expires_str:
                    expires_str += "+00:00"
                expires_at = datetime.fromisoformat(expires_str)
                if now <= expires_at:
                    continue
                done_path = self._move_to_done(md_file, "expired")
                log_action(
                    self.logs, "approval_expired", "ApprovalWatcher",
                    source=md_file.name, result="success",
                    details=f"Expired at {fm.get('expires_at')}",
                )
            except (OSError, ValueError):
                continue

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _move_to_done(self, path: Path, final_status: str) -> Path:
        """Rewrite status, move file to /Done, return destination path.

        Uses atomic write (temp → rename) to prevent partial reads.
        Appends a timestamp suffix if the destination already exists.
        """
        if not path.exists():
            return self.done / path.name

        self.done.mkdir(parents=True, exist_ok=True)
        dest = self.done / path.name
        if dest.exists():
            ts = datetime.now(timezone.utc).strftime("%H%M%S")
            dest = self.done / f"{path.stem}_{ts}{path.suffix}"

        try:
            text = path.read_text(encoding="utf-8")
            updated = _rewrite_status(text, final_status)
            tmp = dest.with_suffix(".tmp")
            tmp.write_text(updated, encoding="utf-8")
            tmp.replace(dest)
            path.unlink(missing_ok=True)
        except OSError as e:
            self._log_error("_move_to_done", e)
            dest = path  # leave in place on failure

        return dest

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> Self:
        """Process existing files in /Approved and /Rejected, then start watchers."""
        # Process anything already sitting there before going live
        for item in self.check_for_updates():
            try:
                self.create_action_file(item)
            except Exception as e:
                self._log_error("start.create_action_file", e)

        log_action(
            self.logs, "watcher_started", "ApprovalWatcher",
            details=f"Monitoring {self.approved.name}/ and {self.rejected.name}/",
        )
        update_dashboard(self.vault_path, {"ApprovalWatcher": "Online"})

        self._observer.start()   # immediate watchdog detection
        super().start()          # polling loop (expiration sweeps + fallback)
        return self

    def stop(self) -> None:
        """Stop polling loop and watchdog observer."""
        super().stop()
        self._observer.stop()
        self._observer.join()
        log_action(
            self.logs, "watcher_stopped", "ApprovalWatcher",
            details="Shutdown complete",
        )
        update_dashboard(self.vault_path, {"ApprovalWatcher": "Offline"})
