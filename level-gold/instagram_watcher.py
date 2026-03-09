"""
instagram_watcher.py — Independent Instagram monitoring watcher.

Polls Instagram for new comments, mentions, and direct messages
using a persistent Playwright session. Completely independent of Facebook
and Twitter watchers — runs as its own PM2 process.

Action file prefix: SOCIAL_IG_<id>.md in AI_Employee_Vault/Needs_Action/

Required env vars:
    IG_SESSION_DIR    — path to .secrets/instagram_session/
    VAULT_PATH        — path to AI_Employee_Vault/ (default: ./AI_Employee_Vault)
    IG_CHECK_INTERVAL — polling interval in seconds (default: 900 = 15 min)
    LI_HEADLESS       — "false" to show browser (default: true)
    DRY_RUN           — if "true", logs actions without writing files

FIRST-TIME SETUP:
    LI_HEADLESS=false uv run python instagram_watcher.py --setup
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
    format="%(asctime)s [InstagramWatcher] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

VAULT_PATH = Path(os.getenv("VAULT_PATH", "AI_Employee_Vault")).resolve()
IG_SESSION_DIR = (
    Path(__file__).parent / os.getenv("IG_SESSION_DIR", ".secrets/instagram_session")
).resolve()
CHECK_INTERVAL = int(os.getenv("IG_CHECK_INTERVAL", "900"))
IG_HEADLESS: bool = os.getenv("LI_HEADLESS", "true").lower() != "false"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# Independent state file — does NOT share with Facebook or Twitter
STATE_FILE = Path(__file__).parent / ".state/ig_processed_ids.json"


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


class InstagramWatcher(BaseWatcher):
    """
    Polls Instagram activity feed for new comments, mentions, and DMs.
    Each notification triggers a SOCIAL_IG_<id>.md in Needs_Action/.

    Completely independent of Facebook/Twitter watchers — no shared state.
    """

    def __init__(self, vault_path=None):
        _vault = Path(vault_path).resolve() if vault_path else VAULT_PATH
        super().__init__(str(_vault), check_interval=CHECK_INTERVAL)
        self._seen_ids = _load_seen_ids()

    def _session_ok(self) -> bool:
        if not IG_SESSION_DIR.exists():
            return False
        return any(IG_SESSION_DIR.iterdir())

    def check_for_updates(self) -> list:
        """
        Open Instagram activity page via Playwright and collect new interactions.
        """
        if not self._session_ok():
            log.warning(
                "Instagram session not configured. "
                "Run: LI_HEADLESS=false uv run python instagram_watcher.py --setup"
            )
            return []

        notifications = []
        try:
            with sync_playwright() as p:
                ctx = p.chromium.launch_persistent_context(
                    str(IG_SESSION_DIR),
                    headless=IG_HEADLESS,
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
                    "https://www.instagram.com",
                    wait_until="domcontentloaded",
                    timeout=45_000,
                )
                time.sleep(2.0)

                # Session health check — URL first, then element
                url = page.url
                if any(kw in url for kw in ("login", "accounts/login", "challenge")):
                    log.error(
                        "Instagram session expired (login page). "
                        "Run: LI_HEADLESS=false uv run python instagram_watcher.py --setup"
                    )
                    ctx.close()
                    return []

                try:
                    el = page.query_selector('input[name="username"]')
                    if el and el.is_visible():
                        log.error("Instagram session expired (login form visible).")
                        ctx.close()
                        return []
                except Exception:
                    pass

                # Navigate to activity/notifications
                page.goto(
                    "https://www.instagram.com/accounts/activity/",
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
                time.sleep(2.0)

                # Collect activity items
                items = page.query_selector_all('[class*="notification"], [role="listitem"]')
                for item in items[:20]:
                    try:
                        text = item.inner_text().strip()
                        if not text or len(text) < 5:
                            continue
                        nid = _make_id(text)
                        if nid in self._seen_ids:
                            continue

                        text_lower = text.lower()
                        if any(kw in text_lower for kw in ["commented", "replied"]):
                            ntype = "comment"
                            priority = "high"
                        elif any(kw in text_lower for kw in ["message", "dm", "request"]):
                            ntype = "message"
                            priority = "urgent"
                        elif any(kw in text_lower for kw in ["mentioned", "tagged"]):
                            ntype = "mention"
                            priority = "high"
                        elif any(kw in text_lower for kw in ["liked", "love"]):
                            ntype = "like"
                            priority = "normal"
                        elif any(kw in text_lower for kw in ["followed", "started following"]):
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
            log.warning("Instagram: page load timed out — will retry next cycle")
        except Exception as exc:
            log.error("Instagram watcher error: %s", exc)

        _save_seen_ids(self._seen_ids)
        return notifications

    def create_action_file(self, item: dict) -> Path:
        """Write SOCIAL_IG_<id>.md to Needs_Action/."""
        now = datetime.now(timezone.utc)
        filename = f"SOCIAL_IG_{item['id']}.md"
        filepath = Path(self.vault_path) / "Needs_Action" / filename

        content = (
            f"---\n"
            f"type: social_instagram\n"
            f"platform: instagram\n"
            f"notification_type: {item['type']}\n"
            f"priority: {item['priority']}\n"
            f"created_at: {now.isoformat()}\n"
            f"status: pending\n"
            f"---\n\n"
            f"## Instagram {item['type'].title()}\n\n"
            f"{item['text']}\n\n"
            f"## Suggested Actions\n\n"
            f"- [ ] Reply to {item['type']}\n"
            f"- [ ] Engage with post if appropriate\n"
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
            "InstagramWatcher started | interval=%ds | vault=%s | dry_run=%s",
            CHECK_INTERVAL, VAULT_PATH, DRY_RUN,
        )
        while True:
            try:
                items = self.check_for_updates()
                for item in items:
                    self.create_action_file(item)
                if items:
                    log.info("Processed %d new Instagram notification(s)", len(items))
            except Exception as exc:
                log.error("Unexpected error: %s", exc)
            time.sleep(CHECK_INTERVAL)


# ---------------------------------------------------------------------------
# CLI entry point — first-time session setup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Instagram Watcher")
    parser.add_argument(
        "--setup", action="store_true",
        help="Open browser non-headless for manual Instagram login (saves session)"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run one check cycle and exit (useful for testing)"
    )
    args = parser.parse_args()

    if args.setup:
        os.environ["LI_HEADLESS"] = "false"
        print(f"[InstagramWatcher] Setup mode — browser will open for manual login")
        print(f"[InstagramWatcher] Session will be saved to: {IG_SESSION_DIR}")
        w = InstagramWatcher()
        results = w.check_for_updates()
        print(f"[InstagramWatcher] Setup complete. Found {len(results)} notification(s).")
        sys.exit(0)

    elif args.once:
        w = InstagramWatcher()
        results = w.check_for_updates()
        for r in results:
            w.create_action_file(r)
        print(f"[InstagramWatcher] One-shot complete. Found {len(results)} notification(s).")
        sys.exit(0)

    else:
        InstagramWatcher().run()
