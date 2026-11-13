# Docs and agent settings
<!-- paths: CLAUDE.md, AGENTS.md, docs/**, .claude/settings*.json -->

- Build plans go in `docs/plans/`; architecture decisions go in `docs/decisions/` as numbered ADRs (the `adr` skill). {topic; initial}
- Keep one CLAUDE.md at the root as the single source of agent instructions; turn off tools that generate extra agent files. {topic; initial}
- CLAUDE.md stays under 4 KB: keep what every session needs and move the rest into `docs/`. {gate: test_claude_md; initial}
- `docs/CODE_MAP.md` lists every module with its purpose: read it to find where code lives, and regenerate it with `scripts/code_map.py` (`templates/python/`) when you add, move or rename a module. {gate: code_map --check; initial}
- `.claude/settings.local.json` is personal and git-ignored; shared settings go in `.claude/settings.json`. {topic; initial}
