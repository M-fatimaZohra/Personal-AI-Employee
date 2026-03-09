"""
twitter_watcher.py — Independent Twitter/X monitoring watcher.

Polls Twitter/X for new mentions, DMs, replies, and quote tweets
using a persistent Playwright session. Completely independent of Facebook
and Instagram watchers — runs as its own PM2 process.

Action file prefix: TWITTER_<id>.md in AI_Employee_Vault/Needs_Action/

Required env vars:
    TWITTER_SESSION_DIR    — path to .secrets/twitter_session/
    VAULT_PATH             — path to AI_Employee_Vault/ (default: ./AI_Employee_Vault)
    TWITTER_CHECK_INTERVAL — polling interval in seconds (default: 900 = 15 min)
    LI_HEADLESS            — "false" to show browser (default: true)
    DRY_RUN                — if "true", logs actions without writing files

FIRST-TIME SETUP:
    LI_HEADLESS=false uv run python twitter_watcher.py --setup
    Log in manually, then Ctrl+C. Session saved automatically.
"""

import os
import json
import time
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from base_watcher import BaseWatcher

load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [TwitterWatcher] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

VAULT_PATH = Path(os.getenv("VAULT_PATH", "AI_Employee_Vault")).resolve()
TWITTER_SESSION_DIR = (
    Path(__file__).parent / os.getenv("TWITTER_SESSION_DIR", ".secrets/twitter_session")
).resolve()
CHECK_INTERVAL = int(os.getenv("TWITTER_CHECK_INTERVAL", "900"))
TWITTER_HEADLESS: bool = os.getenv("LI_HEADLESS", "true").lower() != "false"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# Independent state file — does NOT share with Facebook or Instagram
STATE_FILE = Path(__file__).parent / ".state/twitter_processed_ids.json"


def _load_seen_ids() -> set:
    try:
        if STATE_FILE.exists():
            return set(json.loads(STATE_FILE.read_text()))
    except Exception:
        pass
    return set()


def _save_seen_ids(ids: set) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(list(ids)))


def _make_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:12]


class TwitterWatcher(BaseWatcher):
    """
    Polls Twitter/X notifications tab for mentions, replies, and DMs.
    Each new notification triggers a TWITTER_<id>.md in Needs_Action/.

    Completely independent of Facebook/Instagram watchers — no shared state.
    """

    def __init__(self, vault_path=None):
        _vault = Path(vault_path).resolve() if vault_path else VAULT_PATH
        super().__init__(str(_vault), check_interval=CHECK_INTERVAL)
        self._seen_ids = _load_seen_ids()

    def _session_ok(self) -> bool:
        if not TWITTER_SESSION_DIR.exists():
            return False
        return any(TWITTER_SESSION_DIR.iterdir())

    def check_for_updates(self) -> list:
        """
        Open Twitter/X notifications page via Playwright and collect new items.
        """
        if not self._session_ok():
            log.warning(
                "Twitter session not configured. "
                "Run: LI_HEADLESS=false uv run python twitter_watcher.py --setup"
            )
            return []

        notifications = []
        try:
            with sync_playwright() as p:
                ctx = p.chromium.launch_persistent_context(
                    str(TWITTER_SESSION_DIR),
                    headless=TWITTER_HEADLESS,
                    slow_mo=300,
                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                )
                # ctx.pages is a property (list), NOT a method — sync Playwright
                page = ctx.pages[0] if ctx.pages else ctx.new_page()

                page.goto(
                    "https://twitter.com/notifications",
                    wait_until="domcontentloaded",
                    timeout=45_000,
                )
                time.sleep(2.0)

                # Session health check — URL first, then element
                url = page.url
                if any(kw in url for kw in ("login", "i/flow/login", "logout")):
                    log.error(
                        "Twitter session expired (login page). "
                        "Run: LI_HEADLESS=false uv run python twitter_watcher.py --setup"
                    )
                    ctx.close()
                    return []

                try:
                    el = page.query_selector('[data-testid="loginButton"]')
                    if el and el.is_visible():
                        log.error("Twitter session expired (login button visible).")
                        ctx.close()
                        return []
                except Exception:
                    pass

                # Collect notification cells
                items = page.query_selector_all('[data-testid="cellInnerDiv"]')
                for item in items[:20]:
                    try:
                        text = item.inner_text().strip()
                        if not text or len(text) < 5:
                            continue
                        nid = _make_id(text)
                        if nid in self._seen_ids:
                            continue

                        text_lower = text.lower()
                        if any(kw in text_lower for kw in ["replied", "replied to"]):
                            ntype = "reply"
                            priority = "high"
                        elif any(kw in text_lower for kw in ["mentioned", "mention"]):
                            ntype = "mention"
                            priority = "high"
                        elif any(kw in text_lower for kw in ["message", "dm"]):
                            ntype = "dm"
                            priority = "urgent"
                        elif any(kw in text_lower for kw in ["quoted", "quote"]):
                            ntype = "quote_tweet"
                            priority = "high"
                        elif any(kw in text_lower for kw in ["retweeted", "repost"]):
                            ntype = "retweet"
                            priority = "normal"
                        elif any(kw in text_lower for kw in ["liked", "like"]):
                            ntype = "like"
                            priority = "normal"
                        elif any(kw in text_lower for kw in ["followed", "follow"]):
                            ntype = "follow"
                            priority = "normal"
                        else:
                            ntype = "notification"
                            priority = "normal"

                        notifications.append({
                            "id": nid,
                            "type": ntype,
                            "priority": priority,
                            "text": text[:500],
                        })
                        self._seen_ids.add(nid)
                        time.sleep(0.2)
                    except Exception:
                        continue

                ctx.close()

        except PlaywrightTimeout:
            log.warning("Twitter: page load timed out — will retry next cycle")
        except Exception as exc:
            log.error("Twitter watcher error: %s", exc)

        _save_seen_ids(self._seen_ids)
        return notifications

    def create_action_file(self, item: dict) -> Path:
        """Write TWITTER_<id>.md to Needs_Action/."""
        now = datetime.now(timezone.utc)
        filename = f"TWITTER_{item['id']}.md"
        filepath = Path(self.vault_path) / "Needs_Action" / filename

        content = (
            f"---\n"
            f"type: social_twitter\n"
            f"platform: twitter\n"
            f"notification_type: {item['type']}\n"
            f"priority: {item['priority']}\n"
            f"created_at: {now.isoformat()}\n"
            f"status: pending\n"
            f"---\n\n"
            f"## Twitter/X {item['type'].replace('_', ' ').title()}\n\n"
            f"{item['text']}\n\n"
            f"## Suggested Actions\n\n"
            f"- [ ] Reply to {item['type'].replace('_', ' ')}\n"
            f"- [ ] Engage if appropriate (like/retweet)\n"
            f"- [ ] Archive after processing\n"
        )

        if DRY_RUN:
            log.info("[DRY_RUN] Would write: %s", filepath)
            return filepath

        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")
        log.info("Created: %s (type=%s priority=%s)", filename, item["type"], item["priority"])
        return filepath

    def run(self):
        log.info(
            "TwitterWatcher started | interval=%ds | vault=%s | dry_run=%s",
            CHECK_INTERVAL, VAULT_PATH, DRY_RUN,
        )
        while True:
            try:
                items = self.check_for_updates()
                for item in items:
                    self.create_action_file(item)
                if items:
                    log.info("Processed %d new Twitter notification(s)", len(items))
            except Exception as exc:
                log.error("Unexpected error: %s", exc)
            time.sleep(CHECK_INTERVAL)


# ---------------------------------------------------------------------------
# Standalone setup — bypasses _session_ok() check
# ---------------------------------------------------------------------------

def run_setup() -> None:
    """Open browser for first-time Twitter login. Works even with no session directory."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    TWITTER_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[TwitterWatcher] Setup mode | session dir: {TWITTER_SESSION_DIR}")
    print("[TwitterWatcher] Browser will open — log in to Twitter manually.")
    print("[TwitterWatcher] After login, press Ctrl+C or wait for auto-detection.")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(TWITTER_SESSION_DIR),
            headless=False,          # always visible for setup
            slow_mo=300,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://twitter.com/home", wait_until="domcontentloaded", timeout=45_000)

        # Wait up to 10 minutes for user to log in
        print("[TwitterWatcher] Waiting for login (up to 10 min)...")
        try:
            # Detect successful login: home timeline loads
            page.wait_for_selector(
                '[data-testid="primaryColumn"], [aria-label="Home timeline"]',
                timeout=600_000,
            )
            print("[TwitterWatcher] Login detected — session saved successfully.")
            print(f"[TwitterWatcher] Session stored at: {TWITTER_SESSION_DIR}")
        except PWTimeout:
            print("[TwitterWatcher] Timed out waiting for login.")
        except KeyboardInterrupt:
            print("[TwitterWatcher] Interrupted — session saved as-is.")
        finally:
            ctx.close()


# ---------------------------------------------------------------------------
# CLI entry point — first-time session setup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Twitter/X Watcher")
    parser.add_argument(
        "--setup", action="store_true",
        help="Open browser non-headless for manual Twitter login (saves session)"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run one check cycle and exit (useful for testing)"
    )
    args = parser.parse_args()

    if args.setup:
        run_setup()
        sys.exit(0)

    elif args.once:
        w = TwitterWatcher()
        results = w.check_for_updates()
        for r in results:
            w.create_action_file(r)
        print(f"[TwitterWatcher] One-shot complete. Found {len(results)} notification(s).")
        sys.exit(0)

    else:
        TwitterWatcher().run()
