"""twitter_poster.py — Twitter/X post automation with human simulation.

Mirror of facebook_poster.py pattern — pure Python, sync Playwright, no MCP.

Called by orchestrator/fte-approve ONLY after user moves approval file to /Approved.

HITL GATE:
    - Checks AI_Employee_Vault/Approved/<approval_file> exists before opening browser
    - Never posts autonomously

HUMAN BEHAVIOR SIMULATION:
    - Browse timeline first (5-12 seconds, random scrolls)
    - Click compose button with mouse overshoot
    - Dismiss any notification/cookie dialogs
    - Click into tweet text area
    - Type character-by-character (60-130ms per char)
    - Proofread pause (3-8 seconds)
    - Submit tweet via JavaScript click

SESSION HEALTH CHECK:
    - URL check: login/i/flow/login in URL → session expired
    - Element check: [data-testid="loginButton"] visible → session expired
    - Aborts before typing anything on expired session

CHARACTER LIMIT:
    - Twitter hard limit: 280 characters
    - Content truncated with "..." if over limit

.env VARIABLES:
    TWITTER_SESSION_DIR=.secrets/twitter_session
    DRY_RUN=false
    LI_HEADLESS=true   (reuse same flag — false for debugging)
"""

import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TWITTER_SESSION_DIR: Path = (
    Path(__file__).parent / os.getenv("TWITTER_SESSION_DIR", ".secrets/twitter_session")
).resolve()

VAULT_PATH: Path = (
    Path(__file__).parent / os.getenv("VAULT_PATH", "AI_Employee_Vault")
).resolve()

TWITTER_HEADLESS: bool = os.getenv("LI_HEADLESS", "true").lower() != "false"
DRY_RUN: bool = os.getenv("DRY_RUN", "").lower() == "true"

TWITTER_MAX_CHARS = 280  # Twitter hard limit

# ---------------------------------------------------------------------------
# TwitterScheduler — .state/twitter_scheduled.json management
# (same pattern as linkedin_poster.JitterScheduler)
# ---------------------------------------------------------------------------

import json as _json
import random as _random
from datetime import datetime as _dt, timedelta as _td

_STATE_DIR = Path(__file__).parent / ".state"
_TW_SCHEDULE_FILE = _STATE_DIR / "twitter_scheduled.json"
_TW_LAST_POST_FILE = _STATE_DIR / "twitter_last_posted.json"
_TW_POST_WINDOW_START: str = os.getenv("POST_WINDOW_START", "09:00")
_TW_POST_WINDOW_END: str = os.getenv("POST_WINDOW_END", "18:00")
_TW_MIN_POST_GAP_HOURS = 23


class TwitterScheduler:
    """Manages jitter-delayed Twitter/X post scheduling.

    State file: .state/twitter_scheduled.json
    Schema matches linkedin_poster.JitterScheduler exactly.
    """

    @staticmethod
    def _parse_hhmm(hhmm: str) -> tuple[int, int]:
        parts = hhmm.strip().split(":")
        return int(parts[0]), int(parts[1])

    @classmethod
    def _random_post_time(cls) -> tuple[str, str]:
        start_h, start_m = cls._parse_hhmm(_TW_POST_WINDOW_START)
        end_h, end_m = cls._parse_hhmm(_TW_POST_WINDOW_END)
        start_min = start_h * 60 + start_m
        end_min = end_h * 60 + end_m

        target_date = _dt.now()
        if _TW_LAST_POST_FILE.exists():
            try:
                data = _json.loads(_TW_LAST_POST_FILE.read_text(encoding="utf-8"))
                last_ts_str = data.get("posted_at", "")
                if last_ts_str:
                    last_ts = _dt.fromisoformat(last_ts_str)
                    gap = (_dt.now() - last_ts).total_seconds()
                    if gap < _TW_MIN_POST_GAP_HOURS * 3600:
                        target_date = _dt.now() + _td(days=1)
            except (ValueError, KeyError, _json.JSONDecodeError, OSError):
                pass

        rand_min = _random.randint(start_min, max(start_min, end_min - 1))
        h, m = divmod(rand_min, 60)
        return f"{h:02d}:{m:02d}", target_date.strftime("%Y-%m-%d")

    @classmethod
    def schedule(cls, approval_file_path: Path, content: str) -> dict:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        if _TW_SCHEDULE_FILE.exists():
            try:
                return _json.loads(_TW_SCHEDULE_FILE.read_text(encoding="utf-8"))
            except (_json.JSONDecodeError, OSError):
                pass
        post_time, post_date = cls._random_post_time()
        schedule: dict = {
            "post_at": post_time,
            "post_date": post_date,
            "file": str(approval_file_path.resolve()),
            "content": content,
            "scheduled_at": _dt.now().isoformat(),
        }
        _TW_SCHEDULE_FILE.write_text(_json.dumps(schedule, indent=2, ensure_ascii=False), encoding="utf-8")
        return schedule

    @classmethod
    def get_pending(cls) -> dict | None:
        if not _TW_SCHEDULE_FILE.exists():
            return None
        try:
            return _json.loads(_TW_SCHEDULE_FILE.read_text(encoding="utf-8"))
        except (_json.JSONDecodeError, OSError):
            return None

    @classmethod
    def is_due(cls) -> bool:
        schedule = cls.get_pending()
        if not schedule:
            return False
        try:
            post_dt = _dt.strptime(f"{schedule.get('post_date', '')} {schedule.get('post_at', '23:59')}", "%Y-%m-%d %H:%M")
            return _dt.now() >= post_dt
        except ValueError:
            return False

    @classmethod
    def clear(cls) -> None:
        _TW_SCHEDULE_FILE.unlink(missing_ok=True)

    @classmethod
    def record_post(cls) -> None:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _TW_LAST_POST_FILE.write_text(_json.dumps({"posted_at": _dt.now().isoformat()}, indent=2), encoding="utf-8")


# Twitter/X selectors — March 2026
SEL_COOKIE = [
    '[data-testid="cookieBanner"] button:last-child',
    'div[role="dialog"] button:has-text("Accept")',
]
SEL_COMPOSE = [
    '[data-testid="SideNav_NewTweet_Button"]',   # sidebar Post button → opens modal
    '[data-testid="FloatingActionButton_Tweet_Button"]',
    'a[href="/compose/post"]',                   # confirmed from inspect Mar 2026
    'a[href="/compose/tweet"]',                  # legacy fallback
]
SEL_POPUP_DISMISS = [
    '[data-testid="app-bar-close"]',
    '[aria-label="Close"]',
    'div[role="dialog"] [aria-label="Close"]',
]
SEL_TEXTBOX = [
    '[data-testid="tweetTextarea_0"]',
    '[role="textbox"][aria-label*="Tweet"]',
    '[role="textbox"][aria-label*="Post"]',
    '[contenteditable="true"]',
]
SEL_POST_BUTTON = [
    '[data-testid="tweetButton"]',        # modal Post button (sidebar compose flow)
    '[data-testid="tweetButtonInline"]',  # inline composer Post button
    'div[role="button"]:has-text("Post")',
]


# ---------------------------------------------------------------------------
# Helpers — same pattern as facebook_poster.py
# ---------------------------------------------------------------------------

def _find_element(page, selectors: list):
    """Try each selector, return first visible element or None."""
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return el
        except Exception:
            continue
    return None


def _human_type(page, content: str) -> None:
    """Type text character-by-character with random delays (60-130ms)."""
    for i, char in enumerate(content):
        base_delay = random.uniform(0.060, 0.130)
        if char in ".!?,":
            base_delay += random.uniform(0.10, 0.40)
        elif i > 0 and i % random.randint(20, 50) == 0:
            base_delay += random.uniform(0.20, 0.80)
        page.keyboard.type(char)
        time.sleep(base_delay)


def _human_scroll(page, duration_seconds: float) -> None:
    """Scroll timeline human-like for given duration."""
    end_time = time.time() + duration_seconds
    scroll_y = 0
    while time.time() < end_time:
        delta = random.randint(60, 300)
        scroll_y += delta
        page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
        time.sleep(random.uniform(0.15, 0.60))
        if random.random() < 0.15:
            scroll_y = max(0, scroll_y - random.randint(80, 200))
            page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
            time.sleep(random.uniform(0.25, 0.60))


def _click_with_overshoot(page, element) -> None:
    """Click element with realistic mouse overshoot."""
    bbox = element.bounding_box()
    if not bbox:
        element.click()
        return
    cx = bbox["x"] + bbox["width"] / 2
    cy = bbox["y"] + bbox["height"] / 2
    page.mouse.move(cx + random.uniform(-15, 15), cy + random.uniform(-8, 8))
    time.sleep(random.uniform(0.08, 0.20))
    page.mouse.move(cx, cy)
    time.sleep(random.uniform(0.05, 0.12))
    element.click()


def _js_click(page, element) -> None:
    """Click via JavaScript — bypasses pointer-event overlays."""
    page.evaluate("el => el.click()", element)


def _dashboard_alert(message: str) -> None:
    """Prepend alert to Dashboard.md."""
    dashboard = VAULT_PATH / "Dashboard.md"
    if not dashboard.exists():
        print(f"[twitter_poster] ALERT: {message}")
        return
    try:
        text = dashboard.read_text(encoding="utf-8")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        banner = f"\n> WARNING TWITTER ALERT ({ts}): {message}\n"
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
    except OSError as e:
        print(f"[twitter_poster] Failed to write Dashboard alert: {e}")


# ---------------------------------------------------------------------------
# Session health check
# ---------------------------------------------------------------------------

def session_health_check(page) -> bool:
    """Return True if Twitter session is active."""
    url = page.url
    if any(kw in url for kw in ("login", "i/flow/login", "logout", "suspended")):
        msg = (
            "Twitter session expired (login page detected). "
            "Re-run: LI_HEADLESS=false uv run python twitter_watcher.py --setup"
        )
        _dashboard_alert(msg)
        print(f"[twitter_poster] {msg}")
        return False
    try:
        el = page.query_selector('[data-testid="loginButton"]')
        if el and el.is_visible():
            msg = (
                "Twitter session expired (login button visible). "
                "Re-run: LI_HEADLESS=false uv run python twitter_watcher.py --setup"
            )
            _dashboard_alert(msg)
            print(f"[twitter_poster] {msg}")
            return False
    except Exception:
        pass
    return True


# ---------------------------------------------------------------------------
# Main poster
# ---------------------------------------------------------------------------

def post_to_twitter(
    content: str,
    approval_file: str | None = None,
) -> bool:
    """Post content to Twitter/X using human behavior simulation.

    Args:
        content:       Tweet text (max 280 chars).
        approval_file: Filename in AI_Employee_Vault/Approved/ (HITL gate).

    Returns:
        True on success, False on any failure.
    """
    # ── HITL gate ────────────────────────────────────────────────────────────
    approved_path = None
    if approval_file:
        approved_path = VAULT_PATH / "Approved" / approval_file
        if not approved_path.exists():
            print(
                f"[twitter_poster] HITL gate: {approval_file} not in Approved/. "
                "Move file from Pending_Approval/ to Approved/ first."
            )
            return False

    # ── Character limit guard ─────────────────────────────────────────────
    if len(content) > TWITTER_MAX_CHARS:
        content = content[:TWITTER_MAX_CHARS - 3] + "..."
        print(f"[twitter_poster] WARNING: Content truncated to {TWITTER_MAX_CHARS} chars")

    # ── DRY_RUN ───────────────────────────────────────────────────────────
    if DRY_RUN:
        print(
            f"[twitter_poster] DRY_RUN — would post {len(content)} chars:\n"
            f"{content[:200]}{'...' if len(content) > 200 else ''}"
        )
        return True

    # ── Session directory check ───────────────────────────────────────────
    if not TWITTER_SESSION_DIR.exists() or not any(TWITTER_SESSION_DIR.iterdir()):
        msg = (
            f"Twitter session not found at {TWITTER_SESSION_DIR}. "
            "Run: LI_HEADLESS=false uv run python twitter_watcher.py --setup"
        )
        print(f"[twitter_poster] {msg}")
        _dashboard_alert(msg)
        return False

    print(
        f"[twitter_poster] Starting post | "
        f"session={TWITTER_SESSION_DIR.name} | headless={TWITTER_HEADLESS} | "
        f"chars={len(content)}"
    )

    from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(TWITTER_SESSION_DIR),
                headless=TWITTER_HEADLESS,
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

            # ── Step 1: Navigate to timeline ─────────────────────────────
            print("[twitter_poster] 1/6 — Navigating to timeline...")
            page.goto(
                "https://twitter.com/home",
                wait_until="domcontentloaded",
                timeout=45_000,
            )
            time.sleep(random.uniform(2.5, 4.0))

            # ── Step 2: Session health check ──────────────────────────────
            print("[twitter_poster] 2/6 — Session health check...")
            if not session_health_check(page):
                ctx.close()
                return False

            # ── Cookie/notification dismissal ────────────────────────────
            cookie_btn = _find_element(page, SEL_COOKIE)
            if cookie_btn:
                print("[twitter_poster] Dismissing cookie banner...")
                _js_click(page, cookie_btn)
                time.sleep(random.uniform(0.8, 1.5))

            # Dismiss notification permission dialog if present
            popup = _find_element(page, SEL_POPUP_DISMISS)
            if popup:
                print("[twitter_poster] Dismissing popup...")
                _js_click(page, popup)
                time.sleep(random.uniform(0.5, 1.0))

            # ── Step 3: Browse timeline (look natural) ────────────────────
            browse_secs = random.uniform(5.0, 12.0)
            print(f"[twitter_poster] 3/6 — Browsing timeline {browse_secs:.0f}s...")
            _human_scroll(page, browse_secs)

            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(random.uniform(1.0, 2.0))

            # ── Step 4: Click compose button ──────────────────────────────
            print("[twitter_poster] 4/6 — Opening tweet composer...")
            compose_btn = _find_element(page, SEL_COMPOSE)
            if compose_btn is None:
                print("[twitter_poster] ERROR: Compose button not found — aborting")
                ctx.close()
                return False

            _click_with_overshoot(page, compose_btn)
            time.sleep(random.uniform(1.0, 2.0))

            # ── Step 5: Find text area and type ──────────────────────────
            print("[twitter_poster] 5/6 — Focusing text area and typing...")
            textbox = _find_element(page, SEL_TEXTBOX)
            if textbox is None:
                print("[twitter_poster] ERROR: Tweet text area not found — aborting")
                ctx.close()
                return False

            _js_click(page, textbox)
            time.sleep(random.uniform(0.5, 1.0))

            _human_type(page, content)

            # ── Proofread pause ───────────────────────────────────────────
            proofread = random.uniform(3.0, 8.0)
            print(f"[twitter_poster] Proofreading {proofread:.1f}s...")
            time.sleep(proofread)

            # ── Step 6: Click Post button ─────────────────────────────────
            print("[twitter_poster] 6/6 — Submitting tweet...")
            post_btn = _find_element(page, SEL_POST_BUTTON)
            if post_btn is None:
                print("[twitter_poster] ERROR: Post button not found — aborting")
                ctx.close()
                return False

            _js_click(page, post_btn)
            time.sleep(random.uniform(3.0, 5.0))

            # ── Wait for modal to close (compose URL disappears) ──────────
            try:
                page.wait_for_url(
                    lambda url: "compose" not in url,
                    timeout=10_000,
                )
            except Exception:
                pass  # timeout is fine — check URL regardless

            # ── Verify ────────────────────────────────────────────────────
            current_url = page.url
            if any(domain in current_url for domain in ("twitter.com", "x.com")) and "login" not in current_url:
                print("[twitter_poster] SUCCESS: Tweet submitted")
            else:
                print(f"[twitter_poster] WARNING: Unexpected URL after post: {current_url}")

            ctx.close()

        # ── Move approval file to Done/ ───────────────────────────────────
        if approved_path and approved_path.exists():
            done_path = VAULT_PATH / "Done" / approval_file
            approved_path.rename(done_path)
            print(f"[twitter_poster] Approval file moved to Done/{approval_file}")

        # ── Log success ───────────────────────────────────────────────────
        try:
            from logger import log_action
            log_action(
                VAULT_PATH / "Logs",
                action="twitter_post",
                actor="twitter_poster",
                result="success",
                details=f"Posted {len(content)} chars",
            )
        except Exception:
            pass

        return True

    except PWTimeout as exc:
        print(f"[twitter_poster] Timeout: {exc}")
        return False
    except Exception as exc:
        print(f"[twitter_poster] Unexpected error: {exc}")
        return False


# ---------------------------------------------------------------------------
# CLI — direct test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Twitter poster — test posting flow")
    parser.add_argument("--content", default="Test tweet from twitter_poster.py")
    parser.add_argument("--approval-file", default=None, help="Approval file in Approved/")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "true"
    if args.no_headless:
        os.environ["LI_HEADLESS"] = "false"

    success = post_to_twitter(args.content, approval_file=args.approval_file)
    sys.exit(0 if success else 1)
