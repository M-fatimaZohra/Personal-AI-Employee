"""Abstract base class for all AI Employee watchers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Self


class BaseWatcher(ABC):
    """Base class defining the watcher interface.

    All watchers monitor a vault path and create action files
    when new items are detected.
    """

    VAULT_FOLDERS = ["Drop_Box", "Inbox", "Needs_Action", "Done", "Logs"]

    def __init__(self, vault_path: str | Path, check_interval: int = 5) -> None:
        self.vault_path = Path(vault_path).resolve()
        self.check_interval = check_interval

        # Standard vault paths
        self.drop_box = self.vault_path / "Drop_Box"
        self.inbox = self.vault_path / "Inbox"
        self.needs_action = self.vault_path / "Needs_Action"
        self.done = self.vault_path / "Done"
        self.logs = self.vault_path / "Logs"

        # Auto-create missing vault folders
        for folder in self.VAULT_FOLDERS:
            (self.vault_path / folder).mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def check_for_updates(self) -> list[Path]:
        """Check the monitored source for new items."""
        ...

    @abstractmethod
    def create_action_file(self, item: Path) -> Path:
        """Create an action file in Needs_Action for a detected item."""
        ...

    @abstractmethod
    def start(self) -> Self:
        """Start monitoring. Returns self for chaining."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop monitoring and clean up."""
        ...
