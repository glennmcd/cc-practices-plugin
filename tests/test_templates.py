"""What the templates, this repo's CI and the topic files must keep saying together."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_the_python_template_turns_on_the_print_rule() -> None:
    lint = tomllib.loads(read("templates/python/pyproject-tools.toml"))["tool"]["ruff"]["lint"]
    assert "T20" in lint["select"]
    # A script's output is its interface; library code logs.
    assert lint["per-file-ignores"]["scripts/**"] == ["T20"]


def test_the_print_rule_names_its_gate() -> None:
    rule = next(
        line for line in read("practices/languages/python.md").splitlines() if "`print`" in line
    )
    assert rule.endswith("{gate: ruff T20; initial}")
    assert "`E, F, I, UP, B, SIM, S, T20`" in read("practices/languages/python.md")


def test_ci_runs_the_tests_which_hold_the_duplicate_sentence_check() -> None:
    workflow = read(".github/workflows/tests.yml")
    for step in ("uv sync --locked", "uv run ruff check .", "uv run mypy", "uv run pytest"):
        assert f"- run: {step}" in workflow, step
    assert "def test_no_sentence_is_written_twice" in read("tests/test_practices.py")
    # Actions are pinned to a commit, not a tag that can move.
    uses = [
        line.split("uses:")[1].split("#")[0].strip()
        for line in workflow.splitlines()
        if "uses:" in line
    ]
    assert uses and all(len(u.split("@")[1]) == 40 for u in uses), uses


def test_fakes_replay_recorded_responses_in_both_languages() -> None:
    assert "docs/recorded-responses.md" in read("practices/common/testing.md")
    assert "recorded" in read("practices/languages/python.md")
    assert "recorded" in read("practices/languages/typescript.md")
    example = read("docs/recorded-responses.md")
    assert "```python" in example and "```ts" in example
