---
name: verify
description: Run the project's lint, typecheck and test commands as configured in .claude/cc-practices.json, and report the results. Use before moving on from a change, before a commit, or when asked to check the build.
---

# Verify

1. Read `.claude/cc-practices.json` at the project root. Its `checks` object maps a name to a shell command, for example:

   ```json
   { "checks": { "lint": "uv run ruff check .", "format": "uv run ruff format --check .", "typecheck": "uv run mypy", "test": "uv run pytest" } }
   ```

2. If the file or `checks` is missing, look for the project's documented commands in CLAUDE.md and say that the config is missing.
3. Run every check in the order listed, even after one fails, so the report is complete. Run long test suites in the background if they may exceed two minutes.
4. Report one line per check: pass or fail, and for failures the first relevant error lines (not the whole log).
5. If a check fails, fix the cause in the code. Don't disable a rule, skip a test or loosen types to get a pass unless the user agrees.
