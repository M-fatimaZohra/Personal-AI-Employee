"""orchestrator.py — Platinum Tier Cloud Agent (Draft-Only Mode)

Cloud Agent Responsibilities:
    1. Gmail monitoring    — poll Gmail API every 2 minutes for important emails
    2. Draft creation      — triage emails and draft replies (NEVER send)
    3. Claim-by-move       — atomically claim files from Needs_Action/ to In_Progress/cloud/
    4. Status reporting    — write cloud agent status to Updates/cloud_status.md
    5. Heartbeat loop      — tick every 10 seconds, scan for new items
    6. Graceful shutdown   — SIGINT/SIGTERM stop all watchers cleanly

CRITICAL SECURITY CONSTRAINT:
    This orchestrator runs in DRAFT-ONLY mode. It MUST NEVER execute any
    irreversible action (send email, post to social media, create invoice, etc.).
    All execution happens on the Local Agent only.

Usage:
    uv run python orchestrator.py

For production (via PM2):
    pm2 start ecosystem.config.cjs
"""

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add shared utilities to path
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from logger import log_action

# On Windows, claude is installed as claude.CMD (batch file) requiring shell
_WIN32 = sys.platform == "win32"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VAULT_PATH = Path(__file__).parent.parent / "AI_Employee_Vault"
HEARTBEAT_INTERVAL = 10  # seconds between ticks

# Maps Needs_Action filename prefix → Claude skill name
SKILL_ROUTING: dict[str, str] = {
    "EMAIL_": "fte-gmail-triage",
}

# ---------------------------------------------------------------------------
# Cloud Orchestrator (Draft-Only)
# ---------------------------------------------------------------------------

class CloudOrchestrator:
    """Cloud Agent orchestrator — monitors Gmail, drafts replies, never executes."""

    def __init__(
        self,
        vault_path: str | Path = VAULT_PATH,
        heartbeat: int = HEARTBEAT_INTERVAL,
    ) -> None:
        # Validate draft-only mode
        if os.getenv("CLOUD_DRAFT_ONLY") != "true":
            raise RuntimeError(
                "SECURITY: Cloud orchestrator requires CLOUD_DRAFT_ONLY=true in .env\n"
                "This prevents accidental execution of irreversible actions on the cloud agent."
            )

        self.vault_path = Path(vault_path).resolve()
        self.heartbeat = heartbeat
        self.needs_action = self.vault_path / "Needs_Action"
        self.in_progress_cloud = self.vault_path / "In_Progress" / "cloud"
        self.in_progress_local = self.vault_path / "In_Progress" / "local"
        self.updates = self.vault_path / "Updates"
        self.logs = self.vault_path / "Logs"

        # Ensure directories exist
        self.needs_action.mkdir(parents=True, exist_ok=True)
        self.in_progress_cloud.mkdir(parents=True, exist_ok=True)
        self.updates.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)

        self._watchers: list = []
        self._running: bool = False
        self._tick_count: int = 0

        # Thread-safe tracking of files currently being processed
        self._lock = threading.Lock()
        self._in_flight: set[str] = set()

        # Subprocesses spawned for claude skill invocations
        self._subprocesses: list[subprocess.Popen] = []

    # ------------------------------------------------------------------
    # Claude CLI validation
    # ------------------------------------------------------------------

    def validate_claude(self) -> bool:
        """Return True if ccr (Claude Code Router) is reachable on PATH."""
        try:
            # Strip PM2 IPC vars — NODE_CHANNEL_FD causes Node.js subprocesses
            # to abort (SIGABRT) when inherited from a PM2-managed process.
            env = os.environ.copy()
            env.pop("NODE_CHANNEL_FD", None)
            env.pop("NODE_CHANNEL_SERIALIZATION_MODE", None)
            result = subprocess.run(
                ["ccr", "-v"],
                capture_output=True,
                text=True,
                timeout=10,
                shell=_WIN32,
                env=env,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    # ------------------------------------------------------------------
    # Watcher lifecycle
    # ------------------------------------------------------------------

    def initialize_watchers(self) -> None:
        """Initialize only Gmail watcher for cloud agent."""
        print("\n[orchestrator] Initializing Cloud Agent watchers (draft-only mode)...")
        print("[orchestrator] Mode: CLOUD_DRAFT_ONLY=true ✓")

        # Gmail watcher — the ONLY watcher on cloud agent
        creds_path = Path(__file__).parent.parent / ".secrets" / "gmail_credentials.json"
        if creds_path.exists():
            try:
                from gmail_watcher import GmailWatcher
                self._watchers.append(GmailWatcher(self.vault_path))
                print("[orchestrator] GmailWatcher:       enabled")
            except Exception as exc:
                print(f"[orchestrator] GmailWatcher:       SKIPPED — {exc}")
        else:
            print(
                f"[orchestrator] GmailWatcher:       SKIPPED "
                f"(place gmail_credentials.json in {creds_path.parent})"
            )

        print(f"[orchestrator] Total watchers:     {len(self._watchers)}")
        print("[orchestrator] Social media:       DISABLED (local agent only)")
        print("[orchestrator] WhatsApp:           DISABLED (local agent only)")
        print("[orchestrator] Execution:          DISABLED (draft-only mode)")

    def start_watchers(self) -> None:
        """Start all watcher threads."""
        for w in self._watchers:
            w.start()
            print(f"[orchestrator] Started: {w.__class__.__name__}")

    def stop_watchers(self) -> None:
        """Stop all watcher threads."""
        for w in self._watchers:
            try:
                w.stop()
            except Exception as e:
                print(f"[orchestrator] Warning: error stopping {w.__class__.__name__}: {e}")

    # ------------------------------------------------------------------
    # Claim-by-move (atomic file claiming)
    # ------------------------------------------------------------------

    def try_claim_file(self, filepath: Path) -> bool:
        """Atomically claim a file from Needs_Action/ to In_Progress/cloud/.

        Returns True if this agent successfully claimed the file.
        Returns False if another agent claimed it first (file disappeared).
        """
        # Preserve domain subdirectory (e.g. email/, social/, odoo/)
        domain = filepath.parent.name  # e.g. "email"
        dest_dir = self.in_progress_cloud / domain
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filepath.name

        try:
            # os.rename() is atomic on POSIX — only one agent succeeds
            filepath.rename(dest)
            log_action(
                self.logs,
                "file_claimed",
                "CloudOrchestrator",
                source=filepath.name,
                destination=f"In_Progress/cloud/{domain}/{filepath.name}",
                result="success",
            )
            return True
        except FileNotFoundError:
            # File already claimed by local agent
            return False
        except Exception as e:
            log_action(
                self.logs,
                "claim_failed",
                "CloudOrchestrator",
                source=filepath.name,
                result="error",
                details=str(e),
            )
            return False

    def is_claimed_by_local(self, filename: str) -> bool:
        """Check if a file is already claimed by the local agent."""
        return (self.in_progress_local / filename).exists()

    # ------------------------------------------------------------------
    # Skill dispatch
    # ------------------------------------------------------------------

    def dispatch_skill(self, skill_name: str, filepath: Path) -> None:
        """Invoke a Claude skill on a claimed file."""
        if not getattr(self, "_claude_available", True):
            print(f"[orchestrator] Skipping dispatch — claude CLI unavailable ({filepath.name})")
            return

        with self._lock:
            if filepath.name in self._in_flight:
                return
            self._in_flight.add(filepath.name)

        try:
            # Build command — use ccr code with --dangerously-skip-permissions for
            # automated dispatch (no TTY available in PM2 subprocess context)
            cmd = ["ccr", "code", "--dangerously-skip-permissions", "-p", f"/{skill_name}", str(filepath)]

            # Set environment — strip PM2 IPC vars to prevent Node.js SIGABRT
            env = os.environ.copy()
            env.pop("NODE_CHANNEL_FD", None)
            env.pop("NODE_CHANNEL_SERIALIZATION_MODE", None)
            env["FTE_AUTOMATED_DISPATCH"] = "1"

            print(f"[orchestrator] Dispatching /{skill_name} for {filepath.name}")

            # Spawn subprocess
            proc = subprocess.Popen(
                cmd,
                env=env,
                shell=_WIN32,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self._subprocesses.append(proc)

            # Wait for completion (with timeout)
            try:
                proc.wait(timeout=300)
                if proc.returncode == 0:
                    log_action(
                        self.logs,
                        "skill_dispatched",
                        "CloudOrchestrator",
                        source=filepath.name,
                        result="success",
                        details=f"skill={skill_name}",
                    )
                else:
                    log_action(
                        self.logs,
                        "skill_failed",
                        "CloudOrchestrator",
                        source=filepath.name,
                        result="error",
                        details=f"skill={skill_name} exit_code={proc.returncode}",
                    )
            except subprocess.TimeoutExpired:
                proc.kill()
                log_action(
                    self.logs,
                    "skill_timeout",
                    "CloudOrchestrator",
                    source=filepath.name,
                    result="error",
                    details=f"skill={skill_name} timeout=300s",
                )

        finally:
            with self._lock:
                self._in_flight.discard(filepath.name)

    # ------------------------------------------------------------------
    # Heartbeat loop
    # ------------------------------------------------------------------

    def scan_needs_action(self) -> None:
        """Scan Needs_Action/ for new files and dispatch skills."""
        if not self.needs_action.exists():
            return

        # Platinum Tier — scan domain subdirectories recursively
        for filepath in sorted(self.needs_action.glob("**/*.md")):
            if not filepath.is_file():
                continue

            # Skip if already in flight
            with self._lock:
                if filepath.name in self._in_flight:
                    continue

            # Skip if local agent already claimed it
            if self.is_claimed_by_local(filepath.name):
                continue

            # If claude unavailable, leave file in Needs_Action for local agent
            if not getattr(self, "_claude_available", True):
                continue

            # Try to claim the file
            if not self.try_claim_file(filepath):
                # Another agent claimed it first
                continue

            # File is now in In_Progress/cloud/<domain>/ — dispatch skill
            claimed_path = self.in_progress_cloud / filepath.parent.name / filepath.name

            # Find matching skill
            skill_name = None
            for prefix, skill in SKILL_ROUTING.items():
                if filepath.name.startswith(prefix):
                    skill_name = skill
                    break

            if skill_name:
                # Dispatch in background thread
                thread = threading.Thread(
                    target=self.dispatch_skill,
                    args=(skill_name, claimed_path),
                    daemon=True,
                )
                thread.start()
            else:
                # No skill found — log and skip
                log_action(
                    self.logs,
                    "no_skill_match",
                    "CloudOrchestrator",
                    source=filepath.name,
                    result="skipped",
                )

    def update_cloud_status(self) -> None:
        """Write cloud agent status to Updates/cloud_status.md."""
        status_file = self.updates / "cloud_status.md"

        # Count files in various directories (recursive for domain subdirectories)
        needs_action_count = len(list(self.needs_action.glob("**/*.md"))) if self.needs_action.exists() else 0
        in_progress_count = len(list(self.in_progress_cloud.glob("**/*.md"))) if self.in_progress_cloud.exists() else 0

        # Get Gmail watcher status
        gmail_status = "online" if len(self._watchers) > 0 else "offline"

        # Build status content
        content = f"""---
agent: cloud
last_updated: {datetime.now(timezone.utc).isoformat()}
gmail_status: {gmail_status}
needs_action_count: {needs_action_count}
in_progress_count: {in_progress_count}
tick_count: {self._tick_count}
---

# Cloud Agent Status

**Last Updated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

## Watchers
- Gmail: {gmail_status}

## File Counts
- Needs_Action: {needs_action_count}
- In_Progress/cloud: {in_progress_count}

## Heartbeat
- Tick count: {self._tick_count}
- Interval: {self.heartbeat}s

---
*This file is auto-generated by the Cloud Agent. The Local Agent merges it into Dashboard.md.*
"""

        # Atomic write (temp file + rename)
        temp_file = status_file.with_suffix(".tmp")
        temp_file.write_text(content, encoding="utf-8")
        temp_file.rename(status_file)

    def heartbeat_loop(self) -> None:
        """Main heartbeat loop — runs every HEARTBEAT_INTERVAL seconds."""
        print(f"\n[orchestrator] Heartbeat loop started (interval: {self.heartbeat}s)")

        while self._running:
            self._tick_count += 1

            try:
                # Scan for new items in Needs_Action/
                self.scan_needs_action()

                # Update cloud status
                self.update_cloud_status()

            except Exception as e:
                print(f"[orchestrator] Heartbeat error: {e}")
                log_action(
                    self.logs,
                    "heartbeat_error",
                    "CloudOrchestrator",
                    result="error",
                    details=str(e),
                )

            # Sleep until next tick
            time.sleep(self.heartbeat)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the cloud orchestrator and block in the heartbeat loop."""
        print("\n" + "=" * 60)
        print("Platinum Tier — Cloud Agent (Draft-Only Mode)")
        print("=" * 60)

        # Validate Claude CLI (warning only — Gmail watcher runs without it)
        if not self.validate_claude():
            print("\n[orchestrator] WARNING: claude CLI not found on PATH")
            print("[orchestrator] Skill dispatch disabled. Gmail watching still active.")
            print("[orchestrator] Install: https://github.com/anthropics/claude-code")
            self._claude_available = False
        else:
            print("[orchestrator] Claude CLI:         ✓")
            self._claude_available = True

        # Initialize watchers
        self.initialize_watchers()

        # Start watchers
        self.start_watchers()

        # Set running flag
        self._running = True

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        print("\n[orchestrator] Cloud Agent is running...")
        print("[orchestrator] Press Ctrl+C to stop\n")

        # Enter heartbeat loop (blocks here)
        try:
            self.heartbeat_loop()
        except KeyboardInterrupt:
            print("\n[orchestrator] Keyboard interrupt received")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop all watchers and subprocesses."""
        print("\n[orchestrator] Shutting down...")

        self._running = False

        # Stop watchers
        self.stop_watchers()

        # Terminate subprocesses
        for proc in self._subprocesses:
            if proc.poll() is None:  # Still running
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

        print("[orchestrator] Shutdown complete")

    def _signal_handler(self, signum, frame) -> None:
        """Handle SIGINT/SIGTERM."""
        print(f"\n[orchestrator] Received signal {signum}")
        self.stop()
        sys.exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    orchestrator = CloudOrchestrator()
    orchestrator.run()
