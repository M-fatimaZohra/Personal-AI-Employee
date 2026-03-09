"""Structured JSON Lines logger for the AI Employee vault."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from the script's directory (level-silver/.env)
# This makes DRY_RUN and other settings work without manually exporting env vars.
load_dotenv(Path(__file__).parent / ".env")

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
    approval_status: str = "",
    approved_by: str = "",
    parameters: dict | None = None,
) -> dict:
    """Append a structured log entry to today's JSON Lines log file.

    Args:
        logs_path:       Directory where log files are written (AI_Employee_Vault/Logs/).
        action:          Event name, e.g. "file_processed", "gmail_email_processed".
        actor:           Component that took the action, e.g. "FilesystemWatcher".
        source:          Origin of the item (file path, email sender, etc.).
        destination:     Where the item was written or moved to.
        result:          "success" | "error" | "dry_run" | "filtered".
        details:         Free-text extra context (safe to leave empty).
        approval_status: "approved" | "rejected" | "pending" | "auto" (Gold tier HITL).
        approved_by:     Who approved the action (file path moved to /Approved/).
        parameters:      MCP tool call parameters (sanitized — no passwords/API keys).

    Returns:
        The log entry dict (useful for testing/inspection).
    """
    entry: dict = {
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
    if approval_status:
        entry["approval_status"] = approval_status
    if approved_by:
        entry["approved_by"] = approved_by
    if parameters:
        entry["parameters"] = parameters

    logs_path.mkdir(parents=True, exist_ok=True)
    log_file = logs_path / f"{datetime.now().strftime('%Y-%m-%d')}.json"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return entry
