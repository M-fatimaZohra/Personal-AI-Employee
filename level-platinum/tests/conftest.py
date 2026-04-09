"""
Shared pytest configuration for level-silver tests.

Problem: level-silver/.env sets DRY_RUN=true (safe default for production).
         Tests that assert file writes would fail because the watchers skip
         writing when DRY_RUN is True.

Solution: Force DRY_RUN=False for all tests via an autouse fixture.
          DRY_RUN-specific tests still work because their `with patch(...)`
          context managers push DRY_RUN=True on top of this fixture's patch
          for the duration of that block, then restore it to False afterward.
"""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def force_dry_run_off():
    """Patch DRY_RUN to False in all watcher modules for the duration of each test."""
    # Patch the module-level name in every watcher that imports from logger.
    # gmail_watcher tests pass without this (they mock at a higher level),
    # but patching it anyway keeps the suite consistent.
    targets = [
        "filesystem_watcher.DRY_RUN",
        # whatsapp_watcher is a Node.js file (whatsapp_watcher.js) — no Python
        # module exists to patch. WhatsApp tests mock at a higher level.
        "linkedin_watcher.DRY_RUN",
        "gmail_watcher.DRY_RUN",
    ]
    active = [patch(t, False) for t in targets]
    for p in active:
        p.start()
    yield
    for p in active:
        p.stop()
