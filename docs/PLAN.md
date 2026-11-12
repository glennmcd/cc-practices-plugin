# Plan

What is left for cc-practices from the fleet-kit roadmap (Marquardt's two articles, rebuilt round by
round). The split: cc-practices holds the general practices (rules, skills, reviewer, commit guard,
templates); fleet-kit holds what only a fleet needs (token hooks, measurement, CI gates, control plane).
Its plan is `fleet-kit/docs/PLAN.md`.

Done so far: unattended mode (`CC_PRACTICES_UNATTENDED`, 0.2.0) and command compaction left to rtk's own
hook (0.3.0).

## 1. Rules layer (roadmap round 2)

The always-loaded text should be small and every rule should say why it exists.

- Cap the always-loaded practices at about 2 KB (`common.md` is about 3.0 KB, plus a language file and
  `unattended.md`). Move detail into topic files the agent reads on demand.
- Topic files cite the incident that caused each rule (issue or PR number).
- Rule delivery classes: mark each rule as always loaded, read on demand, or enforced by a hook or gate.
  A rule that can be checked moves to the last class (see 4).
- Code maps: a short per-project file that tells the agent where things are, so it reads less.
- Handoff template: the 30-line comment `unattended.md` asks for, as a template file.
- Remove sentences that repeat between `common.md`, the language files and `RTK.md`.

*Done when*: a test fails if the session-start text exceeds the byte cap; every rule names its class;
the handoff template exists and `unattended.md` points to it.

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
