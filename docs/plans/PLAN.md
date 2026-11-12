# Plan

What is left for cc-practices from the fleet-kit roadmap (Marquardt's two articles, rebuilt round by
round). The split: cc-practices holds the general practices (rules, skills, reviewer, commit guard,
templates); fleet-kit holds what only a fleet needs (token hooks, measurement, CI gates, control plane).
Its plan is `fleet-kit/docs/plans/PLAN.md`.

Done so far: unattended mode (`CC_PRACTICES_UNATTENDED`, 0.2.0) and command compaction left to rtk's own
hook (0.3.0).

## 1. Rules layer (roadmap round 2)

The always-loaded text should be small and every rule should say why it exists.

First cut done in 0.4.0: topic files in `practices/common/` and `practices/languages/`, each rule
marked `{class; source}` (`core`, `topic`, `review`, `gate: <name>`), session start built from the core
rules, tests for the markers, a 3,072-byte cap on the largest case (now about 2.6 KB) and no repeated
sentences. Every rule's source is `initial` so far.

Left for a second cut:

- Lower the cap toward 2 KB, by moving rules to gates (see 4) or out of `core`.
- Triggered pointers: after an Edit or Write on matching paths (`tests/**`, `.github/workflows/**`,
  `pyproject.toml`), tell the agent once per session to read that topic file. Adds a `triggered` class.
  Check first that a PostToolUse hook can add context for the agent.
- Code maps: `templates/python/code_map.py` writes `docs/CODE_MAP.md` (one line per module: path,
  docstring summary, public names), with `--check` as a CI step.
- Handoff template: the 30-line comment `unattended.md` asks for, as `templates/handoff.md`.
- Replace `initial` sources with incident numbers as incidents happen.

*Done when*: the cap test is at 2,048 bytes or less; the handoff template exists and `unattended.md`
points to it; the Python CI template checks the code map.

## 2. Tests from recorded responses

cc-practices says fakes and HTTP mocks; Marquardt says recorded real responses as fixtures. Reconcile as
fakes fed recorded responses.

*Done when*: `python.md` and `typescript.md` say so, with a short example of recording a response once
and replaying it in a fake.

## 3. Adversarial reviewer (roadmap round 4, review half)

`code-reviewer` is cooperative: invoked by the author, told not to invent issues, gives no verdict.
Marquardt's reviewer is independent, adversarial, read-only, and must approve at the PR's head commit.
Extend the existing agent rather than add a second one.

- An adversarial mode that looks for reasons to reject.
- A verdict (approve or request changes) tied to the head commit SHA, in a form a CI check can read.
  The merge check itself belongs to fleet-kit.

*Done when*: the reviewer can be run on a PR and leaves a verdict naming the head SHA.

## 4. Prose rules to gates

Most rules are prose, which is followed most of the time; a hook, test or CI gate is followed every
time. Move each checkable rule into a gate that cites its incident.

- Candidates: ruff `S` (security) and `T20` (no `print`) in the Python template; a duplicate-sentence
  check across the practice files.
- Each gate is listed next to the rule it replaces, and the prose rule is removed.

*Done when*: the templates enable the new ruff rules and the duplicate-sentence check runs in CI.

## 5. Agent-ready issue template (roadmap round 4, issue half)

Unattended agents treat an issue with a *Done when* list as approval. Ship the issue template that
produces one: problem, scope, out of scope, *Done when*.

*Done when*: `templates/` has the issue template and the README explains how to install it.

## Also open

- Hook cost: with fleet-kit installed, each Bash call starts three `uv run --script` processes. Consider
  one dispatcher process for both plugins' Bash hooks, or a faster runner.
- Check whether sub-agents receive SessionStart output; if not, the practices never reach them.
