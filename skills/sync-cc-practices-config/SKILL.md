---
name: sync-cc-practices-config
description: Compare a project's .claude/cc-practices.json with the plugin's current templates and propose the missing keys, checks and language entries. Use after updating the cc-practices plugin, when setting up a project, or when asked to sync or refresh the practices config.
---

# Sync config

The plugin never edits a project's `.claude/cc-practices.json`: the project owns it, and a template change reaches it only through this skill.

1. Read `.claude/cc-practices.json`. If it is missing, copy `${CLAUDE_PLUGIN_ROOT}/templates/<language>/cc-practices.json` for each language the project uses (ask which if unclear), merge them, and stop here.
2. Read the template for each entry in the project's `languages` from `${CLAUDE_PLUGIN_ROOT}/templates/<language>/cc-practices.json`. Flag a `languages` entry with no template or no `practices/languages/` file.
3. Compare key by key. Report only differences, in three groups:
   - **Missing**: keys, `checks` entries or `format.extensions` that a template has and the project lacks.
   - **Unknown**: project keys no template or `hooks/practices.py` reads, which are probably typos or stale.
   - **Local**: values that differ on purpose (a `--directory` prefix, a custom `format.command`, a second language's `-ts` checks, `allowAgentCommits`). List them as kept, never as errors.
4. Show the proposed edit as a short diff. Never overwrite a project's existing value with a template value, and leave `allowAgentCommits` alone.
5. Apply the edit only after the user agrees, keeping the file's formatting. Then run the `verify` skill to confirm every configured check still runs.
