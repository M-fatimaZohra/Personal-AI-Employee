"""orchestrator.py — Gold Tier AI Employee central execution engine.

Responsibilities:
    1. Watcher lifecycle   — initialise and manage all watchers in threads.
    2. Heartbeat loop      — tick every HEARTBEAT_INTERVAL seconds.
    3. Autonomous dispatch — on each tick, scan /Needs_Action for new files
                             and invoke the correct Claude skill automatically.
    4. Plan awareness      — detect active Plan files with unchecked steps
                             and re-prompt Claude to continue (Ralph Wiggum).
    5. Dashboard sync      — call update_dashboard() on every tick so the
                             Obsidian UI always reflects live state.
    6. Odoo health check   — every ODOO_HEALTH_INTERVAL ticks, probe Odoo
                             JSON-RPC and update service_health in Dashboard.
    7. Graceful shutdown   — SIGINT / SIGTERM stop all watchers + subprocesses.

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

from backoff import CircuitBreaker, ServiceDegradedError
from dashboard_updater import update_dashboard
from facebook_poster import FacebookScheduler, post_to_facebook
from instagram_poster import InstagramScheduler, post_to_instagram
from linkedin_poster import JitterScheduler, post_to_linkedin
from logger import log_action
from twitter_poster import TwitterScheduler, post_to_twitter

# On Windows, ccr is installed as ccr.CMD (a batch file) which cannot be
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
    "EMAIL_":             "fte-gmail-triage",
    "WHATSAPP_":          "fte-whatsapp-reply",
    "LINKEDIN_NOTIF_":    "fte-triage",
    "SOCIAL_FB_":         "fte-triage",           # Facebook → triage → fte-social-post if reply needed
    "SOCIAL_IG_":         "fte-triage",           # Instagram → triage → fte-social-post if reply needed
    "TWITTER_":           "fte-triage",           # Twitter/X → triage → fte-social-post if reply needed
    "FILE_":              "fte-triage",
    "ATTACHMENT_EXTRACT_": "fte-extract-attachment",  # PDF/txt attachment → structured order approval
    "ODOO_":              "fte-plan",                 # Invoice/order workflow → multi-domain plan
}

# Plans skill — invoked when an active plan has unchecked steps
PLAN_SKILL = "fte-plan"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    """Central execution engine for the Gold Tier AI Employee.

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

        # Gold Tier — Odoo circuit breaker and health tracking
        self._odoo_cb = CircuitBreaker(name="odoo", failure_threshold=3, timeout_seconds=900, logs_path=self.logs)
        self._odoo_health_interval = int(os.getenv("ODOO_HEALTH_INTERVAL", "6"))  # check every N ticks

        # Social media circuit breakers — track posting failures per platform
        self._social_fb_cb = CircuitBreaker(name="social_facebook", failure_threshold=3, timeout_seconds=1800, logs_path=self.logs)
        self._social_ig_cb = CircuitBreaker(name="social_instagram", failure_threshold=3, timeout_seconds=1800, logs_path=self.logs)
        self._social_tw_cb = CircuitBreaker(name="social_twitter", failure_threshold=3, timeout_seconds=1800, logs_path=self.logs)
        self._social_health_interval = int(os.getenv("SOCIAL_HEALTH_INTERVAL", "6"))  # check every N ticks

        # Instagram media availability — set True when media/ folder has no unused images
        self._ig_posting_paused: bool = False

        self._service_health: dict = {}

        self.approved = self.vault_path / "Approved"
        self._tick_count: int = 0

        self._watchers: list = []
        self._running: bool = False

        # Thread-safe tracking of filenames currently dispatched to Claude
        self._lock = threading.Lock()
        self._in_flight: set[str] = set()

        # Subprocesses spawned for claude skill invocations
        self._subprocesses: list[subprocess.Popen] = []

        # Track approval files already dispatched this session — prevents re-dispatch
        # when fte-approve exits 0 but fails to move the file out of /Approved.
        self._dispatched_approvals: set[str] = set()

        # Daily Done/ archiving — track last archive date
        self._last_archive_date: str = ""

    # ------------------------------------------------------------------
    # Claude CLI validation
    # ------------------------------------------------------------------

    def validate_claude(self) -> bool:
        """Return True if the ``ccr code`` CLI is reachable on PATH."""
        try:
            result = subprocess.run(
                ["ccr", "code", "--version"],
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

        # Facebook watcher — requires FB session directory
        fb_session = Path(__file__).parent / ".secrets" / "facebook_session"
        if fb_session.exists() and any(fb_session.iterdir()):
            try:
                from facebook_watcher import FacebookWatcher
                self._watchers.append(FacebookWatcher(self.vault_path))
                print("[orchestrator] FacebookWatcher:    enabled")
            except Exception as exc:
                print(f"[orchestrator] FacebookWatcher:    SKIPPED — {exc}")
        else:
            print(
                "[orchestrator] FacebookWatcher:    SKIPPED "
                "(no session — run: LI_HEADLESS=false uv run python facebook_watcher.py --setup)"
            )

        # Instagram watcher — requires IG session directory
        ig_session = Path(__file__).parent / ".secrets" / "instagram_session"
        if ig_session.exists() and any(ig_session.iterdir()):
            try:
                from instagram_watcher import InstagramWatcher
                self._watchers.append(InstagramWatcher(self.vault_path))
                print("[orchestrator] InstagramWatcher:   enabled")
            except Exception as exc:
                print(f"[orchestrator] InstagramWatcher:   SKIPPED — {exc}")
        else:
            print(
                "[orchestrator] InstagramWatcher:   SKIPPED "
                "(no session — run: LI_HEADLESS=false uv run python instagram_watcher.py --setup)"
            )

        # Twitter watcher — requires Twitter session directory
        tw_session = Path(__file__).parent / ".secrets" / "twitter_session"
        if tw_session.exists() and any(tw_session.iterdir()):
            try:
                from twitter_watcher import TwitterWatcher
                self._watchers.append(TwitterWatcher(self.vault_path))
                print("[orchestrator] TwitterWatcher:     enabled")
            except Exception as exc:
                print(f"[orchestrator] TwitterWatcher:     SKIPPED — {exc}")
        else:
            print(
                "[orchestrator] TwitterWatcher:     SKIPPED "
                "(no session — run: LI_HEADLESS=false uv run python twitter_watcher.py --setup)"
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
                        "ccr", "code", "-p", prompt,
                        "--model", "haiku",
                        "--no-session-persistence",
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
    # IMPORTANT: keep this in sync with every skill that writes status: to Needs_Action files.
    _PROCESSED_STATUSES: frozenset[str] = frozenset({
        # Email skills
        "replied_routine", "escalated", "replied", "sent", "moved_to_done",
        # Triage / generic
        "pending_approval", "done", "archived", "ignored_personal",
        "triaged",          # fte-triage after classifying a file-drop
        # Attachment pipeline
        "processed",        # fte-extract-attachment after writing to Pending_Approval
        # Plan / workflow
        "in_progress",      # ODOO_EMAIL_*.md after fte-plan creates a plan
        "plan_created",     # alternative status fte-plan may write
        "complete",         # plan / workflow fully done
        # Error / terminal states — do not retry
        "failed",
        "blocked",
        "dispatched",
        "executed",
        "skipped",
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
            # Auto-cleanup: move processed files out of Needs_Action → Done
            if self._already_processed(filepath):
                done_dir = self.vault_path / "Done"
                done_dir.mkdir(exist_ok=True)
                dest = done_dir / filepath.name
                if dest.exists():
                    from datetime import datetime as _dt
                    ts = _dt.now().strftime("%H%M%S")
                    dest = done_dir / f"{filepath.stem}_{ts}{filepath.suffix}"
                try:
                    filepath.rename(dest)
                    log_action(self.logs, "needs_action_archived", "Orchestrator",
                               source=filepath.name, destination=dest.name, result="success",
                               details="Auto-archived processed file from Needs_Action to Done")
                except OSError:
                    pass
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

            # Only count genuinely unchecked steps — ignore permanently blocked/failed ones.
            # A step starting with "- [ ]" but annotated [FAILED / [BLOCKED / [CANCELLED
            # should NOT trigger a re-dispatch.
            unchecked = [
                ln for ln in text.splitlines()
                if "- [ ]" in ln
                and "[FAILED" not in ln
                and "[BLOCKED" not in ln
                and "[CANCELLED" not in ln
            ]
            if not unchecked:
                continue  # all steps done or permanently blocked

            # Enforce a retry cap: count ⚠️ retry annotations in the Notes section.
            # If >= 3 retries have been logged, mark the plan blocked and skip.
            retry_count = text.count("⚠️")
            if retry_count >= 3:
                # Rewrite plan status to blocked so it won't be dispatched again
                try:
                    new_text = text.replace("status: in_progress", "status: blocked_max_retries", 1)
                    if new_text != text:
                        plan_file.write_text(new_text, encoding="utf-8")
                    log_action(
                        self.logs, "plan_blocked_max_retries", "Orchestrator",
                        source=plan_file.name, result="blocked",
                        details=f"Plan has {retry_count} retry warnings — blocked to prevent infinite loop. Manual intervention required.",
                    )
                except OSError:
                    pass
                continue

            # Skip plans whose frontmatter status is already terminal or waiting for user
            terminal_plan_statuses = {
                "complete", "blocked", "blocked_max_retries", "cancelled",
                "awaiting_approval",  # plan created an approval in Pending_Approval — waiting for user
            }
            for line in text.splitlines()[:20]:
                if line.startswith("status:"):
                    s = line.split(":", 1)[1].strip().strip('"').strip("'")
                    if s in terminal_plan_statuses:
                        break
            else:
                s = ""
            if s in terminal_plan_statuses:
                continue

            with self._lock:
                if plan_file.name in self._in_flight:
                    continue

            # Dispatch continuation prompt — exact format expected by fte-plan skill
            prompt = f"/fte-plan continue {plan_file.name}"
            self._dispatch(plan_file, prompt)
            break  # one plan per tick — prevents parallel Claude pile-up

    # Statuses in Approved/ files that mean fte-approve already ran — do not re-dispatch.
    _APPROVAL_DONE_STATUSES: frozenset[str] = frozenset({
        "executed", "executed_manual", "validation_failed", "failed",
        "skipped_no_image", "acknowledged", "incomplete_pricing",
        "odoo_invoice_failed", "odoo_partner_failed",
    })

    def _approval_already_executed(self, filepath: Path) -> bool:
        """Return True if the approval file's status shows it was already processed."""
        try:
            text = filepath.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines()[:30]:
                if line.startswith("status:"):
                    status = line.split(":", 1)[1].strip().strip('"').strip("'")
                    return status in self._APPROVAL_DONE_STATUSES
        except OSError:
            pass
        return False

    def _handle_social_post_approval(self, filepath: Path) -> bool:
        """Route social post approvals to appropriate scheduler.

        Returns True if this was a social post and was handled, False otherwise.
        """
        try:
            text = filepath.read_text(encoding="utf-8")
            if not text.startswith("---"):
                return False

            # Parse frontmatter
            parts = text.split("---", 2)
            if len(parts) < 3:
                return False

            frontmatter = {}
            for line in parts[1].splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    frontmatter[key.strip()] = value.strip().strip('"').strip("'")

            action = frontmatter.get("action", "")
            if action != "social_post":
                return False

            platform = frontmatter.get("platform", "").lower()
            if platform not in ("facebook", "instagram", "twitter"):
                log_action(self.logs, "social_post_invalid_platform", "Orchestrator",
                          source=filepath.name, result="error",
                          details=f"Invalid platform: {platform} — must be facebook, instagram, or twitter")
                return False

            # Extract post content from ## Post Content section
            content = self._extract_post_content(text)
            if not content:
                log_action(self.logs, "social_post_no_content", "Orchestrator",
                          source=filepath.name, result="error",
                          details="No content found in ## Post Content section")
                return False

            # Move to Done first, then schedule with correct path
            done_dir = self.vault_path / "Done"
            done_dir.mkdir(exist_ok=True)
            dest = done_dir / filepath.name
            if not dest.exists():
                filepath.rename(dest)
                log_action(self.logs, "social_post_approved", "Orchestrator",
                          source=filepath.name, destination=dest.name,
                          result="success", details=f"Moved to Done — {platform} post scheduled")

            # Route to appropriate scheduler with Done path
            if platform == "facebook":
                schedule = FacebookScheduler.schedule(dest, content)
                log_action(self.logs, "facebook_post_scheduled", "Orchestrator",
                          source=filepath.name, result="success",
                          details=f"Scheduled for {schedule.get('post_date')} {schedule.get('post_at')} | {len(content)} chars")
            elif platform == "instagram":
                schedule = InstagramScheduler.schedule(dest, content)
                log_action(self.logs, "instagram_post_scheduled", "Orchestrator",
                          source=filepath.name, result="success",
                          details=f"Scheduled for {schedule.get('post_date')} {schedule.get('post_at')} | {len(content)} chars")
            elif platform == "twitter":
                schedule = TwitterScheduler.schedule(dest, content)
                log_action(self.logs, "twitter_post_scheduled", "Orchestrator",
                          source=filepath.name, result="success",
                          details=f"Scheduled for {schedule.get('post_date')} {schedule.get('post_at')} | {len(content)} chars")

            return True

        except Exception as e:
            log_action(self.logs, "social_post_error", "Orchestrator",
                      source=filepath.name, result="error",
                      details=f"Failed to schedule social post: {e}")
            return False

    def _extract_post_content(self, text: str) -> str:
        """Extract content from ## Post Content section."""
        marker = "## Post Content"
        idx = text.find(marker)
        if idx == -1:
            return ""

        body = text[idx + len(marker):]
        # Trim at next heading
        next_heading = body.find("\n## ")
        if next_heading != -1:
            body = body[:next_heading]

        return body.strip()

    def check_approved(self) -> None:
        """Scan /Approved for files and route to appropriate handler.

        Social posts (action: social_post) are routed directly to schedulers.
        All other approvals are dispatched to fte-approve skill.

        The ApprovalWatcher handles instant watchdog events; this method is
        a safety net that catches any files the event handler may have missed
        (e.g. files dropped while the watcher was restarting).  The in-flight
        set prevents duplicate dispatches.
        """
        if not self.approved.exists():
            return

        done_dir = self.vault_path / "Done"

        for filepath in sorted(self.approved.glob("*.md")):
            if not filepath.is_file():
                continue

            # WhatsApp approvals are owned exclusively by whatsapp_watcher.js.
            # chokidar picks up APPROVAL_WA_*.md and calls sock.sendMessage().
            # If we also dispatch fte-approve here, it runs mv to /Done before
            # Baileys reads the file → the WhatsApp message is never sent.
            if filepath.name.startswith("APPROVAL_WA_"):
                continue

            # Skip files fte-approve already processed — move them to Done to clean up.
            if self._approval_already_executed(filepath):
                done_dir.mkdir(exist_ok=True)
                dest = done_dir / filepath.name
                if not dest.exists():
                    try:
                        filepath.rename(dest)
                        log_action(self.logs, "approved_archived", "Orchestrator",
                                   source=filepath.name, destination=dest.name,
                                   result="success", details="Auto-moved executed approval to Done")
                    except OSError:
                        pass
                continue

            with self._lock:
                if filepath.name in self._in_flight:
                    continue

            # If already dispatched this session and subprocess completed (not in-flight),
            # the skill ran but didn't move the file — clean it up now.
            if filepath.name in self._dispatched_approvals:
                done_dir.mkdir(exist_ok=True)
                dest = done_dir / filepath.name
                if not dest.exists():
                    try:
                        filepath.rename(dest)
                        log_action(self.logs, "approved_stale_archived", "Orchestrator",
                                   source=filepath.name, destination=dest.name,
                                   result="success",
                                   details="Approval dispatched but skill did not move it — archived to Done")
                    except OSError:
                        pass
                continue

            # Check if this is a social post approval — route to scheduler instead of fte-approve
            if self._handle_social_post_approval(filepath):
                continue

            self._dispatched_approvals.add(filepath.name)
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

    def check_facebook_schedule(self) -> None:
        """Fire the Playwright Facebook post when the jitter-scheduled time arrives."""
        if not FacebookScheduler.is_due():
            return

        schedule = FacebookScheduler.get_pending()
        if not schedule:
            return

        content = schedule.get("content", "")
        if not content:
            log_action(self.logs, "facebook_schedule_error", "Orchestrator",
                       result="error", details="Scheduled FB post has no content — clearing")
            FacebookScheduler.clear()
            return

        log_action(self.logs, "facebook_post_firing", "Orchestrator",
                   result="info", details=f"Firing scheduled Facebook post ({len(content)} chars)")

        success = post_to_facebook(content=content)

        if success:
            FacebookScheduler.record_post()
            FacebookScheduler.clear()
            log_action(self.logs, "facebook_post_success", "Orchestrator",
                       result="success", details="Facebook post submitted; schedule cleared")
        else:
            log_action(self.logs, "facebook_post_failed", "Orchestrator",
                       result="error", details="Facebook post failed — schedule retained for retry")

    def check_instagram_schedule(self) -> None:
        """Fire the Playwright Instagram post when the jitter-scheduled time arrives.

        Checks media availability first. If no unused images remain:
        - Sets _ig_posting_paused = True
        - Writes a Dashboard warning
        - Skips posting until new images are added to media/
        """
        if self._ig_posting_paused:
            # Check again if media has been replenished
            if InstagramScheduler.has_media():
                self._ig_posting_paused = False
                log_action(self.logs, "instagram_media_restored", "Orchestrator",
                           result="info", details="Media available again — Instagram posting resumed")
            else:
                return

        if not InstagramScheduler.is_due():
            return

        schedule = InstagramScheduler.get_pending()
        if not schedule:
            return

        content = schedule.get("content", "")
        image_path_str = schedule.get("image_path")

        if not image_path_str:
            # Try to pick a fresh image
            media = InstagramScheduler.get_next_media()
            if media is None:
                self._ig_posting_paused = True
                warn_msg = (
                    "Instagram posting PAUSED — no unused images in media/ folder. "
                    "Add images to level-gold/media/ to resume."
                )
                log_action(self.logs, "instagram_no_media", "Orchestrator",
                           result="error", details=warn_msg)
                # Write Dashboard warning
                dashboard = self.vault_path / "Dashboard.md"
                if dashboard.exists():
                    try:
                        text = dashboard.read_text(encoding="utf-8")
                        from datetime import datetime as _dtnow
                        banner = f"\n> WARNING INSTAGRAM ({_dtnow.now().strftime('%Y-%m-%d %H:%M')}): {warn_msg}\n"
                        lines = text.splitlines(keepends=True)
                        new_lines: list = []
                        inserted = False
                        for line in lines:
                            new_lines.append(line)
                            if not inserted and line.startswith("#"):
                                new_lines.append(banner)
                                inserted = True
                        if not inserted:
                            new_lines.insert(0, banner)
                        tmp = dashboard.with_suffix(".tmp")
                        tmp.write_text("".join(new_lines), encoding="utf-8")
                        tmp.replace(dashboard)
                    except OSError:
                        pass
                return
            image_path_str = str(media.resolve())

        image_path = Path(image_path_str)
        if not image_path.exists():
            log_action(self.logs, "instagram_media_missing", "Orchestrator",
                       result="error", details=f"Scheduled image not found: {image_path}")
            InstagramScheduler.clear()
            return

        if not content:
            log_action(self.logs, "instagram_schedule_error", "Orchestrator",
                       result="error", details="Scheduled IG post has no content — clearing")
            InstagramScheduler.clear()
            return

        log_action(self.logs, "instagram_post_firing", "Orchestrator",
                   result="info", details=f"Firing scheduled Instagram post ({len(content)} chars, image={image_path.name})")

        success = post_to_instagram(content=content, image_path=str(image_path))

        if success:
            InstagramScheduler.record_post(image_path=image_path)
            InstagramScheduler.clear()
            log_action(self.logs, "instagram_post_success", "Orchestrator",
                       result="success", details=f"Instagram post submitted; image={image_path.name}; schedule cleared")
        else:
            log_action(self.logs, "instagram_post_failed", "Orchestrator",
                       result="error", details="Instagram post failed — schedule retained for retry")

    def check_twitter_schedule(self) -> None:
        """Fire the Playwright Twitter post when the jitter-scheduled time arrives."""
        if not TwitterScheduler.is_due():
            return

        schedule = TwitterScheduler.get_pending()
        if not schedule:
            return

        content = schedule.get("content", "")
        if not content:
            log_action(self.logs, "twitter_schedule_error", "Orchestrator",
                       result="error", details="Scheduled Twitter post has no content — clearing")
            TwitterScheduler.clear()
            return

        log_action(self.logs, "twitter_post_firing", "Orchestrator",
                   result="info", details=f"Firing scheduled Twitter post ({len(content)} chars)")

        success = post_to_twitter(content=content)

        if success:
            TwitterScheduler.record_post()
            TwitterScheduler.clear()
            log_action(self.logs, "twitter_post_success", "Orchestrator",
                       result="success", details="Twitter post submitted; schedule cleared")
        else:
            log_action(self.logs, "twitter_post_failed", "Orchestrator",
                       result="error", details="Twitter post failed — schedule retained for retry")

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

        fb_sched = FacebookScheduler.get_pending()
        if fb_sched:
            watcher_status["Facebook_Scheduled"] = f"{fb_sched.get('post_date')} {fb_sched.get('post_at')}"

        ig_sched = InstagramScheduler.get_pending()
        if ig_sched:
            watcher_status["Instagram_Scheduled"] = f"{ig_sched.get('post_date')} {ig_sched.get('post_at')}"
            if self._ig_posting_paused:
                watcher_status["Instagram_Scheduled"] += " [PAUSED — no media]"

        tw_sched = TwitterScheduler.get_pending()
        if tw_sched:
            watcher_status["Twitter_Scheduled"] = f"{tw_sched.get('post_date')} {tw_sched.get('post_at')}"

        update_dashboard(
            self.vault_path,
            watcher_status,
            service_health=self._service_health if self._service_health else None,
        )

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
    def cleanup_done(self) -> None:
        """Delete files from Done/ that are older than 24 hours."""
        from datetime import date
        today = date.today().isoformat()
        if self._last_archive_date == today:
            return
        done_dir = self.vault_path / "Done"
        if not done_dir.exists():
            self._last_archive_date = today
            return
        import time as _time
        cutoff = _time.time() - 86400  # 24 hours ago
        deleted = 0
        for f in list(done_dir.glob("*.md")):
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
                deleted += 1
        if deleted:
            log_action(self.logs, "done_cleaned", "Orchestrator",
                       result="success", details=f"Deleted {deleted} files older than 24h from Done/")
        self._last_archive_date = today

    # Heartbeat loop
    # ------------------------------------------------------------------

    def check_odoo_health(self) -> None:
        """Probe Odoo JSON-RPC and update _service_health for Dashboard display."""
        import urllib.request
        import json as _json

        odoo_url = os.getenv("ODOO_URL", "http://localhost:8069")
        odoo_db = os.getenv("ODOO_DB", "fte-business")
        odoo_key = os.getenv("ODOO_API_KEY", "")

        def _probe():
            req = urllib.request.Request(
                f"{odoo_url}/json/2/res.partner/search",
                data=_json.dumps({"domain": [], "limit": 1, "context": {"lang": "en_US"}}).encode(),
                headers={
                    "Authorization": f"bearer {odoo_key}",
                    "X-Odoo-Database": odoo_db,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()

        prev_status = self._service_health.get("odoo", "unknown")
        try:
            self._odoo_cb.call(_probe)
            self._service_health["odoo"] = self._odoo_cb.status
            # Only log on state change (ok→degraded or first-time ok) — avoids log spam
            if prev_status != self._odoo_cb.status:
                log_action(self.logs, "odoo_health_ok", "Orchestrator", details="Odoo reachable")
        except ServiceDegradedError:
            self._service_health["odoo"] = self._odoo_cb.status
            if prev_status != self._odoo_cb.status:
                log_action(self.logs, "odoo_health_degraded", "Orchestrator",
                           result="error", details="Odoo circuit open — skipping")
        except Exception as exc:
            self._odoo_cb._on_failure(exc)
            self._service_health["odoo"] = self._odoo_cb.status
            log_action(self.logs, "odoo_health_error", "Orchestrator",
                       result="error", details=str(exc))

    def check_social_health(self) -> None:
        """Probe social media session directories and update _service_health for Dashboard display.

        Uses session directory existence as a health proxy — no live network calls to
        social platforms to avoid triggering bot-detection systems. If a session directory
        is missing or empty the platform is flagged as degraded. The circuit breaker state
        is updated externally by instagram_poster / linkedin_poster on actual posting failures.
        """
        social_platforms = [
            ("social_facebook",  self._social_fb_cb,  ".secrets/facebook_session"),
            ("social_instagram", self._social_ig_cb,  ".secrets/instagram_session"),
            ("social_twitter",   self._social_tw_cb,  ".secrets/twitter_session"),
        ]
        base = Path(__file__).parent

        for svc_name, cb, session_rel in social_platforms:
            session_dir = base / session_rel
            session_ok = session_dir.exists() and any(session_dir.iterdir()) if session_dir.exists() else False

            if session_ok:
                # Session exists — consider healthy unless CB is open from prior failures
                if cb.state == "closed":
                    self._service_health[svc_name] = cb.status
                else:
                    # CB is open or half_open from a previous posting failure
                    self._service_health[svc_name] = cb.status
            else:
                # No session — report as offline (not an error, just not configured)
                self._service_health[svc_name] = {
                    "circuit_state": "open",
                    "failure_count": 0,
                    "retry_in_seconds": None,
                    "_note": "session not configured",
                }

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
            self.check_facebook_schedule()
        except Exception as exc:
            log_action(
                self.logs, "orchestrator_error", "Orchestrator",
                result="error", details=f"check_facebook_schedule: {exc}",
            )

        try:
            self.check_instagram_schedule()
        except Exception as exc:
            log_action(
                self.logs, "orchestrator_error", "Orchestrator",
                result="error", details=f"check_instagram_schedule: {exc}",
            )

        try:
            self.check_twitter_schedule()
        except Exception as exc:
            log_action(
                self.logs, "orchestrator_error", "Orchestrator",
                result="error", details=f"check_twitter_schedule: {exc}",
            )

        # Daily Done/ cleanup — runs once per day
        try:
            self.cleanup_done()
        except Exception as exc:
            log_action(self.logs, "orchestrator_error", "Orchestrator",
                       result="error", details=f"cleanup_done: {exc}")

        # Gold Tier: Odoo health check every N ticks
        if self._tick_count % self._odoo_health_interval == 0:
            try:
                self.check_odoo_health()
            except Exception as exc:
                log_action(
                    self.logs, "orchestrator_error", "Orchestrator",
                    result="error", details=f"check_odoo_health: {exc}",
                )

        # Gold Tier: Social media session health check every N ticks
        if self._tick_count % self._social_health_interval == 0:
            try:
                self.check_social_health()
            except Exception as exc:
                log_action(
                    self.logs, "orchestrator_error", "Orchestrator",
                    result="error", details=f"check_social_health: {exc}",
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

    print("[orchestrator] Gold Tier AI Employee — starting")
    print(f"[orchestrator] Vault:     {vault.resolve()}")
    print(f"[orchestrator] Heartbeat: {heartbeat}s")

    orch = Orchestrator(vault_path=vault, heartbeat=heartbeat)

    # Warn early if ccr code CLI is missing — don't block startup
    if not orch.validate_claude():
        print(
            "[orchestrator] WARNING: 'ccr code' CLI not found on PATH — "
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
