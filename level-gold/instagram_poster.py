"""instagram_poster.py — Instagram post automation with human simulation.

Mirror of facebook_poster.py pattern — pure Python, sync Playwright, no MCP.

Called by orchestrator/fte-approve ONLY after user moves approval file to /Approved.

HITL GATE:
    - Checks AI_Employee_Vault/Approved/<approval_file> exists before opening browser
    - Never posts autonomously

IMAGE REQUIREMENT:
    - Instagram requires an image/video to post — --image-path is mandatory
    - If image file does not exist, aborts with clear error
    - Supported: .jpg, .jpeg, .png, .mp4

HUMAN BEHAVIOR SIMULATION:
    - Browse feed first (5-12 seconds, random scrolls)
    - Click Create (+) button with mouse overshoot
    - Select image via file input
    - Navigate through composer steps (Select → Crop → Filter → Caption)
    - Type caption character-by-character (60-130ms per char)
    - Proofread pause (3-8 seconds)
    - Submit post via JavaScript click

SESSION HEALTH CHECK:
    - URL check: login/accounts/login in URL → session expired
    - Element check: input[name="username"] visible → session expired
    - Aborts before typing anything on expired session

CHARACTER LIMIT:
    - Instagram caption limit: 2200 characters
    - Content truncated with "..." if over limit

.env VARIABLES:
    IG_SESSION_DIR=.secrets/instagram_session
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

IG_SESSION_DIR: Path = (
    Path(__file__).parent / os.getenv("IG_SESSION_DIR", ".secrets/instagram_session")
).resolve()

VAULT_PATH: Path = (
    Path(__file__).parent / os.getenv("VAULT_PATH", "AI_Employee_Vault")
).resolve()

IG_HEADLESS: bool = os.getenv("LI_HEADLESS", "true").lower() != "false"
DRY_RUN: bool = os.getenv("DRY_RUN", "").lower() == "true"

IG_MAX_CHARS = 2_200  # Instagram caption limit

SUPPORTED_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".mp4", ".mov"}

# Media directory — images waiting to be posted to Instagram
MEDIA_DIR: Path = Path(__file__).parent / "media"

# ---------------------------------------------------------------------------
# InstagramScheduler — .state/instagram_scheduled.json management
# (same pattern as linkedin_poster.JitterScheduler + media availability check)
# ---------------------------------------------------------------------------

import json as _json
import random as _random
from datetime import datetime as _dt, timedelta as _td

_STATE_DIR = Path(__file__).parent / ".state"
_IG_SCHEDULE_FILE = _STATE_DIR / "instagram_scheduled.json"
_IG_LAST_POST_FILE = _STATE_DIR / "instagram_last_posted.json"
_IG_USED_MEDIA_FILE = _STATE_DIR / "ig_used_media.json"
_IG_POST_WINDOW_START: str = os.getenv("POST_WINDOW_START", "09:00")
_IG_POST_WINDOW_END: str = os.getenv("POST_WINDOW_END", "18:00")
_IG_MIN_POST_GAP_HOURS = 23


class InstagramScheduler:
    """Manages jitter-delayed Instagram post scheduling with media tracking.

    State files:
      .state/instagram_scheduled.json  — current pending post
      .state/instagram_last_posted.json — timestamp of last post (23h gap)
      .state/ig_used_media.json        — list of already-posted image filenames
    """

    @staticmethod
    def _parse_hhmm(hhmm: str) -> tuple[int, int]:
        parts = hhmm.strip().split(":")
        return int(parts[0]), int(parts[1])

    @classmethod
    def _random_post_time(cls) -> tuple[str, str]:
        start_h, start_m = cls._parse_hhmm(_IG_POST_WINDOW_START)
        end_h, end_m = cls._parse_hhmm(_IG_POST_WINDOW_END)
        start_min = start_h * 60 + start_m
        end_min = end_h * 60 + end_m

        target_date = _dt.now()
        if _IG_LAST_POST_FILE.exists():
            try:
                data = _json.loads(_IG_LAST_POST_FILE.read_text(encoding="utf-8"))
                last_ts_str = data.get("posted_at", "")
                if last_ts_str:
                    last_ts = _dt.fromisoformat(last_ts_str)
                    gap = (_dt.now() - last_ts).total_seconds()
                    if gap < _IG_MIN_POST_GAP_HOURS * 3600:
                        target_date = _dt.now() + _td(days=1)
            except (ValueError, KeyError, _json.JSONDecodeError, OSError):
                pass

        rand_min = _random.randint(start_min, max(start_min, end_min - 1))
        h, m = divmod(rand_min, 60)
        return f"{h:02d}:{m:02d}", target_date.strftime("%Y-%m-%d")

    @classmethod
    def _load_used_media(cls) -> list[str]:
        try:
            if _IG_USED_MEDIA_FILE.exists():
                return _json.loads(_IG_USED_MEDIA_FILE.read_text(encoding="utf-8"))
        except (_json.JSONDecodeError, OSError):
            pass
        return []

    @classmethod
    def _save_used_media(cls, used: list[str]) -> None:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _IG_USED_MEDIA_FILE.write_text(_json.dumps(used, indent=2), encoding="utf-8")

    @classmethod
    def get_next_media(cls) -> Path | None:
        """Return path to the next unused image in media/, or None if exhausted."""
        if not MEDIA_DIR.exists():
            return None
        used = cls._load_used_media()
        candidates = sorted(
            f for f in MEDIA_DIR.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_IMAGE_TYPES
            and f.name not in used
        )
        return candidates[0] if candidates else None

    @classmethod
    def mark_media_used(cls, image_path: Path) -> None:
        """Record image as used so it won't be picked again."""
        used = cls._load_used_media()
        if image_path.name not in used:
            used.append(image_path.name)
            cls._save_used_media(used)

    @classmethod
    def has_media(cls) -> bool:
        """Return True if at least one unused image is available in media/."""
        return cls.get_next_media() is not None

    @classmethod
    def schedule(cls, approval_file_path: Path, content: str) -> dict:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        if _IG_SCHEDULE_FILE.exists():
            try:
                return _json.loads(_IG_SCHEDULE_FILE.read_text(encoding="utf-8"))
            except (_json.JSONDecodeError, OSError):
                pass
        post_time, post_date = cls._random_post_time()
        # Pick and reserve an image at schedule time
        media = cls.get_next_media()
        schedule: dict = {
            "post_at": post_time,
            "post_date": post_date,
            "file": str(approval_file_path.resolve()),
            "content": content,
            "image_path": str(media.resolve()) if media else None,
            "scheduled_at": _dt.now().isoformat(),
        }
        _IG_SCHEDULE_FILE.write_text(_json.dumps(schedule, indent=2, ensure_ascii=False), encoding="utf-8")
        return schedule

    @classmethod
    def get_pending(cls) -> dict | None:
        if not _IG_SCHEDULE_FILE.exists():
            return None
        try:
            return _json.loads(_IG_SCHEDULE_FILE.read_text(encoding="utf-8"))
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
        _IG_SCHEDULE_FILE.unlink(missing_ok=True)

    @classmethod
    def record_post(cls, image_path: Path | None = None) -> None:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _IG_LAST_POST_FILE.write_text(_json.dumps({"posted_at": _dt.now().isoformat()}, indent=2), encoding="utf-8")
        if image_path:
            cls.mark_media_used(image_path)

# Instagram selectors — March 2026
SEL_COOKIE = [
    'button:has-text("Allow all cookies")',
    'button:has-text("Accept All")',
    '[aria-label="Allow all cookies"]',
]
SEL_CREATE_BTN = [
    '[aria-label="New post"]',
    'svg[aria-label="New post"]',
    '[aria-label="Create"]',
    'a[href="/create/select/"]',
]
SEL_FILE_INPUT = [
    'input[type="file"]',
    'input[accept*="image"]',
]
SEL_NEXT_BTN = [
    'div[role="button"]:has-text("Next")',
    'button:has-text("Next")',
]
SEL_SHARE_BTN = [
    'div[role="button"]:has-text("Share")',
    'button:has-text("Share")',
]
SEL_CAPTION = [
    '[aria-label="Write a caption..."]',
    '[placeholder*="caption"]',
    'div[role="textbox"][aria-label*="caption"]',
]
SEL_POPUP_DISMISS = [
    'button:has-text("Not Now")',
    'button:has-text("Cancel")',
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
        if char in ".!?,#":
            base_delay += random.uniform(0.10, 0.40)
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
    """Click via JavaScript — bypasses pointer-event overlays."""
    page.evaluate("el => el.click()", element)


def _dashboard_alert(message: str) -> None:
    """Prepend alert to Dashboard.md."""
    dashboard = VAULT_PATH / "Dashboard.md"
    if not dashboard.exists():
        print(f"[instagram_poster] ALERT: {message}")
        return
    try:
        text = dashboard.read_text(encoding="utf-8")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        banner = f"\n> WARNING INSTAGRAM ALERT ({ts}): {message}\n"
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
        print(f"[instagram_poster] Failed to write Dashboard alert: {e}")


# ---------------------------------------------------------------------------
# Session health check
# ---------------------------------------------------------------------------

def session_health_check(page) -> bool:
    """Return True if Instagram session is active."""
    url = page.url
    if any(kw in url for kw in ("login", "accounts/login", "challenge", "suspended")):
        msg = (
            "Instagram session expired (login page detected). "
            "Re-run: LI_HEADLESS=false uv run python instagram_watcher.py --setup"
        )
        _dashboard_alert(msg)
        print(f"[instagram_poster] {msg}")
        return False
    try:
        el = page.query_selector('input[name="username"]')
        if el and el.is_visible():
            msg = (
                "Instagram session expired (login form visible). "
                "Re-run: LI_HEADLESS=false uv run python instagram_watcher.py --setup"
            )
            _dashboard_alert(msg)
            print(f"[instagram_poster] {msg}")
            return False
    except Exception:
        pass
    return True


# ---------------------------------------------------------------------------
# Main poster
# ---------------------------------------------------------------------------

def post_to_instagram(
    content: str,
    image_path: str,
    approval_file: str | None = None,
) -> bool:
    """Post image + caption to Instagram using human behavior simulation.

    Args:
        content:       Caption text (max 2200 chars).
        image_path:    Absolute or relative path to image file (required).
        approval_file: Filename in AI_Employee_Vault/Approved/ (HITL gate).

    Returns:
        True on success, False on any failure.
    """
    # ── Image validation ──────────────────────────────────────────────────
    img = Path(image_path).resolve()
    if not img.exists():
        print(f"[instagram_poster] ERROR: Image not found: {img}")
        return False
    if img.suffix.lower() not in SUPPORTED_IMAGE_TYPES:
        print(
            f"[instagram_poster] ERROR: Unsupported file type '{img.suffix}'. "
            f"Supported: {', '.join(SUPPORTED_IMAGE_TYPES)}"
        )
        return False

    # ── HITL gate ────────────────────────────────────────────────────────────
    approved_path = None
    if approval_file:
        approved_path = VAULT_PATH / "Approved" / approval_file
        if not approved_path.exists():
            print(
                f"[instagram_poster] HITL gate: {approval_file} not in Approved/. "
                "Move file from Pending_Approval/ to Approved/ first."
            )
            return False

    # ── Character limit guard ─────────────────────────────────────────────
    if len(content) > IG_MAX_CHARS:
        content = content[:IG_MAX_CHARS - 3] + "..."
        print(f"[instagram_poster] WARNING: Content truncated to {IG_MAX_CHARS} chars")

    # ── DRY_RUN ───────────────────────────────────────────────────────────
    if DRY_RUN:
        print(
            f"[instagram_poster] DRY_RUN — would post image={img.name} "
            f"caption={len(content)} chars:\n"
            f"{content[:200]}{'...' if len(content) > 200 else ''}"
        )
        return True

    # ── Session directory check ───────────────────────────────────────────
    if not IG_SESSION_DIR.exists() or not any(IG_SESSION_DIR.iterdir()):
        msg = (
            f"Instagram session not found at {IG_SESSION_DIR}. "
            "Run: LI_HEADLESS=false uv run python instagram_watcher.py --setup"
        )
        print(f"[instagram_poster] {msg}")
        _dashboard_alert(msg)
        return False

    print(
        f"[instagram_poster] Starting post | "
        f"session={IG_SESSION_DIR.name} | headless={IG_HEADLESS} | "
        f"image={img.name} | caption={len(content)} chars"
    )

    from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(IG_SESSION_DIR),
                headless=IG_HEADLESS,
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

            # ── Step 1: Navigate to feed ──────────────────────────────────
            print("[instagram_poster] 1/7 — Navigating to feed...")
            page.goto(
                "https://www.instagram.com",
                wait_until="domcontentloaded",
                timeout=45_000,
            )
            time.sleep(random.uniform(2.5, 4.0))

            # ── Step 2: Session health check ──────────────────────────────
            print("[instagram_poster] 2/7 — Session health check...")
            if not session_health_check(page):
                ctx.close()
                return False

            # ── Cookie dismissal ──────────────────────────────────────────
            cookie_btn = _find_element(page, SEL_COOKIE)
            if cookie_btn:
                print("[instagram_poster] Dismissing cookie banner...")
                _js_click(page, cookie_btn)
                time.sleep(random.uniform(0.8, 1.5))

            # Dismiss notification permission dialog
            popup = _find_element(page, SEL_POPUP_DISMISS)
            if popup:
                print("[instagram_poster] Dismissing popup...")
                _js_click(page, popup)
                time.sleep(random.uniform(0.5, 1.0))

            # ── Step 3: Browse feed (look natural) ────────────────────────
            browse_secs = random.uniform(5.0, 12.0)
            print(f"[instagram_poster] 3/7 — Browsing feed {browse_secs:.0f}s...")
            _human_scroll(page, browse_secs)

            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(random.uniform(1.0, 2.0))

            # ── Step 4: Click Create (+) button ──────────────────────────
            print("[instagram_poster] 4/7 — Opening post composer...")
            create_btn = _find_element(page, SEL_CREATE_BTN)
            if create_btn is None:
                print("[instagram_poster] ERROR: Create button not found — aborting")
                ctx.close()
                return False

            _click_with_overshoot(page, create_btn)
            time.sleep(random.uniform(1.5, 2.5))

            # ── Step 5: Upload image via file input ───────────────────────
            print(f"[instagram_poster] 5/7 — Uploading image: {img.name}...")
            file_input = page.query_selector('input[type="file"]')
            if file_input is None:
                # Try triggering "Select from computer" button
                select_btn = page.query_selector('button:has-text("Select from computer")')
                if select_btn:
                    _js_click(page, select_btn)
                    time.sleep(1.0)
                    file_input = page.query_selector('input[type="file"]')

            if file_input is None:
                print("[instagram_poster] ERROR: File input not found — aborting")
                ctx.close()
                return False

            file_input.set_input_files(str(img))
            time.sleep(random.uniform(2.0, 3.5))

            # ── Step 5a: Navigate through crop/filter steps ───────────────
            # Always click Next at least 2 times (Crop, Filter minimum).
            # Only check caption box (not Share) to avoid false positives from
            # background page elements matching div[role="button"]:has-text("Share").
            for _nav_step in range(4):
                if _nav_step >= 2:
                    caption_el = page.query_selector('[aria-label="Write a caption..."]')
                    if caption_el and caption_el.is_visible():
                        print(f"[instagram_poster]   -> Caption step reached after {_nav_step} Next click(s)")
                        break
                next_btn = _find_element(page, SEL_NEXT_BTN)
                if next_btn:
                    print(f"[instagram_poster]   -> Advancing step {_nav_step + 1}...")
                    _js_click(page, next_btn)
                    time.sleep(random.uniform(1.5, 2.5))
                else:
                    print(f"[instagram_poster]   -> No Next button at nav step {_nav_step + 1}")
                    break

            # Wait for caption box to be ready
            try:
                page.wait_for_selector('[aria-label="Write a caption..."]', timeout=8_000)
            except Exception:
                pass

            # ── Step 6: Type caption ──────────────────────────────────────
            print(f"[instagram_poster] 6/7 — Typing caption ({len(content)} chars)...")
            caption_box = page.query_selector('[aria-label="Write a caption..."]')
            if caption_box and caption_box.is_visible():
                caption_box.click()  # native click — properly focuses contenteditable
                time.sleep(random.uniform(0.5, 1.0))
                _human_type(page, content)
            else:
                print("[instagram_poster] WARNING: Caption box not found — posting without caption")

            # ── Proofread pause ───────────────────────────────────────────
            proofread = random.uniform(3.0, 8.0)
            print(f"[instagram_poster] Proofreading {proofread:.1f}s...")
            time.sleep(proofread)

            # ── Step 7: Click Share button ────────────────────────────────
            # IMPORTANT: scoped to [aria-label="Create new post"] modal to prevent
            # clicking background page elements that also match :has-text("Share").
            print("[instagram_poster] 7/7 — Submitting post...")
            try:
                page.click(
                    '[aria-label="Create new post"] div[role="button"]:has-text("Share")',
                    timeout=8_000,
                )
            except PWTimeout:
                print("[instagram_poster] ERROR: Share button not found in modal — aborting")
                ctx.close()
                return False

            # ── Wait for Post shared confirmation ─────────────────────────
            try:
                page.wait_for_selector('text="Post shared"', timeout=20_000)
                print("[instagram_poster] SUCCESS: Post shared confirmed")
            except Exception:
                current_url = page.url
                if "instagram.com" in current_url and "login" not in current_url:
                    print("[instagram_poster] SUCCESS: Post submitted (no confirmation element)")
                else:
                    print(f"[instagram_poster] WARNING: Unexpected URL after post: {current_url}")

            ctx.close()

        # ── Move approval file to Done/ ───────────────────────────────────
        if approved_path and approved_path.exists():
            done_path = VAULT_PATH / "Done" / approval_file
            approved_path.rename(done_path)
            print(f"[instagram_poster] Approval file moved to Done/{approval_file}")

        # ── Log success ───────────────────────────────────────────────────
        try:
            from logger import log_action
            log_action(
                VAULT_PATH / "Logs",
                action="instagram_post",
                actor="instagram_poster",
                result="success",
                details=f"Posted image={img.name} caption={len(content)} chars",
            )
        except Exception:
            pass

        return True

    except PWTimeout as exc:
        print(f"[instagram_poster] Timeout: {exc}")
        return False
    except Exception as exc:
        print(f"[instagram_poster] Unexpected error: {exc}")
        return False


# ---------------------------------------------------------------------------
# CLI — direct test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Instagram poster — test posting flow")
    parser.add_argument("--content", default="Test post from instagram_poster.py")
    parser.add_argument("--image-path", required=True, help="Path to image file (required)")
    parser.add_argument("--approval-file", default=None, help="Approval file in Approved/")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "true"
    if args.no_headless:
        os.environ["LI_HEADLESS"] = "false"

    success = post_to_instagram(
        args.content,
        image_path=args.image_path,
        approval_file=args.approval_file,
    )
    sys.exit(0 if success else 1)
