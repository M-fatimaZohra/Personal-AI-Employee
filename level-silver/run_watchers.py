"""Entry point — starts all Silver tier AI Employee watchers."""

import os
import signal
import sys
import time
from pathlib import Path

from approval_watcher import ApprovalWatcher
from filesystem_watcher import FilesystemWatcher

VAULT_PATH = Path(__file__).parent / "AI_Employee_Vault"


def main():
    print("[silver-fte] Starting watchers...")
    print(f"[silver-fte] Vault: {VAULT_PATH.resolve()}")
    print(f"[silver-fte] Drop files into: {VAULT_PATH / 'Drop_Box'}")

    watchers = []

    # --- Filesystem watcher (always on) ---
    fs_watcher = FilesystemWatcher(VAULT_PATH)
    watchers.append(fs_watcher)

    # --- Approval watcher (always on) ---
    approval_watcher = ApprovalWatcher(VAULT_PATH)
    watchers.append(approval_watcher)

    # --- Gmail watcher (optional — requires credentials) ---
    gmail_creds = Path(__file__).parent / ".secrets" / "gmail_credentials.json"
    if gmail_creds.exists():
        try:
            from gmail_watcher import GmailWatcher
            watchers.append(GmailWatcher(VAULT_PATH))
            print("[silver-fte] Gmail watcher:     enabled")
        except Exception as e:
            print(f"[silver-fte] Gmail watcher:     SKIPPED — {e}")
    else:
        print(
            f"[silver-fte] Gmail watcher:     SKIPPED "
            f"(place gmail_credentials.json in {gmail_creds.parent})"
        )

    # --- WhatsApp watcher — managed by PM2 as Node.js process (Baileys) ---
    # whatsapp_watcher.js handles receive + send via WebSocket.
    # Python does not import or start it — PM2 owns this process entirely.
    wa_session = Path(__file__).parent / ".secrets" / "whatsapp_session"
    if wa_session.exists() and any(wa_session.iterdir()):
        print("[silver-fte] WhatsApp watcher:  Online (Baileys Node.js — managed by PM2)")
    else:
        print(
            "[silver-fte] WhatsApp watcher:  SKIPPED "
            "(run: node whatsapp_watcher.js --setup)"
        )

    # --- LinkedIn watcher (optional — requires Playwright session) ---
    li_session = Path(__file__).parent / ".secrets" / "linkedin_session"
    if li_session.exists() and any(li_session.iterdir()):
        try:
            from linkedin_watcher import LinkedInWatcher
            watchers.append(LinkedInWatcher(VAULT_PATH))
            print("[silver-fte] LinkedIn watcher:  enabled")
        except Exception as e:
            print(f"[silver-fte] LinkedIn watcher:  SKIPPED — {e}")
    else:
        print(
            "[silver-fte] LinkedIn watcher:  SKIPPED "
            "(run: uv run python linkedin_watcher.py --setup)"
        )

    def shutdown(signum, frame):
        print("\n[silver-fte] Shutting down watchers...")
        for w in reversed(watchers):
            try:
                w.stop()
            except Exception:
                pass
        print("[silver-fte] Goodbye.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Start all watchers
    for w in watchers:
        w.start()

    active = [type(w).__name__ for w in watchers]
    print(f"[silver-fte] Running: {', '.join(active)} | Ctrl+C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
