# Plan

What is left for cc-practices from the fleet-kit roadmap (Marquardt's two articles, rebuilt round by
round). The split: cc-practices holds the general practices (rules, skills, reviewer, commit guard,
templates); fleet-kit holds what only a fleet needs (token hooks, measurement, CI gates, control plane).
Its plan is `fleet-kit/docs/plans/PLAN.md`.

Done so far: unattended mode (`CC_PRACTICES_UNATTENDED`, 0.2.0), command compaction left to rtk's own
hook (0.3.0), topic files with a byte cap (0.4.0), and the core rules for sub-agents through a
`SubagentStart` hook (0.5.0), a commit guard that reads the config of the repo being committed
to rather than the session folder's (0.5.1; quoted `-C` paths in 0.5.2), and the rest of the rules
layer (0.6.0, below), and the reviewer side of round 4 (0.7.0: sections 3 and 5). Sub-agents never receive SessionStart output: none of 18 sub-agent transcripts
had it, including two in commitment-tracker-ai whose parent sessions did.

## 1. Rules layer (roadmap round 2): done

Done in 0.4.0 and 0.6.0:

- Topic files in `practices/common/` and `practices/languages/`, each rule marked `{class; source}`;
  session start built from the core rules; no repeated sentences.
- A 2,048-byte cap on the largest session-start case (now about 1,980 bytes on this machine). Rules
  that a hook, gate or reviewer covers left `core`: unsafe Python calls (`gate: ruff S`), the commit
  rule (`gate: guard-commit`), quiet commands (rtk's hook) and untrusted input (`review`).
- Pointers: a topic file's `<!-- paths: ... -->` line makes the format hook point to it the first
  time in a session an edit matches. Paths are per topic file rather than a `triggered` class,
  because the pointer sends the agent to the whole file. Seen working live in this repo.
- `templates/handoff.md`, which `unattended.md` names through a `{plugin}` placeholder.
- `templates/python/code_map.py` (`docs/CODE_MAP.md`, `--check` in the CI template) and
  `templates/python/test_claude_md.py` (4 KB cap on `CLAUDE.md`), both as gates in `docs.md`.

Ongoing: replace `initial` sources with incident numbers as incidents happen. commitment-tracker-ai's
CLAUDE.md (8,690 bytes) fails the new cap when it adopts the template.

## 2. Tests from recorded responses: done

cc-practices says fakes and HTTP mocks; Marquardt says recorded real responses as fixtures. Reconciled as
fakes fed recorded responses.

Done in 0.8.0: the rule is in `testing.md`, `python.md` and `typescript.md` name it for their fakes, and
`docs/recorded-responses.md` has the steps and an example in each language.

## 3. Adversarial reviewer (roadmap round 4, review half): done

`code-reviewer` is cooperative: invoked by the author, told not to invent issues, gives no verdict.
Marquardt's reviewer is independent, adversarial, read-only, and must approve at the PR's head commit.
Extend the existing agent rather than add a second one.

- An adversarial mode that looks for reasons to reject.
- A verdict (approve or request changes) tied to the head commit SHA, in a form a CI check can read.
  The merge check itself belongs to fleet-kit.

Done in 0.7.0: `code-reviewer` has an adversarial mode that ends in a `VERDICT:` line, and the `review-pr`
skill runs it and posts the verdict through `skills/review-pr/post_verdict.py`, which refuses a PR that is red,
a draft or whose head moved. The marker is pinned by a test here and in fleet-kit. The reviewer now has its own
account (`g26work`); on fleet-kit's review slots `post_verdict.py` refuses to post as any other account
(`FLEET_REVIEWER_LOGIN`), and the skill has an unattended path.

## 4. Prose rules to gates: done

Most rules are prose, which is followed most of the time; a hook, test or CI gate is followed every
time. Move each checkable rule into a gate that cites its incident.

- Done in 0.6.0: ruff `S` in the Python template, minus `S603` everywhere and `S101`/`S105`/`S106`
  in tests. On four repos, 98% of the 1,623 `S` findings were test asserts; the rest is a one-off
  cleanup per repo (flakehunter-airflow has 9 real `S314` XML findings).
- Done in 0.8.0: ruff `T20` (no `print`) in the Python template, except in `scripts/`; the `print` rule in
  `python.md` is now `gate: ruff T20`. This repo has a CI workflow (`.github/workflows/tests.yml`: ruff, mypy,
  pytest), so the duplicate-sentence check runs on every push. This repo does not turn on `T20` for itself: its
  hooks and scripts talk to Claude Code through `print`.
- Each gate is listed next to the rule it covers.

## 5. Agent-ready issue template (roadmap round 4, issue half): done

Unattended agents treat an issue with a *Done when* list as approval. Ship the issue template that
produces one: problem, scope, out of scope, *Done when*.

Done in 0.7.0: `templates/github/ISSUE_TEMPLATE/agent-ready.md`, installed as the README describes.

## Also open

- Hook cost: measured on the fleet machine (2026-11-14). `practices.py guard-commit` takes 79 ms under
  `uv run --script`, and fleet-kit's four hooks take 70 ms together when started in parallel. No dispatcher
  for a fleet of four author agents; the numbers and the reasoning are in fleet-kit's
  `docs/control-plane.md`, *Hook cost*. Measure again before going past about a dozen agents.
- `SubagentStart` confirmed (2026-11-14): `first_context.py --project git --subagent` shows a
  `hook SubagentStart` part of 1,232 characters (about 308 tokens) in a `cc-practices:code-reviewer`
  sub-agent's transcript from 2026-11-13. The hook stays unmatched: 308 tokens is small next to a review, and
  a reviewer that knows the rules can hold a change to them.
