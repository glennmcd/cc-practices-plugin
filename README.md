# cc-practices

A Claude Code plugin with the development practices shared across Glenn's projects, extracted from
[FlakeHunter](https://github.com/glennmcd/flakehunter) (TypeScript) and flakehunter-airflow (Python). It is
used locally and installed from a directory marketplace, not published.

## What it adds

| Piece | What it does |
| --- | --- |
| `practices/common.md`, `python.md`, `typescript.md` | Shared rules, added to context at session start (common plus the project's languages) |
| `agents/code-reviewer`, `agents/security-auditor` | Read-only review agents |
| `skills/tdd-change` | Align, failing test, implement, verify, docs |
| `skills/verify` | Runs the project's configured lint, typecheck and test commands |
| `skills/commit-message` | Conventional Commit message, type chosen by effect on users |
| `skills/adr` | Numbered decision record in `docs/decisions/` |
| `hooks/` | Session-start rules, format on edit, `git commit` guard |
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
  "checks": { "lint": "uv run ruff check .", "typecheck": "uv run mypy", "test": "uv run pytest" },
  "allowAgentCommits": false
}
```

- `languages` picks the practice files loaded at session start.
- `format.command` is an argument list (no shell); `{file}` is the edited file. It runs only on files inside the
  project with a listed extension. A missing formatter is skipped quietly; a failure is reported to Claude without
  blocking the edit.
- `checks` is read by the `verify` skill.
- `allowAgentCommits` defaults to `false`: the `PreToolUse` hook blocks `git commit` (Bash or PowerShell, with or
  without `-C`/`-c` options) and asks for a suggested message instead.

Without the file, the plugin loads only the common practices, formats nothing and blocks agent commits.

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
