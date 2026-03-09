"""Abstract base class for all AI Employee watchers."""

import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Self


class BaseWatcher(ABC):
    """Base class defining the watcher interface.

    All watchers monitor a vault path and create action files
    when new items are detected.

    Subclasses implement:
        - check_for_updates() → list of items to process
        - create_action_file(item) → writes markdown to Needs_Action

    The default run() / start() / stop() provide a thread-based polling loop.
    Event-driven watchers (e.g. FilesystemWatcher) override start()/stop().
    """

    VAULT_FOLDERS = [
        "Drop_Box",
        "Inbox",
        "Needs_Action",
        "Done",
        "Logs",
        # Silver tier extensions
        "Plans",
        "Pending_Approval",
        "Approved",
        "Rejected",
    ]

    def __init__(self, vault_path: str | Path, check_interval: int = 5) -> None:
        self.vault_path = Path(vault_path).resolve()
        self.check_interval = check_interval

        # Standard vault paths
        self.drop_box = self.vault_path / "Drop_Box"
        self.inbox = self.vault_path / "Inbox"
        self.needs_action = self.vault_path / "Needs_Action"
        self.done = self.vault_path / "Done"
        self.logs = self.vault_path / "Logs"
        self.plans = self.vault_path / "Plans"
        self.pending_approval = self.vault_path / "Pending_Approval"
        self.approved = self.vault_path / "Approved"
        self.rejected = self.vault_path / "Rejected"

        # Auto-create missing vault folders
        for folder in self.VAULT_FOLDERS:
            (self.vault_path / folder).mkdir(parents=True, exist_ok=True)

        # Polling loop state
        self._running: bool = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Abstract interface — subclasses must implement these two methods
    # ------------------------------------------------------------------

    @abstractmethod
    def check_for_updates(self) -> list[Any]:
        """Check the monitored source for new items.

        Returns a list of items (type depends on subclass — Path, dict, etc.)
        that should be passed to create_action_file().
        """
        ...

    @abstractmethod
    def create_action_file(self, item: Any) -> Path:
        """Create an action file in Needs_Action for a detected item.

        Should write a markdown file with YAML frontmatter and return its path.
        If the item is filtered/skipped, return the intended path without writing.
        """
        ...

    # ------------------------------------------------------------------
    # Default polling loop — used by API-based watchers (Gmail, Telegram)
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Polling loop: call check_for_updates(), create_action_file() for each result.

        Runs on a background thread (started by start()). Sleeps in 1-second
        increments so stop() can interrupt quickly.
        """
        while self._running:
            try:
                items = self.check_for_updates()
                for item in items:
                    if not self._running:
                        break
                    try:
                        self.create_action_file(item)
                    except Exception as e:
                        self._log_error("run.create_action_file", e)
            except Exception as e:
                self._log_error("run.check_for_updates", e)

            # Interruptible sleep
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)

    def _log_error(self, context: str, exc: Exception) -> None:
        """Write a minimal error entry to today's log (no external dependency)."""
        import json
        from datetime import datetime, timezone

        self.logs.mkdir(parents=True, exist_ok=True)
        log_file = self.logs / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "watcher_error",
            "actor": type(self).__name__,
            "context": context,
            "error": str(exc),
            "result": "error",
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    # ------------------------------------------------------------------
    # Default start / stop — thread-based; override for event-driven watchers
    # ------------------------------------------------------------------

    def start(self) -> Self:
        """Start the polling loop in a background daemon thread."""
        self._running = True
        self._thread = threading.Thread(
            target=self.run,
            name=type(self).__name__,
            daemon=True,
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        """Stop the polling loop and wait for the thread to finish."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.check_interval + 5)
