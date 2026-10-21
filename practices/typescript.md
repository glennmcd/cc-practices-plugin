# TypeScript practices (cc-practices plugin)

- Use `bun` and `bunx`, not npm, yarn or direct `node` commands, unless the project pins another tool. Commit `bun.lock`; CI runs `bun install --frozen-lockfile`.
- Biome for lint, format and import order (`biome ci .` fails on any diff; `biome check --write .` fixes). `tsc --noEmit` per package for types.
- Validate data at the boundary with Zod; share request and response schemas from one package so the API and its clients agree.
- Code that runs on Lambda runs on Node, not Bun: use no Bun-only APIs there, and register routes explicitly (bundlers cannot see files loaded from disk at runtime).
- Test pure helpers with plain unit tests and components with server rendering; keep tests offline with in-memory databases and fake clients.
