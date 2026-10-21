---
name: adr
description: Record an architecture decision as a numbered ADR in docs/decisions/. Use when a design choice is made or changed (a library, a storage model, an API contract, a trade-off) or when asked to write a decision record.
argument-hint: [decision title]
---

# Architecture decision record

Decision: $ARGUMENTS

1. List `docs/decisions/`. The new file is the next four-digit number plus a kebab-case title: `0007-model-behind-adapter.md`. Create the folder and a `README.md` index if they don't exist.
2. Use this shape, short and concrete:

   ```markdown
   # NNNN. Title

   Date: YYYY-MM-DD · Status: Accepted

   ## Context
   The problem and the forces at play, with numbers where they exist.

   ## Decision
   What we do, in one or two paragraphs.

   ## Consequences
   What gets easier, what gets harder, and what we would revisit and when.

   ## Alternatives considered
   Each option in a line or two and why it lost.
   ```

3. If it replaces an earlier decision, set the old one's status to `Superseded by NNNN` and link both ways.
4. Add a line to `docs/decisions/README.md`, and link the ADR from CLAUDE.md or the plan in `docs/plans/` that depends on it.
5. Commit with `docs: add ADR NNNN <title>` (only if the project allows agent commits).
