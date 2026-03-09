"""Filesystem watcher — monitors Drop_Box, creates action files, archives to Inbox."""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Self

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from base_watcher import BaseWatcher
from dashboard_updater import update_dashboard
from logger import DRY_RUN, log_action


class DropFolderHandler(FileSystemEventHandler):
    """Watchdog event handler that delegates new Drop_Box files to FilesystemWatcher."""

    def __init__(self, watcher: "FilesystemWatcher") -> None:
        super().__init__()
        self.watcher = watcher

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        # Small delay so the file finishes writing before we process it
        time.sleep(0.5)
        source = Path(event.src_path)
        if source.exists():
            self.watcher.create_action_file(source)


class FilesystemWatcher(BaseWatcher):
    """Monitors Drop_Box for new files.

    Pipeline per file:
        1. Detect file dropped in Drop_Box (via watchdog event)
        2. Read content (text) or note binary
        3. Create FILE_<stem>.md action file in Needs_Action with YAML frontmatter
        4. Move original file to Inbox/ (archive — preserves access to original)
        5. Log action and update Dashboard.md

    Silver-tier change vs Bronze:
        Files are moved to Inbox/ instead of deleted, so the user retains
        the original while the action file drives the workflow.
    """

    def __init__(self, vault_path: str | Path, check_interval: int = 5) -> None:
        super().__init__(vault_path, check_interval)
        self._observer = Observer()
        self._handler = DropFolderHandler(self)

    # ------------------------------------------------------------------
    # BaseWatcher interface
    # ------------------------------------------------------------------

    def check_for_updates(self) -> list[Any]:
        """Return files already sitting in Drop_Box on startup."""
        if not self.drop_box.exists():
            return []
        return [f for f in self.drop_box.iterdir() if f.is_file()]

    def _unique_dest(self, stem: str, folder: Path) -> Path:
        """Return a unique filename in the given folder (no overwrites)."""
        dest = folder / f"FILE_{stem}.md"
        if not dest.exists():
            return dest
        counter = 2
        while True:
            dest = folder / f"FILE_{stem}_{counter}.md"
            if not dest.exists():
                return dest
            counter += 1

    def create_action_file(self, item: Any) -> Path:
        """Create a FILE_*.md action file in Needs_Action; move original to Inbox.

        Args:
            item: Path to the file dropped in Drop_Box.

        Returns:
            Path to the action file written in Needs_Action.
        """
        item = Path(item)
        now = datetime.now(timezone.utc).isoformat()
        stem = item.stem
        dest = self._unique_dest(stem, self.needs_action)
        inbox_dest = self.inbox / item.name

        # Detect text vs binary
        try:
            body = item.read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            body = f"[Binary file: {item.name}]"

        frontmatter = (
            f"---\n"
            f"type: file_drop\n"
            f"original_name: {item.name}\n"
            f"dropped_at: {now}\n"
            f"inbox_path: Inbox/{item.name}\n"
            f"status: needs_action\n"
            f"priority: normal\n"
            f"source: Drop_Box\n"
            f"processed_by: null\n"
            f"---\n\n"
        )

        if DRY_RUN:
            log_action(
                self.logs, "file_processed", "FilesystemWatcher",
                source=str(item),
                destination=str(dest),
                result="dry_run",
                details="Would create action file and move original to Inbox",
            )
            return dest

        # Write action file to Needs_Action
        dest.write_text(frontmatter + body, encoding="utf-8")

        # Move original to Inbox (archive — not deleted)
        try:
            if inbox_dest.exists():
                # Avoid overwriting an existing file in Inbox
                ts = datetime.now(timezone.utc).strftime("%H%M%S")
                inbox_dest = self.inbox / f"{item.stem}_{ts}{item.suffix}"
            item.rename(inbox_dest)
        except OSError as e:
            log_action(
                self.logs, "file_inbox_move_error", "FilesystemWatcher",
                source=str(item),
                destination=str(inbox_dest),
                result="error",
                details=str(e),
            )

        log_action(
            self.logs, "file_processed", "FilesystemWatcher",
            source=f"Drop_Box/{item.name}",
            destination=dest.name,
            result="success",
            details=f"Original archived to Inbox/{inbox_dest.name}",
        )
        update_dashboard(self.vault_path, {"FilesystemWatcher": "Online"})

        return dest

    # ------------------------------------------------------------------
    # Lifecycle — event-driven (watchdog), not polling
    # ------------------------------------------------------------------

    def start(self) -> Self:
        """Process any files already in Drop_Box, then start watchdog observer."""
        for f in self.check_for_updates():
            try:
                self.create_action_file(f)
            except Exception as e:
                log_action(
                    self.logs, "file_error", "FilesystemWatcher",
                    source=str(f),
                    result="error",
                    details=str(e),
                )

        log_action(
            self.logs, "watcher_started", "FilesystemWatcher",
            details=f"Monitoring {self.drop_box}",
        )
        update_dashboard(self.vault_path, {"FilesystemWatcher": "Online"})

        self._observer.schedule(self._handler, str(self.drop_box), recursive=False)
        self._observer.start()
        return self

    def stop(self) -> None:
        """Stop the watchdog observer."""
        self._observer.stop()
        self._observer.join()
        log_action(
            self.logs, "watcher_stopped", "FilesystemWatcher",
            details="Shutdown complete",
        )
        update_dashboard(self.vault_path, {"FilesystemWatcher": "Offline"})
