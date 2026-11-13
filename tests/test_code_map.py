"""Tests for templates/python/code_map.py, the code map generator projects copy into scripts/."""

from pathlib import Path

import code_map
import pytest


def write(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def project(root: Path) -> Path:
    write(root, "src/pkg/__init__.py", "")
    store = '"""Saves orders.\n\nMore detail."""\n\nclass Store: ...\ndef load(): ...\n'
    write(root, "src/pkg/store.py", store + "def _hidden(): ...\n")
    write(root, "src/pkg/api.py", '__all__ = ["app"]\napp = 1\ndef helper(): ...\n')
    write(root, "src/pkg/broken.py", "def (:\n")
    return root


def test_one_line_per_module_with_summary_and_public_names(tmp_path: Path) -> None:
    lines = code_map.module_lines(project(tmp_path) / "src", tmp_path)
    assert lines == [
        "- `src/pkg/__init__.py`",
        "- `src/pkg/api.py`: app",
        "- `src/pkg/broken.py`: (syntax error)",
        "- `src/pkg/store.py`: Saves orders. Public: Store, load",
    ]


def test_long_name_lists_are_cut(tmp_path: Path) -> None:
    names = "".join(f"def f{i}(): ...\n" for i in range(12))
    write(tmp_path, "src/m.py", names)
    [line] = code_map.module_lines(tmp_path / "src", tmp_path)
    assert line.endswith("f7, and 4 more")


def run(root: Path, *args: str) -> int:
    return code_map.main(["--root", str(root), *args])


def test_writes_the_map_and_check_passes(tmp_path: Path) -> None:
    project(tmp_path)
    assert run(tmp_path) == 0
    text = (tmp_path / "docs" / "CODE_MAP.md").read_text(encoding="utf-8")
    assert text.startswith("# Code map\n")
    assert "- `src/pkg/store.py`: Saves orders. Public: Store, load\n" in text
    assert run(tmp_path, "--check") == 0


def test_check_fails_when_the_map_is_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project(tmp_path)
    run(tmp_path)
    write(tmp_path, "src/pkg/new.py", '"""New."""\n')
    assert run(tmp_path, "--check") == 1
    assert "out of date" in capsys.readouterr().err


def test_check_fails_when_the_map_is_missing(tmp_path: Path) -> None:
    assert run(project(tmp_path), "--check") == 1


def test_missing_source_folder_is_an_error(tmp_path: Path) -> None:
    assert run(tmp_path) == 2
