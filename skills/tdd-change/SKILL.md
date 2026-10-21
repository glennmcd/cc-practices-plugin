---
name: tdd-change
description: Make a code change test-first - align on scope, write a failing test, implement, verify with the project's checks, update docs. Use when asked to add a feature, endpoint, rule or fix in a project that uses the cc-practices plugin.
argument-hint: [change description]
---

# Test-driven change

Change to make: $ARGUMENTS

Don't skip steps; run each command before moving on.

## 0. Align first
State what will change, the public shape (function signature, endpoint and response, CLI flags), what will not be touched, the failure cases, and how you will validate it. For work from a brief or issue, wait for approval before editing product code. Find the closest existing example in the repo and name it as the model to follow.

## 1. Schema or types first
If the change crosses a boundary (API request/response, model output, config), add or extend the validation model (Pydantic or Zod) and give it parse and reject tests.

## 2. Failing test
- Put the test beside its peers, following the project's naming.
- Cover the happy path with exact values, edge cases, and each failure path (bad input, missing data, external failure).
- Table-style cases use `pytest.mark.parametrize` (Python) or `test.each` (TypeScript).
- External services are faked through the project's adapter interface or an HTTP mock (`respx`); never call the network.
- Run just that test and confirm it fails for the right reason (missing behaviour, not an import or typo error).

## 3. Implement
Put logic in a plain module, not in the route, DAG or handler; the framework layer only wires it in. Keep the change to the agreed scope.

## 4. Verify
Run the `verify` skill (the project's lint, typecheck and test commands from `.claude/cc-practices.json`). Fix what fails; don't weaken a check to make it pass.

## 5. Generated files and docs
Regenerate any committed generated file the change affects (OpenAPI spec, client) in the same change. Update the project's CLAUDE.md or docs where the change alters a command, route or rule. Then suggest a Conventional Commit message (the `commit-message` skill); commit only if the project sets `allowAgentCommits`.
