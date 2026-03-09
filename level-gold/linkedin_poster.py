"""linkedin_poster.py — LinkedIn post automation with jitter scheduling and human simulation.

This module is the "hands" for LinkedIn posting. It is ONLY called by the orchestrator
after a user has explicitly approved a LINKEDIN_DRAFT_*.md by moving it to /Approved.

STRICT HITL GATE:
    - This module NEVER calls itself autonomously.
    - The orchestrator calls post_scheduled() only when:
      (a) .state/linkedin_scheduled.json exists
      (b) The scheduled post_at time has passed
      (c) The approval file was explicitly moved to /Approved by the user

JITTER SYSTEM:
    - Post time is randomized within POST_WINDOW_START–POST_WINDOW_END (default 09:00–18:00)
    - A 23-hour minimum gap is enforced between consecutive posts
    - Schedule persisted to .state/linkedin_scheduled.json

HUMAN BEHAVIOR SIMULATION (primary mitigation against account restriction):
    - Browse feed first (15–45 random seconds) with variable scroll speed
    - Character-by-character typing (60–130ms per character + micro-pauses)
    - Proofread pause (4–10 random seconds) before clicking Post
    - Mouse movement overshoot on buttons to simulate real cursor paths

SESSION HEALTH CHECK:
    - On every Playwright open: detect if login page is visible
    - If yes: write alert to Dashboard.md and abort immediately
    - Prevents bot from typing into wrong fields on expired sessions — major bot-detection red flag

BURNER ACCOUNT STRATEGY:
    - LINKEDIN_SESSION_DIR env var points to the Playwright persistent session directory
    - Set .secrets/linkedin_burner_session during testing (default)
    - Graduate to .secrets/linkedin_session for primary account after ≥2 weeks of stable operation

.env VARIABLES:
    LINKEDIN_SESSION_DIR=.secrets/linkedin_burner_session  # Playwright session directory
    POST_WINDOW_START=09:00    # Earliest post time (24h format, inclusive)
    POST_WINDOW_END=18:00      # Latest post time (24h format, exclusive)
    LI_HEADLESS=true           # Set false for debugging / first setup
    DRY_RUN=false              # Set true to log actions without posting
"""

import json
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from logger import log_action

load_dotenv(Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Session directory: LINKEDIN_SESSION_DIR takes priority over legacy LI_SESSION_PATH
_SESSION_RAW: str = os.getenv(
    "LINKEDIN_SESSION_DIR",
    os.getenv("LI_SESSION_PATH", ".secrets/linkedin_session"),
)
LINKEDIN_SESSION_DIR: Path = (Path(__file__).parent / _SESSION_RAW).resolve()

LI_HEADLESS: bool   = os.getenv("LI_HEADLESS", "true").lower() != "false"
DRY_RUN: bool       = os.getenv("DRY_RUN", "").lower() == "true"

POST_WINDOW_START: str = os.getenv("POST_WINDOW_START", "09:00")
POST_WINDOW_END: str   = os.getenv("POST_WINDOW_END", "18:00")

MIN_POST_GAP_HOURS = 23       # enforce 23h minimum between consecutive posts
LINKEDIN_POST_MAX_CHARS = 3_000  # LinkedIn's hard character limit for posts

# State files (gitignored via .state/ pattern)
STATE_DIR      = Path(__file__).parent / ".state"
SCHEDULE_FILE  = STATE_DIR / "linkedin_scheduled.json"
LAST_POST_FILE = STATE_DIR / "linkedin_last_posted.json"

# LinkedIn selectors — early 2026; may need updating as LinkedIn evolves
SEL_SIGNED_IN   = 'a[href*="/notifications/"]'
SEL_FEED_POST   = (
    'button.artdeco-button:has-text("Start a post"),'
    ' .share-box-feed-entry__trigger,'
    ' [data-control-name="create_post_action_bar"]'
)
SEL_EDITOR      = '.ql-editor, [contenteditable="true"], div[role="textbox"]'
SEL_SUBMIT      = (
    'button.share-actions__primary-action,'
    ' button:has-text("Post"),'
    ' [data-control-name="submit_post"]'
)
SEL_COOKIE_WALL = 'button[action-type="ACCEPT"]'


# ---------------------------------------------------------------------------
# JitterScheduler — .state/linkedin_scheduled.json management
# ---------------------------------------------------------------------------

class JitterScheduler:
    """Manages one-per-day jitter-delayed LinkedIn post scheduling.

    Schedule file schema (.state/linkedin_scheduled.json):
    {
        "post_at": "14:37",               -- HH:MM on post_date
        "post_date": "2026-02-20",        -- YYYY-MM-DD
        "file": "<absolute approval path>", -- approval file that triggered this
        "content": "<post text>",         -- text to post to LinkedIn
        "scheduled_at": "<ISO timestamp>" -- when the approval was received
    }
    """

    @staticmethod
    def _parse_hhmm(hhmm: str) -> tuple[int, int]:
        parts = hhmm.strip().split(":")
        return int(parts[0]), int(parts[1])

    @classmethod
    def _random_post_time(cls) -> tuple[str, str]:
        """Return (HH:MM, YYYY-MM-DD) for a randomized post time.

        Enforces:
        - Time within POST_WINDOW_START–POST_WINDOW_END
        - 23-hour minimum gap from last post (schedules for tomorrow if gap not met)
        """
        start_h, start_m = cls._parse_hhmm(POST_WINDOW_START)
        end_h, end_m     = cls._parse_hhmm(POST_WINDOW_END)
        start_min = start_h * 60 + start_m
        end_min   = end_h * 60 + end_m

        # Check last post time — enforce 23h gap (all comparisons in naive local time)
        target_date = datetime.now()
        if LAST_POST_FILE.exists():
            try:
                data = json.loads(LAST_POST_FILE.read_text(encoding="utf-8"))
                last_ts_str = data.get("posted_at", "")
                if last_ts_str:
                    last_ts = datetime.fromisoformat(last_ts_str)
                    gap = (datetime.now() - last_ts).total_seconds()
                    if gap < MIN_POST_GAP_HOURS * 3600:
                        # Shift to tomorrow to respect gap
                        target_date = datetime.now() + timedelta(days=1)
            except (ValueError, KeyError, json.JSONDecodeError, OSError):
                pass

        rand_min = random.randint(start_min, max(start_min, end_min - 1))
        h, m = divmod(rand_min, 60)
        date_str = target_date.strftime("%Y-%m-%d")
        return f"{h:02d}:{m:02d}", date_str

    @classmethod
    def schedule(cls, approval_file_path: Path, content: str) -> dict:
        """Schedule a LinkedIn post for a jittered future time.

        Called by ApprovalWatcher when type=linkedin_post is approved.
        Writes .state/linkedin_scheduled.json.

        Args:
            approval_file_path: Path to the approval file in /Approved.
            content: Post text extracted from the approval file.

        Returns:
            The schedule dict that was written.
        """
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        # Guard: don't overwrite an existing pending schedule
        if SCHEDULE_FILE.exists():
            try:
                return json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        post_time, post_date = cls._random_post_time()
        schedule: dict = {
            "post_at": post_time,
            "post_date": post_date,
            "file": str(approval_file_path.resolve()),
            "content": content,
            "scheduled_at": datetime.now().isoformat(),
        }
        SCHEDULE_FILE.write_text(
            json.dumps(schedule, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return schedule

    @classmethod
    def get_pending(cls) -> Optional[dict]:
        """Return the pending schedule dict, or None if no schedule exists."""
        if not SCHEDULE_FILE.exists():
            return None
        try:
            return json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    @classmethod
    def is_due(cls) -> bool:
        """Return True if the scheduled post time has arrived or passed."""
        schedule = cls.get_pending()
        if not schedule:
            return False
        post_date_str = schedule.get("post_date", "")
        post_time_str = schedule.get("post_at", "23:59")
        try:
            post_dt = datetime.strptime(f"{post_date_str} {post_time_str}", "%Y-%m-%d %H:%M")
            return datetime.now() >= post_dt
        except ValueError:
            return False

    @classmethod
    def clear(cls) -> None:
        """Remove the schedule file after a successful post."""
        SCHEDULE_FILE.unlink(missing_ok=True)

    @classmethod
    def record_post(cls) -> None:
        """Record timestamp of the last successful post (for 23h gap enforcement)."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        LAST_POST_FILE.write_text(
            json.dumps(
                {"posted_at": datetime.now().isoformat()},
                indent=2,
            ),
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

def extract_post_content(file_text: str) -> str:
    """Extract the actual LinkedIn post text from a draft/approval file.

    Looks for content under the '## Draft Post' section heading.
    Strips blockquote review notes (lines starting with '>') and
    separator lines ('---'). Returns the clean post text.

    Args:
        file_text: Full text content of the draft file.

    Returns:
        The extracted post text, stripped of markdown metadata.
    """
    lines = file_text.splitlines()
    in_post_section = False
    content_lines: list[str] = []

    for line in lines:
        if line.strip().startswith("## Draft Post"):
            in_post_section = True
            continue

        if in_post_section:
            # Stop at the next section heading
            if line.startswith("## "):
                break
            # Skip review instructions and separators
            if line.startswith(">") or line.strip() == "---":
                continue
            content_lines.append(line)

    result = "\n".join(content_lines).strip()

    # Fallback: if no '## Draft Post' section found, use entire body after frontmatter
    if not result:
        parts = file_text.split("---", 2)
        if len(parts) >= 3:
            result = parts[2].strip()

    return result


# ---------------------------------------------------------------------------
# Session health check
# ---------------------------------------------------------------------------

def session_health_check(page, vault_path: Optional[Path] = None) -> bool:
    """Return True if the LinkedIn session is active (user is logged in).

    Detects login page or login form visibility and:
    - Writes an alert banner to Dashboard.md
    - Returns False so the caller aborts immediately

    This prevents the Playwright bot from typing credentials into the
    wrong fields on an expired session — a major bot-detection signal.

    Args:
        page: Playwright page object (already navigated to LinkedIn).
        vault_path: Vault root for writing Dashboard alert.

    Returns:
        True if logged in, False if login page detected.
    """
    current_url = page.url
    login_indicators = ("login", "checkpoint", "authwall", "uas/login")
    if any(ind in current_url for ind in login_indicators):
        _dashboard_alert(
            vault_path,
            "LinkedIn SESSION EXPIRED — Login page detected. "
            "Re-authenticate: uv run python linkedin_watcher.py --setup",
        )
        return False

    # Secondary check: look for visible login form element
    try:
        el = page.query_selector("#username")
        if el and el.is_visible():
            _dashboard_alert(
                vault_path,
                "LinkedIn SESSION EXPIRED — Login form visible. "
                "Re-authenticate: uv run python linkedin_watcher.py --setup",
            )
            return False
    except Exception:
        pass

    return True


def _dashboard_alert(vault_path: Optional[Path], message: str) -> None:
    """Prepend an alert banner to Dashboard.md."""
    if vault_path is None:
        print(f"[linkedin_poster] ALERT: {message}")
        return

    dashboard = vault_path / "Dashboard.md"
    if not dashboard.exists():
        print(f"[linkedin_poster] ALERT: {message}")
        return

    try:
        text = dashboard.read_text(encoding="utf-8")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        banner = f"\n> ⚠️ LINKEDIN ALERT ({ts}): {message}\n"
        # Insert the alert after the first heading line
        lines = text.splitlines(keepends=True)
        new_lines: list[str] = []
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
    except OSError as e:
        print(f"[linkedin_poster] Failed to write Dashboard alert: {e}")


# ---------------------------------------------------------------------------
# Human behavior simulation helpers
# ---------------------------------------------------------------------------

def _human_type(page, content: str) -> None:
    """Type text into the currently focused element character-by-character.

    Delay per character: 60–130ms, with additional micro-pauses after
    punctuation and occasional mid-burst pauses to simulate reading/editing.

    Args:
        page: Playwright page object.
        content: Text to type.
    """
    for i, char in enumerate(content):
        base_delay = random.uniform(0.060, 0.130)

        # Extra pause after sentence-ending punctuation (thinking moment)
        if char in ".!?":
            base_delay += random.uniform(0.15, 0.55)

        # Occasional longer pause mid-text (proofreading while typing)
        elif i > 0 and i % random.randint(25, 60) == 0:
            base_delay += random.uniform(0.25, 1.0)

        page.keyboard.type(char)
        time.sleep(base_delay)


def _human_scroll(page, duration_seconds: float) -> None:
    """Scroll the page in a human-like variable pattern for the given duration.

    Uses small, randomised scroll increments with pauses to simulate a human
    browsing the LinkedIn feed before composing a post.

    Args:
        page: Playwright page object.
        duration_seconds: Total time to spend scrolling.
    """
    end_time = time.time() + duration_seconds
    scroll_y = 0

    while time.time() < end_time:
        delta = random.randint(60, 280)
        scroll_y += delta
        page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
        time.sleep(random.uniform(0.1, 0.55))

        # Occasionally scroll back up (humans re-read content)
        if random.random() < 0.12:
            scroll_y = max(0, scroll_y - random.randint(80, 220))
            page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
            time.sleep(random.uniform(0.3, 0.7))


def _click_with_overshoot(page, element) -> None:
    """Click an element after a realistic mouse-movement with slight overshoot.

    Real users rarely move the mouse directly to the center of a button —
    they overshoot by a few pixels then correct. This helper replicates that.

    Args:
        page: Playwright page object.
        element: Playwright element handle to click.
    """
    bbox = element.bounding_box()
    if not bbox:
        element.click()
        return

    center_x = bbox["x"] + bbox["width"] / 2
    center_y = bbox["y"] + bbox["height"] / 2

    # Overshoot position (random ±5–18px from center)
    over_x = center_x + random.uniform(-18, 18)
    over_y = center_y + random.uniform(-10, 10)

    page.mouse.move(over_x, over_y)
    time.sleep(random.uniform(0.08, 0.22))
    page.mouse.move(center_x, center_y)
    time.sleep(random.uniform(0.05, 0.15))
    element.click()


# ---------------------------------------------------------------------------
# LinkedIn poster — main entry point
# ---------------------------------------------------------------------------

def post_to_linkedin(
    content: str,
    session_dir: Path = LINKEDIN_SESSION_DIR,
    vault_path: Optional[Path] = None,
) -> bool:
    """Post *content* to LinkedIn using human behavior simulation.

    STRICT HITL CONTRACT: this function must only be called AFTER:
    1. The user manually moved a LINKEDIN_DRAFT_*.md to /Approved
    2. JitterScheduler.is_due() returns True

    Human simulation steps (primary bot-detection mitigation):
        1. Open feed (not post dialog) — looks like organic navigation
        2. Session health check — abort if login page detected
        3. Browse + scroll feed for 15–45 random seconds
        4. Click "Start a post" with mouse overshoot
        5. Type content character-by-character (60–130ms/char)
        6. Proofread pause (4–10 random seconds)
        7. Click "Post"

    Args:
        content: The post text to submit (plain text, no markdown).
        session_dir: Path to Playwright persistent session directory.
        vault_path: Vault root for Dashboard alerts on session errors.

    Returns:
        True on successful post, False on any failure.
    """
    # ── LinkedIn character limit guard ───────────────────────────────────────
    original_len = len(content)
    if original_len > LINKEDIN_POST_MAX_CHARS:
        content = content[: LINKEDIN_POST_MAX_CHARS - 3] + "..."
        truncation_msg = (
            f"Post truncated {original_len} → {len(content)} chars "
            f"(LinkedIn limit: {LINKEDIN_POST_MAX_CHARS})"
        )
        print(f"[linkedin_poster] WARNING: {truncation_msg}")
        if vault_path is not None:
            log_action(
                vault_path / "Logs",
                action="post_truncated",
                actor="linkedin_poster",
                result="warning",
                details=truncation_msg,
            )

    if DRY_RUN:
        print(
            f"[linkedin_poster] DRY_RUN — would post {len(content)} chars:\n"
            f"{content[:200]}{'...' if len(content) > 200 else ''}"
        )
        return True

    if not session_dir.exists():
        msg = (
            f"Session directory not found: {session_dir}\n"
            "Run: uv run python linkedin_watcher.py --setup"
        )
        print(f"[linkedin_poster] {msg}")
        _dashboard_alert(vault_path, msg)
        return False

    print(
        f"[linkedin_poster] Starting post | "
        f"session={session_dir.name} | headless={LI_HEADLESS}"
    )

    from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(session_dir),
                headless=LI_HEADLESS,
                slow_mo=200,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            # ── Step 1: Navigate to feed ─────────────────────────────────────
            print("[linkedin_poster] 1/7 — Navigating to feed...")
            page.goto(
                "https://www.linkedin.com/feed/",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            time.sleep(random.uniform(2.0, 4.0))

            # ── Step 2: Session health check ──────────────────────────────────
            print("[linkedin_poster] 2/7 — Session health check...")
            if not session_health_check(page, vault_path):
                ctx.close()
                return False

            # Accept cookie banner if shown
            try:
                cookie = page.query_selector(SEL_COOKIE_WALL)
                if cookie and cookie.is_visible():
                    cookie.click()
                    time.sleep(random.uniform(0.5, 1.0))
            except Exception:
                pass

            # ── Step 3: Browse feed (human simulation) ────────────────────────
            browse_secs = random.uniform(15.0, 45.0)
            print(f"[linkedin_poster] 3/7 — Browsing feed {browse_secs:.0f}s...")
            _human_scroll(page, browse_secs)

            # ── Step 4: Click "Start a post" ──────────────────────────────────
            # Scroll back to top — the "Start a post" button is at the top of the feed
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(random.uniform(1.0, 2.0))
            print("[linkedin_poster] 4/7 — Opening post dialog...")
            trigger = None
            for sel in [
                '[aria-label="Start a post"]',        # current LinkedIn DOM (2026)
                'button.artdeco-button:has-text("Start a post")',
                ".share-box-feed-entry__trigger",
                '[data-control-name="create_post_action_bar"]',
            ]:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        trigger = el
                        break
                except Exception:
                    continue

            if trigger is None:
                print("[linkedin_poster] ERROR: 'Start a post' button not found — aborting")
                ctx.close()
                return False

            _click_with_overshoot(page, trigger)
            time.sleep(random.uniform(1.5, 2.5))

            # ── Step 5: Locate editor ─────────────────────────────────────────
            editor = None
            for sel in [".ql-editor", '[contenteditable="true"]', 'div[role="textbox"]']:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        el.click()
                        time.sleep(random.uniform(0.3, 0.6))
                        editor = el
                        break
                except Exception:
                    continue

            if editor is None:
                print("[linkedin_poster] ERROR: Post editor not found — aborting")
                ctx.close()
                return False

            # ── Step 6: Type content character-by-character ───────────────────
            print(f"[linkedin_poster] 5/7 — Typing {len(content)} chars...")
            _human_type(page, content)

            # ── Step 7: Proofread pause ───────────────────────────────────────
            proofread = random.uniform(4.0, 10.0)
            print(f"[linkedin_poster] 6/7 — Proofreading {proofread:.1f}s...")
            time.sleep(proofread)

            # ── Step 8: Click Post ────────────────────────────────────────────
            print("[linkedin_poster] 7/7 — Submitting...")
            submit = None
            for sel in [
                "button.share-actions__primary-action",
                'button:has-text("Post")',
                '[data-control-name="submit_post"]',
            ]:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible() and el.is_enabled():
                        submit = el
                        break
                except Exception:
                    continue

            if submit is None:
                print("[linkedin_poster] ERROR: Post button not found — aborting")
                ctx.close()
                return False

            _click_with_overshoot(page, submit)
            # Wait for the feed to reload after posting
            time.sleep(random.uniform(3.0, 5.0))
            ctx.close()

        print("[linkedin_poster] Post submitted successfully")
        return True

    except PWTimeout as exc:
        print(f"[linkedin_poster] Timeout: {exc}")
        return False
    except Exception as exc:
        print(f"[linkedin_poster] Unexpected error: {exc}")
        return False


# ---------------------------------------------------------------------------
# CLI — manual test / dry-run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="LinkedIn poster — test the posting flow"
    )
    parser.add_argument("--content", default="Test post from linkedin_poster.py")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "true"

    vault = Path(__file__).parent / "AI_Employee_Vault"
    success = post_to_linkedin(args.content, vault_path=vault)
    sys.exit(0 if success else 1)
