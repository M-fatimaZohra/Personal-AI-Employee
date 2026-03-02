"""orchestrator.py — Silver Tier AI Employee central execution engine.

Responsibilities:
    1. Watcher lifecycle   — initialise and manage all watchers in threads.
    2. Heartbeat loop      — tick every HEARTBEAT_INTERVAL seconds.
    3. Autonomous dispatch — on each tick, scan /Needs_Action for new files
                             and invoke the correct Claude skill automatically.
    4. Plan awareness      — detect active Plan files with unchecked steps
                             and re-prompt Claude to continue (Ralph Wiggum).
    5. Dashboard sync      — call update_dashboard() on every tick so the
                             Obsidian UI always reflects live state.
    6. Graceful shutdown   — SIGINT / SIGTERM stop all watchers + subprocesses.

Typical usage (via PM2 or directly):
    uv run python orchestrator.py

For production, prefer starting via PM2 using ecosystem.config.js which
manages automatic restart, log aggregation, and reboot persistence:
    pm2 start ecosystem.config.js
"""

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from dashboard_updater import update_dashboard
from linkedin_poster import JitterScheduler, post_to_linkedin
from logger import log_action

# On Windows, claude is installed as claude.CMD (a batch file) which cannot be
# executed directly by CreateProcess — it requires the shell to launch it.
_WIN32 = sys.platform == "win32"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VAULT_PATH = Path(__file__).parent / "AI_Employee_Vault"
HEARTBEAT_INTERVAL = 10  # seconds between ticks (user can override via env)
SKILL_DISPATCH_TIMEOUT = 300  # seconds before a claude subprocess is terminated

# Maps Needs_Action filename prefix → Claude skill name
SKILL_ROUTING: dict[str, str] = {
    "EMAIL_":          "fte-gmail-triage",
    "WHATSAPP_":       "fte-whatsapp-reply",   # WhatsApp messages → Categorizer-Responder
    "LINKEDIN_NOTIF_": "fte-triage",          # LinkedIn notifications → general triage
    "FILE_":           "fte-triage",
}

# Plans skill — invoked when an active plan has unchecked steps
PLAN_SKILL = "fte-plan"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    """Central execution engine for the Silver Tier AI Employee.

    All watcher threads and skill subprocesses are owned by this object.
    Call start() to launch everything, run() to block in the heartbeat loop,
    and stop() (or send SIGINT/SIGTERM) to shut down cleanly.
    """

    def __init__(
        self,
        vault_path: str | Path = VAULT_PATH,
        heartbeat: int = HEARTBEAT_INTERVAL,
    ) -> None:
        self.vault_path = Path(vault_path).resolve()
        self.heartbeat = heartbeat
        self.needs_action = self.vault_path / "Needs_Action"
        self.plans = self.vault_path / "Plans"
        self.logs = self.vault_path / "Logs"

        self.approved = self.vault_path / "Approved"
        self._tick_count: int = 0

        self._watchers: list = []
        self._running: bool = False

        # Thread-safe tracking of filenames currently dispatched to Claude
        self._lock = threading.Lock()
        self._in_flight: set[str] = set()

        # Subprocesses spawned for claude skill invocations
        self._subprocesses: list[subprocess.Popen] = []

    # ------------------------------------------------------------------
    # Claude CLI validation
    # ------------------------------------------------------------------

    def validate_claude(self) -> bool:
        """Return True if the ``claude`` CLI is reachable on PATH."""
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                shell=_WIN32,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    # ------------------------------------------------------------------
    # Watcher lifecycle
    # ------------------------------------------------------------------

    def init_watchers(self) -> None:
        """Initialise all available watchers and start them in daemon threads."""
        from approval_watcher import ApprovalWatcher
        from filesystem_watcher import FilesystemWatcher

        # Always-on watchers
        self._watchers.append(FilesystemWatcher(self.vault_path))
        self._watchers.append(ApprovalWatcher(self.vault_path))
        print("[orchestrator] FilesystemWatcher: enabled")
        print("[orchestrator] ApprovalWatcher:   enabled")

        # Gmail watcher — requires OAuth credentials
        creds_path = Path(__file__).parent / ".secrets" / "gmail_credentials.json"
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

        # Telegram watcher — REMOVED (replaced by WhatsApp + LinkedIn per hackathon requirements)
        # Telegram was originally planned but dropped in favor of WhatsApp/LinkedIn implementation

        # WhatsApp watcher — managed by PM2 as a separate Node.js process (Baileys).
        # whatsapp_watcher.js handles receive + send via WebSocket — no browser, no CDP.
        # Python does NOT import or start WhatsAppWatcher; PM2 owns this process entirely.
        wa_session = Path(__file__).parent / ".secrets" / "whatsapp_session"
        if wa_session.exists() and any(wa_session.iterdir()):
            print("[orchestrator] WhatsAppWatcher:    Online (Baileys Node.js — managed by PM2)")
        else:
            print(
                "[orchestrator] WhatsAppWatcher:    SKIPPED "
                "(no session — run: node whatsapp_watcher.js --setup)"
            )

        # LinkedIn watcher — requires LI_SESSION_PATH with a valid Playwright session
        li_session = Path(__file__).parent / ".secrets" / "linkedin_session"
        if li_session.exists() and any(li_session.iterdir()):
            try:
                from linkedin_watcher import LinkedInWatcher
                self._watchers.append(LinkedInWatcher(self.vault_path))
                print("[orchestrator] LinkedInWatcher:    enabled")
            except Exception as exc:
                print(f"[orchestrator] LinkedInWatcher:    SKIPPED — {exc}")
        else:
            print(
                "[orchestrator] LinkedInWatcher:    SKIPPED "
                "(no session found — run: uv run python linkedin_watcher.py --setup)"
            )

        # Start them all
        for watcher in self._watchers:
            watcher.start()

        # Real-time Needs_Action watcher — fires immediately on new file, no tick delay
        self._start_needs_action_observer()

    # ------------------------------------------------------------------
    # Real-time filesystem observers (instant dispatch, no tick delay)
    # ------------------------------------------------------------------

    def _start_needs_action_observer(self) -> None:
        """Start watchdog observers for instant file detection.

        Per Decision 7 in plan.md: the orchestrator uses watchdog to monitor
        /Needs_Action and dispatches skills on-demand. The tick loop is a
        safety net only; this observer is the primary dispatch mechanism.

        Watches two folders:
          - /Needs_Action      → new .md file → _dispatch() immediately
          - /Pending_Approval  → new .md file → sync_dashboard() so Obsidian
                                               shows the HITL queue instantly
        """
        orch = self

        class _NeedsActionHandler(FileSystemEventHandler):
            def on_created(self, event):
                if event.is_directory or not event.src_path.endswith(".md"):
                    return
                filepath = Path(event.src_path)
                skill = orch.skill_for(filepath.name)
                if skill is None:
                    return
                time.sleep(0.3)  # brief settle — let writer flush the file
                if orch._already_processed(filepath):
                    return
                orch._dispatch(filepath, f"/{skill} {filepath.name}")

        class _PendingApprovalHandler(FileSystemEventHandler):
            def on_created(self, event):
                if event.is_directory or not event.src_path.endswith(".md"):
                    return
                try:
                    orch.sync_dashboard()
                except Exception:
                    pass

        self.needs_action.mkdir(parents=True, exist_ok=True)
        pending_approval = self.vault_path / "Pending_Approval"
        pending_approval.mkdir(parents=True, exist_ok=True)

        observer = Observer()
        observer.schedule(_NeedsActionHandler(), str(self.needs_action), recursive=False)
        observer.schedule(_PendingApprovalHandler(), str(pending_approval), recursive=False)
        observer.daemon = True
        observer.start()
        print("[orchestrator] RealTimeWatcher:    enabled (Needs_Action + Pending_Approval)")

    # ------------------------------------------------------------------
    # Skill routing
    # ------------------------------------------------------------------

    def skill_for(self, filename: str) -> Optional[str]:
        """Return the Claude skill name for *filename*, or ``None`` if unknown."""
        for prefix, skill in SKILL_ROUTING.items():
            if filename.startswith(prefix):
                return skill
        return None

    # ------------------------------------------------------------------
    # Skill dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, filepath: Path, prompt: str) -> None:
        """Spawn ``claude --print "<prompt>"`` in a daemon thread.

        The filename is added to ``_in_flight`` immediately and removed
        when the subprocess exits (success or failure).

        Args:
            filepath: Path to the file triggering this dispatch (used for
                      in-flight tracking and log entries).
            prompt:   Full prompt string to pass to ``claude --print``.
        """
        with self._lock:
            if filepath.name in self._in_flight:
                return
            self._in_flight.add(filepath.name)

        def _run() -> None:
            proc: Optional[subprocess.Popen] = None
            # Flag file tells stop.py this is an automated dispatch — skip
            # Ralph Wiggum re-injection.  Env var alone is unreliable because
            # Claude Code may sanitise the subprocess env before invoking hooks.
            _flag_dir = Path(__file__).parent / ".state"
            _flag_dir.mkdir(exist_ok=True)
            _flag = _flag_dir / f"dispatch_{threading.current_thread().ident}_{int(time.time())}.flag"
            _flag.write_text("1")
            try:
                proc = subprocess.Popen(
                    [
                        "claude", "--print",
                        "--model", "haiku",
                        "--no-session-persistence",
                        prompt,
                    ],
                    cwd=str(Path(__file__).parent),
                    stdin=subprocess.DEVNULL,   # prevent claude blocking on PM2 stdin
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    shell=_WIN32,
                    env={**os.environ, "FTE_AUTOMATED_DISPATCH": "1"},
                )
                with self._lock:
                    self._subprocesses.append(proc)

                _, stderr_output = proc.communicate(timeout=SKILL_DISPATCH_TIMEOUT)

                log_action(
                    self.logs,
                    "skill_dispatched",
                    "Orchestrator",
                    source=filepath.name,
                    result="success" if proc.returncode == 0 else "error",
                    details=(
                        f"exit={proc.returncode} | prompt='{prompt[:80]}'"
                        + (f" | stderr={stderr_output[:120]}" if stderr_output.strip() else "")
                    ),
                )
            except subprocess.TimeoutExpired:
                if proc:
                    proc.terminate()
                log_action(
                    self.logs,
                    "skill_timeout",
                    "Orchestrator",
                    source=filepath.name,
                    result="error",
                    details=f"Timeout after {SKILL_DISPATCH_TIMEOUT}s — process terminated",
                )
            except Exception as exc:
                log_action(
                    self.logs,
                    "skill_dispatch_error",
                    "Orchestrator",
                    source=filepath.name,
                    result="error",
                    details=str(exc),
                )
            finally:
                _flag.unlink(missing_ok=True)  # remove dispatch flag — stop.py can block again
                with self._lock:
                    self._in_flight.discard(filepath.name)
                    # Prune completed subprocesses from the list
                    self._subprocesses = [
                        p for p in self._subprocesses if p.poll() is None
                    ]

        thread = threading.Thread(target=_run, name=f"skill:{filepath.name}", daemon=True)
        thread.start()

    # ------------------------------------------------------------------
    # Heartbeat actions
    # ------------------------------------------------------------------

    # Statuses written by skills to mark a file as already processed.
    # Orchestrator skips these to prevent re-dispatch loops.
    _PROCESSED_STATUSES: frozenset[str] = frozenset({
        "replied_routine", "escalated", "ignored_personal",
        "pending_approval", "done", "archived", "sent", "replied",
        "moved_to_done",   # set by fte-gmail-triage / fte-gmail-reply after moving file
    })

    def _already_processed(self, filepath: Path) -> bool:
        """Return True if frontmatter status indicates this file was already handled."""
        try:
            text = filepath.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines()[:30]:
                if line.startswith("status:"):
                    status = line.split(":", 1)[1].strip().strip('"').strip("'")
                    return status in self._PROCESSED_STATUSES
        except OSError:
            pass
        return False

    def check_needs_action(self) -> None:
        """Scan /Needs_Action for unprocessed files and dispatch the correct skill."""
        if not self.needs_action.exists():
            return

        for filepath in sorted(self.needs_action.glob("*.md")):
            if not filepath.is_file():
                continue

            with self._lock:
                if filepath.name in self._in_flight:
                    continue

            # Skip files the skill has already handled (status written to frontmatter)
            if self._already_processed(filepath):
                continue

            skill = self.skill_for(filepath.name)
            if skill is None:
                continue  # no routing rule for this prefix — skip silently

            self._dispatch(filepath, f"/{skill} {filepath.name}")

    def check_plans(self) -> None:
        """Detect active Plan files with unchecked steps and re-prompt Claude.

        This is the Ralph Wiggum pattern: if Claude left a Plan unfinished,
        the orchestrator re-injects the continuation prompt automatically.
        One plan at a time to avoid overwhelming Claude.
        """
        if not self.plans.exists():
            return

        for plan_file in sorted(self.plans.glob("*.md")):
            if not plan_file.is_file():
                continue

            try:
                text = plan_file.read_text(encoding="utf-8")
            except OSError:
                continue

            unchecked = [ln for ln in text.splitlines() if "- [ ]" in ln]
            if not unchecked:
                continue  # all steps done

            with self._lock:
                if plan_file.name in self._in_flight:
                    continue

            # Dispatch continuation prompt — exact format expected by fte-plan skill
            prompt = f"/fte-plan continue {plan_file.name}"
            self._dispatch(plan_file, prompt)
            break  # one plan per tick — prevents parallel Claude pile-up

    def check_approved(self) -> None:
        """Scan /Approved for files and immediately dispatch fte-approve.

        The ApprovalWatcher handles instant watchdog events; this method is
        a safety net that catches any files the event handler may have missed
        (e.g. files dropped while the watcher was restarting).  The in-flight
        set prevents duplicate dispatches.
        """
        if not self.approved.exists():
            return

        for filepath in sorted(self.approved.glob("*.md")):
            if not filepath.is_file():
                continue

            # WhatsApp approvals are owned exclusively by whatsapp_watcher.js.
            # chokidar picks up APPROVAL_WA_*.md and calls sock.sendMessage().
            # If we also dispatch fte-approve here, it runs mv to /Done before
            # Baileys reads the file → the WhatsApp message is never sent.
            if filepath.name.startswith("APPROVAL_WA_"):
                continue

            # Email approvals are owned exclusively by ApprovalWatcher._mcp_send_impl().
            # ApprovalWatcher has watchdog (instant) + polling (10s fallback) + IDTracker
            # dedup + retry_with_backoff(3 attempts). Dispatching fte-approve here too
            # creates a race where both call mcp__email__send_email → duplicate email.
            if filepath.name.startswith("APPROVAL_email_"):
                continue

            with self._lock:
                if filepath.name in self._in_flight:
                    continue

            self._dispatch(filepath, f"/fte-approve {filepath.name}")

    def check_linkedin_schedule(self) -> None:
        """Fire the Playwright LinkedIn post when the jitter-scheduled time arrives.

        Reads .state/linkedin_scheduled.json on every tick.  When the post_at
        time has passed, calls post_to_linkedin() with human simulation, then:
        - Records the post time (for 23h gap enforcement on next schedule)
        - Clears the schedule file

        On failure the schedule file is left in place so the next tick retries.
        This method is idempotent and safe to call every heartbeat cycle.
        """
        if not JitterScheduler.is_due():
            schedule = JitterScheduler.get_pending()
            if schedule:
                post_time = f"{schedule.get('post_date')} {schedule.get('post_at')}"
                log_action(
                    self.logs, "linkedin_schedule_pending", "Orchestrator",
                    result="info",
                    details=f"LinkedIn post scheduled for {post_time} — waiting",
                )
            return

        schedule = JitterScheduler.get_pending()
        if not schedule:
            return

        content = schedule.get("content", "")
        if not content:
            log_action(
                self.logs, "linkedin_schedule_error", "Orchestrator",
                result="error",
                details="Scheduled post has no content — clearing schedule",
            )
            JitterScheduler.clear()
            return

        log_action(
            self.logs, "linkedin_post_firing", "Orchestrator",
            result="info",
            details=f"Firing scheduled LinkedIn post ({len(content)} chars)",
        )

        from pathlib import Path as _Path
        import os as _os

        session_raw = _os.getenv(
            "LINKEDIN_SESSION_DIR",
            _os.getenv("LI_SESSION_PATH", ".secrets/linkedin_session"),
        )
        session_dir = (_Path(__file__).parent / session_raw).resolve()

        success = post_to_linkedin(
            content=content,
            session_dir=session_dir,
            vault_path=self.vault_path,
        )

        if success:
            JitterScheduler.record_post()
            JitterScheduler.clear()
            log_action(
                self.logs, "linkedin_post_success", "Orchestrator",
                result="success",
                details="LinkedIn post submitted; schedule cleared",
            )
        else:
            log_action(
                self.logs, "linkedin_post_failed", "Orchestrator",
                result="error",
                details="LinkedIn post failed — schedule retained for next tick retry",
            )

    def sync_dashboard(self) -> None:
        """Update Dashboard.md with live watcher statuses."""
        watcher_status = {type(w).__name__: "Online" for w in self._watchers}

        # WhatsApp is managed by PM2 as a separate Node.js process — not in self._watchers.
        # Mark Online if session files exist (session = watcher has authenticated and run).
        wa_session = Path(__file__).parent / ".secrets" / "whatsapp_session"
        if wa_session.exists() and any(wa_session.iterdir()):
            watcher_status["WhatsAppWatcher"] = "Online (PM2)"

        schedule = JitterScheduler.get_pending()
        if schedule:
            post_time = f"{schedule.get('post_date')} {schedule.get('post_at')}"
            watcher_status["LinkedIn_Scheduled"] = post_time
        update_dashboard(self.vault_path, watcher_status)

    def _log_tick(
        self,
        needs_action_count: int,
        plans_pending: int,
        approved_count: int,
    ) -> None:
        """Append a JSON Lines tick entry to Logs/orchestrator.log.

        Each line records what the orchestrator saw and did during one heartbeat
        cycle. This gives a complete audit trail of autonomous agent activity
        separate from the daily event log.

        Args:
            needs_action_count: Number of .md files found in /Needs_Action this tick.
            plans_pending:      Number of plans with at least one unchecked step.
            approved_count:     Number of .md files found in /Approved this tick.
        """
        import json
        from datetime import datetime, timezone

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tick": self._tick_count,
            "heartbeat_s": self.heartbeat,
            "needs_action_files": needs_action_count,
            "plans_with_unchecked_steps": plans_pending,
            "approved_files": approved_count,
        }

        self.logs.mkdir(parents=True, exist_ok=True)
        log_file = self.logs / "orchestrator.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # Heartbeat loop
    # ------------------------------------------------------------------

    def tick(self) -> None:
        """Execute one heartbeat cycle: dispatch + plan check + approved check + dashboard + tick log."""
        self._tick_count += 1

        # Collect counts before dispatch for the tick log
        needs_action_count = (
            sum(1 for f in self.needs_action.glob("*.md") if f.is_file())
            if self.needs_action.exists() else 0
        )
        plans_pending = 0
        if self.plans.exists():
            for pf in self.plans.glob("*.md"):
                try:
                    if "- [ ]" in pf.read_text(encoding="utf-8"):
                        plans_pending += 1
                except OSError:
                    pass
        approved_count = (
            sum(1 for f in self.approved.glob("*.md") if f.is_file())
            if self.approved.exists() else 0
        )

        try:
            self.check_needs_action()
        except Exception as exc:
            log_action(
                self.logs, "orchestrator_error", "Orchestrator",
                result="error", details=f"check_needs_action: {exc}",
            )

        try:
            self.check_plans()
        except Exception as exc:
            log_action(
                self.logs, "orchestrator_error", "Orchestrator",
                result="error", details=f"check_plans: {exc}",
            )

        try:
            self.check_approved()
        except Exception as exc:
            log_action(
                self.logs, "orchestrator_error", "Orchestrator",
                result="error", details=f"check_approved: {exc}",
            )

        try:
            self.check_linkedin_schedule()
        except Exception as exc:
            log_action(
                self.logs, "orchestrator_error", "Orchestrator",
                result="error", details=f"check_linkedin_schedule: {exc}",
            )

        try:
            self.sync_dashboard()
        except Exception as exc:
            log_action(
                self.logs, "orchestrator_error", "Orchestrator",
                result="error", details=f"sync_dashboard: {exc}",
            )

        # Always write a tick entry — the autonomous activity audit trail
        try:
            self._log_tick(needs_action_count, plans_pending, approved_count)
        except Exception:
            pass  # never let tick logging crash the heartbeat

    def run(self) -> None:
        """Block in the heartbeat loop until stop() is called."""
        self._running = True
        log_action(
            self.logs,
            "orchestrator_started",
            "Orchestrator",
            details=f"Heartbeat: {self.heartbeat}s | Vault: {self.vault_path}",
        )
        print(
            f"[orchestrator] Heartbeat loop started "
            f"(interval={self.heartbeat}s) | Ctrl+C to stop"
        )

        while self._running:
            self.tick()
            # Interruptible sleep — checks _running every second
            for _ in range(self.heartbeat):
                if not self._running:
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Stop the heartbeat loop, all watchers, and all running subprocesses."""
        self._running = False

        # Stop watchers in reverse start order
        for watcher in reversed(self._watchers):
            try:
                watcher.stop()
            except Exception:
                pass

        # Terminate any running claude subprocesses
        with self._lock:
            for proc in self._subprocesses:
                try:
                    proc.terminate()
                except Exception:
                    pass
            self._subprocesses.clear()
            self._in_flight.clear()

        log_action(
            self.logs,
            "orchestrator_stopped",
            "Orchestrator",
            details="All watchers and subprocesses terminated",
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    heartbeat = int(os.getenv("ORCHESTRATOR_HEARTBEAT", str(HEARTBEAT_INTERVAL)))
    vault = Path(os.getenv("VAULT_PATH", str(VAULT_PATH)))

    print("[orchestrator] Silver Tier AI Employee — starting")
    print(f"[orchestrator] Vault:     {vault.resolve()}")
    print(f"[orchestrator] Heartbeat: {heartbeat}s")

    orch = Orchestrator(vault_path=vault, heartbeat=heartbeat)

    # Warn early if claude CLI is missing — don't block startup
    if not orch.validate_claude():
        print(
            "[orchestrator] WARNING: 'claude' CLI not found on PATH — "
            "skill dispatch will fail.\n"
            "[orchestrator]          Install: npm install -g @anthropic-ai/claude-code"
        )

    # Graceful shutdown on SIGINT / SIGTERM
    def _shutdown(signum, frame) -> None:
        print("\n[orchestrator] Shutdown signal received — stopping...")
        orch.stop()
        print("[orchestrator] Goodbye.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Initialise and start all watchers
    orch.init_watchers()
    active = [type(w).__name__ for w in orch._watchers]
    print(f"[orchestrator] Active watchers: {', '.join(active)}")

    # Run the blocking heartbeat loop
    try:
        orch.run()
    except KeyboardInterrupt:
        _shutdown(None, None)


if __name__ == "__main__":
    main()
