# Shared practices (cc-practices plugin)

These apply to every project that enables the plugin. The project's own CLAUDE.md wins where it is narrower.

## Working loop

- Write the failing test first where practical, and confirm it fails for the right reason. Every new function, route or rule ships with its tests in the same change, including failure paths.
- Before moving on, run the project's lint, typecheck and test commands (the `verify` skill reads them from `.claude/cc-practices.json`).
- Tests never touch the network or a hosted service: use fakes behind the project's adapter interfaces, HTTP mocks, or in-memory databases.
- Ask before adding a dependency the project brief does not name.
- Keep command output small: run quiet or failures-only variants first and widen only when they don't explain the problem. With `compactOutput` on, Bash commands are rewritten through `rtk`; use `rtk recall` for anything it elided, and the raw command when the exact output is what you are reporting.

## Code and secrets

- Keep framework glue thin: logic lives in plain modules that can be tested without the framework; routes, DAGs and handlers only wire things together.
- Put external services (models, CI hosts, storage) behind an interface with one real adapter, so tests pass a fake and swapping providers is configuration.
- Secrets come from the environment or a secret store, never code, committed config or logs. Error messages name the missing variable, never its value. Never log tokens, full request headers or user content the project marks private.
- Treat uploaded or fetched input as untrusted: cap sizes while streaming, and never trust declared sizes or client-supplied identity.
- Generated files (OpenAPI specs, API clients) are committed and never edited by hand. Regenerate them in the same change as their source, and have CI fail when they are stale.

## Commits, docs and releases

- Commit messages and PR titles use Conventional Commits. Pick the type by what changes for users of the deployed thing, not by file kind: `fix:` is a patch, `feat:` a minor, and `docs:`, `chore:`, `ci:`, `test:`, `refactor:`, `build:`, `style:` do not release. A docs-only change is `docs:` however large. Use the `commit-message` skill.
- PRs are squash-merged with the PR title as the commit message.
- Whether the agent may run `git commit` is set per project (`allowAgentCommits`); when it may not, suggest the message and leave the commit to the user.
- Build plans go in `docs/plans/`; architecture decisions go in `docs/decisions/` as numbered ADRs (the `adr` skill).
- Keep one CLAUDE.md at the root as the single source of agent instructions; turn off tools that generate extra agent files.
- `.claude/settings.local.json` is personal and git-ignored; shared settings go in `.claude/settings.json`.
- The agent never deploys or bootstraps cloud infrastructure; it can synthesize and test, and the owner runs the deploy.
- GitHub Actions are pinned to a commit SHA with the tag in a comment; workflows get least-privilege `permissions`.
