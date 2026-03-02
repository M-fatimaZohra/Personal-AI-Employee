#!/usr/bin/env python3
"""stop.py — Claude Code Stop Hook (Ralph Wiggum pattern)

Fires whenever Claude is about to stop a session. If unchecked plan steps
remain in AI_Employee_Vault/Plans/, re-injects a /fte-plan continuation
prompt (up to MAX_INJECTIONS times). Logs every decision via logger.log_action.

Claude Code Stop Hook Protocol:
  - stdin:  JSON context {"session_id", "stop_hook_active", "last_assistant_message", ...}
  - stdout: {"decision": "block", "reason": "<prompt>"} → Claude continues with reason as next prompt
  - stdout: empty (or exit 0)                           → Claude is allowed to stop
  - stop_hook_active: True when Claude is ALREADY in a hook-triggered continuation
"""

import json
import os
import sys
import time
from pathlib import Path

# ── Locate level-silver root from this script's location ──────────────────────
# This script lives at: level-silver/.claude/hooks/stop.py
# So parent chain:      hooks/ → .claude/ → level-silver/
HOOK_DIR = Path(__file__).parent          # .claude/hooks/
SILVER_ROOT = HOOK_DIR.parent.parent      # level-silver/

# ── Constants ──────────────────────────────────────────────────────────────────
VAULT = SILVER_ROOT / "AI_Employee_Vault"
PLANS_DIR = VAULT / "Plans"
LOGS_DIR = VAULT / "Logs"
STATE_FILE = HOOK_DIR / ".injection_state.json"  # persists count across calls
STATE_DIR  = SILVER_ROOT / ".state"              # flag files written by orchestrator

MAX_INJECTIONS  = 5    # hard limit — prevents infinite re-injection loops
FLAG_MAX_AGE_S  = 400  # SKILL_DISPATCH_TIMEOUT (300s) + 100s buffer


# ── State helpers ──────────────────────────────────────────────────────────────

def _load_state() -> dict:
    """Load injection count + last plan name from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"count": 0, "last_plan": ""}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def _clear_state() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()


# ── Logging helper ─────────────────────────────────────────────────────────────

def _log(action: str, result: str, details: str = "") -> None:
    """Log via logger.log_action (best-effort; never crash the hook)."""
    try:
        sys.path.insert(0, str(SILVER_ROOT))
        from logger import log_action  # noqa: PLC0415
        log_action(
            LOGS_DIR,
            action=action,
            actor="stop_hook",
            result=result,
            details=details,
        )
    except Exception:
        pass  # logging must never block the hook decision


# ── Plan scanner ───────────────────────────────────────────────────────────────

def _find_unchecked_plan() -> tuple:
    """Scan Plans/ for the first .md file containing '- [ ]' (unchecked step).

    Returns:
        (plan_path, plan_name) if an active plan with unchecked steps exists.
        (None, "")             if all plans are complete or Plans/ is empty.
    """
    if not PLANS_DIR.exists():
        return None, ""

    for plan_file in sorted(PLANS_DIR.glob("*.md")):
        try:
            text = plan_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "- [ ]" in text:
            return plan_file, plan_file.name

    return None, ""


# ── Automated-dispatch detector ────────────────────────────────────────────────

def _is_automated_dispatch() -> bool:
    """Return True if an orchestrator/ApprovalWatcher dispatch is currently active.

    Checks the env var first (fast path). Falls back to a flag file on disk
    because Claude Code sanitises the subprocess environment before invoking
    hooks, so FTE_AUTOMATED_DISPATCH=1 set on the parent claude process is
    stripped and never reaches this script via os.environ.

    Flag file protocol:
      - orchestrator._dispatch()._run() writes .state/dispatch_<tid>_<ts>.flag
        before Popen and deletes it in the finally block.
      - approval_watcher._mcp_send_impl() writes .state/dispatch_aw_<ts>.flag
        around subprocess.run and deletes it in the finally block.
      - Any flag file younger than FLAG_MAX_AGE_S seconds means an active
        dispatch owns this claude session → skip re-injection.
    """
    if os.environ.get("FTE_AUTOMATED_DISPATCH") == "1":
        return True
    if STATE_DIR.exists():
        now = time.time()
        for flag in STATE_DIR.glob("dispatch_*.flag"):
            try:
                if now - flag.stat().st_mtime < FLAG_MAX_AGE_S:
                    return True
            except OSError:
                pass
    return False


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    # 0. Bypass for automated orchestrator/ApprovalWatcher dispatches.
    #    When orchestrator.py or approval_watcher.py spawn `claude --print`,
    #    they set FTE_AUTOMATED_DISPATCH=1.  The Ralph Wiggum re-injection
    #    must NOT block these — it would cause every skill to hit the 300s
    #    SKILL_DISPATCH_TIMEOUT, orphan claude processes, and create infinite
    #    retry loops.  Interactive claude sessions (no env var) keep the
    #    full re-injection behaviour.
    if _is_automated_dispatch():
        _clear_state()
        _log(
            "stop_hook_skipped",
            "info",
            "Automated dispatch active (flag file or env var) — bypassing re-injection",
        )
        sys.exit(0)

    # 1. Read Claude's stop context from stdin
    try:
        raw = sys.stdin.read()
        ctx = json.loads(raw) if raw.strip() else {}
    except Exception:
        ctx = {}

    stop_hook_active: bool = ctx.get("stop_hook_active", False)

    # 2. Load persistent injection state
    state = _load_state()
    count: int = state.get("count", 0)

    # 3. Scan Plans/ for unchecked steps
    plan_path, plan_name = _find_unchecked_plan()

    # 4. Decision tree ────────────────────────────────────────────────────────

    if plan_path is None:
        # No active plans with unchecked steps → allow Claude to stop cleanly
        _clear_state()
        _log(
            "stop_hook_exit",
            "success",
            "No unchecked plan steps found — allowing stop",
        )
        sys.exit(0)

    if count >= MAX_INJECTIONS:
        # Safety limit reached → allow stop to prevent runaway loops
        _clear_state()
        _log(
            "stop_hook_limit",
            "error",
            f"Max injections ({MAX_INJECTIONS}) reached for plan '{plan_name}' — forcing stop",
        )
        sys.exit(0)

    # 5. Block stop and re-inject plan continuation prompt ────────────────────
    new_count = count + 1
    _save_state({"count": new_count, "last_plan": plan_name})

    reason = f"/fte-plan continue {plan_name}"

    _log(
        "stop_hook_inject",
        "success",
        f"Unchecked steps in '{plan_name}' — re-injecting '{reason}' "
        f"(injection {new_count}/{MAX_INJECTIONS}; stop_hook_active={stop_hook_active})",
    )

    # Claude Code Stop hook: write JSON to stdout to re-inject as next prompt
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


if __name__ == "__main__":
    main()
