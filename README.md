# cc-practices

A Claude Code plugin with the development practices shared across Glenn's projects, extracted from
[FlakeHunter](https://github.com/glennmcd/flakehunter) (TypeScript) and flakehunter-airflow (Python). It is
used locally and installed from a directory marketplace, not published.

## What it adds

| Piece | What it does |
| --- | --- |
| `practices/common.md`, `python.md`, `typescript.md` | Shared rules, added to context at session start (common plus the project's languages) |
| `practices/unattended.md` | Rules that replace waiting for a person, added only in [unattended sessions](#unattended-sessions) |
| `agents/code-reviewer`, `agents/security-auditor` | Read-only review agents, pinned to Sonnet |
| `skills/tdd-change` | Align, failing test, implement, verify, docs |
| `skills/verify` | Runs the project's configured lint, typecheck and test commands |
| `skills/commit-message` | Conventional Commit message, type chosen by effect on users |
| `skills/adr` | Numbered decision record in `docs/decisions/` |
| `hooks/` | Session-start rules, format on edit, `git commit` guard, check that rtk's hook is installed |
| `templates/` | Per-language `cc-practices.json`, Python CI, Dependabot, pyproject tool settings, import-layering test, `SECURITY.md` |

## Install

Requires `uv` on `PATH`: the hooks run `hooks/practices.py` with `uv run --script` (standard library only).

```bash
claude plugin marketplace add C:/Users/glenn/Documents/git/cc-practices-plugin
claude plugin install cc-practices@cc-practices --scope local
```

`--scope local` writes the enablement to the project's git-ignored `.claude/settings.local.json`, so nothing
machine-specific is committed. After editing the plugin, run `claude plugin marketplace update cc-practices` and
`claude plugin update cc-practices@cc-practices`, then restart the session.

## Configure a project

Copy `templates/<language>/cc-practices.json` to the project's `.claude/cc-practices.json`:

```json
{
  "languages": ["python"],
  "format": { "extensions": [".py"], "command": ["uv", "run", "ruff", "format", "{file}"] },
  "checks": {
    "lint": "uv run ruff check --output-format concise .",
    "typecheck": "uv run mypy",
    "test": "uv run pytest -q --tb=short"
  },
  "allowAgentCommits": false
}
```

- `languages` picks the practice files loaded at session start (on startup, `/clear` and compaction; a
  resumed session already has them).
- `format.command` is an argument list (no shell); `{file}` is the edited file. It runs only on files inside the
  project with a listed extension. A missing formatter is skipped quietly; a failure is reported to Claude without
  blocking the edit.
- `checks` is read by the `verify` skill. Use quiet, failures-only flags: the skill reruns a single failing
  check in detail when it needs more.
- `allowAgentCommits` defaults to `false`: the `PreToolUse` hook blocks `git commit` (Bash or PowerShell, with or
  without `-C`/`-c` options) and asks for a suggested message instead.
Without the file, the plugin loads only the common practices, formats nothing and blocks agent commits.

## Compact command output with rtk

cc-practices does not rewrite commands itself. [rtk](https://github.com/rtk-ai/rtk)'s own hook does, on every
Bash and PowerShell call, which is what makes it reliable: a hook runs every time, a rule in a prompt most of
the time. Install it once per machine:

```bash
rtk init -g --auto-patch
rtk init -g --show
```

The first adds `rtk hook claude` to `~/.claude/settings.json`; the second checks it. At session start
cc-practices reads the user, project and local settings files, and when `rtk` is on `PATH` but no hook calls
it, tells Claude to ask you to run the install. It never edits your settings.

rtk's hook returns the rewritten command with no permission decision, so it goes through your normal
permission check and works unattended. rtk honours `deny` rules (a denied command is not rewritten), but an
`ask` rule such as `Bash(git log:*)` no longer matches once the command reads `rtk git log`. Do not add an
allow rule like `Bash(rtk:*)`: it would let any rewritten command through without a prompt.

## Unattended sessions

Set `CC_PRACTICES_UNATTENDED=1` in the environment of sessions no one is watching, such as fleet agents on a
VM. It is an environment variable rather than a config key because the config is committed: a laptop checkout
and an agent clone of the same repository share it. Export it where the agents are launched so the hook
processes inherit it. When it is set:

- `practices/unattended.md` is added at session start: an issue with a *Done when* list counts as approval,
  and anything that needs the owner becomes a handoff comment on the issue or PR, after which the agent ends.
- `git commit` is allowed whatever `allowAgentCommits` says. Without this, a sub-agent that
  fleet-kit's context ceiling tells to commit and hand off could do neither.

## Develop

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy
claude plugin validate .
```

## Not generalized

These stay in their projects:

- FlakeHunter's Fastify, Drizzle, PGlite, Next.js and CDK conventions, and the `new-endpoint` skill's specifics
  (`tdd-change` is its generic form).
- `.claude/launch.json` (ports differ per project) and `.vscode` launch configs.
- release-please config and its version-sync test (the Node release type; a Python project needs
  `release-type: python`) and project CI beyond the Python template.
- The AWS Agent Toolkit block in FlakeHunter's CLAUDE.md, which that toolkit's installer writes.
- `permissions.deny` for `git commit`: plugins cannot ship permissions, so the `guard-commit` hook replaces it.
- flakehunter-airflow's dev container and Airflow-in-`.venv` caveats, Connection and Variable names, `X-FH-*`
  idempotency rules, and the contract-drift workflow and pinned-spec pairing with FlakeHunter.
