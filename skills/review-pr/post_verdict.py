# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""The reviewer's side of fleet-kit's verdict-at-head check: readiness, and posting the verdict.

    post_verdict.py ready --repo owner/name --pr 7
    post_verdict.py post --repo owner/name --pr 7 --sha <head sha> --verdict approve --body-file f

`ready` prints JSON: ok, head_sha, reason. A PR is ready when it is not a draft and every check
other than `reviewer-verdict` has finished and passed, because a review of a red PR can only say
what CI already said.

`post` refuses unless the PR's head is still the commit that was reviewed, then comments with the
marker that fleet-kit's `gates/verdict.py` reads (fleet-kit docs/verdict.md). The marker is the
contract: a test here and one in fleet-kit pin its literal form. Uses the `gh` CLI, signed in as an
account listed in `verdict.reviewers`. Standard library only.

When `FLEET_REVIEWER_LOGIN` is set, as on a fleet's review slots, `post` first checks that `gh` is
signed in as that account and refuses otherwise. A review slot also holds the authors' token, so a
mix-up over which variable carries which token would otherwise post the verdict as the author.

When `FLEET_ROLE` is `author`, as on a fleet's author slots, both commands refuse before any call:
`ready` answers not ok and `post` posts nothing. An author never reviews its own pull request; the
review slot does. Two author agents once saw `reviewer-verdict` red on their own pull requests, ran
this skill and approved themselves.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

CHECK_NAME = "reviewer-verdict"
VERDICTS = ("approve", "request_changes")
FULL_SHA = re.compile(r"[0-9a-f]{40}")
GOOD = {"success", "neutral", "skipped"}

AUTHOR_SLOT = (
    "this is a fleet author slot (FLEET_ROLE=author): an author never reviews its own pull "
    "request. Leave `reviewer-verdict` red; the review slot posts the verdict"
)

Gh = Callable[..., Any]


class HeadMoved(Exception):
    """The PR's head is not the commit that was reviewed."""


class WrongAccount(Exception):
    """`gh` is signed in as someone other than the expected reviewer."""


def format_marker(sha: str, verdict: str) -> str:
    if not FULL_SHA.fullmatch(sha):
        raise ValueError(f"sha must be a full lowercase 40-character commit hash, got {sha!r}")
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}, got {verdict!r}")
    return f"<!-- fleet-verdict v1 {json.dumps({'sha': sha, 'verdict': verdict})} -->"


def compose_comment(sha: str, verdict: str, body: str) -> str:
    """The marker, then the review. The review text can never carry a second marker."""
    if re.search(r"fleet-?verdict", body, re.IGNORECASE):
        raise ValueError("the review text must not contain a fleet-verdict marker")
    return f"{format_marker(sha, verdict)}\n\n{body.strip()}\n"


def gh_api(method: str, path: str, fields: dict[str, str] | None = None) -> Any:
    cmd = ["gh", "api", "-X", method, path]
    for key, value in (fields or {}).items():
        cmd += ["-f", f"{key}={value}"]
    out = subprocess.run(cmd, capture_output=True, check=True).stdout.decode("utf-8")
    return json.loads(out) if out.strip() else {}


def ready(repo: str, pr: int, gh: Gh = gh_api) -> dict[str, Any]:
    pull = gh("GET", f"repos/{repo}/pulls/{pr}")
    sha = pull["head"]["sha"]
    if pull.get("draft"):
        return {"ok": False, "head_sha": sha, "reason": "the PR is a draft"}
    checks = gh("GET", f"repos/{repo}/commits/{sha}/check-runs?per_page=100").get("check_runs", [])
    others = [c for c in checks if c.get("name") != CHECK_NAME]
    running = sorted(c["name"] for c in others if c.get("status") != "completed")
    failed = sorted(
        c["name"]
        for c in others
        if c.get("status") == "completed" and c.get("conclusion") not in GOOD
    )
    if failed:
        return {"ok": False, "head_sha": sha, "reason": f"failing checks: {', '.join(failed)}"}
    if running:
        return {
            "ok": False,
            "head_sha": sha,
            "reason": f"checks still running: {', '.join(running)}",
        }
    note = "" if others else "no checks ran on this commit"
    return {"ok": True, "head_sha": sha, "reason": note}


def post(
    repo: str,
    pr: int,
    sha: str,
    verdict: str,
    body: str,
    gh: Gh = gh_api,
    warn: Callable[[str], None] = lambda message: print(message, file=sys.stderr),
    expect_login: str | None = None,
) -> str:
    comment = compose_comment(sha, verdict, body)  # validates sha and verdict before any call
    if expect_login:
        login = str(gh("GET", "user").get("login") or "")
        if login.lower() != expect_login.lower():
            raise WrongAccount(
                f"gh is signed in as {login or 'nobody'}, not the reviewer {expect_login}"
            )
    now = gh("GET", f"repos/{repo}/pulls/{pr}")["head"]["sha"]
    if now != sha:
        raise HeadMoved(f"the PR head is now {now[:7]}, not the reviewed {sha[:7]}; review again")
    url = str(
        gh("POST", f"repos/{repo}/issues/{pr}/comments", {"body": comment}).get("html_url", "")
    )
    after = gh("GET", f"repos/{repo}/pulls/{pr}")["head"]["sha"]
    if after != sha:
        warn(
            f"a push landed while posting: the head is now {after[:7]}; "
            f"the verdict covers {sha[:7]} only"
        )
    return url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="post_verdict")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("ready", "post"):
        p = sub.add_parser(name)
        p.add_argument("--repo", required=True)
        p.add_argument("--pr", required=True, type=int)
        if name == "post":
            p.add_argument("--sha", required=True)
            p.add_argument("--verdict", required=True, choices=VERDICTS)
            p.add_argument("--body-file", required=True)
    args = parser.parse_args(argv)
    if os.environ.get("FLEET_ROLE") == "author":
        if args.command == "ready":
            print(json.dumps({"ok": False, "head_sha": "", "reason": AUTHOR_SLOT}))
            return 1
        print(f"not posted: {AUTHOR_SLOT}", file=sys.stderr)
        return 2
    if args.command == "ready":
        result = ready(args.repo, args.pr, gh_api)
        print(json.dumps(result))
        return 0 if result["ok"] else 1
    try:
        print(
            post(
                args.repo,
                args.pr,
                args.sha,
                args.verdict,
                Path(args.body_file).read_text("utf-8"),
                gh_api,
                expect_login=os.environ.get("FLEET_REVIEWER_LOGIN") or None,
            )
        )
    except (HeadMoved, WrongAccount, ValueError) as error:
        print(f"not posted: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
