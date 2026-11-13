# Docs and agent settings
<!-- paths: CLAUDE.md, AGENTS.md, docs/**, .claude/settings*.json -->

- Build plans go in `docs/plans/`; architecture decisions go in `docs/decisions/` as numbered ADRs (the `adr` skill). {topic; initial}
- Keep one CLAUDE.md at the root as the single source of agent instructions; turn off tools that generate extra agent files. {topic; initial}
- `.claude/settings.local.json` is personal and git-ignored; shared settings go in `.claude/settings.json`. {topic; initial}
