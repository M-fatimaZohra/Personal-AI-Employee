"""Structured JSON Lines logger for the AI Employee vault."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


DRY_RUN = os.getenv("DRY_RUN", "").lower() == "true"


def log_action(
    logs_path: Path,
    action: str,
    actor: str,
    *,
    source: str = "",
    destination: str = "",
    result: str = "success",
    details: str = "",
) -> dict:
    """Append a structured log entry to today's log file.

    Returns the log entry dict for testing/inspection.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "actor": actor,
        "source": source,
        "destination": destination,
        "result": result,
    }
    if DRY_RUN:
        entry["dry_run"] = True
    if details:
        entry["details"] = details

    logs_path.mkdir(parents=True, exist_ok=True)
    log_file = logs_path / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return entry
