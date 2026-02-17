"""Filesystem watcher — monitors Drop_Box and creates action files."""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Self

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from base_watcher import BaseWatcher
from dashboard_updater import update_dashboard
from logger import DRY_RUN, log_action


class DropFolderHandler(FileSystemEventHandler):
    """Watchdog handler that delegates to the FilesystemWatcher."""

    def __init__(self, watcher: "FilesystemWatcher") -> None:
        super().__init__()
        self.watcher = watcher

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        # Small delay to let the file finish writing
        time.sleep(0.5)
        source = Path(event.src_path)
        if source.exists():
            self.watcher.create_action_file(source)


class FilesystemWatcher(BaseWatcher):
    """Monitors Drop_Box for new files, creates action files in Needs_Action."""

    def __init__(self, vault_path: str | Path, check_interval: int = 5) -> None:
        super().__init__(vault_path, check_interval)
        self._observer = Observer()
        self._handler = DropFolderHandler(self)

    def check_for_updates(self) -> list[Path]:
        """Check Drop_Box for existing files (on startup)."""
        if not self.drop_box.exists():
            return []
        return [f for f in self.drop_box.iterdir() if f.is_file()]

    def _unique_dest(self, stem: str) -> Path:
        """Generate a unique filename in Needs_Action to avoid overwrites."""
        dest = self.needs_action / f"FILE_{stem}.md"
        if not dest.exists():
            return dest
        counter = 2
        while True:
            dest = self.needs_action / f"FILE_{stem}_{counter}.md"
            if not dest.exists():
                return dest
            counter += 1

    def create_action_file(self, item: Path) -> Path:
        """Create an action file with YAML frontmatter in Needs_Action."""
        now = datetime.now(timezone.utc).isoformat()
        stem = item.stem
        dest = self._unique_dest(stem)

        # Determine if file is text or binary
        try:
            body = item.read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            body = f"[Binary file: {item.name}]"

        frontmatter = (
            f"---\n"
            f"type: file_drop\n"
            f"original_name: {item.name}\n"
            f"dropped_at: {now}\n"
            f"status: needs_action\n"
            f"priority: normal\n"
            f"source: Drop_Box\n"
            f"processed_by: null\n"
            f"---\n\n"
        )

        if DRY_RUN:
            log_action(
                self.logs, "file_processed", "FilesystemWatcher",
                source=str(item), destination=str(dest),
                result="dry_run", details="Would create action file",
            )
            return dest

        dest.write_text(frontmatter + body, encoding="utf-8")

        # Remove original from Drop_Box after processing
        try:
            item.unlink()
        except OSError:
            pass

        log_action(
            self.logs, "file_processed", "FilesystemWatcher",
            source=f"Drop_Box/{item.name}", destination=str(dest.name),
            result="success",
        )

        # Update dashboard
        update_dashboard(self.vault_path, {"FilesystemWatcher": "Online"})

        return dest

    def start(self) -> Self:
        """Process existing files, then start watchdog observer."""
        # Process any files already in Drop_Box
        existing = self.check_for_updates()
        for f in existing:
            try:
                self.create_action_file(f)
            except Exception as e:
                log_action(
                    self.logs, "file_error", "FilesystemWatcher",
                    source=str(f), result="error", details=str(e),
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
