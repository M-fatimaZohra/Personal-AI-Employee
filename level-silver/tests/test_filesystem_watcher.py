"""Tests for FilesystemWatcher action file creation."""

import tempfile
from pathlib import Path

from filesystem_watcher import FilesystemWatcher


def _make_vault(tmp: Path) -> Path:
    vault = tmp / "AI_Employee_Vault"
    vault.mkdir()
    return vault


def test_create_action_file_text():
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(Path(tmp))
        watcher = FilesystemWatcher(str(vault))
        # Create a test file in Drop_Box
        test_file = watcher.drop_box / "invoice.txt"
        test_file.write_text("Invoice content here", encoding="utf-8")

        result = watcher.create_action_file(test_file)

        assert result.exists()
        assert result.name == "FILE_invoice.md"
        content = result.read_text(encoding="utf-8")
        assert "type: file_drop" in content
        assert "original_name: invoice.txt" in content
        assert "status: needs_action" in content
        assert "Invoice content here" in content


def test_create_action_file_binary():
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(Path(tmp))
        watcher = FilesystemWatcher(str(vault))
        test_file = watcher.drop_box / "image.png"
        test_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        result = watcher.create_action_file(test_file)

        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "[Binary file: image.png]" in content


def test_create_action_file_duplicate():
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(Path(tmp))
        watcher = FilesystemWatcher(str(vault))

        # First file
        f1 = watcher.drop_box / "report.txt"
        f1.write_text("First", encoding="utf-8")
        r1 = watcher.create_action_file(f1)
        assert r1.name == "FILE_report.md"

        # Second file with same name
        f2 = watcher.drop_box / "report.txt"
        f2.write_text("Second", encoding="utf-8")
        r2 = watcher.create_action_file(f2)
        assert r2.name == "FILE_report_2.md"

        # Third
        f3 = watcher.drop_box / "report.txt"
        f3.write_text("Third", encoding="utf-8")
        r3 = watcher.create_action_file(f3)
        assert r3.name == "FILE_report_3.md"
