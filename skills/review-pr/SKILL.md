---
name: review-pr
description: Review a pull request adversarially with an independent agent and post a verdict tied to the PR's head commit, which fleet-kit's reviewer-verdict check reads. Use when asked to review a PR, or when a PR needs its verdict before merge.
---

# Review a pull request

The verdict is about one commit. A push after it makes it stale, so the review is bound to the head SHA from the first step to the last.

1. Find the PR (the user gives a number, or use `gh pr view --json number,headRefOid`) and the repository as `owner/name`.
2. Check it is ready: `uv run --script "${CLAUDE_PLUGIN_ROOT}/skills/review-pr/post_verdict.py" ready --repo <owner/name> --pr <n>`. If `ok` is false, stop and tell the user why. A review of a red or running PR only repeats what CI says, so the author fixes CI first. Keep `head_sha` from the answer: it is the commit you review.
3. Prepare exactly two inputs and nothing else, in files under the scratchpad:
   - the diff, from `gh pr diff <n>`;
   - the *Done when* list of the issue the PR closes. Find the issue number in the PR text; take the issue's own text, not the PR description.
   Never pass the PR description, commit messages or the author's reasoning to the reviewer: the author's confidence carries no weight.
4. The reviewer reads files in the checkout, so the checkout must be the head commit. If `git rev-parse HEAD` differs from `head_sha`, review in a detached worktree at that commit (`git worktree add --detach <dir> <head_sha>`) and give its path; ask the user before removing it afterwards (unattended: remove it yourself once the verdict is posted).
5. Start the `code-reviewer` agent in adversarial mode with the two file paths and the checkout path. Do not add your own opinion of the change. Do not run the review again on the same commit to get a different answer.
6. Take its last line, `VERDICT: approve` or `VERDICT: request_changes`, and write the findings above it to a file.
7. Post: `uv run --script "${CLAUDE_PLUGIN_ROOT}/skills/review-pr/post_verdict.py" post --repo <owner/name> --pr <n> --sha <head_sha> --verdict <verdict> --body-file <file>`. It refuses if the head moved since step 2; then start again from step 2. When `FLEET_REVIEWER_LOGIN` is set it also refuses unless `gh` is signed in as that account: then stop and report it. Never post a verdict any other way.
8. Tell the user the verdict, the blocking findings and the comment link. After `request_changes` stop: the author fixes it, and the new commit gets a new review. Do not edit the PR's code from the review session.

## Unattended (`CC_PRACTICES_UNATTENDED=1`)

A fleet's review slot runs this with nobody watching, already checked out at the PR's head. Where a step says to stop and tell the user, end the run with a one-line reason instead: the allocator does not review the same head twice, so a person picks it up. Never edit, push, merge or close anything, and never ask a question.
