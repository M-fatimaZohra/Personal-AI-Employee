"""Tests for approval_watcher.ApprovalWatcher."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from approval_watcher import (
    ApprovalWatcher,
    _parse_frontmatter,
    _rewrite_status,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_vault(tmp_path: Path) -> Path:
    """Create a minimal vault directory structure."""
    vault = tmp_path / "AI_Employee_Vault"
    vault.mkdir()
    for folder in ["Approved", "Rejected", "Done", "Pending_Approval", "Logs",
                   "Needs_Action", "Drop_Box", "Inbox", "Plans"]:
        (vault / folder).mkdir()
    return vault


def write_approval(folder: Path, name: str, **fm_fields) -> Path:
    """Write a minimal approval file to *folder*."""
    fm_lines = "\n".join(f"{k}: {v}" for k, v in fm_fields.items())
    content = f"---\n{fm_lines}\n---\n\nDraft content here.\n"
    path = folder / name
    path.write_text(content, encoding="utf-8")
    return path


def make_watcher(vault: Path) -> ApprovalWatcher:
    """Construct an ApprovalWatcher without starting threads."""
    return ApprovalWatcher(vault, check_interval=1)


# ---------------------------------------------------------------------------
# Unit tests: _parse_frontmatter
# ---------------------------------------------------------------------------

def test_parse_frontmatter_basic():
    text = "---\ntype: email_reply\nto: x@y.com\n---\n\nbody"
    fm = _parse_frontmatter(text)
    assert fm["type"] == "email_reply"
    assert fm["to"] == "x@y.com"


def test_parse_frontmatter_no_frontmatter():
    assert _parse_frontmatter("just body") == {}


def test_parse_frontmatter_incomplete_delimiters():
    assert _parse_frontmatter("---\ntype: x\n") == {}


# ---------------------------------------------------------------------------
# Unit tests: _rewrite_status
# ---------------------------------------------------------------------------

def test_rewrite_status_updates_existing():
    text = "---\ntype: email_reply\nstatus: pending\n---\n\nbody\n"
    result = _rewrite_status(text, "executed")
    assert "status: executed" in result
    assert "status: pending" not in result


def test_rewrite_status_preserves_body():
    text = "---\nstatus: pending\n---\n\nHello world\n"
    result = _rewrite_status(text, "rejected")
    assert "Hello world" in result


# ---------------------------------------------------------------------------
# ApprovalWatcher._validate
# ---------------------------------------------------------------------------

def test_validate_valid_email_reply(tmp_path):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)
    err = w._validate({"type": "email_reply", "to": "x@y.com", "subject": "Hi"})
    assert err == ""


def test_validate_missing_type(tmp_path):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)
    err = w._validate({"to": "x@y.com"})
    assert "Missing required field: type" in err


def test_validate_unknown_type(tmp_path):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)
    err = w._validate({"type": "carrier_pigeon"})
    assert "Unknown action type" in err


def test_validate_missing_required_field(tmp_path):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)
    # email_reply requires 'to' and 'subject'
    err = w._validate({"type": "email_reply", "to": "x@y.com"})
    assert "subject" in err


def test_validate_linkedin_post_no_required_fields(tmp_path):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)
    err = w._validate({"type": "linkedin_post"})
    assert err == ""


# ---------------------------------------------------------------------------
# _process_rejected
# ---------------------------------------------------------------------------

def test_process_rejected_moves_to_done(tmp_path):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)
    path = write_approval(vault / "Rejected", "APPROVAL_001.md",
                          type="email_reply", status="pending")

    done_path = w._process_rejected(path)

    assert done_path.parent == vault / "Done"
    assert not path.exists()


def test_process_rejected_sets_status(tmp_path):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)
    path = write_approval(vault / "Rejected", "APPROVAL_002.md",
                          type="email_reply", status="pending")

    done_path = w._process_rejected(path)

    content = done_path.read_text()
    assert "status: rejected" in content


def test_process_rejected_writes_log(tmp_path):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)
    path = write_approval(vault / "Rejected", "APPROVAL_log.md",
                          type="email_reply", status="pending")

    w._process_rejected(path)

    log_files = list((vault / "Logs").glob("*.json"))
    assert log_files
    entries = [json.loads(l) for l in log_files[0].read_text().splitlines() if l.strip()]
    actions = [e["action"] for e in entries]
    assert "approval_rejected" in actions


# ---------------------------------------------------------------------------
# _process_approved — happy path (DRY_RUN stub)
# ---------------------------------------------------------------------------

def test_process_approved_valid_dry_run(tmp_path, monkeypatch):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)
    monkeypatch.setattr("approval_watcher.DRY_RUN", True)

    path = write_approval(vault / "Approved", "APPROVAL_dry.md",
                          type="email_reply", to="a@b.com",
                          subject="Hello", status="pending")

    done_path = w._process_approved(path)

    assert done_path.parent == vault / "Done"
    assert "dry_run" in done_path.read_text()


def test_process_approved_executes_mcp_stub(tmp_path, monkeypatch):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)
    monkeypatch.setattr("approval_watcher.DRY_RUN", False)

    dispatched = []

    def fake_mcp(action_data):
        dispatched.append(action_data["type"])

    # Replace the backoff-wrapped version directly
    w._send_via_mcp = fake_mcp

    path = write_approval(vault / "Approved", "APPROVAL_exec.md",
                          type="email_reply", to="a@b.com",
                          subject="Hi", status="pending")

    done_path = w._process_approved(path)

    assert dispatched == ["email_reply"]
    assert done_path.parent == vault / "Done"
    assert "status: executed" in done_path.read_text()


# ---------------------------------------------------------------------------
# _process_approved — validation failure
# ---------------------------------------------------------------------------

def test_process_approved_invalid_type_routes_to_rejected(tmp_path, monkeypatch):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)
    monkeypatch.setattr("approval_watcher.DRY_RUN", False)

    path = write_approval(vault / "Approved", "APPROVAL_bad.md",
                          type="carrier_pigeon", status="pending")

    done_path = w._process_approved(path)

    assert done_path.parent == vault / "Done"
    assert "status: validation_failed" in done_path.read_text()
    assert "Validation Error" in done_path.read_text()


def test_process_approved_missing_required_field(tmp_path, monkeypatch):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)
    monkeypatch.setattr("approval_watcher.DRY_RUN", False)

    # email_reply without 'to'
    path = write_approval(vault / "Approved", "APPROVAL_noto.md",
                          type="email_reply", subject="Hi", status="pending")

    done_path = w._process_approved(path)
    assert "validation_failed" in done_path.read_text()


# ---------------------------------------------------------------------------
# IDTracker prevents duplicate processing
# ---------------------------------------------------------------------------

def test_id_tracker_prevents_double_processing(tmp_path, monkeypatch):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)
    monkeypatch.setattr("approval_watcher.DRY_RUN", True)

    path = write_approval(vault / "Approved", "APPROVAL_dedup.md",
                          type="email_reply", to="x@y.com",
                          subject="Hi", status="pending")

    # First call — should process and move
    done_path = w.create_action_file(("approved", path))
    assert done_path.parent == vault / "Done"

    # Second call with same stem — IDTracker must skip it
    result = w.create_action_file(("approved", path))
    # path no longer exists (moved), result is the original path returned unchanged
    assert result == path


# ---------------------------------------------------------------------------
# Expiration sweep
# ---------------------------------------------------------------------------

def test_sweep_expired_moves_expired_file(tmp_path):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)

    past = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    path = write_approval(vault / "Pending_Approval", "APPROVAL_old.md",
                          type="email_reply", status="pending",
                          expires_at=past)

    w._sweep_expired()

    assert not path.exists()
    done_files = list((vault / "Done").glob("*.md"))
    assert done_files
    assert "status: expired" in done_files[0].read_text()


def test_sweep_expired_leaves_fresh_file(tmp_path):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)

    future = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    path = write_approval(vault / "Pending_Approval", "APPROVAL_fresh.md",
                          type="email_reply", status="pending",
                          expires_at=future)

    w._sweep_expired()

    assert path.exists()  # must not be moved
    assert not list((vault / "Done").glob("*.md"))


def test_sweep_expired_skips_files_without_expires_at(tmp_path):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)

    path = write_approval(vault / "Pending_Approval", "APPROVAL_noexp.md",
                          type="email_reply", status="pending")

    w._sweep_expired()

    assert path.exists()  # no expires_at — must not touch it


# ---------------------------------------------------------------------------
# check_for_updates
# ---------------------------------------------------------------------------

def test_check_for_updates_returns_approved_and_rejected(tmp_path):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)

    write_approval(vault / "Approved", "APPROVAL_a.md",
                   type="email_reply", to="x@y.com", subject="Hi")
    write_approval(vault / "Rejected", "APPROVAL_b.md",
                   type="email_reply", status="pending")

    items = w.check_for_updates()
    decisions = {decision for decision, _ in items}
    assert "approved" in decisions
    assert "rejected" in decisions


def test_check_for_updates_excludes_already_tracked(tmp_path):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)

    path = write_approval(vault / "Approved", "APPROVAL_seen.md",
                          type="email_reply", to="x@y.com", subject="Hi")

    w._tracker.mark_processed("approvals", path.stem)
    items = w.check_for_updates()
    assert not items


# ---------------------------------------------------------------------------
# _move_to_done
# ---------------------------------------------------------------------------

def test_move_to_done_collision_gets_timestamp_suffix(tmp_path):
    vault = make_vault(tmp_path)
    w = make_watcher(vault)

    p1 = write_approval(vault / "Approved", "APPROVAL_col.md",
                        type="email_reply", status="pending")
    p2 = write_approval(vault / "Rejected", "APPROVAL_col.md",
                        type="email_reply", status="pending")

    d1 = w._move_to_done(p1, "executed")
    d2 = w._move_to_done(p2, "rejected")

    assert d1 != d2
    assert d1.parent == vault / "Done"
    assert d2.parent == vault / "Done"
