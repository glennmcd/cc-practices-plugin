# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""The cc-practices hook script. hooks.json runs it with `uv run --script` in one of four modes:

  session-start  prints the core rules (common topics plus one file per configured language) and
                 the list of topic files into context, and a notice when rtk is installed but
                 its Claude Code hook is not
  subagent-start gives each sub-agent the same core rules as JSON `additionalContext`, since
                 sub-agents never receive SessionStart output
  format         after Edit/Write, runs the project's formatter on the edited file
  guard-commit   before Bash/PowerShell, blocks `git commit` unless agent commits are allowed by the
                 config of the repo it runs in (following `cd` and `git -C`), else of the session

Compacting command output is left to rtk's own hook (`rtk init -g`), which runs on every call:
a gate rather than a rule. This script only checks that the hook is there; it never edits the
user's settings.

Each project configures it in `.claude/cc-practices.json`; without that file every mode does the
safe minimum (common practices only, no formatting, commits blocked). Standard library only.

`CC_PRACTICES_UNATTENDED=1` in the environment marks a session no one is watching (a fleet agent
on a VM). It is set per machine, not per repo, because a laptop checkout and an agent clone share
the committed config. Unattended, session-start adds practices/unattended.md and guard-commit
allows commits.

Each rule is one bullet in one topic file, ending in `{class; source}`. The class says how the
rule reaches the agent: `core` (printed at session start), `topic` (read from the topic file when
the task needs it), `review` (checked in review) or `gate: <name>` (enforced by that check). The
source is the incident behind the rule (`#12`, `owner/repo#12`) or `initial`. Only core rules are
printed, without their markers, so each rule is written once.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TextIO

CONFIG_PATH = Path(".claude") / "cc-practices.json"
UNATTENDED_ENV = "CC_PRACTICES_UNATTENDED"
UNATTENDED_PRACTICES = "unattended"
PRACTICES_DIR = Path(__file__).resolve().parent.parent / "practices"
FORMAT_TIMEOUT_SECONDS = 60
# `rtk hook claude` (rtk init -g) or the older `rtk-rewrite` script, anywhere in a hooks section.
RTK_HOOK = re.compile(r"rtk(?:\.exe)?(?:\\?[\"'])?\s+hook\b|rtk-rewrite")  # on JSON-encoded text
RTK_HOOK_MISSING = (
    "cc-practices: rtk is installed but its Claude Code hook is not, so command output is not "
    "compacted. Tell the user to run `rtk init -g --auto-patch` and restart the session."
)

# `git`, any global options (`-C dir`, `-c key=value`, `--no-pager`), then `commit`/`commit-tree`.
GIT_COMMIT = re.compile(
    r"(?:^|[\s;&|(/\\])git(?:\.exe)?"
    r"(?:\s+(?:-C\s+\S+|-c\s+\S+|--?[\w-]+(?:=\S+)?))*"
    r"\s+commit(?:-tree)?(?=$|[\s;&|)])"
)
GIT_C_OPTION = re.compile(r"\s-C\s+(\S+)")
# `cd`, `pushd`, `Set-Location` or `sl` at the start of a command, then a quoted or bare folder.
CHANGE_DIR = re.compile(
    r"(?:^|[;&|(\n])\s*(?:cd|pushd|chdir|set-location|sl)\s+"
    r"(?:-(?:literal)?path\s+)?(?P<dir>\"[^\"]*\"|'[^']*'|[^\s;&|)]+)",
    re.IGNORECASE,
)
GIT_BASH_DRIVE = re.compile(r"^/([a-zA-Z])(?:/|$)")
LANGUAGE_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
RULE = re.compile(
    r"^- (?P<text>.+?)\s+\{(?P<cls>core|topic|review|gate: [^;{}]+);\s*"
    r"(?P<source>initial|#\d+|[\w.-]+/[\w.-]+#\d+)\}\s*$"
)
HEADER = (
    "# Shared practices (cc-practices plugin)\n\n"
    "The project's CLAUDE.md wins where it is narrower. These are the core rules; the rest are in "
    "topic files under `{folder}`: {topics}. Read the topic your task touches before you start."
)

Runner = Callable[[list[str], Path], tuple[int, str]]
Which = Callable[[str], str | None]


@dataclass(frozen=True)
class Config:
    languages: list[str] = field(default_factory=list)
    format_extensions: list[str] = field(default_factory=list)
    format_command: list[str] = field(default_factory=list)
    allow_commits: bool = False
    unattended: bool = False


def is_unattended(env: Mapping[str, str]) -> bool:
    return env.get(UNATTENDED_ENV, "").strip().lower() in {"1", "true", "yes"}


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
    )


def is_git_commit(command: str) -> bool:
    return GIT_COMMIT.search(command) is not None


def native_path(text: str, windows: bool = os.name == "nt") -> str:
    """Turn a Git Bash drive path (`/c/Users`) into a Windows one (`C:/Users`)."""
    drive = GIT_BASH_DRIVE.match(text) if windows else None
    if drive is None:
        return text
    return f"{drive.group(1).upper()}:/{text[drive.end() :]}"


def _step(folder: Path | None, target: str) -> Path | None:
    """The folder after changing to `target` from `folder`; None once it can't be known."""
    target = target.strip("\"'")
    if folder is None or not target or any(char in target for char in "$`%"):
        return None
    return folder / Path(native_path(target)).expanduser()


def commit_folders(command: str, cwd: Path) -> list[Path | None]:
    """The folder each `git commit` in `command` runs in, following `cd` and `git -C`.

    None marks a commit whose folder depends on a variable or substitution.
    """
    events = [(m.start(), "cd", m) for m in CHANGE_DIR.finditer(command)]
    events += [(m.start(), "commit", m) for m in GIT_COMMIT.finditer(command)]
    folder: Path | None = cwd
    folders: list[Path | None] = []
    for _, kind, match in sorted(events, key=lambda event: event[0]):
        if kind == "cd":
            folder = _step(folder, match.group("dir"))
            continue
        target = folder
        for option in GIT_C_OPTION.findall(match.group()):
            target = _step(target, option)
        folders.append(target)
    return folders


def find_repo(folder: Path) -> Path | None:
    for candidate in [folder, *folder.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def commit_config(folder: Path | None, project: Path) -> tuple[Config, Path]:
    """The config that decides a commit in `folder`: its repo's, else the session folder's."""
    repo = find_repo(folder) if folder is not None else None
    if repo is not None and (repo / CONFIG_PATH).is_file():
        return load_config(repo), repo / CONFIG_PATH
    return load_config(project), project / CONFIG_PATH


@dataclass(frozen=True)
class Rule:
    text: str
    cls: str
    source: str


@dataclass(frozen=True)
class Topic:
    path: Path
    title: str
    rules: list[Rule]
    problems: list[str]


def read_topic(path: Path) -> Topic:
    """A topic file: a `# Title` line and one bullet per rule. Other bullets are problems."""
    title, rules, problems = path.stem, [], []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("- "):
            match = RULE.match(line)
            if match:
                rules.append(Rule(match["text"], match["cls"], match["source"]))
            else:
                problems.append(f"{path.name}:{number}: rule has no {{class; source}} marker")
        elif line.strip():
            problems.append(f"{path.name}:{number}: only a title and rule bullets are allowed")
    return Topic(path, title, rules, problems)


def topic_files(folder: Path, languages: list[str], unattended: bool = False) -> list[Path]:
    """Common topics, then the configured languages, then the unattended rules when asked for."""
    paths = sorted((folder / "common").glob("*.md"))
    for lang in languages:
        path = folder / "languages" / f"{lang}.md"
        if LANGUAGE_NAME.match(lang) and path.is_file() and path not in paths:
            paths.append(path)
    if unattended and (folder / f"{UNATTENDED_PRACTICES}.md").is_file():
        paths.append(folder / f"{UNATTENDED_PRACTICES}.md")
    return paths


def practices_text(
    folder: Path, languages: list[str], unattended: bool = False, shown_folder: str | None = None
) -> str:
    """The session-start text: a header naming the topic files, then each topic's core rules."""
    topics = [read_topic(path) for path in topic_files(folder, languages, unattended)]
    listed = [t for t in topics if t.path.stem != UNATTENDED_PRACTICES]
    names = ", ".join(t.path.relative_to(folder).as_posix() for t in listed)
    parts = [HEADER.format(folder=shown_folder or folder.as_posix(), topics=names)]
    for topic in topics:
        core = [f"- {rule.text}" for rule in topic.rules if rule.cls == "core"]
        if core:
            parts.append("\n".join([f"## {topic.title}", *core]))
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


def settings_files(project: Path, env: Mapping[str, str]) -> list[Path]:
    """The Claude Code settings files whose hooks apply to a session in `project`."""
    config_dir = env.get("CLAUDE_CONFIG_DIR")
    user = Path(config_dir) if config_dir else Path.home() / ".claude"
    local = project / ".claude"
    return [user / "settings.json", local / "settings.json", local / "settings.local.json"]


def has_rtk_hook(paths: list[Path]) -> bool:
    """True when any of the settings files registers rtk's hook. Unreadable files are skipped."""
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        hooks = data.get("hooks") if isinstance(data, dict) else None
        if hooks and RTK_HOOK.search(json.dumps(hooks)):
            return True
    return False


def _session_start(
    config: Config, project: Path, env: Mapping[str, str], stdout: TextIO, which: Which
) -> int:
    text = practices_text(PRACTICES_DIR, config.languages, config.unattended)
    if which("rtk") and not has_rtk_hook(settings_files(project, env)):
        text += "\n\n" + RTK_HOOK_MISSING
    stdout.write(text + "\n")
    return 0


def _subagent_start(config: Config, stdout: TextIO) -> int:
    """The same core rules for a sub-agent, which never sees SessionStart output.

    Claude Code shows `additionalContext` from a SubagentStart hook to the new sub-agent. The rtk
    notice is left out: it asks the user to act, and a sub-agent cannot.
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": practices_text(PRACTICES_DIR, config.languages, config.unattended),
        }
    }
    stdout.write(json.dumps(output) + "\n")
    return 0


def _guard_commit(
    config: Config, project: Path, cwd: Path, tool_input: Mapping[str, object], stderr: TextIO
) -> int:
    command = tool_input.get("command")
    if config.unattended or not isinstance(command, str):
        return 0
    for folder in commit_folders(command, cwd):
        decider, path = commit_config(folder, project)
        if decider.allow_commits:
            continue
        stderr.write(
            "cc-practices: agent commits are blocked in this repo. Leave the commit to the user "
            'and suggest a Conventional Commit message instead, or set "allowAgentCommits": true '
            f"in {path}.\n"
        )
        return 2
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
    which: Which = shutil.which,
) -> int:
    mode = argv[0] if argv else ""
    if mode not in {"session-start", "subagent-start", "format", "guard-commit"}:
        stderr.write(f"cc-practices: unknown mode {mode!r}\n")
        return 1
    try:
        payload = json.loads(stdin.read() or "{}")
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    project = Path(env.get("CLAUDE_PROJECT_DIR") or str(payload.get("cwd") or os.getcwd()))
    config = replace(load_config(project), unattended=is_unattended(env))
    tool_input = payload.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}

    if mode == "session-start":
        return _session_start(config, project, env, stdout, which)
    if mode == "subagent-start":
        return _subagent_start(config, stdout)
    if mode == "guard-commit":
        cwd = Path(str(payload.get("cwd") or project))
        return _guard_commit(config, project, cwd, tool_input, stderr)
    return _format(config, project, tool_input, stderr, runner or run_command)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
