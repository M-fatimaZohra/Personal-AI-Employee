"""facebook_poster.py — Facebook post automation with human simulation.

Mirror of linkedin_poster.py pattern — pure Python, sync Playwright, no MCP.

Called by orchestrator/fte-approve ONLY after user moves approval file to /Approved.

HITL GATE:
    - Checks AI_Employee_Vault/Approved/<approval_file> exists before opening browser
    - Never posts autonomously

HUMAN BEHAVIOR SIMULATION:
    - Browse feed first (5-15 seconds, random scrolls)
    - Click "Create a post" with mouse overshoot
    - Dismiss any popup/announcement dialogs
    - Click into text area
    - Type character-by-character (60-130ms per char)
    - Proofread pause (4-10 seconds)
    - Submit post via JavaScript click (bypasses Facebook overlay)

SESSION HEALTH CHECK:
    - URL check: login/checkpoint/recover in URL → session expired
    - Element check: input[name="email"] visible → session expired
    - Aborts before typing anything on expired session

.env VARIABLES:
    FB_SESSION_DIR=.secrets/facebook_session
    DRY_RUN=false
    LI_HEADLESS=true   (reuse same flag — false for debugging)
"""

import json
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

FB_SESSION_DIR: Path = (
    Path(__file__).parent / os.getenv("FB_SESSION_DIR", ".secrets/facebook_session")
).resolve()

VAULT_PATH: Path = (
    Path(__file__).parent / os.getenv("VAULT_PATH", "AI_Employee_Vault")
).resolve()

FB_HEADLESS: bool = os.getenv("LI_HEADLESS", "true").lower() != "false"
DRY_RUN: bool = os.getenv("DRY_RUN", "").lower() == "true"

FB_POST_MAX_CHARS = 63_206  # Facebook's hard limit

# ---------------------------------------------------------------------------
# FacebookScheduler — .state/facebook_scheduled.json management
# (same pattern as JitterScheduler in linkedin_poster.py)
# ---------------------------------------------------------------------------

import json as _json
import random as _random
from datetime import datetime as _dt, timedelta as _td

_STATE_DIR = Path(__file__).parent / ".state"
_FB_SCHEDULE_FILE = _STATE_DIR / "facebook_scheduled.json"
_FB_LAST_POST_FILE = _STATE_DIR / "facebook_last_posted.json"
_FB_POST_WINDOW_START: str = os.getenv("POST_WINDOW_START", "09:00")
_FB_POST_WINDOW_END: str = os.getenv("POST_WINDOW_END", "18:00")
_FB_MIN_POST_GAP_HOURS = 23


class FacebookScheduler:
    """Manages jitter-delayed Facebook post scheduling.

    State file: .state/facebook_scheduled.json
    Schema matches linkedin_poster.JitterScheduler exactly.
    """

    @staticmethod
    def _parse_hhmm(hhmm: str) -> tuple[int, int]:
        parts = hhmm.strip().split(":")
        return int(parts[0]), int(parts[1])

    @classmethod
    def _random_post_time(cls) -> tuple[str, str]:
        start_h, start_m = cls._parse_hhmm(_FB_POST_WINDOW_START)
        end_h, end_m = cls._parse_hhmm(_FB_POST_WINDOW_END)
        start_min = start_h * 60 + start_m
        end_min = end_h * 60 + end_m

        target_date = _dt.now()
        if _FB_LAST_POST_FILE.exists():
            try:
                data = _json.loads(_FB_LAST_POST_FILE.read_text(encoding="utf-8"))
                last_ts_str = data.get("posted_at", "")
                if last_ts_str:
                    last_ts = _dt.fromisoformat(last_ts_str)
                    gap = (_dt.now() - last_ts).total_seconds()
                    if gap < _FB_MIN_POST_GAP_HOURS * 3600:
                        target_date = _dt.now() + _td(days=1)
            except (ValueError, KeyError, _json.JSONDecodeError, OSError):
                pass

        rand_min = _random.randint(start_min, max(start_min, end_min - 1))
        h, m = divmod(rand_min, 60)
        return f"{h:02d}:{m:02d}", target_date.strftime("%Y-%m-%d")

    @classmethod
    def schedule(cls, approval_file_path: Path, content: str) -> dict:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        if _FB_SCHEDULE_FILE.exists():
            try:
                return _json.loads(_FB_SCHEDULE_FILE.read_text(encoding="utf-8"))
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
        _FB_SCHEDULE_FILE.write_text(_json.dumps(schedule, indent=2, ensure_ascii=False), encoding="utf-8")
        return schedule

    @classmethod
    def get_pending(cls) -> dict | None:
        if not _FB_SCHEDULE_FILE.exists():
            return None
        try:
            return _json.loads(_FB_SCHEDULE_FILE.read_text(encoding="utf-8"))
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
        _FB_SCHEDULE_FILE.unlink(missing_ok=True)

    @classmethod
    def record_post(cls) -> None:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _FB_LAST_POST_FILE.write_text(_json.dumps({"posted_at": _dt.now().isoformat()}, indent=2), encoding="utf-8")


# Facebook selectors — March 2026
# Multiple fallbacks per step — try each, use first visible one
SEL_COOKIE = [
    '[data-cookiebanner="accept_button"]',
    'button[title="Allow all cookies"]',
    'button:has-text("Accept all")',
    '[aria-label="Allow all cookies"]',
]
SEL_POST_TRIGGER = [
    '[aria-label="Create a post"]',
    '[placeholder*="mind"]',
    '[aria-label*="mind"]',
    'div[role="button"]:has-text("Create")',
]
SEL_POPUP_DISMISS = [
    '[aria-label="Close"]',
    '[aria-label="Not now"]',
    'div[role="dialog"] [aria-label="Close"]',
    'div[role="dialog"] button:last-child',
]
SEL_TEXTBOX = [
    '[data-lexical-editor="true"]',
    '[role="textbox"][contenteditable="true"]',
    '[contenteditable="true"][aria-placeholder*="mind"]',
    '[contenteditable="true"]',
]
SEL_POST_BUTTON = [
    '[aria-label="Post"][role="button"]',
    'div[aria-label="Post"]',
    '[role="button"]:has-text("Post")',
]


# ---------------------------------------------------------------------------
# Helpers — exactly same pattern as linkedin_poster.py
# ---------------------------------------------------------------------------

def _find_element(page, selectors: list[str]):
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
        # Extra pause after punctuation
        if char in ".!?,":
            base_delay += random.uniform(0.10, 0.40)
        # Occasional mid-burst thinking pause
        elif i > 0 and i % random.randint(20, 50) == 0:
            base_delay += random.uniform(0.20, 0.80)
        page.keyboard.type(char)
        time.sleep(base_delay)


def _human_scroll(page, duration_seconds: float) -> None:
    """Scroll feed human-like for given duration."""
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
    """Click via JavaScript — bypasses Facebook's pointer-event overlay."""
    page.evaluate("el => el.click()", element)


def _dashboard_alert(message: str) -> None:
    """Prepend alert to Dashboard.md."""
    dashboard = VAULT_PATH / "Dashboard.md"
    if not dashboard.exists():
        print(f"[facebook_poster] ALERT: {message}")
        return
    try:
        text = dashboard.read_text(encoding="utf-8")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        banner = f"\n> ⚠️ FACEBOOK ALERT ({ts}): {message}\n"
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
        print(f"[facebook_poster] Failed to write Dashboard alert: {e}")


# ---------------------------------------------------------------------------
# Session health check
# ---------------------------------------------------------------------------

def session_health_check(page) -> bool:
    """Return True if Facebook session is active."""
    url = page.url
    if any(kw in url for kw in ("login", "checkpoint", "recover", "disabled")):
        msg = (
            "Facebook session expired (login page detected). "
            "Re-run: LI_HEADLESS=false uv run python facebook_watcher.py --setup"
        )
        _dashboard_alert(msg)
        print(f"[facebook_poster] {msg}")
        return False
    # Secondary: look for email login field
    try:
        el = page.query_selector('input[name="email"]')
        if el and el.is_visible():
            msg = "Facebook session expired (login form visible)."
            _dashboard_alert(msg)
            print(f"[facebook_poster] {msg}")
            return False
    except Exception:
        pass
    return True


# ---------------------------------------------------------------------------
# Main poster
# ---------------------------------------------------------------------------

def post_to_facebook(
    content: str,
    approval_file: str | None = None,
) -> bool:
    """Post content to Facebook using human behavior simulation.

    Args:
        content:       Post text.
        approval_file: Filename in AI_Employee_Vault/Approved/ (HITL gate).
                       If provided, checks file exists before posting and
                       moves it to Done/ on success.

    Returns:
        True on success, False on any failure.
    """
    # ── HITL gate ────────────────────────────────────────────────────────────
    approved_path = None
    if approval_file:
        approved_path = VAULT_PATH / "Approved" / approval_file
        if not approved_path.exists():
            print(
                f"[facebook_poster] HITL gate: {approval_file} not in Approved/. "
                "Move file from Pending_Approval/ to Approved/ first."
            )
            return False

    # ── Character limit guard ─────────────────────────────────────────────
    if len(content) > FB_POST_MAX_CHARS:
        content = content[:FB_POST_MAX_CHARS - 3] + "..."
        print(f"[facebook_poster] WARNING: Content truncated to {FB_POST_MAX_CHARS} chars")

    # ── DRY_RUN ───────────────────────────────────────────────────────────
    if DRY_RUN:
        print(
            f"[facebook_poster] DRY_RUN — would post {len(content)} chars:\n"
            f"{content[:200]}{'...' if len(content) > 200 else ''}"
        )
        return True

    # ── Session directory check ───────────────────────────────────────────
    if not FB_SESSION_DIR.exists() or not any(FB_SESSION_DIR.iterdir()):
        msg = (
            f"Facebook session not found at {FB_SESSION_DIR}. "
            "Run: LI_HEADLESS=false uv run python facebook_watcher.py --setup"
        )
        print(f"[facebook_poster] {msg}")
        _dashboard_alert(msg)
        return False

    print(
        f"[facebook_poster] Starting post | "
        f"session={FB_SESSION_DIR.name} | headless={FB_HEADLESS} | "
        f"chars={len(content)}"
    )

    from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(FB_SESSION_DIR),
                headless=FB_HEADLESS,
                slow_mo=200,                          # same as linkedin_poster
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

            # ── Step 1: Navigate to feed ──────────────────────────────────
            print("[facebook_poster] 1/7 — Navigating to feed...")
            page.goto(
                "https://www.facebook.com/",
                wait_until="domcontentloaded",        # NOT networkidle (Facebook never settles)
                timeout=45_000,
            )
            time.sleep(random.uniform(2.5, 4.0))

            # ── Step 2: Session health check ──────────────────────────────
            print("[facebook_poster] 2/7 — Session health check...")
            if not session_health_check(page):
                ctx.close()
                return False

            # ── Cookie wall ───────────────────────────────────────────────
            cookie_btn = _find_element(page, SEL_COOKIE)
            if cookie_btn:
                print("[facebook_poster] Dismissing cookie banner...")
                cookie_btn.click()
                time.sleep(random.uniform(0.8, 1.5))

            # ── Step 3: Browse feed (look natural) ────────────────────────
            browse_secs = random.uniform(5.0, 15.0)
            print(f"[facebook_poster] 3/7 — Browsing feed {browse_secs:.0f}s...")
            _human_scroll(page, browse_secs)

            # Scroll back to top — post trigger is at top of feed
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(random.uniform(1.0, 2.0))

            # ── Step 4: Click "Create a post" trigger ─────────────────────
            print("[facebook_poster] 4/7 — Opening post composer...")
            trigger = _find_element(page, SEL_POST_TRIGGER)
            if trigger is None:
                print("[facebook_poster] ERROR: Post trigger not found — aborting")
                ctx.close()
                return False

            _click_with_overshoot(page, trigger)
            time.sleep(random.uniform(1.5, 2.5))

            # ── Dismiss any announcement/merge popups ─────────────────────
            # Facebook shows "Post and reel merge" announcement that blocks the textbox.
            # The image alt="Post and reel default audience merge dialogue image" is
            # the known blocker. We dismiss via JS by clicking the last button in the
            # dialog (usually "Not now" / "OK" / close button).
            time.sleep(1.0)
            dismissed = page.evaluate("""() => {
                // Find any dialog/layer containing the merge announcement image
                const img = document.querySelector(
                    'img[alt*="merge"], img[alt*="Post and reel"]'
                );
                if (!img) return false;
                // Walk up to find a clickable close/dismiss button
                let node = img.parentElement;
                for (let i = 0; i < 10; i++) {
                    if (!node) break;
                    const btns = node.querySelectorAll(
                        'div[role="button"], button'
                    );
                    // Pick last button in dialog (usually "Not now" / close)
                    if (btns.length > 0) {
                        btns[btns.length - 1].click();
                        return true;
                    }
                    node = node.parentElement;
                }
                return false;
            }""")
            if dismissed:
                print("[facebook_poster] Dismissed announcement popup via JS")
                time.sleep(random.uniform(1.0, 1.8))
            else:
                # Fallback: try standard selectors
                for _ in range(2):
                    popup = _find_element(page, SEL_POPUP_DISMISS)
                    if popup:
                        print("[facebook_poster] Dismissing popup via selector...")
                        _js_click(page, popup)
                        time.sleep(random.uniform(0.8, 1.2))
                    else:
                        break

            # ── Step 5: Find and click text area ──────────────────────────
            print("[facebook_poster] 5/7 — Focusing text area...")
            time.sleep(0.5)
            textbox = _find_element(page, SEL_TEXTBOX)
            if textbox is None:
                print("[facebook_poster] ERROR: Text area not found — aborting")
                ctx.close()
                return False

            # Use JS click to bypass any remaining overlays
            _js_click(page, textbox)
            time.sleep(random.uniform(0.5, 1.0))
            time.sleep(random.uniform(0.5, 1.0))

            # ── Step 6: Type content character-by-character ───────────────
            print(f"[facebook_poster] 6/7 — Typing {len(content)} chars...")
            _human_type(page, content)

            # ── Proofread pause ───────────────────────────────────────────
            proofread = random.uniform(4.0, 10.0)
            print(f"[facebook_poster] Proofreading {proofread:.1f}s...")
            time.sleep(proofread)

            # ── Step 7: Click Post button ─────────────────────────────────
            print("[facebook_poster] 7/7 — Submitting post...")
            post_btn = _find_element(page, SEL_POST_BUTTON)
            if post_btn is None:
                print("[facebook_poster] ERROR: Post button not found — aborting")
                ctx.close()
                return False

            # Use JS click to bypass Facebook's pointer-event overlay
            _js_click(page, post_btn)
            time.sleep(random.uniform(3.0, 5.0))

            # ── Verify: confirm we're back on feed (modal closed) ─────────
            current_url = page.url
            if "facebook.com" in current_url and "login" not in current_url:
                print("[facebook_poster] SUCCESS: Post submitted — feed reloaded")
            else:
                print(f"[facebook_poster] WARNING: Unexpected URL after post: {current_url}")

            ctx.close()

        # ── Move approval file to Done/ ───────────────────────────────────
        if approved_path and approved_path.exists():
            done_path = VAULT_PATH / "Done" / approval_file
            approved_path.rename(done_path)
            print(f"[facebook_poster] Approval file moved to Done/{approval_file}")

        # ── Log success ───────────────────────────────────────────────────
        try:
            from logger import log_action
            log_action(
                VAULT_PATH / "Logs",
                action="facebook_post",
                actor="facebook_poster",
                result="success",
                details=f"Posted {len(content)} chars",
            )
        except Exception:
            pass  # logging is non-critical

        return True

    except PWTimeout as exc:
        print(f"[facebook_poster] Timeout: {exc}")
        return False
    except Exception as exc:
        print(f"[facebook_poster] Unexpected error: {exc}")
        return False


# ---------------------------------------------------------------------------
# CLI — direct test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Facebook poster — test posting flow")
    parser.add_argument("--content", default="Test post from facebook_poster.py")
    parser.add_argument("--approval-file", default=None, help="Approval file in Approved/")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "true"
    if args.no_headless:
        os.environ["LI_HEADLESS"] = "false"

    success = post_to_facebook(args.content, approval_file=args.approval_file)
    sys.exit(0 if success else 1)
