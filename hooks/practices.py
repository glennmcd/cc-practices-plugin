# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""The cc-practices hook script. hooks.json runs it with `uv run --script` in one of three modes:

  session-start  prints practices/common.md plus one file per configured language into context
  format         after Edit/Write, runs the project's formatter on the edited file
  guard-commit   before Bash/PowerShell, blocks `git commit` unless the project allows agent commits
  compact-output before Bash, rewrites the command through `rtk rewrite` when the project opts in

Each project configures it in `.claude/cc-practices.json`; without that file every mode does the
safe minimum (common practices only, no formatting, commits blocked, no rewriting). Standard
library only.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

CONFIG_PATH = Path(".claude") / "cc-practices.json"
PRACTICES_DIR = Path(__file__).resolve().parent.parent / "practices"
FORMAT_TIMEOUT_SECONDS = 60
REWRITE_TIMEOUT_SECONDS = 10

# `git`, any global options (`-C dir`, `-c key=value`, `--no-pager`), then `commit`/`commit-tree`.
GIT_COMMIT = re.compile(
    r"(?:^|[\s;&|(/\\])git(?:\.exe)?"
    r"(?:\s+(?:-C\s+\S+|-c\s+\S+|--?[\w-]+(?:=\S+)?))*"
    r"\s+commit(?:-tree)?(?=$|[\s;&|)])"
)
LANGUAGE_NAME = re.compile(r"^[a-z][a-z0-9-]*$")

Runner = Callable[[list[str], Path], tuple[int, str]]
Rewriter = Callable[[str], str | None]


@dataclass(frozen=True)
class Config:
    languages: list[str] = field(default_factory=list)
    format_extensions: list[str] = field(default_factory=list)
    format_command: list[str] = field(default_factory=list)
    allow_commits: bool = False
    compact_output: bool = False


def _str_list(value: object) -> list[str]:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    return []


def load_config(project: Path) -> Config:
    path = project / CONFIG_PATH
    if not path.is_file():
        return Config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"cc-practices: ignoring {CONFIG_PATH.as_posix()}: {error}", file=sys.stderr)
        return Config()
    if not isinstance(data, dict):
        return Config()
    fmt = data.get("format")
    fmt = fmt if isinstance(fmt, dict) else {}
    return Config(
        languages=_str_list(data.get("languages")),
        format_extensions=_str_list(fmt.get("extensions")),
        format_command=_str_list(fmt.get("command")),
        allow_commits=data.get("allowAgentCommits") is True,
        compact_output=data.get("compactOutput") is True,
    )


def is_git_commit(command: str) -> bool:
    return GIT_COMMIT.search(command) is not None


def practices_text(folder: Path, languages: list[str]) -> str:
    names = ["common", *(lang for lang in languages if LANGUAGE_NAME.match(lang))]
    parts = [
        (folder / f"{name}.md").read_text(encoding="utf-8").strip()
        for name in names
        if (folder / f"{name}.md").is_file()
    ]
    return "\n\n".join(parts)


def formatter_env(env: Mapping[str, str]) -> dict[str, str]:
    """The hook's environment minus the virtualenv `uv run --script` created for this script."""
    return {key: value for key, value in env.items() if key != "VIRTUAL_ENV"}


def run_command(args: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        env=formatter_env(os.environ),
        capture_output=True,
        text=True,
        timeout=FORMAT_TIMEOUT_SECONDS,
        check=False,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def rtk_rewrite(command: str) -> str | None:
    """The command `rtk rewrite` proposes, or None when rtk is missing or has no equivalent.

    rtk exits 0 (or 3, when it wants the user asked) with the rewrite on stdout, and 1 when the
    command has no compact form. Its diagnostics go to stderr and are ignored.
    """
    rtk = shutil.which("rtk")
    if rtk is None:
        return None
    try:
        result = subprocess.run(
            [rtk, "rewrite", command],
            capture_output=True,
            text=True,
            timeout=REWRITE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    rewritten = result.stdout.strip()
    return rewritten if result.returncode in {0, 3} and rewritten else None


def _session_start(config: Config, stdout: TextIO) -> int:
    stdout.write(practices_text(PRACTICES_DIR, config.languages) + "\n")
    return 0


def _guard_commit(config: Config, tool_input: Mapping[str, object], stderr: TextIO) -> int:
    command = tool_input.get("command")
    if config.allow_commits or not isinstance(command, str) or not is_git_commit(command):
        return 0
    stderr.write(
        "cc-practices: agent commits are blocked in this project. Leave the commit to the user "
        'and suggest a Conventional Commit message instead, or set "allowAgentCommits": true '
        f"in {CONFIG_PATH.as_posix()}.\n"
    )
    return 2


def _compact_output(
    config: Config, tool_input: Mapping[str, object], stdout: TextIO, rewriter: Rewriter
) -> int:
    command = tool_input.get("command")
    if not config.compact_output or not isinstance(command, str) or not command.strip():
        return 0
    rewritten = rewriter(command)
    if rewritten is None or rewritten == command.strip():
        return 0
    # "ask", not "allow": an "allow" would skip the prompt the original command would have had.
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": "cc-practices: compact output via rtk",
            "updatedInput": {**tool_input, "command": rewritten},
        }
    }
    stdout.write(json.dumps(output) + "\n")
    return 0


def _format(
    config: Config, project: Path, tool_input: Mapping[str, object], stderr: TextIO, runner: Runner
) -> int:
    file_path = tool_input.get("file_path")
    if not config.format_command or not isinstance(file_path, str):
        return 0
    target = Path(file_path).resolve()
    if target.suffix not in config.format_extensions or not target.is_relative_to(
        project.resolve()
    ):
        return 0
    args = [arg.replace("{file}", str(file_path)) for arg in config.format_command]
    try:
        code, output = runner(args, project)
    except FileNotFoundError:
        return 0  # the formatter is not installed (yet); nothing to report
    except subprocess.TimeoutExpired:
        stderr.write(f"cc-practices: formatter timed out after {FORMAT_TIMEOUT_SECONDS}s\n")
        return 2
    if code == 0:
        return 0
    stderr.write(f"cc-practices: formatter failed on {file_path}:\n{output}\n")
    return 2


def main(
    argv: list[str],
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    env: Mapping[str, str] = os.environ,
    runner: Runner | None = None,
    rewriter: Rewriter | None = None,
) -> int:
    mode = argv[0] if argv else ""
    if mode not in {"session-start", "format", "guard-commit", "compact-output"}:
        stderr.write(f"cc-practices: unknown mode {mode!r}\n")
        return 1
    try:
        payload = json.loads(stdin.read() or "{}")
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    project = Path(env.get("CLAUDE_PROJECT_DIR") or str(payload.get("cwd") or os.getcwd()))
    config = load_config(project)
    tool_input = payload.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}

    if mode == "session-start":
        return _session_start(config, stdout)
    if mode == "guard-commit":
        return _guard_commit(config, tool_input, stderr)
    if mode == "compact-output":
        return _compact_output(config, tool_input, stdout, rewriter or rtk_rewrite)
    return _format(config, project, tool_input, stderr, runner or run_command)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
