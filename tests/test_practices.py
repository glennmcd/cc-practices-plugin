"""Tests for hooks/practices.py, the plugin's single hook script."""

import io
import json
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

import practices
from practices import Config, is_git_commit, load_config, main, practices_text

# --- is_git_commit -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'feat: x'",
        "git commit",
        "git add . && git commit -m x",
        "cd backend; git commit --amend",
        "git -C ../other commit -m x",
        "git -c user.name=bot commit -m x",
        "git --no-pager commit -m x",
        "git.exe commit -m x",
        "git commit-tree HEAD^{tree}",
        "(git commit -m x)",
        'git -C "my repo" commit -m x',
        "git -C 'my repo' commit -m x",
        'git -c user.name="A B" commit -m x',
    ],
)
def test_detects_git_commit(command: str) -> None:
    assert is_git_commit(command)


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git log --grep commit",
        "git show HEAD --stat",
        "git diff",
        "gitcommit",
        "echo committed",
        "",
    ],
)
def test_ignores_other_commands(command: str) -> None:
    assert not is_git_commit(command)


# --- load_config ---------------------------------------------------------------------------------


def write_config(project: Path, data: object) -> None:
    (project / ".claude").mkdir(exist_ok=True)
    (project / ".claude" / "cc-practices.json").write_text(json.dumps(data), encoding="utf-8")


def test_missing_config_gives_safe_defaults(tmp_path: Path) -> None:
    assert load_config(tmp_path) == Config(
        languages=[], format_extensions=[], format_command=[], allow_commits=False
    )


def test_reads_full_config(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        {
            "languages": ["python"],
            "format": {"extensions": [".py"], "command": ["uv", "run", "ruff", "format", "{file}"]},
            "checks": {"test": "uv run pytest"},
            "allowAgentCommits": True,
        },
    )
    config = load_config(tmp_path)
    assert config.languages == ["python"]
    assert config.format_extensions == [".py"]
    assert config.format_command == ["uv", "run", "ruff", "format", "{file}"]
    assert config.allow_commits is True


def test_malformed_config_falls_back_to_defaults(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "cc-practices.json").write_text("{not json", encoding="utf-8")
    assert load_config(tmp_path).allow_commits is False
    assert "cc-practices.json" in capsys.readouterr().err


def test_wrongly_typed_fields_are_ignored(tmp_path: Path) -> None:
    write_config(tmp_path, {"languages": "python", "allowAgentCommits": "yes", "format": []})
    assert load_config(tmp_path) == Config(
        languages=[], format_extensions=[], format_command=[], allow_commits=False
    )


# --- practices_text ------------------------------------------------------------------------------


PLUGIN_ROOT = Path(practices.__file__).resolve().parent.parent
SHIPPED = PLUGIN_ROOT / "practices"
# The session-start text in its largest case (common + one language + unattended) stays under
# this. Lower it as rules move to topic files or gates; never raise it.
SESSION_START_CAP_BYTES = 2_048
# Room for the plugin folder path the text prints, which differs per machine.
SHOWN_ROOT = "x" * 90


def rule(text: str, cls: str = "core") -> str:
    return f"- {text} {{{cls}; initial}}"


def make_practices(folder: Path) -> Path:
    files = {
        "common/testing.md": ["# Testing", rule("CORE ONE."), rule("TOPIC ONE.", "topic")],
        "common/docs.md": ["# Docs", rule("TOPIC TWO.", "topic")],
        "languages/python.md": ["# Python", rule("PYTHON CORE.")],
        "languages/typescript.md": ["# TypeScript", rule("TYPESCRIPT CORE.")],
        "unattended.md": ["# Unattended", rule("UNATTENDED CORE."), rule("See `{plugin}/t.md`.")],
    }
    for name, lines in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return folder


def test_practices_text_prints_core_rules_without_markers(tmp_path: Path) -> None:
    text = practices_text(make_practices(tmp_path), ["python"], shown_root="PLUGIN")
    assert "## Testing\n- CORE ONE." in text
    assert "PYTHON CORE." in text
    assert "TOPIC ONE." not in text and "## Docs" not in text
    assert "{core" not in text
    names = "common/docs.md, common/testing.md, languages/python.md"
    assert f"under `PLUGIN/{tmp_path.name}`: {names}." in text


def test_practices_text_skips_other_and_unknown_languages(tmp_path: Path) -> None:
    text = practices_text(make_practices(tmp_path), ["cobol", "../secret", "unattended"])
    assert "TYPESCRIPT" not in text and "PYTHON" not in text and "UNATTENDED" not in text


def test_unattended_rules_load_only_when_unattended(tmp_path: Path) -> None:
    folder = make_practices(tmp_path)
    assert "UNATTENDED CORE." not in practices_text(folder, [])
    text = practices_text(folder, [], unattended=True)
    assert "## Unattended\n- UNATTENDED CORE." in text
    assert "unattended.md" not in text.split("\n\n")[1]


def test_plugin_placeholder_names_the_plugin_folder(tmp_path: Path) -> None:
    folder = make_practices(tmp_path / "plugin" / "practices")
    text = practices_text(folder, [], unattended=True)
    assert f"See `{(tmp_path / 'plugin').as_posix()}/t.md`." in text
    assert "See `ROOT/t.md`." in practices_text(folder, [], unattended=True, shown_root="ROOT")


def test_read_topic_reports_rules_without_a_marker(tmp_path: Path) -> None:
    path = tmp_path / "t.md"
    lines = ["# T", rule("Good."), "- No marker.", "- Bad class. {often; initial}", "Prose."]
    path.write_text("\n".join(lines), encoding="utf-8")
    topic = practices.read_topic(path)
    assert [r.text for r in topic.rules] == ["Good."]
    assert [p.split(": ", 1)[0] for p in topic.problems] == ["t.md:3", "t.md:4", "t.md:5"]


@pytest.mark.parametrize("source", ["initial", "#12", "owner/repo#3"])
def test_rule_sources_are_initial_or_an_issue(source: str) -> None:
    assert practices.RULE.match(f"- Text. {{gate: ruff S; {source}}}")


# --- shipped practice files ----------------------------------------------------------------------


def shipped_topics() -> list[Path]:
    return sorted(SHIPPED.rglob("*.md"))


def test_every_shipped_rule_has_a_class_and_a_source() -> None:
    topics = [practices.read_topic(path) for path in shipped_topics()]
    assert [p for t in topics for p in t.problems] == []
    assert all(t.rules for t in topics)


def test_session_start_text_stays_under_the_cap() -> None:
    languages = sorted(path.stem for path in (SHIPPED / "languages").glob("*.md"))
    sizes = {
        (lang, unattended): len(
            practices_text(SHIPPED, [lang], unattended, SHOWN_ROOT).encode("utf-8")
        )
        for lang in languages
        for unattended in (False, True)
    }
    print(sizes)
    assert max(sizes.values()) <= SESSION_START_CAP_BYTES, sizes


def sentences(path: Path) -> list[str]:
    text = re.sub(r"\{[^{}]*;[^{}]*\}", "", path.read_text(encoding="utf-8"))
    text = re.sub(r"(?s)^---.*?---", "", text)
    found = []
    for part in re.split(r"(?<=[.!?])\s+|\n", text):
        words = re.findall(r"[a-z0-9`'-]+", part.lower())
        if len(words) >= 20:
            found.append(" ".join(words))
    return found


def test_no_sentence_is_written_twice() -> None:
    # Each explanation lives in one place; a repeat costs tokens and the copies drift apart.
    files = [
        *shipped_topics(),
        *PLUGIN_ROOT.glob("skills/*/SKILL.md"),
        *PLUGIN_ROOT.glob("agents/*.md"),
    ]
    seen: dict[str, Path] = {}
    repeats = []
    for path in files:
        for sentence in sentences(path):
            if sentence in seen:
                repeats.append(f"{path.name} repeats {seen[sentence].name}: {sentence[:60]}")
            seen.setdefault(sentence, path)
    assert repeats == []


# --- formatter environment -----------------------------------------------------------------------


def test_formatter_env_drops_the_hook_script_venv() -> None:
    # `uv run --script` sets VIRTUAL_ENV for the hook; a project's own `uv run` must not inherit it.
    env = practices.formatter_env({"VIRTUAL_ENV": "/cache/practices", "PATH": "/bin", "HOME": "/h"})
    assert "VIRTUAL_ENV" not in env
    assert env["PATH"] == "/bin"
    assert env["HOME"] == "/h"


# --- main ----------------------------------------------------------------------------------------


UNATTENDED = {"CC_PRACTICES_UNATTENDED": "1"}


def run(
    mode: str,
    payload: Mapping[str, object],
    project: Path,
    runner: practices.Runner | None = None,
    env: Mapping[str, str] | None = None,
    which: practices.Which = lambda _name: None,
    state_dir: Path | None = None,
) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(
        [mode],
        stdin=io.StringIO(json.dumps(payload)),
        stdout=out,
        stderr=err,
        env={"CLAUDE_PROJECT_DIR": str(project), **(env or {})},
        runner=runner,
        which=which,
        state_dir=state_dir or project / ".pointer-state",
    )
    return code, out.getvalue(), err.getvalue()


def bash(command: str) -> dict[str, object]:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def test_guard_blocks_commit_by_default(tmp_path: Path) -> None:
    code, _, err = run("guard-commit", bash("git commit -m x"), tmp_path)
    assert code == 2
    assert "allowAgentCommits" in err


def test_guard_allows_commit_when_configured(tmp_path: Path) -> None:
    write_config(tmp_path, {"allowAgentCommits": True})
    assert run("guard-commit", bash("git commit -m x"), tmp_path)[0] == 0


def test_guard_allows_other_commands(tmp_path: Path) -> None:
    assert run("guard-commit", bash("git status"), tmp_path)[0] == 0


def test_guard_reads_powershell_commands(tmp_path: Path) -> None:
    payload = {"tool_name": "PowerShell", "tool_input": {"command": "git commit -m x"}}
    assert run("guard-commit", payload, tmp_path)[0] == 2


# --- guard-commit reads the config of the repo being committed to --------------------------------


def make_repo(path: Path, allow: bool | None = None, git_file: bool = False) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    if git_file:  # a worktree has a `.git` file pointing at the main repo
        (path / ".git").write_text("gitdir: ../main/.git/worktrees/x\n", encoding="utf-8")
    else:
        (path / ".git").mkdir()
    if allow is not None:
        write_config(path, {"allowAgentCommits": allow})
    return path


def guard(command: str, project: Path, cwd: Path | None = None) -> tuple[int, str]:
    payload: dict[str, object] = {**bash(command), "cwd": str(cwd or project)}
    code, _, err = run("guard-commit", payload, project)
    return code, err


def test_guard_reads_the_repo_of_the_shell_folder(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo", allow=True)
    assert guard("git commit -m x", tmp_path, cwd=repo)[0] == 0


def test_guard_reads_the_repo_above_a_subfolder(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo", allow=True)
    (repo / "src").mkdir()
    assert guard("git commit -m x", tmp_path, cwd=repo / "src")[0] == 0


@pytest.mark.parametrize(
    "command",
    [
        "git -C repo commit -m x",
        'git -C "my repo" commit -m x',
        "git -C 'my repo' commit -m x",
        "cd repo && git commit -m x",
        "cd repo; git add -A; git commit -m x",
        "(cd repo && git commit -m x)",
        "Set-Location repo; git commit -m x",
        "Set-Location -Path repo; git commit -m x",
        "cd 'my repo' && git commit -m x",
        'cd "my repo" && git commit -m x',
    ],
)
def test_guard_follows_cd_and_git_c(tmp_path: Path, command: str) -> None:
    make_repo(tmp_path / "repo", allow=True)
    make_repo(tmp_path / "my repo", allow=True)
    assert guard(command, tmp_path)[0] == 0


def test_guard_resolves_cd_from_the_shell_folder(tmp_path: Path) -> None:
    make_repo(tmp_path / "a" / "repo", allow=True)
    assert guard("cd repo && git commit -m x", tmp_path, cwd=tmp_path / "a")[0] == 0


def test_guard_falls_back_to_the_session_config(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    assert guard("git commit -m x", tmp_path, cwd=repo)[0] == 2
    write_config(tmp_path, {"allowAgentCommits": True})
    assert guard("git commit -m x", tmp_path, cwd=repo)[0] == 0


def test_guard_repo_config_overrides_the_session_config(tmp_path: Path) -> None:
    write_config(tmp_path, {"allowAgentCommits": True})
    repo = make_repo(tmp_path / "repo", allow=False)
    code, err = guard("git commit -m x", tmp_path, cwd=repo)
    assert code == 2
    assert str(repo / ".claude" / "cc-practices.json") in err


def test_guard_blocks_when_any_commit_is_blocked(tmp_path: Path) -> None:
    make_repo(tmp_path / "a", allow=True)
    make_repo(tmp_path / "b")
    assert guard("git -C a commit -m x && git -C b commit -m y", tmp_path)[0] == 2
    assert guard('git -C "b" commit -m y', tmp_path)[0] == 2
    assert guard("git -C a commit -m x && cd a && git commit -m y", tmp_path)[0] == 0


def test_guard_reads_a_worktree(tmp_path: Path) -> None:
    tree = make_repo(tmp_path / "tree", allow=True, git_file=True)
    assert guard("git commit -m x", tmp_path, cwd=tree)[0] == 0


def test_guard_ignores_cd_to_a_variable(tmp_path: Path) -> None:
    make_repo(tmp_path / "repo", allow=True)
    assert guard('cd "$REPO" && git commit -m x', tmp_path)[0] == 2
    assert guard("git commit -m x", tmp_path, cwd=tmp_path / "repo")[0] == 0


@pytest.mark.parametrize(
    ("text", "windows", "expected"),
    [
        ("/c/Users/me", True, "C:/Users/me"),
        ("/d", True, "D:/"),
        ("/c/Users/me", False, "/c/Users/me"),
        ("repo", True, "repo"),
        ("/usr/lib", True, "/usr/lib"),
    ],
)
def test_native_path_converts_git_bash_drives(text: str, windows: bool, expected: str) -> None:
    assert practices.native_path(text, windows) == expected


def test_session_start_prints_practices(tmp_path: Path) -> None:
    write_config(tmp_path, {"languages": ["python"]})
    code, out, _ = run("session-start", {"hook_event_name": "SessionStart"}, tmp_path)
    assert code == 0
    assert "Python" in out
    assert "Unattended" not in out


# --- unattended sessions -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1", True), ("true", True), ("YES", True), (" 1 ", True), ("0", False), ("", False)],
)
def test_is_unattended_reads_the_environment(value: str, expected: bool) -> None:
    assert practices.is_unattended({"CC_PRACTICES_UNATTENDED": value}) is expected


def test_is_unattended_is_false_when_unset() -> None:
    assert practices.is_unattended({}) is False


def test_guard_allows_commit_when_unattended(tmp_path: Path) -> None:
    # A sub-agent past fleet-kit's context ceiling may run only git/gh and is told to commit.
    payload = {"agent_id": "a1", **bash("git add -A && git commit -m 'feat: x' && git push")}
    write_config(tmp_path, {"allowAgentCommits": False})
    assert run("guard-commit", payload, tmp_path, env=UNATTENDED)[0] == 0


def test_session_start_adds_unattended_rules(tmp_path: Path) -> None:
    write_config(tmp_path, {"languages": ["python"]})
    code, out, _ = run("session-start", {}, tmp_path, env=UNATTENDED)
    assert code == 0
    assert "Python" in out
    assert "Done when" in out


class FakeRunner:
    def __init__(self, returncode: int = 0, output: str = "", missing: bool = False) -> None:
        self.calls: list[list[str]] = []
        self.returncode = returncode
        self.output = output
        self.missing = missing

    def __call__(self, args: list[str], cwd: Path) -> tuple[int, str]:
        self.calls.append(args)
        if self.missing:
            raise FileNotFoundError(args[0])
        return self.returncode, self.output


def edit(path: str) -> dict[str, object]:
    return {"tool_name": "Edit", "tool_input": {"file_path": path}}


def python_config(project: Path) -> None:
    write_config(
        project, {"format": {"extensions": [".py"], "command": ["ruff", "format", "{file}"]}}
    )


def test_format_runs_command_on_matching_file(tmp_path: Path) -> None:
    python_config(tmp_path)
    runner = FakeRunner()
    target = str(tmp_path / "src" / "a.py")
    assert run("format", edit(target), tmp_path, runner)[0] == 0
    assert runner.calls == [["ruff", "format", target]]


def test_format_ignores_other_extensions(tmp_path: Path) -> None:
    python_config(tmp_path)
    runner = FakeRunner()
    assert run("format", edit(str(tmp_path / "README.md")), tmp_path, runner)[0] == 0
    assert runner.calls == []


def test_format_does_nothing_without_config(tmp_path: Path) -> None:
    runner = FakeRunner()
    assert run("format", edit(str(tmp_path / "a.py")), tmp_path, runner)[0] == 0
    assert runner.calls == []


def test_format_ignores_files_outside_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    python_config(project)
    runner = FakeRunner()
    assert run("format", edit(str(tmp_path / "elsewhere.py")), project, runner)[0] == 0
    assert runner.calls == []


def test_format_failure_is_reported_without_blocking(tmp_path: Path) -> None:
    python_config(tmp_path)
    runner = FakeRunner(returncode=1, output="error: invalid syntax")
    code, _, err = run("format", edit(str(tmp_path / "a.py")), tmp_path, runner)
    assert code == 2
    assert "invalid syntax" in err


def test_format_skips_quietly_when_tool_is_missing(tmp_path: Path) -> None:
    python_config(tmp_path)
    code, _, err = run("format", edit(str(tmp_path / "a.py")), tmp_path, FakeRunner(missing=True))
    assert code == 0
    assert err == ""


# --- pointers to topic files after an edit -------------------------------------------------------


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("tests/**", "tests/a/test_b.py", True),
        ("tests/**", "src/tests.py", False),
        ("**/test_*.py", "test_a.py", True),
        ("**/test_*.py", "src/pkg/test_a.py", True),
        ("**/test_*.py", "src/pkg/a_test.py", False),
        ("pyproject.toml", "pyproject.toml", True),
        ("pyproject.toml", "sub/pyproject.toml", False),
        (".github/workflows/**", ".github/workflows/ci.yml", True),
        ("*.md", "docs/a.md", False),
    ],
)
def test_glob_match(pattern: str, path: str, expected: bool) -> None:
    assert practices.glob_match(pattern, path) is expected


def test_read_topic_reads_the_paths_comment(tmp_path: Path) -> None:
    path = tmp_path / "t.md"
    path.write_text("# T\n<!-- paths: tests/**, **/test_*.py -->\n" + rule("A."), "utf-8")
    topic = practices.read_topic(path)
    assert topic.paths == ["tests/**", "**/test_*.py"]
    assert topic.problems == []


def pointer(
    project: Path,
    file: str,
    session: str = "s1",
    runner: practices.Runner | None = None,
    state_dir: Path | None = None,
) -> tuple[int, str]:
    payload = {**edit(str(project / file)), "session_id": session}
    code, out, err = run("format", payload, project, runner=runner, state_dir=state_dir)
    if out:
        context = json.loads(out)["hookSpecificOutput"]
        assert context["hookEventName"] == "PostToolUse"
        return code, context["additionalContext"]
    return code, err


def test_edit_points_to_the_matching_topic_once_per_session(tmp_path: Path) -> None:
    code, text = pointer(tmp_path, "tests/test_a.py")
    assert code == 0
    assert "practices/common/testing.md" in text
    assert pointer(tmp_path, "tests/test_b.py") == (0, "")
    assert "testing.md" in pointer(tmp_path, "tests/test_a.py", session="s2")[1]


def test_edit_points_to_language_topics_only_when_configured(tmp_path: Path) -> None:
    assert pointer(tmp_path, "pyproject.toml") == (0, "")
    write_config(tmp_path, {"languages": ["python"]})
    assert "languages/python.md" in pointer(tmp_path, "pyproject.toml", session="s2")[1]


def test_edit_outside_the_project_points_nowhere(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    payload = {**edit(str(tmp_path / "tests" / "test_a.py")), "session_id": "s1"}
    assert run("format", payload, project)[1] == ""


def test_pointer_rides_along_with_a_formatter_failure(tmp_path: Path) -> None:
    python_config(tmp_path)
    runner = FakeRunner(returncode=1, output="error: invalid syntax")
    code, err = pointer(tmp_path, "tests/test_a.py", runner=runner)
    assert code == 2
    assert "invalid syntax" in err and "testing.md" in err


def test_pointer_without_writable_state_still_points(tmp_path: Path) -> None:
    blocker = tmp_path / "state-is-a-file"
    blocker.write_text("", encoding="utf-8")
    assert "testing.md" in pointer(tmp_path, "tests/test_a.py", state_dir=blocker)[1]


def test_every_shipped_pointer_names_an_existing_kind_of_path() -> None:
    pointed = {t.path.name: t.paths for t in map(practices.read_topic, shipped_topics())}
    assert pointed["testing.md"] and pointed["delivery.md"] and pointed["python.md"]
    assert pointed["unattended.md"] == []


def test_unknown_mode_is_an_error(tmp_path: Path) -> None:
    assert run("nope", {}, tmp_path)[0] == 1


def test_bad_stdin_does_not_block(tmp_path: Path) -> None:
    err = io.StringIO()
    code = main(
        ["guard-commit"],
        stdin=io.StringIO("not json"),
        stdout=io.StringIO(),
        stderr=err,
        env={"CLAUDE_PROJECT_DIR": str(tmp_path)},
    )
    assert code == 0


# --- rtk hook check ------------------------------------------------------------------------------


def write_settings(folder: Path, data: object) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "settings.json").write_text(json.dumps(data), encoding="utf-8")


def rtk_settings(command: str) -> dict[str, object]:
    hook = {"type": "command", "command": command}
    return {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [hook]}]}}


def start(project: Path, user: Path, rtk: str | None) -> str:
    env = {"CLAUDE_CONFIG_DIR": str(user)}
    code, out, _ = run("session-start", {}, project, env=env, which=lambda _name: rtk)
    assert code == 0
    return out


def test_notice_when_rtk_is_installed_without_its_hook(tmp_path: Path) -> None:
    write_settings(tmp_path / "user", {"hooks": {"Notification": []}})
    out = start(tmp_path / "project", tmp_path / "user", rtk="/bin/rtk")
    assert "rtk init -g --auto-patch" in out


@pytest.mark.parametrize(
    "command",
    ["rtk hook claude", '"C:\\tools\\rtk.exe" hook claude', "~/.claude/hooks/rtk-rewrite.sh"],
)
def test_no_notice_when_the_user_settings_have_the_hook(tmp_path: Path, command: str) -> None:
    write_settings(tmp_path / "user", rtk_settings(command))
    assert "rtk init" not in start(tmp_path / "project", tmp_path / "user", rtk="/bin/rtk")


def test_no_notice_when_the_project_settings_have_the_hook(tmp_path: Path) -> None:
    write_settings(tmp_path / "project" / ".claude", rtk_settings("rtk hook claude"))
    assert "rtk init" not in start(tmp_path / "project", tmp_path / "user", rtk="/bin/rtk")


def test_no_notice_without_rtk(tmp_path: Path) -> None:
    assert "rtk init" not in start(tmp_path / "project", tmp_path / "user", rtk=None)


def test_unreadable_settings_count_as_no_hook(tmp_path: Path) -> None:
    (tmp_path / "user").mkdir()
    (tmp_path / "user" / "settings.json").write_text("{not json", encoding="utf-8")
    assert "rtk init" in start(tmp_path / "project", tmp_path / "user", rtk="/bin/rtk")


def test_hook_check_ignores_rtk_outside_hooks(tmp_path: Path) -> None:
    write_settings(tmp_path / "user", {"permissions": {"allow": ["Bash(rtk hook claude)"]}})
    assert not practices.has_rtk_hook([tmp_path / "user" / "settings.json"])


def test_settings_files_default_to_the_home_folder(tmp_path: Path) -> None:
    files = practices.settings_files(tmp_path, {})
    assert files[0] == Path.home() / ".claude" / "settings.json"
    assert files[1:] == [
        tmp_path / ".claude" / "settings.json",
        tmp_path / ".claude" / "settings.local.json",
    ]


# --- subagent-start ------------------------------------------------------------------------------


def subagent_context(project: Path, env: Mapping[str, str] | None = None) -> str:
    payload = {"hook_event_name": "SubagentStart", "agent_id": "a1", "agent_type": "Explore"}
    code, out, _ = run("subagent-start", payload, project, env=env, which=lambda _name: "/bin/rtk")
    assert code == 0
    output = json.loads(out)["hookSpecificOutput"]
    assert output["hookEventName"] == "SubagentStart"
    return str(output["additionalContext"])


def test_subagent_start_gives_the_session_start_rules(tmp_path: Path) -> None:
    write_config(tmp_path, {"languages": ["python"]})
    context = subagent_context(tmp_path)
    _, session, _ = run("session-start", {}, tmp_path)
    assert context == session.strip()
    assert "## Python" in context


def test_subagent_start_adds_unattended_rules(tmp_path: Path) -> None:
    assert "Done when" in subagent_context(tmp_path, env=UNATTENDED)
    assert "Done when" not in subagent_context(tmp_path)


def test_subagent_start_leaves_out_the_rtk_notice(tmp_path: Path) -> None:
    # rtk is "installed" and no settings file has its hook; the notice asks the user, not an agent.
    context = subagent_context(tmp_path, env={"CLAUDE_CONFIG_DIR": str(tmp_path / "user")})
    assert "rtk init" not in context


def test_hooks_json_registers_every_mode() -> None:
    hooks = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    commands = {
        event: [h["command"].rsplit(" ", 1)[1] for group in groups for h in group["hooks"]]
        for event, groups in hooks.items()
    }
    assert commands == {
        "SessionStart": ["session-start"],
        "SubagentStart": ["subagent-start"],
        "PreToolUse": ["guard-commit"],
        "PostToolUse": ["format"],
    }
