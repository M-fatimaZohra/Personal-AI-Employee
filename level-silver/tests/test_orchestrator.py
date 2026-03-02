"""Tests for orchestrator.Orchestrator."""

import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orchestrator import SKILL_ROUTING, Orchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "AI_Employee_Vault"
    vault.mkdir()
    for folder in [
        "Needs_Action", "Plans", "Logs", "Done",
        "Drop_Box", "Inbox", "Approved", "Rejected",
        "Pending_Approval",
    ]:
        (vault / folder).mkdir()
    return vault


def make_orchestrator(tmp_path: Path) -> Orchestrator:
    vault = make_vault(tmp_path)
    return Orchestrator(vault_path=vault, heartbeat=1)


# ---------------------------------------------------------------------------
# validate_claude
# ---------------------------------------------------------------------------

def test_validate_claude_returns_true_when_found(tmp_path, monkeypatch):
    orch = make_orchestrator(tmp_path)
    mock_result = MagicMock()
    mock_result.returncode = 0
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)
    assert orch.validate_claude() is True


def test_validate_claude_returns_false_when_not_found(tmp_path, monkeypatch):
    orch = make_orchestrator(tmp_path)

    def raise_fnf(*a, **kw):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", raise_fnf)
    assert orch.validate_claude() is False


def test_validate_claude_returns_false_on_nonzero_exit(tmp_path, monkeypatch):
    orch = make_orchestrator(tmp_path)
    mock_result = MagicMock()
    mock_result.returncode = 1
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)
    assert orch.validate_claude() is False


# ---------------------------------------------------------------------------
# skill_for — routing table
# ---------------------------------------------------------------------------

def test_skill_for_email_prefix(tmp_path):
    orch = make_orchestrator(tmp_path)
    assert orch.skill_for("EMAIL_abc123.md") == "fte-gmail-triage"


def test_skill_for_whatsapp_prefix(tmp_path):
    orch = make_orchestrator(tmp_path)
    assert orch.skill_for("WHATSAPP_789xyz.md") == "fte-whatsapp-reply"


def test_skill_for_file_prefix(tmp_path):
    orch = make_orchestrator(tmp_path)
    assert orch.skill_for("FILE_report.md") == "fte-triage"


def test_skill_for_unknown_prefix_returns_none(tmp_path):
    orch = make_orchestrator(tmp_path)
    assert orch.skill_for("UNKNOWN_thing.md") is None
    assert orch.skill_for("random.md") is None


def test_skill_routing_table_is_complete():
    """Ensure all expected prefixes are present."""
    assert "EMAIL_" in SKILL_ROUTING
    assert "WHATSAPP_" in SKILL_ROUTING
    assert "LINKEDIN_NOTIF_" in SKILL_ROUTING
    assert "FILE_" in SKILL_ROUTING


# ---------------------------------------------------------------------------
# check_needs_action — dispatch logic
# ---------------------------------------------------------------------------

def test_check_needs_action_dispatches_email_file(tmp_path):
    orch = make_orchestrator(tmp_path)
    dispatched = []

    def fake_dispatch(filepath, prompt):
        dispatched.append((filepath.name, prompt))

    orch._dispatch = fake_dispatch
    (orch.needs_action / "EMAIL_abc.md").write_text("---\ntype: email\n---\n")

    orch.check_needs_action()

    assert len(dispatched) == 1
    assert dispatched[0][0] == "EMAIL_abc.md"
    assert "/fte-gmail-triage" in dispatched[0][1]


def test_check_needs_action_dispatches_whatsapp_and_file(tmp_path):
    orch = make_orchestrator(tmp_path)
    dispatched = []
    orch._dispatch = lambda fp, p: dispatched.append(fp.name)

    (orch.needs_action / "WHATSAPP_001.md").write_text("---\ntype: whatsapp_message\n---\n")
    (orch.needs_action / "FILE_doc.md").write_text("---\ntype: file_drop\n---\n")

    orch.check_needs_action()

    assert "WHATSAPP_001.md" in dispatched
    assert "FILE_doc.md" in dispatched


def test_check_needs_action_skips_unknown_prefix(tmp_path):
    orch = make_orchestrator(tmp_path)
    dispatched = []
    orch._dispatch = lambda fp, p: dispatched.append(fp.name)

    (orch.needs_action / "PLAN_something.md").write_text("body")
    (orch.needs_action / "random.md").write_text("body")

    orch.check_needs_action()

    assert dispatched == []


def test_check_needs_action_skips_in_flight_files(tmp_path):
    orch = make_orchestrator(tmp_path)
    dispatched = []
    orch._dispatch = lambda fp, p: dispatched.append(fp.name)

    path = orch.needs_action / "EMAIL_xyz.md"
    path.write_text("---\ntype: email\n---\n")

    with orch._lock:
        orch._in_flight.add("EMAIL_xyz.md")

    orch.check_needs_action()

    assert dispatched == []


def test_check_needs_action_no_action_if_folder_missing(tmp_path):
    orch = make_orchestrator(tmp_path)
    orch.needs_action.rmdir()
    dispatched = []
    orch._dispatch = lambda fp, p: dispatched.append(fp.name)

    orch.check_needs_action()  # must not raise

    assert dispatched == []


# ---------------------------------------------------------------------------
# check_plans — Ralph Wiggum pattern
# ---------------------------------------------------------------------------

def test_check_plans_dispatches_for_unchecked_steps(tmp_path):
    orch = make_orchestrator(tmp_path)
    dispatched = []
    orch._dispatch = lambda fp, p: dispatched.append((fp.name, p))

    plan = orch.plans / "PLAN_task1.md"
    plan.write_text("---\ntype: plan\n---\n\n- [x] Done step\n- [ ] Pending step\n")

    orch.check_plans()

    assert len(dispatched) == 1
    assert "PLAN_task1.md" in dispatched[0][1]
    assert "fte-plan" in dispatched[0][1]


def test_check_plans_skips_fully_checked_plan(tmp_path):
    orch = make_orchestrator(tmp_path)
    dispatched = []
    orch._dispatch = lambda fp, p: dispatched.append(fp.name)

    plan = orch.plans / "PLAN_done.md"
    plan.write_text("---\ntype: plan\n---\n\n- [x] Step one\n- [x] Step two\n")

    orch.check_plans()

    assert dispatched == []


def test_check_plans_skips_in_flight_plan(tmp_path):
    orch = make_orchestrator(tmp_path)
    dispatched = []
    orch._dispatch = lambda fp, p: dispatched.append(fp.name)

    plan = orch.plans / "PLAN_active.md"
    plan.write_text("---\ntype: plan\n---\n\n- [ ] Not done\n")

    with orch._lock:
        orch._in_flight.add("PLAN_active.md")

    orch.check_plans()

    assert dispatched == []


def test_check_plans_dispatches_only_one_plan_per_tick(tmp_path):
    """Prevent parallel Claude pile-up — only the first unfinished plan per tick."""
    orch = make_orchestrator(tmp_path)
    dispatched = []
    orch._dispatch = lambda fp, p: dispatched.append(fp.name)

    for i in range(3):
        p = orch.plans / f"PLAN_task{i}.md"
        p.write_text(f"---\ntype: plan\n---\n\n- [ ] Step {i}\n")

    orch.check_plans()

    assert len(dispatched) == 1


def test_check_plans_no_action_if_folder_missing(tmp_path):
    orch = make_orchestrator(tmp_path)
    orch.plans.rmdir()
    dispatched = []
    orch._dispatch = lambda fp, p: dispatched.append(fp.name)

    orch.check_plans()  # must not raise

    assert dispatched == []


# ---------------------------------------------------------------------------
# _dispatch — in-flight dedup
# ---------------------------------------------------------------------------

def test_dispatch_adds_to_in_flight_and_removes_on_completion(tmp_path):
    orch = make_orchestrator(tmp_path)

    completed = threading.Event()
    started = threading.Event()

    def fake_popen(*args, **kwargs):
        started.set()
        proc = MagicMock()
        proc.communicate.return_value = ("", "")
        proc.returncode = 0
        proc.poll.return_value = 0
        completed.set()
        return proc

    filepath = orch.needs_action / "EMAIL_test.md"
    filepath.write_text("body")

    with patch("subprocess.Popen", side_effect=fake_popen):
        orch._dispatch(filepath, "/fte-gmail-triage EMAIL_test.md")
        started.wait(timeout=2)
        completed.wait(timeout=2)
        time.sleep(0.1)  # let thread finalise

    with orch._lock:
        assert "EMAIL_test.md" not in orch._in_flight


def test_dispatch_prevents_duplicate_calls(tmp_path):
    orch = make_orchestrator(tmp_path)
    popen_calls: list = []

    def fake_popen(*args, **kwargs):
        popen_calls.append(1)
        proc = MagicMock()
        proc.communicate.return_value = ("", "")
        proc.returncode = 0
        proc.poll.return_value = 0
        return proc

    filepath = orch.needs_action / "EMAIL_dup.md"
    filepath.write_text("body")

    with orch._lock:
        orch._in_flight.add("EMAIL_dup.md")

    with patch("subprocess.Popen", side_effect=fake_popen):
        orch._dispatch(filepath, "/fte-gmail-triage EMAIL_dup.md")
        time.sleep(0.1)

    assert popen_calls == []  # no subprocess was started


# ---------------------------------------------------------------------------
# tick — orchestrates all three actions
# ---------------------------------------------------------------------------

def test_tick_calls_all_three_methods(tmp_path):
    orch = make_orchestrator(tmp_path)
    calls = []

    orch.check_needs_action = lambda: calls.append("needs_action")
    orch.check_plans = lambda: calls.append("plans")
    orch.sync_dashboard = lambda: calls.append("dashboard")

    orch.tick()

    assert calls == ["needs_action", "plans", "dashboard"]


def test_tick_continues_despite_individual_errors(tmp_path):
    orch = make_orchestrator(tmp_path)
    calls = []

    def raise_err():
        raise RuntimeError("boom")

    orch.check_needs_action = raise_err
    orch.check_plans = raise_err
    orch.sync_dashboard = lambda: calls.append("dashboard")

    orch.tick()  # must not raise

    assert "dashboard" in calls


# ---------------------------------------------------------------------------
# stop — clean shutdown
# ---------------------------------------------------------------------------

def test_stop_calls_stop_on_all_watchers(tmp_path):
    orch = make_orchestrator(tmp_path)
    stopped = []

    mock_w1 = MagicMock()
    mock_w1.stop.side_effect = lambda: stopped.append("w1")
    mock_w2 = MagicMock()
    mock_w2.stop.side_effect = lambda: stopped.append("w2")
    orch._watchers = [mock_w1, mock_w2]

    orch.stop()

    assert "w1" in stopped
    assert "w2" in stopped


def test_stop_terminates_running_subprocesses(tmp_path):
    orch = make_orchestrator(tmp_path)
    terminated = []

    proc = MagicMock()
    proc.poll.return_value = None  # still running
    proc.terminate.side_effect = lambda: terminated.append(1)

    with orch._lock:
        orch._subprocesses.append(proc)

    orch.stop()

    assert terminated == [1]


def test_stop_clears_in_flight(tmp_path):
    orch = make_orchestrator(tmp_path)
    with orch._lock:
        orch._in_flight.add("EMAIL_x.md")

    orch.stop()

    with orch._lock:
        assert len(orch._in_flight) == 0


def test_stop_tolerates_watcher_stop_exceptions(tmp_path):
    orch = make_orchestrator(tmp_path)

    bad = MagicMock()
    bad.stop.side_effect = RuntimeError("crash")
    orch._watchers = [bad]

    orch.stop()  # must not raise
