"""Persistent ID tracker — prevents reprocessing of seen messages/files.

Usage:
    tracker = IDTracker(vault_path / ".state")
    if not tracker.is_processed("gmail", message_id):
        tracker.mark_processed("gmail", message_id)
        # ... process message ...
"""

import json
from pathlib import Path

_CAP = 1_000  # maximum stored IDs per category (prevents file bloat)


class IDTracker:
    """Manages a JSON file in a .state/ directory with category-based ID lists.

    Each category (e.g. "gmail", "telegram", "filesystem") holds up to _CAP
    unique string IDs.  On construction the file is loaded; on every write the
    file is atomically replaced so partial-write corruption cannot occur.

    Args:
        state_dir: Directory that will hold ``processed_ids.json``.
                   Created automatically if it does not exist.
    """

    def __init__(self, state_dir: str | Path) -> None:
        self._state_dir = Path(state_dir)
        self._path = self._state_dir / "processed_ids.json"
        self._data: dict[str, list[str]] = self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, list[str]]:
        """Load state from disk.  Returns empty dict on missing or corrupt file."""
        if not self._path.exists():
            return {}
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return {}
            # Validate structure: only keep categories that are lists
            return {k: list(v) for k, v in data.items() if isinstance(v, list)}
        except (json.JSONDecodeError, OSError, ValueError):
            return {}

    def _save(self) -> None:
        """Atomically persist state to disk."""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self._path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_processed(self, category: str, id: str) -> bool:
        """Return True if *id* has already been marked in *category*."""
        return id in self._data.get(category, [])

    def mark_processed(self, category: str, id: str) -> None:
        """Record *id* in *category* and persist to disk.

        Skips write if *id* is already present.  Enforces the _CAP limit by
        dropping the oldest entries when the list exceeds capacity.
        """
        bucket = self._data.setdefault(category, [])
        if id in bucket:
            return  # already tracked — no write needed
        bucket.append(id)
        if len(bucket) > _CAP:
            # Drop oldest entries to stay within cap
            self._data[category] = bucket[-_CAP:]
        self._save()

    def categories(self) -> list[str]:
        """Return list of known categories (useful for introspection/tests)."""
        return list(self._data.keys())

    def count(self, category: str) -> int:
        """Return number of tracked IDs in *category* (0 if unknown)."""
        return len(self._data.get(category, []))
