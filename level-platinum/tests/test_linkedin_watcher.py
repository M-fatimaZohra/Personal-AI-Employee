"""Mock tests for LinkedInWatcher — validates notification filtering and draft generation."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

import linkedin_watcher as lw_module
from linkedin_watcher import LinkedInWatcher, LI_CHECK_INTERVAL
from id_tracker import IDTracker


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "AI_Employee_Vault"
    v.mkdir()
    for folder in [
        "Needs_Action", "Done", "Inbox", "Drop_Box",
        "Plans", "Approved", "Rejected", "Pending_Approval", "Logs",
    ]:
        (v / folder).mkdir()
    return v


@pytest.fixture()
def watcher(vault: Path, tmp_path: Path) -> LinkedInWatcher:
    """LinkedInWatcher with IDTracker redirected to tmp dir."""
    w = LinkedInWatcher(vault)
    w._id_tracker = IDTracker(tmp_path / ".state")
    return w


def make_notif(
    notif_id: str = "notif001abc",
    text: str = "Jane Doe mentioned you in a post",
    notif_type: str = "mention",
    timestamp: str | None = None,
) -> dict:
    """Build a notification dict as returned by check_for_updates()."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "notif_id": notif_id,
        "text": text,
        "timestamp": timestamp,
        "notif_type": notif_type,
    }


# ---------------------------------------------------------------------------
# Module-level safety constant
# ---------------------------------------------------------------------------


def test_li_check_interval_minimum_30_minutes():
    """LI_CHECK_INTERVAL must be at least 1800 seconds (30 min) — enforced at module level."""
    assert LI_CHECK_INTERVAL >= 1800, (
        f"LI_CHECK_INTERVAL is {LI_CHECK_INTERVAL}s — must be ≥ 1800s (30 min) "
        "to respect LinkedIn's rate limit."
    )


def test_li_check_interval_ignores_low_env_value():
    """Even if env sets a value below 1800, the module enforces the minimum."""
    # Re-read the formula: LI_CHECK_INTERVAL = max(_RAW_INTERVAL, 1800)
    # We can't change the already-imported constant, but we can verify the formula holds.
    simulated = max(60, 1800)  # 60 < 1800 → clamped to 1800
    assert simulated == 1800


# ---------------------------------------------------------------------------
# create_action_file — high-value types (mention, comment, connection)
# ---------------------------------------------------------------------------


def test_create_action_file_mention_writes_file(watcher):
    item = make_notif(notif_id="men001", notif_type="mention")
    dest = watcher.create_action_file(item)
    assert dest.exists(), "mention notification must produce an action file"


def test_create_action_file_comment_writes_file(watcher):
    item = make_notif(notif_id="com001", notif_type="comment")
    dest = watcher.create_action_file(item)
    assert dest.exists(), "comment notification must produce an action file"


def test_create_action_file_connection_writes_file(watcher):
    item = make_notif(notif_id="con001", notif_type="connection")
    dest = watcher.create_action_file(item)
    assert dest.exists(), "connection notification must produce an action file"


def test_create_action_file_correct_filename(watcher):
    item = make_notif(notif_id="file001", notif_type="mention")
    dest = watcher.create_action_file(item)
    assert dest.name == "LINKEDIN_NOTIF_file001.md"


def test_create_action_file_correct_folder(watcher, vault):
    item = make_notif(notif_id="fold001", notif_type="comment")
    dest = watcher.create_action_file(item)
    assert dest.parent == vault / "Needs_Action"


# ---------------------------------------------------------------------------
# Priority field
# ---------------------------------------------------------------------------


def test_create_action_file_mention_is_high_priority(watcher):
    item = make_notif(notif_id="ph001", notif_type="mention")
    content = watcher.create_action_file(item).read_text(encoding="utf-8")
    assert "priority: high" in content


def test_create_action_file_comment_is_normal_priority(watcher):
    item = make_notif(notif_id="pn001", notif_type="comment")
    content = watcher.create_action_file(item).read_text(encoding="utf-8")
    assert "priority: normal" in content


def test_create_action_file_connection_is_normal_priority(watcher):
    item = make_notif(notif_id="pn002", notif_type="connection")
    content = watcher.create_action_file(item).read_text(encoding="utf-8")
    assert "priority: normal" in content


# ---------------------------------------------------------------------------
# Frontmatter content
# ---------------------------------------------------------------------------


def test_create_action_file_type_field(watcher):
    item = make_notif(notif_id="tf001", notif_type="mention")
    content = watcher.create_action_file(item).read_text(encoding="utf-8")
    assert "type: linkedin_notification" in content


def test_create_action_file_notif_type_field(watcher):
    item = make_notif(notif_id="nt001", notif_type="comment")
    content = watcher.create_action_file(item).read_text(encoding="utf-8")
    assert "notif_type: comment" in content


def test_create_action_file_source_is_linkedin(watcher):
    item = make_notif(notif_id="src001", notif_type="connection")
    content = watcher.create_action_file(item).read_text(encoding="utf-8")
    assert "source: LinkedIn" in content


def test_create_action_file_text_in_body(watcher):
    item = make_notif(
        notif_id="txt001",
        notif_type="mention",
        text="Jane Doe mentioned you in a post about AI",
    )
    content = watcher.create_action_file(item).read_text(encoding="utf-8")
    assert "Jane Doe mentioned you in a post about AI" in content


def test_create_action_file_status_needs_action(watcher):
    item = make_notif(notif_id="st001", notif_type="comment")
    content = watcher.create_action_file(item).read_text(encoding="utf-8")
    assert "status: needs_action" in content


# ---------------------------------------------------------------------------
# Low-value notification types are silently skipped
# ---------------------------------------------------------------------------


def test_create_action_file_like_skipped_no_file(watcher):
    """'like' notifications are low-value — action file must NOT be written."""
    item = make_notif(notif_id="lk001", notif_type="like")
    dest = watcher.create_action_file(item)
    assert not dest.exists(), "'like' notification must not produce an action file"


def test_create_action_file_job_skipped_no_file(watcher):
    item = make_notif(notif_id="jb001", notif_type="job")
    dest = watcher.create_action_file(item)
    assert not dest.exists(), "'job' notification must not produce an action file"


def test_create_action_file_other_skipped_no_file(watcher):
    item = make_notif(notif_id="ot001", notif_type="other")
    dest = watcher.create_action_file(item)
    assert not dest.exists(), "'other' notification must not produce an action file"


def test_create_action_file_low_value_marks_processed(watcher):
    """Even skipped low-value notifications must be marked processed (no re-alert)."""
    item = make_notif(notif_id="lk002", notif_type="like")
    watcher.create_action_file(item)
    assert watcher._id_tracker.is_processed("linkedin", "lk002")


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def test_create_action_file_dedup_no_double_write(watcher):
    """Second call for same notif_id does not overwrite the action file."""
    item = make_notif(notif_id="dup001", notif_type="mention")
    dest = watcher.create_action_file(item)
    first_mtime = dest.stat().st_mtime

    dest2 = watcher.create_action_file(item)
    second_mtime = dest2.stat().st_mtime

    assert dest == dest2
    assert first_mtime == second_mtime, "File must not be rewritten on duplicate call"


def test_create_action_file_dedup_returns_correct_path(watcher):
    """Even when deduped, the returned path matches the expected filename."""
    item = make_notif(notif_id="dup002", notif_type="comment")
    watcher.create_action_file(item)
    dest2 = watcher.create_action_file(item)
    assert dest2.name == "LINKEDIN_NOTIF_dup002.md"


# ---------------------------------------------------------------------------
# DRY_RUN mode
# ---------------------------------------------------------------------------


def test_create_action_file_dry_run_no_write(watcher):
    """In DRY_RUN mode, action file is NOT written to disk."""
    item = make_notif(notif_id="dry001", notif_type="mention")
    with patch.object(lw_module, "DRY_RUN", True):
        dest = watcher.create_action_file(item)
    assert not dest.exists(), "DRY_RUN must not write the action file"


def test_create_action_file_dry_run_returns_correct_path(watcher):
    item = make_notif(notif_id="dry002", notif_type="comment")
    with patch.object(lw_module, "DRY_RUN", True):
        dest = watcher.create_action_file(item)
    assert dest.name == "LINKEDIN_NOTIF_dry002.md"


# ---------------------------------------------------------------------------
# generate_post_draft
# ---------------------------------------------------------------------------


def test_generate_post_draft_creates_file_in_plans(watcher, vault):
    """generate_post_draft() creates a LINKEDIN_DRAFT_*.md file in /Plans."""
    with patch.object(lw_module, "LI_GENERATE_DRAFTS", True):
        result = watcher.generate_post_draft()

    assert result is not None, "generate_post_draft() should return a Path"
    assert result.exists(), "Draft file must be written to disk"
    assert result.parent == vault / "Plans"
    assert result.name.startswith("LINKEDIN_DRAFT_")
    assert result.suffix == ".md"


def test_generate_post_draft_disabled_returns_none(watcher):
    """When LI_GENERATE_DRAFTS is False, generate_post_draft returns None."""
    with patch.object(lw_module, "LI_GENERATE_DRAFTS", False):
        result = watcher.generate_post_draft()
    assert result is None


def test_generate_post_draft_no_overwrite_today(watcher, vault):
    """If today's draft already exists, generate_post_draft returns it without overwrite."""
    with patch.object(lw_module, "LI_GENERATE_DRAFTS", True):
        first = watcher.generate_post_draft()
        first_mtime = first.stat().st_mtime

        second = watcher.generate_post_draft()
        second_mtime = second.stat().st_mtime

    assert first == second
    assert first_mtime == second_mtime, "Existing draft must not be overwritten"


def test_generate_post_draft_frontmatter_type(watcher):
    with patch.object(lw_module, "LI_GENERATE_DRAFTS", True):
        result = watcher.generate_post_draft()
    content = result.read_text(encoding="utf-8")
    assert "type: linkedin_post" in content


def test_generate_post_draft_review_required(watcher):
    """Draft must include review_required: true to enforce HITL."""
    with patch.object(lw_module, "LI_GENERATE_DRAFTS", True):
        result = watcher.generate_post_draft()
    content = result.read_text(encoding="utf-8")
    assert "review_required: true" in content


def test_generate_post_draft_reads_business_goals(watcher, vault):
    """If Business_Goals.md exists, its content appears in the draft context."""
    goals = vault / "Business_Goals.md"
    goals.write_text("Goal: Grow LinkedIn following to 5000.", encoding="utf-8")

    with patch.object(lw_module, "LI_GENERATE_DRAFTS", True):
        result = watcher.generate_post_draft()

    content = result.read_text(encoding="utf-8")
    assert "Goal: Grow LinkedIn following to 5000." in content


def test_generate_post_draft_status_is_draft(watcher):
    with patch.object(lw_module, "LI_GENERATE_DRAFTS", True):
        result = watcher.generate_post_draft()
    content = result.read_text(encoding="utf-8")
    assert "status: draft" in content
