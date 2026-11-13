# TypeScript
<!-- paths: **/package.json, biome.json, **/tsconfig*.json -->

- Use `bun` and `bunx`, not npm, yarn or direct `node`, unless the project pins another tool; commit `bun.lock`, and CI runs `bun install --frozen-lockfile`. {core; initial}
- Biome for lint, format and import order (`biome ci .` fails on any diff; `biome check --write .` fixes). `tsc --noEmit` per package for types. {topic; initial}
- Validate data at the boundary with Zod; share request and response schemas from one package so the API and its clients agree. {topic; initial}
- Code that runs on Lambda runs on Node, not Bun: use no Bun-only APIs there, and register routes explicitly (bundlers cannot see files loaded from disk at runtime). {topic; initial}
- Test pure helpers with plain unit tests and components with server rendering, using in-memory databases and fake clients. {topic; initial}
