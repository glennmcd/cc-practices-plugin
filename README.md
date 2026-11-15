# cc-practices

A Claude Code plugin with the development practices shared across Glenn's projects, extracted from
[FlakeHunter](https://github.com/glennmcd/flakehunter) (TypeScript) and flakehunter-airflow (Python). It is
used locally and installed from a directory marketplace, not published.

## What it adds

| Piece | What it does |
| --- | --- |
| `practices/common/`, `practices/languages/` | Rules by topic; the `core` ones are added at session start (see [Rules](#rules)) |
| `practices/unattended.md` | Rules that replace waiting for a person, added only in [unattended sessions](#unattended-sessions) |
| `agents/code-reviewer`, `agents/security-auditor` | Read-only review agents, pinned to Sonnet; `code-reviewer` also has an adversarial mode |
| `skills/review-pr` | Reviews a PR adversarially with an independent agent and posts a verdict tied to its head commit ([below](#review-a-pull-request)) |
| `skills/tdd-change` | Align, failing test, implement, verify, docs |
| `skills/verify` | Runs the project's configured lint, typecheck and test commands |
| `skills/commit-message` | Conventional Commit message, type chosen by effect on users |
| `skills/adr` | Numbered decision record in `docs/decisions/` |
| `skills/sync-config` | Diffs a project's `cc-practices.json` against the current templates and proposes missing keys |
| `hooks/` | Core rules at session start and to every sub-agent, format on edit with a pointer to the topic file that covers it, `git commit` guard, check that rtk's hook is installed |
| `templates/` | Per-language `cc-practices.json`, Python CI, Dependabot, pyproject tool settings, import-layering test, code map, CLAUDE.md size test, handoff comment, `SECURITY.md`, the agent-ready GitHub issue template |

## Install

Requires `uv` on `PATH`: the hooks run `hooks/practices.py` with `uv run --script` (standard library only).

```bash
claude plugin marketplace add C:/Users/glenn/Documents/git/cc-practices-plugin
claude plugin install cc-practices@cc-practices --scope local
```

`--scope local` writes the enablement to the project's git-ignored `.claude/settings.local.json`, so nothing
machine-specific is committed. After editing the plugin, run `claude plugin marketplace update cc-practices` and
`claude plugin update cc-practices@cc-practices`, then restart the session. Run the `sync-cc-practices-config` skill in each project to pick up template changes the update did not apply.

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

- `languages` picks the language files in `practices/languages/` whose core rules are loaded at session
  start (on startup, `/clear` and compaction; a resumed session already has them).
- `format.command` is an argument list (no shell); `{file}` is the edited file. It runs only on files inside the
  project with a listed extension. A missing formatter is skipped quietly; a failure is reported to Claude without
  blocking the edit.
- `checks` is read by the `verify` skill. Use quiet, failures-only flags: the skill reruns a single failing
  check in detail when it needs more.
- `allowAgentCommits` defaults to `false`: the `PreToolUse` hook blocks `git commit` (Bash or PowerShell, with or
  without `-C`/`-c` options) and asks for a suggested message instead. The hook reads the setting from the repo
  the commit runs in, found from the shell's folder, any `cd`, `Set-Location` or `pushd` earlier in the command,
  and `git -C`. A repo without a config uses the one in the folder the session was opened in, so a session over
  several repos follows each repo's own setting. A folder given by a variable can't be followed and also uses
  the session folder's config.
Without the file, the plugin loads only the common practices, formats nothing and blocks agent commits.

A Python project can also take, from `templates/python/`:

- `pyproject-tools.toml`: ruff with the `S` security rules, minus `S603`, and minus `assert` and
  password-name checks in tests; and `T20` (no `print`), except in `scripts/`;
- `test_layout.py` and `test_claude_md.py` for `tests/`: package import rules, and a 4 KB cap on `CLAUDE.md`;
- `code_map.py` for `scripts/`: writes `docs/CODE_MAP.md`, and `ci.yml` runs its `--check`.

## Rules

Every session pays for the text loaded at its start on every model call, so that text holds only the core
rules and points to the rest. Sub-agents never see SessionStart output, so a `SubagentStart` hook gives each
one the same text as `additionalContext`. Each rule is one bullet in one topic file, ending in `{class; source}`:

```markdown
- Secrets come from the environment or a secret store, never from code, committed config or logs. {core; initial}
```

| Class | How the rule reaches the agent |
| --- | --- |
| `core` | Printed at session start and given to every sub-agent, without the marker |
| `topic` | The agent reads the topic file when its task touches that topic; session start lists the files, and an edit to one of the file's paths points to it |
| `gate: <name>` | Enforced by the named check, whose failure message names the rule |
| `review` | Checked in review |

The source is the incident behind the rule, as `#12` or `owner/repo#12`; rules from before incidents were
tracked say `initial`. Move a rule to a gate when it can be checked, and out of `core` when it is rarely
needed. `{plugin}` in a rule becomes the plugin's folder, so a rule can name a template by its full path.

A topic file may list the paths it covers on its second line:

```markdown
<!-- paths: tests/**, **/test_*.py, **/conftest.py -->
```

The first time in a session that Claude edits a matching file, the format hook tells it to read that topic
file. `**/` matches any number of folders and `*` stays within one. The hook remembers which files it has
pointed to in a small per-session file in the system temp folder.

Tests enforce the layer:

- every bullet in `practices/` has a valid class and source;
- the session-start text stays under 2,048 bytes in its largest case (common, one language, unattended), a
  cap that is only ever lowered;
- no sentence of 20 or more words appears twice across the practice files, skills and agents.

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

## Review a pull request

`/review-pr` runs the `code-reviewer` agent in adversarial mode on a PR and posts its verdict as a comment
that names the PR's head commit. It first checks that the PR is not a draft and that CI has finished and
passed, gives the reviewer only the diff and the issue's *Done when* list, and refuses to post if a push
landed in the meantime. The comment is read by fleetwright's `reviewer-verdict` check (`docs/verdict.md` there),
which a ruleset can require, so a PR cannot merge on an old approval. The helper is
`skills/review-pr/post_verdict.py`; it needs the `gh` CLI signed in as an account listed in the check's
`verdict.reviewers`. With `FLEETWRIGHT_REVIEWER_LOGIN` set, as on fleetwright's review slots, it refuses to post unless
`gh` is signed in as that account. Unattended, the skill ends with a one-line reason instead of asking, and never
edits, pushes or merges.

### Agent-ready issues

Copy `templates/github/ISSUE_TEMPLATE/agent-ready.md` to the repository's `.github/ISSUE_TEMPLATE/`. It asks for
the problem (what should happen, what happens now, what it costs), the scope, what is out of scope and a
*Done when* checklist, so an unattended agent can start with no history and know when it is finished. Unattended
agents treat that list as approval to start.

## Unattended sessions

Set `CC_PRACTICES_UNATTENDED=1` in the environment of sessions no one is watching, such as fleet agents on a
VM. It is an environment variable rather than a config key because the config is committed: a laptop checkout
and an agent clone of the same repository share it. Export it where the agents are launched so the hook
processes inherit it. When it is set:

- The rules in `practices/unattended.md` are added at session start: an issue with a *Done when* list counts as approval,
  and anything that needs the owner becomes a handoff comment on the issue or PR, in the form of
  `templates/handoff.md`, after which the agent ends.
- `git commit` is allowed whatever `allowAgentCommits` says. Without this, a sub-agent that
  fleetwright's context ceiling tells to commit and hand off could do neither.

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
