---
name: commit-message
description: Write a Conventional Commit message or PR title for the current change, choosing the type by its effect on users. Use when committing, opening a PR, or asked for a commit message.
---

# Conventional Commit message

1. Look at the staged diff (`git diff --cached`; if nothing is staged, `git diff`) and `git log --oneline -10` for the project's scopes.
2. Pick the **type by what changes for people using the deployed thing**, not by which files changed:

   | Type | Use for | Release effect (0.x) |
   | --- | --- | --- |
   | `feat` | new user-visible capability | minor |
   | `fix` | a bug users could hit | patch |
   | `docs` | documentation only, however large | none |
   | `test` | tests only | none |
   | `refactor` | behaviour-preserving code change | none |
   | `build` / `ci` / `chore` / `style` | tooling, CI, housekeeping, formatting | none |

   A breaking change adds `!` after the type (or a `BREAKING CHANGE:` footer). Never write `feat(docs):`.
3. Format: `type(scope): summary`, imperative, lower case, no trailing period, about 72 characters at most. The scope is the area (`api`, `extractor`, `eval`, `web`), optional.
4. Add a body only when the why is not obvious: what problem, what changed, what was left out. Wrap at 72.
5. End with any attribution lines the session requires.
6. Commit only if `.claude/cc-practices.json` sets `"allowAgentCommits": true`; otherwise give the user the message. PRs are squash-merged, so a PR title follows the same rules.
