"""Tests for id_tracker.IDTracker."""

import json
import pytest
from pathlib import Path

from id_tracker import IDTracker, _CAP


def test_is_processed_false_for_new_id(tmp_path):
    tracker = IDTracker(tmp_path)
    assert tracker.is_processed("gmail", "msg001") is False


def test_mark_processed_then_is_processed_true(tmp_path):
    tracker = IDTracker(tmp_path)
    tracker.mark_processed("gmail", "msg001")
    assert tracker.is_processed("gmail", "msg001") is True


def test_different_categories_are_independent(tmp_path):
    tracker = IDTracker(tmp_path)
    tracker.mark_processed("gmail", "id1")
    assert tracker.is_processed("gmail", "id1") is True
    assert tracker.is_processed("telegram", "id1") is False
    assert tracker.is_processed("filesystem", "id1") is False


def test_persists_across_instances(tmp_path):
    t1 = IDTracker(tmp_path)
    t1.mark_processed("filesystem", "hash_abc")

    t2 = IDTracker(tmp_path)
    assert t2.is_processed("filesystem", "hash_abc") is True


def test_cap_enforced_at_1000_items(tmp_path):
    tracker = IDTracker(tmp_path)
    for i in range(_CAP + 100):
        tracker.mark_processed("gmail", f"msg{i:05d}")

    data = json.loads((tmp_path / "processed_ids.json").read_text())
    assert len(data["gmail"]) == _CAP
    # Oldest entries should be gone; newest should survive
    assert f"msg{_CAP + 99:05d}" in data["gmail"]
    assert "msg00000" not in data["gmail"]


def test_duplicate_ids_not_added_twice(tmp_path):
    tracker = IDTracker(tmp_path)
    tracker.mark_processed("gmail", "msg001")
    tracker.mark_processed("gmail", "msg001")

    data = json.loads((tmp_path / "processed_ids.json").read_text())
    assert data["gmail"].count("msg001") == 1


def test_corrupt_json_handled_gracefully(tmp_path):
    state_file = tmp_path / "processed_ids.json"
    state_file.write_text("not valid json!!!", encoding="utf-8")

    tracker = IDTracker(tmp_path)  # must not raise
    assert tracker.is_processed("gmail", "any_id") is False

    # Should still work normally after corruption
    tracker.mark_processed("gmail", "id_after_corrupt")
    assert tracker.is_processed("gmail", "id_after_corrupt") is True


def test_missing_state_dir_created_on_mark(tmp_path):
    nested_state = tmp_path / "nested" / ".state"
    tracker = IDTracker(nested_state)
    tracker.mark_processed("telegram", "upd001")
    assert (nested_state / "processed_ids.json").exists()


def test_count_returns_correct_number(tmp_path):
    tracker = IDTracker(tmp_path)
    assert tracker.count("gmail") == 0
    tracker.mark_processed("gmail", "a")
    tracker.mark_processed("gmail", "b")
    assert tracker.count("gmail") == 2
    assert tracker.count("telegram") == 0


def test_categories_returns_known_categories(tmp_path):
    tracker = IDTracker(tmp_path)
    tracker.mark_processed("gmail", "x")
    tracker.mark_processed("filesystem", "y")
    cats = tracker.categories()
    assert "gmail" in cats
    assert "filesystem" in cats


def test_invalid_json_structure_handled(tmp_path):
    state_file = tmp_path / "processed_ids.json"
    # Valid JSON but wrong shape (list instead of dict)
    state_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    tracker = IDTracker(tmp_path)
    assert tracker.is_processed("gmail", "id1") is False
