"""Tests for hooks/practices.py, the plugin's single hook script."""

import io
import json
import subprocess
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


def test_practices_text_has_common_and_selected_languages(tmp_path: Path) -> None:
    (tmp_path / "common.md").write_text("COMMON", encoding="utf-8")
    (tmp_path / "python.md").write_text("PYTHON", encoding="utf-8")
    (tmp_path / "typescript.md").write_text("TYPESCRIPT", encoding="utf-8")
    text = practices_text(tmp_path, ["python"])
    assert "COMMON" in text
    assert "PYTHON" in text
    assert "TYPESCRIPT" not in text


def test_practices_text_skips_unknown_language(tmp_path: Path) -> None:
    (tmp_path / "common.md").write_text("COMMON", encoding="utf-8")
    assert practices_text(tmp_path, ["cobol", "../secret"]) == "COMMON"


def test_shipped_practices_files_exist() -> None:
    folder = Path(practices.__file__).resolve().parent.parent / "practices"
    for name in ["common.md", "python.md", "typescript.md", "unattended.md"]:
        assert (folder / name).is_file(), name


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
) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(
        [mode],
        stdin=io.StringIO(json.dumps(payload)),
        stdout=out,
        stderr=err,
        env={"CLAUDE_PROJECT_DIR": str(project), **(env or {})},
        runner=runner,
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


def test_unattended_rules_cannot_be_loaded_as_a_language(tmp_path: Path) -> None:
    (tmp_path / "common.md").write_text("COMMON", encoding="utf-8")
    (tmp_path / "unattended.md").write_text("UNATTENDED", encoding="utf-8")
    assert practices_text(tmp_path, ["unattended"]) == "COMMON"
    assert practices_text(tmp_path, [], unattended=True) == "COMMON\n\nUNATTENDED"


def test_compact_output_is_off_when_unattended(tmp_path: Path) -> None:
    write_config(tmp_path, {"compactOutput": True})
    out = io.StringIO()
    rewriter = FakeRewriter("rtk git status")
    code = main(
        ["compact-output"],
        stdin=io.StringIO(json.dumps(bash("git status"))),
        stdout=out,
        stderr=io.StringIO(),
        env={"CLAUDE_PROJECT_DIR": str(tmp_path), **UNATTENDED},
        rewriter=rewriter,
    )
    assert (code, out.getvalue()) == (0, "")
    assert rewriter.calls == []


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


# --- compact-output ------------------------------------------------------------------------------


class FakeRewriter:
    def __init__(self, result: str | None) -> None:
        self.calls: list[str] = []
        self.result = result

    def __call__(self, command: str) -> str | None:
        self.calls.append(command)
        return self.result


def compact(
    payload: Mapping[str, object], project: Path, rewriter: FakeRewriter
) -> tuple[int, str]:
    out = io.StringIO()
    code = main(
        ["compact-output"],
        stdin=io.StringIO(json.dumps(payload)),
        stdout=out,
        stderr=io.StringIO(),
        env={"CLAUDE_PROJECT_DIR": str(project)},
        rewriter=rewriter,
    )
    return code, out.getvalue()


def test_compact_output_is_off_by_default(tmp_path: Path) -> None:
    rewriter = FakeRewriter("rtk git status")
    assert compact(bash("git status"), tmp_path, rewriter) == (0, "")
    assert rewriter.calls == []


def test_compact_output_rewrites_and_asks(tmp_path: Path) -> None:
    write_config(tmp_path, {"compactOutput": True})
    payload = {"tool_name": "Bash", "tool_input": {"command": "git status", "timeout": 5000}}
    code, out = compact(payload, tmp_path, FakeRewriter("rtk git status"))
    assert code == 0
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    # "ask" keeps the user's permission prompt; "allow" would skip it for the rewritten command.
    assert decision["permissionDecision"] == "ask"
    assert decision["updatedInput"] == {"command": "rtk git status", "timeout": 5000}


@pytest.mark.parametrize("result", [None, "rtk git status"])
def test_compact_output_leaves_command_alone_without_a_new_rewrite(
    tmp_path: Path, result: str | None
) -> None:
    write_config(tmp_path, {"compactOutput": True})
    assert compact(bash("rtk git status"), tmp_path, FakeRewriter(result)) == (0, "")


def test_compact_output_ignores_empty_commands(tmp_path: Path) -> None:
    write_config(tmp_path, {"compactOutput": True})
    rewriter = FakeRewriter("rtk")
    assert compact(bash("  "), tmp_path, rewriter) == (0, "")
    assert rewriter.calls == []


def test_rtk_rewrite_is_none_without_rtk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert practices.rtk_rewrite("git status") is None


@pytest.mark.parametrize(
    ("returncode", "stdout", "expected"),
    [
        (0, "rtk git status\n", "rtk git status"),
        (3, "rtk git status\n", "rtk git status"),
        (1, "", None),
        (2, "rtk git status\n", None),
        (0, "", None),
    ],
)
def test_rtk_rewrite_reads_exit_code_and_stdout(
    monkeypatch: pytest.MonkeyPatch, returncode: int, stdout: str, expected: str | None
) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: "/bin/rtk")

    def fake_run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        assert args == ["/bin/rtk", "rewrite", "git status"]
        return subprocess.CompletedProcess(args, returncode, stdout, "[rtk] warning\n")

    monkeypatch.setattr("subprocess.run", fake_run)
    assert practices.rtk_rewrite("git status") == expected


def test_rtk_rewrite_is_none_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: "/bin/rtk")

    def slow_run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(args, 10)

    monkeypatch.setattr("subprocess.run", slow_run)
    assert practices.rtk_rewrite("git status") is None
