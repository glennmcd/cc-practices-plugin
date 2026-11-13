"""Tests for templates/python/test_claude_md.py, the CLAUDE.md size cap for a project's tests/."""

from pathlib import Path

import test_claude_md


def test_a_small_claude_md_passes(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("x" * 100, encoding="utf-8")
    assert test_claude_md.over_cap(tmp_path, 100) is None


def test_a_large_claude_md_fails_with_its_size(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("é" * 60, encoding="utf-8")  # 120 bytes, 60 characters
    message = test_claude_md.over_cap(tmp_path, 100)
    assert message is not None
    assert "120 bytes" in message and "100" in message


def test_no_claude_md_passes(tmp_path: Path) -> None:
    assert test_claude_md.over_cap(tmp_path, 100) is None
