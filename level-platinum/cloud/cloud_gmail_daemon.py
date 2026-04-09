#!/usr/bin/env python3
"""
cloud_gmail_daemon.py - Standalone Gmail watcher daemon for cloud VM
Runs gmail_watcher in a loop without requiring Claude Code CLI
"""
import time
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from gmail_watcher import GmailWatcher
from logger import log_action

def main():
    vault = Path(__file__).parent / "AI_Employee_Vault"

    print("[cloud-gmail-daemon] Starting Gmail watcher (cloud mode)")
    print(f"[cloud-gmail-daemon] Vault: {vault}")

    watcher = GmailWatcher(vault)

    print("[cloud-gmail-daemon] Authenticating with Gmail...")
    watcher._service = watcher._authenticate()
    print("[cloud-gmail-daemon] Authentication successful")

    print("[cloud-gmail-daemon] Starting monitoring loop (every 2 minutes)")

    while True:
        try:
            print(f"[cloud-gmail-daemon] Checking for new emails...")
            new_items = watcher.check_for_updates()

            if new_items:
                print(f"[cloud-gmail-daemon] Found {len(new_items)} new emails")
                for item in new_items:
                    action_file = watcher.create_action_file(item)
                    print(f"[cloud-gmail-daemon] Created: {action_file.name}")
            else:
                print(f"[cloud-gmail-daemon] No new emails")

            # Sleep for 2 minutes
            time.sleep(120)

        except KeyboardInterrupt:
            print("\n[cloud-gmail-daemon] Shutting down gracefully...")
            break
        except Exception as e:
            print(f"[cloud-gmail-daemon] ERROR: {e}")
            log_action("cloud-gmail-daemon", "error", {"error": str(e)})
            # Sleep 30 seconds on error, then retry
            time.sleep(30)

if __name__ == "__main__":
    main()
