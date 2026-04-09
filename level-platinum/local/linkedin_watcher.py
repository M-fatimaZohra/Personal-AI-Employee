"""LinkedIn watcher — Playwright-based, personal use, read-only + draft output.

⚠️  TERMS OF SERVICE NOTICE  ⚠️
    LinkedIn's User Agreement (Section 8.2) prohibits scraping, crawling,
    and automated access to LinkedIn services.  This watcher is for personal/
    educational hackathon use ONLY on your OWN account.

    NEVER use this for:
        - Scraping other users' profiles or posts
        - Sending automated connection requests or messages
        - Bulk data collection
        - Commercial purposes

    For any commercial use, apply for the LinkedIn Partner Program:
    https://developer.linkedin.com/product-catalog

PERSONAL USE SAFEGUARDS IN THIS FILE:
    - Read-only: reads ONLY your own notifications (never posts automatically)
    - Rate-limited: minimum 30-minute intervals between checks
    - Human-like: slow_mo=500ms, random pauses between actions
    - Draft-only output: posts are written to /Plans for your manual review
    - Session-persistent: login once, session reused (minimises requests)
    - Capped: reads at most LI_MAX_NOTIFS notifications per check

FIRST-TIME SETUP:
    1. Set LI_SESSION_PATH in .env (default: .secrets/linkedin_session/)
    2. Run with headless=false for first login:
         LI_HEADLESS=false uv run python linkedin_watcher.py --setup
       Log in manually in the opened browser window.
    3. Session saved automatically — subsequent runs are headless.

.env VARIABLES:
    LI_SESSION_PATH=.secrets/linkedin_session   # persistent session dir
    LI_HEADLESS=true                             # true after first login
    LI_CHECK_INTERVAL=1800                       # seconds between checks (min 1800 = 30min)
    LI_MAX_NOTIFS=10                             # max notifications per scan
    LI_POST_TOPICS=AI,automation,productivity    # themes for draft posts
    LI_GENERATE_DRAFTS=true                      # auto-generate draft posts (read Business_Goals)

WORKFLOW:
    Monitoring mode:  Detects new notifications → LINKEDIN_NOTIF_*.md in /Needs_Action
    Draft mode:       Reads Business_Goals.md → LINKEDIN_DRAFT_*.md in /Plans (HITL required)
"""

import hashlib
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from base_watcher import BaseWatcher
from id_tracker import IDTracker
from logger import DRY_RUN, log_action

load_dotenv(Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Configuration (from .env)
# ---------------------------------------------------------------------------

# LINKEDIN_SESSION_DIR is the canonical env var name (matches plan.md and .env.example).
# LI_SESSION_PATH is kept as a legacy fallback for backwards compatibility.
_SESSION_RAW: str       = os.getenv(
    "LINKEDIN_SESSION_DIR",
    os.getenv("LI_SESSION_PATH", ".secrets/linkedin_session"),
)
LI_SESSION_PATH: Path   = (Path(__file__).parent.parent / _SESSION_RAW).resolve()
LI_HEADLESS: bool       = os.getenv("LI_HEADLESS", "true").lower() != "false"
_RAW_INTERVAL: int      = int(os.getenv("LI_CHECK_INTERVAL", "1800"))
LI_CHECK_INTERVAL: int  = max(_RAW_INTERVAL, 1800)  # enforce 30-minute minimum
LI_MAX_NOTIFS: int      = int(os.getenv("LI_MAX_NOTIFS", "10"))
LI_GENERATE_DRAFTS: bool = os.getenv("LI_GENERATE_DRAFTS", "true").lower() == "true"
# DRY_RUN imported from logger (centralised source)

_TOPICS_RAW: str = os.getenv("LI_POST_TOPICS", "AI,automation,productivity")
POST_TOPICS: list[str] = [t.strip() for t in _TOPICS_RAW.split(",") if t.strip()]

# LinkedIn URLs
LI_HOME_URL   = "https://www.linkedin.com/feed/"
LI_NOTIF_URL  = "https://www.linkedin.com/notifications/"
LI_LOGIN_URL  = "https://www.linkedin.com/login"

# Selectors — LinkedIn (early 2026)
# LinkedIn updates their DOM regularly; these may need updating.
SEL_NOTIF_LINK    = 'a[href*="/notifications/"]'
SEL_NOTIF_ITEM    = '[data-urn], .notification-item, [class*="notification__"]'
SEL_NOTIF_TEXT    = '[class*="notification__content"], .text-body-medium, .notification-text'
SEL_NOTIF_TIME    = 'time[datetime], [class*="timestamp"]'
SEL_LOGIN_EMAIL   = '#username'
SEL_LOGIN_PASS    = '#password'
SEL_FEED_POST     = '[data-id], [class*="feed-shared-update"]'
SEL_SIGNED_IN     = '[data-control-name="nav.notifications"] , a[href*="/notifications/"]'
SEL_COOKIE_WALL   = 'button[action-type="ACCEPT"]'


# ---------------------------------------------------------------------------
# LinkedInWatcher
# ---------------------------------------------------------------------------

class LinkedInWatcher(BaseWatcher):
    """Monitors LinkedIn for new notifications using a persistent Playwright session.

    Two outputs:
        1. LINKEDIN_NOTIF_<id>.md  → /Needs_Action  (new notifications)
        2. LINKEDIN_DRAFT_<date>.md → /Plans         (AI-drafted post for manual review)

    The draft output requires HITL approval before any posting.
    This watcher NEVER posts to LinkedIn automatically.
    """

    def __init__(self, vault_path: str | Path) -> None:
        super().__init__(vault_path, check_interval=LI_CHECK_INTERVAL)

        # Domain-based folder: LinkedIn notifications go to Needs_Action/social/
        self.needs_action = self.vault_path / "Needs_Action" / "social"
        self.needs_action.mkdir(parents=True, exist_ok=True)

        self._id_tracker = IDTracker(Path(__file__).parent / ".state")
        LI_SESSION_PATH.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # BaseWatcher interface
    # ------------------------------------------------------------------

    def check_for_updates(self) -> list[dict]:
        """Read LinkedIn notifications using a persistent browser session.

        Returns list of notification dicts with keys:
            notif_id, text, timestamp, notif_type
        """
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

        results: list[dict] = []

        try:
            with sync_playwright() as pw:
                ctx = pw.chromium.launch_persistent_context(
                    str(LI_SESSION_PATH),
                    headless=LI_HEADLESS,
                    slow_mo=500,           # 500ms between actions — human-like
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        # Disable images to reduce bandwidth/fingerprinting
                        "--blink-settings=imagesEnabled=false",
                    ],
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                )

                page = ctx.pages[0] if ctx.pages else ctx.new_page()

                # Navigate to LinkedIn feed
                page.goto(LI_HOME_URL, wait_until="domcontentloaded", timeout=30_000)

                # Handle cookie consent banner if it appears
                try:
                    cookie_btn = page.query_selector(SEL_COOKIE_WALL)
                    if cookie_btn and cookie_btn.is_visible():
                        cookie_btn.click()
                        time.sleep(0.5)
                except Exception:
                    pass

                # Verify signed in
                try:
                    page.wait_for_selector(SEL_SIGNED_IN, timeout=15_000)
                except PWTimeout:
                    # Not signed in — check if on login page
                    if "login" in page.url or "checkpoint" in page.url:
                        if LI_HEADLESS:
                            print(
                                "[LinkedInWatcher] Not logged in (headless mode).\n"
                                "  Run first-time setup:\n"
                                "    LI_HEADLESS=false uv run python linkedin_watcher.py --setup"
                            )
                            ctx.close()
                            return []
                        else:
                            print("[LinkedInWatcher] Please log in manually in the browser...")
                            # Wait for user to log in
                            try:
                                page.wait_for_selector(SEL_SIGNED_IN, timeout=600_000)
                                print("[LinkedInWatcher] Login detected! Session saved.")
                            except PWTimeout:
                                print("[LinkedInWatcher] Login timeout — closing.")
                                ctx.close()
                                return []

                # Navigate to notifications page
                time.sleep(1.0)  # pause before next navigation
                page.goto(LI_NOTIF_URL, wait_until="domcontentloaded", timeout=20_000)
                time.sleep(1.5)

                # Read notification items
                notif_items = page.query_selector_all(SEL_NOTIF_ITEM)
                count = 0

                for item in notif_items[:LI_MAX_NOTIFS]:
                    if count >= LI_MAX_NOTIFS:
                        break
                    try:
                        # Extract notification text
                        text_el = item.query_selector(SEL_NOTIF_TEXT)
                        if not text_el:
                            # Fallback: use full item text
                            raw_text = item.inner_text().strip()
                        else:
                            raw_text = text_el.inner_text().strip()

                        if not raw_text or len(raw_text) < 5:
                            continue

                        # Extract timestamp
                        time_el = item.query_selector(SEL_NOTIF_TIME)
                        ts_attr = time_el.get_attribute("datetime") if time_el else ""
                        ts = ts_attr or datetime.now(timezone.utc).isoformat()

                        # Detect notification type from text
                        text_lower = raw_text.lower()
                        if "liked" in text_lower:
                            notif_type = "like"
                        elif "comment" in text_lower:
                            notif_type = "comment"
                        elif "connection" in text_lower or "connect" in text_lower:
                            notif_type = "connection"
                        elif "mention" in text_lower or "tagged" in text_lower:
                            notif_type = "mention"
                        elif "job" in text_lower:
                            notif_type = "job"
                        else:
                            notif_type = "other"

                        # Generate stable ID from content hash
                        notif_id = hashlib.sha256(
                            (raw_text[:100] + ts).encode()
                        ).hexdigest()[:12]

                        results.append({
                            "notif_id":   notif_id,
                            "text":       raw_text[:500],  # cap length
                            "timestamp":  ts,
                            "notif_type": notif_type,
                        })
                        count += 1

                        # Human-like delay between reading items
                        time.sleep(0.3)

                    except Exception as e:
                        log_action(
                            self.logs,
                            "linkedin_notif_read_error",
                            "LinkedInWatcher",
                            result="error",
                            details=str(e),
                        )

                ctx.close()

        except Exception as exc:
            log_action(
                self.logs,
                "linkedin_watcher_error",
                "LinkedInWatcher",
                result="error",
                details=str(exc),
            )

        return results

    def create_action_file(self, item: dict) -> Path:
        """Write LINKEDIN_NOTIF_<id>.md to /Needs_Action.

        Args:
            item: Notification dict from check_for_updates().

        Returns:
            Path to the created (or skipped) action file.
        """
        notif_id: str   = item["notif_id"]
        text: str       = item.get("text", "")
        ts: str         = item.get("timestamp", datetime.now(timezone.utc).isoformat())
        notif_type: str = item.get("notif_type", "other")

        filepath = self.needs_action / f"LINKEDIN_NOTIF_{notif_id}.md"

        # De-duplicate
        if self._id_tracker.is_processed("linkedin", notif_id):
            return filepath

        # Only write action files for high-value notification types
        important_types = {"mention", "comment", "connection"}
        if notif_type not in important_types:
            # Log silently skipped notifications
            log_action(
                self.logs,
                "linkedin_notif_skipped",
                "LinkedInWatcher",
                result="filtered",
                details=f"notif_id={notif_id} | type={notif_type} (low priority)",
            )
            self._id_tracker.mark_processed("linkedin", notif_id)
            return filepath

        content = f"""---
type: linkedin_notification
notif_id: {notif_id}
notif_type: {notif_type}
received_at: {ts}
status: needs_action
priority: {"high" if notif_type in {"mention"} else "normal"}
source: LinkedIn
processed_by: null
---

## Notification

{text}

## Suggested Actions

- [ ] Review this LinkedIn {notif_type}
- [ ] Decide: respond, like, or ignore
- [ ] If response needed: draft reply manually in LinkedIn

## Note

Respond manually in LinkedIn — this system does not post to LinkedIn automatically.
"""

        if DRY_RUN:
            log_action(
                self.logs,
                "linkedin_notif_detected",
                "LinkedInWatcher",
                destination=str(filepath),
                result="dry_run",
                details=f"notif_id={notif_id} | type={notif_type}",
            )
        else:
            filepath.write_text(content, encoding="utf-8")
            self._id_tracker.mark_processed("linkedin", notif_id)
            log_action(
                self.logs,
                "linkedin_notif_processed",
                "LinkedInWatcher",
                destination=str(filepath),
                result="success",
                details=f"notif_id={notif_id} | type={notif_type}",
            )

        return filepath

    # ------------------------------------------------------------------
    # Draft post generation (HITL — never auto-posts)
    # ------------------------------------------------------------------

    def generate_post_draft(self) -> Path | None:
        """Generate a LinkedIn post draft in /Plans based on Business_Goals.md.

        Reads Business_Goals.md and recent Done/ activity to draft a
        professional post.  The draft is placed in /Plans for HITL review.
        NEVER posts automatically — user must manually copy-paste to LinkedIn.

        Returns:
            Path to the draft file, or None if generation was skipped.
        """
        if not LI_GENERATE_DRAFTS:
            return None

        # Read Business_Goals.md for context
        goals_path = self.vault_path / "Business_Goals.md"
        goals_text = ""
        if goals_path.exists():
            goals_text = goals_path.read_text(encoding="utf-8")[:2000]

        # Read recent Done/ items for "wins" context
        recent_wins: list[str] = []
        if self.done.exists():
            done_files = sorted(self.done.glob("*.md"), reverse=True)[:5]
            for f in done_files:
                try:
                    content = f.read_text(encoding="utf-8")
                    first_line = content.splitlines()[0] if content.strip() else ""
                    recent_wins.append(f"- {first_line.strip('#').strip()}")
                except OSError:
                    pass

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        topics_str = ", ".join(POST_TOPICS)
        wins_str = "\n".join(recent_wins) if recent_wins else "- No recent activity logged"

        draft_path = self.plans / f"LINKEDIN_DRAFT_{today}.md"

        # Don't overwrite today's draft if it already exists
        if draft_path.exists():
            return draft_path

        draft_content = f"""---
type: linkedin_post
status: draft
created_at: {datetime.now(timezone.utc).isoformat()}
topics: [{topics_str}]
review_required: true
---

## Draft LinkedIn Post

> ⚠️  REVIEW REQUIRED — Edit the post content below, then move this file
> to `/Approved`. The system will auto-post via Playwright at a randomised
> time within the configured posting window (default 09:00–18:00).
> A 23-hour minimum gap between posts is enforced automatically.

---

<!-- INSTRUCTIONS FOR CLAUDE (fte-linkedin-draft skill):
     Use the Business Goals and recent wins below to draft a professional
     LinkedIn post (150-300 words). Topics: {topics_str}.
     Make it specific, insightful, and authentically human-sounding.
     End with a question to drive engagement.
     Suggest 3-5 relevant hashtags.
-->

**Business Context:**
{goals_text[:800] if goals_text else "(Business_Goals.md not found — create it for better drafts)"}

**Recent Wins:**
{wins_str}

## Draft Post

[Invoke `/fte-linkedin-draft` skill to generate the actual post content here]

## To Approve

1. Invoke `/fte-linkedin-draft` to fill in the Draft Post section above
2. Review and edit the post content
3. Move this file to `/Approved` — the orchestrator will schedule and auto-post it
4. Dashboard will show: "LinkedIn post scheduled for HH:MM"
5. File moves to `/Done` automatically once posted
"""

        if DRY_RUN:
            log_action(
                self.logs,
                "linkedin_draft_created",
                "LinkedInWatcher",
                destination=str(draft_path),
                result="dry_run",
                details=f"topics={topics_str}",
            )
        else:
            draft_path.write_text(draft_content, encoding="utf-8")
            log_action(
                self.logs,
                "linkedin_draft_created",
                "LinkedInWatcher",
                destination=str(draft_path),
                result="success",
                details=f"topics={topics_str}",
            )

        return draft_path

    # ------------------------------------------------------------------
    # Lifecycle — override run() to also generate drafts
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Polling loop: read notifications + optionally generate post drafts."""
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

                # Generate a draft post if due (once per day)
                if LI_GENERATE_DRAFTS:
                    try:
                        self.generate_post_draft()
                    except Exception as e:
                        self._log_error("run.generate_post_draft", e)

            except Exception as e:
                self._log_error("run.check_for_updates", e)

            # Interruptible sleep (30-min default)
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)

    def start(self):
        """Start the LinkedIn watcher."""
        print(
            f"[LinkedInWatcher] Starting | session={LI_SESSION_PATH} "
            f"| headless={LI_HEADLESS} | interval={LI_CHECK_INTERVAL}s "
            f"(min 30min enforced)"
        )
        return super().start()

    def stop(self) -> None:
        """Stop the polling loop."""
        super().stop()
        log_action(
            self.logs,
            "linkedin_watcher_stopped",
            "LinkedInWatcher",
            result="success",
        )


# ---------------------------------------------------------------------------
# CLI entry point — first-time session setup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="LinkedIn Watcher")
    parser.add_argument("--setup", action="store_true", help="Run non-headless for manual login")
    parser.add_argument("--draft", action="store_true", help="Generate a post draft and exit")
    args = parser.parse_args()

    vault = Path(__file__).parent / "AI_Employee_Vault"
    w = LinkedInWatcher(vault)

    if args.setup:
        os.environ["LI_HEADLESS"] = "false"
        print("[LinkedInWatcher] Setup mode — browser will open for manual login")
        print(f"[LinkedInWatcher] Session will be saved to: {LI_SESSION_PATH}")
        results = w.check_for_updates()
        print(f"[LinkedInWatcher] Setup complete. Found {len(results)} notification(s).")
        sys.exit(0)

    elif args.draft:
        print("[LinkedInWatcher] Draft mode — generating LinkedIn post draft")
        path = w.generate_post_draft()
        print(f"[LinkedInWatcher] Draft written to: {path}")
        sys.exit(0)

    else:
        print("Usage:")
        print("  uv run python linkedin_watcher.py --setup   (first-time login)")
        print("  uv run python linkedin_watcher.py --draft   (generate post draft)")
        print("  Or import LinkedInWatcher in run_watchers.py")
