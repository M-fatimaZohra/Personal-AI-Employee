"""Entry point to run all AI Employee watchers."""

import signal
import sys
import time
from pathlib import Path

from filesystem_watcher import FilesystemWatcher

VAULT_PATH = Path(__file__).parent / "AI_Employee_Vault"


def main():
    print(f"[bronze-fte] Starting watchers...")
    print(f"[bronze-fte] Vault: {VAULT_PATH.resolve()}")
    print(f"[bronze-fte] Drop files into: {VAULT_PATH / 'Drop_Box'}")

    watcher = FilesystemWatcher(VAULT_PATH)

    def shutdown(signum, frame):
        print("\n[bronze-fte] Shutting down watchers...")
        watcher.stop()
        print("[bronze-fte] Goodbye.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    watcher.start()
    print("[bronze-fte] Watchers running. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
