# Unattended session (cc-practices plugin)

No one is watching this session (`CC_PRACTICES_UNATTENDED` is set). These rules replace every step above that waits for a person:

- An issue with a *Done when* list is your approval: start without asking. Without that list, hand off and ask for one.
- Never wait for an answer. When something needs the owner (a dependency the issue does not name, a choice the issue does not settle, a failure outside the agreed scope), hand off and end.
- A handoff is a comment on the issue or PR, under 30 lines: what is done, what is left, the decision needed, the head commit and the next command.
- Commit with a Conventional Commit message and push your branch before you hand off or end.
