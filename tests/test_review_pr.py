"""Round 4, reviewer side: the posting helper, the adversarial reviewer, the skill, the template.

The verdict marker is a contract with fleet-kit's `gates/verdict.py`, the check that reads it.
The same literal sits in both repositories' tests, so neither side can change the format alone.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import post_verdict
import pytest

ROOT = Path(__file__).resolve().parent.parent
HEAD = "a" * 40
MOVED = "b" * 40

# Copied from fleet-kit's gates/verdict.py. If it changes there, change it here and below.
FLEET_KIT_MARKER = re.compile(r"^<!--\s*fleet-verdict\s+v1\s+(\{.*\})\s*-->[ \t]*$")
CONTRACT_FIXTURE = (
    '<!-- fleet-verdict v1 {"sha": "'
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "verdict": "approve"} -->'
)


# --- the marker ----------------------------------------------------------------------------------


def test_the_marker_matches_the_pinned_contract_fixture() -> None:
    assert post_verdict.format_marker(HEAD, "approve") == CONTRACT_FIXTURE


@pytest.mark.parametrize("verdict", ["approve", "request_changes"])
def test_the_marker_is_read_by_fleet_kits_pattern(verdict: str) -> None:
    first_line = post_verdict.compose_comment(HEAD, verdict, "Body").splitlines()[0]
    found = FLEET_KIT_MARKER.match(first_line)
    assert found is not None
    assert json.loads(found.group(1)) == {"sha": HEAD, "verdict": verdict}


@pytest.mark.parametrize("sha", ["", HEAD[:7], HEAD[:39], HEAD + "a", HEAD.upper(), "main", "HEAD"])
def test_a_sha_that_is_not_a_full_lowercase_hash_is_refused(sha: str) -> None:
    with pytest.raises(ValueError, match="sha"):
        post_verdict.format_marker(sha, "approve")


@pytest.mark.parametrize("verdict", ["", "APPROVE", "approved", "lgtm", "approve "])
def test_only_the_two_verdicts_are_allowed(verdict: str) -> None:
    with pytest.raises(ValueError, match="verdict"):
        post_verdict.format_marker(HEAD, verdict)


@pytest.mark.parametrize(
    "body",
    [
        '<!-- fleet-verdict v1 {"sha": "x", "verdict": "approve"} -->',
        "see <!-- Fleet-Verdict v1 --> here",
        "text\n<!--fleet-verdict v1 {}-->",
    ],
)
def test_review_text_cannot_carry_a_second_marker(body: str) -> None:
    with pytest.raises(ValueError, match="marker"):
        post_verdict.compose_comment(HEAD, "approve", body)


def test_the_comment_is_the_marker_then_the_review() -> None:
    comment = post_verdict.compose_comment(HEAD, "request_changes", "1. Bug at a.py:3")
    assert (
        comment == CONTRACT_FIXTURE.replace("approve", "request_changes") + "\n\n1. Bug at a.py:3\n"
    )


# --- a fake GitHub API ---------------------------------------------------------------------------


class FakeGh:
    def __init__(self, replies: dict[str, Any], heads: list[str] | None = None) -> None:
        self.replies = replies
        self.heads = list(heads or [HEAD])
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def __call__(self, method: str, path: str, fields: dict[str, str] | None = None) -> Any:
        self.calls.append((method, path, fields or {}))
        if f"{method} {path}" == "GET repos/o/r/pulls/7":
            sha = self.heads.pop(0) if len(self.heads) > 1 else self.heads[0]
            return {"head": {"sha": sha}, "draft": False, **self.replies.get("pull", {})}
        for key, reply in self.replies.items():
            if f"{method} {path}".startswith(key):
                return reply
        raise AssertionError(f"unexpected call {method} {path}")

    @property
    def posted(self) -> list[dict[str, str]]:
        return [f for m, p, f in self.calls if m == "POST"]


def runs(*items: tuple[str, str, str | None]) -> dict[str, Any]:
    return {
        f"GET repos/o/r/commits/{HEAD}/check-runs": {
            "check_runs": [{"name": n, "status": s, "conclusion": c} for n, s, c in items]
        }
    }


# --- ready: review only a PR whose CI is done and green ------------------------------------------


def test_ready_when_every_check_passed() -> None:
    gh = FakeGh(runs(("backend", "completed", "success"), ("lint", "completed", "skipped")))
    result = post_verdict.ready("o/r", 7, gh)
    assert result["ok"] is True and result["head_sha"] == HEAD


def test_not_ready_while_a_check_is_running() -> None:
    result = post_verdict.ready("o/r", 7, FakeGh(runs(("e2e", "in_progress", None))))
    assert result["ok"] is False and "e2e" in result["reason"]


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out", "action_required"])
def test_not_ready_when_a_check_failed(conclusion: str) -> None:
    result = post_verdict.ready("o/r", 7, FakeGh(runs(("backend", "completed", conclusion))))
    assert result["ok"] is False and "backend" in result["reason"]


def test_the_verdict_check_itself_does_not_block_the_review() -> None:
    # It fails until someone reviews; waiting for it would wait forever.
    gh = FakeGh(
        runs(("backend", "completed", "success"), ("reviewer-verdict", "completed", "failure"))
    )
    assert post_verdict.ready("o/r", 7, gh)["ok"] is True


def test_a_draft_is_not_ready() -> None:
    gh = FakeGh({**runs(("backend", "completed", "success")), "pull": {"draft": True}})
    assert post_verdict.ready("o/r", 7, gh)["ok"] is False


# --- post: only for the head that was reviewed ---------------------------------------------------


def test_post_comments_when_the_head_is_the_reviewed_commit() -> None:
    gh = FakeGh({"POST repos/o/r/issues/7/comments": {"html_url": "https://x/c/1"}})
    url = post_verdict.post("o/r", 7, HEAD, "approve", "No findings.", gh)
    assert url == "https://x/c/1"
    assert gh.posted[0]["body"].startswith(CONTRACT_FIXTURE + "\n\n")


def test_post_refuses_when_the_head_moved_since_the_review() -> None:
    gh = FakeGh({"POST repos/o/r/issues/7/comments": {"html_url": "u"}}, heads=[MOVED])
    with pytest.raises(post_verdict.HeadMoved) as raised:
        post_verdict.post("o/r", 7, HEAD, "approve", "ok", gh)
    assert MOVED[:7] in str(raised.value)
    assert gh.posted == []


def test_post_reports_a_push_that_lands_after_the_comment() -> None:
    gh = FakeGh({"POST repos/o/r/issues/7/comments": {"html_url": "u"}}, heads=[HEAD, MOVED])
    messages: list[str] = []
    post_verdict.post("o/r", 7, HEAD, "approve", "ok", gh, warn=messages.append)
    assert len(gh.posted) == 1 and messages and MOVED[:7] in messages[0]


def test_post_never_posts_a_malformed_marker() -> None:
    gh = FakeGh({"POST repos/o/r/issues/7/comments": {"html_url": "u"}})
    with pytest.raises(ValueError, match="sha"):
        post_verdict.post("o/r", 7, "abc123", "approve", "ok", gh)
    assert gh.calls == []


# --- the adversarial reviewer, the skill and the issue template ----------------------------------


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    block = text.split("---", 2)[1]
    return dict(line.split(": ", 1) for line in block.strip().splitlines() if ": " in line)


def test_the_reviewer_stays_read_only() -> None:
    assert frontmatter(ROOT / "agents" / "code-reviewer.md")["tools"] == "Read, Grep, Glob"


def test_the_reviewer_has_an_adversarial_mode_that_ends_in_a_verdict_line() -> None:
    text = (ROOT / "agents" / "code-reviewer.md").read_text(encoding="utf-8")
    assert "adversarial" in text.lower()
    assert "VERDICT: approve" in text and "VERDICT: request_changes" in text


def test_the_skill_is_registered_and_uses_the_helper() -> None:
    skill = ROOT / "skills" / "review-pr" / "SKILL.md"
    meta = frontmatter(skill)
    text = skill.read_text(encoding="utf-8")
    assert meta["name"] == "review-pr" and meta["description"]
    assert "post_verdict.py" in text and "ready" in text and "post" in text
    assert (ROOT / "skills" / "review-pr" / "post_verdict.py").exists()


def test_the_skill_keeps_the_author_out_of_the_review() -> None:
    text = (ROOT / "skills" / "review-pr" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "description" in text and "never" in text


def test_the_issue_template_asks_for_what_an_agent_needs() -> None:
    path = ROOT / "templates" / "github" / "ISSUE_TEMPLATE" / "agent-ready.md"
    text = path.read_text(encoding="utf-8")
    for heading in ("## Problem", "## Scope", "## Out of scope", "## Done when"):
        assert heading in text, heading
    assert "- [ ]" in text
    assert "currently" in frontmatter(path)["title"]
