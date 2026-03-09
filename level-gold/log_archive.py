"""log_archive.py — Move log files older than 90 days to AI_Employee_Vault/Logs/Archive/.

Usage (run manually or via Task Scheduler):
    uv run python log_archive.py [--vault <path>] [--days <N>] [--dry-run]

Defaults:
    --vault  level-gold/AI_Employee_Vault
    --days   90
"""

import argparse
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path


def archive_old_logs(
    vault_path: str | Path,
    retention_days: int = 90,
    dry_run: bool = False,
) -> dict:
    """Move log files older than *retention_days* to Logs/Archive/.

    Only touches daily log files matching the pattern YYYY-MM-DD.json.
    orchestrator.log and other non-date files are left untouched.

    Args:
        vault_path:      Path to AI_Employee_Vault directory.
        retention_days:  Files older than this many days are archived.
        dry_run:         If True, print what would be moved without moving.

    Returns:
        dict with keys: archived (list of filenames), skipped (int), errors (list).
    """
    vault = Path(vault_path)
    logs_dir = vault / "Logs"
    archive_dir = logs_dir / "Archive"

    if not logs_dir.exists():
        print(f"[log_archive] Logs directory not found: {logs_dir}")
        return {"archived": [], "skipped": 0, "errors": []}

    if not dry_run:
        archive_dir.mkdir(parents=True, exist_ok=True)

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    archived: list[str] = []
    skipped: int = 0
    errors: list[str] = []

    for log_file in sorted(logs_dir.glob("*.json")):
        if not log_file.is_file():
            continue

        # Only archive date-named daily logs (YYYY-MM-DD.json)
        stem = log_file.stem
        try:
            file_date = datetime.strptime(stem, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            skipped += 1
            continue  # orchestrator.log or other non-date files — skip

        if file_date >= cutoff:
            skipped += 1
            continue  # within retention window — keep

        dest = archive_dir / log_file.name
        if dry_run:
            print(f"[log_archive] DRY_RUN — would archive: {log_file.name} (age: {(datetime.now(timezone.utc) - file_date).days}d)")
            archived.append(log_file.name)
        else:
            try:
                shutil.move(str(log_file), str(dest))
                print(f"[log_archive] Archived: {log_file.name} -> Archive/{log_file.name}")
                archived.append(log_file.name)
            except OSError as exc:
                msg = f"{log_file.name}: {exc}"
                print(f"[log_archive] ERROR: {msg}")
                errors.append(msg)

    # Write a summary entry to the current day's log
    if not dry_run and archived:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        summary_log = logs_dir / f"{today}.json"
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "log_archive",
            "actor": "log_archive",
            "result": "success",
            "details": f"Archived {len(archived)} file(s) older than {retention_days} days: {', '.join(archived[:5])}{'...' if len(archived) > 5 else ''}",
        }
        with open(summary_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return {"archived": archived, "skipped": skipped, "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive log files older than N days.")
    parser.add_argument(
        "--vault",
        default=str(Path(__file__).parent / "AI_Employee_Vault"),
        help="Path to AI_Employee_Vault (default: ./AI_Employee_Vault)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Retention period in days (default: 90)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be archived without moving any files",
    )
    args = parser.parse_args()

    print(f"[log_archive] Vault: {args.vault}")
    print(f"[log_archive] Retention: {args.days} days")
    if args.dry_run:
        print("[log_archive] DRY_RUN mode — no files will be moved")

    result = archive_old_logs(args.vault, args.days, args.dry_run)

    print(
        f"[log_archive] Done — archived: {len(result['archived'])}, "
        f"skipped: {result['skipped']}, errors: {len(result['errors'])}"
    )
    if result["errors"]:
        for err in result["errors"]:
            print(f"[log_archive]   ERROR: {err}")


if __name__ == "__main__":
    main()
