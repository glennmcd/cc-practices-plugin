# Commits, CI and releases
<!-- paths: .github/workflows/**, .github/dependabot.yml, CHANGELOG.md -->

- Commit messages and PR titles use Conventional Commits, typed by what changes for users (the `commit-message` skill). {core; initial}
- Commit only when the project sets `allowAgentCommits` or the session is unattended; otherwise suggest the message. {gate: guard-commit; initial}
- PRs are squash-merged with the PR title as the commit message. {topic; initial}
- The agent never deploys or bootstraps cloud infrastructure; it can synthesize and test, and the owner runs the deploy. {core; initial}
- GitHub Actions are pinned to a commit SHA with the tag in a comment; workflows get least-privilege `permissions`. {topic; initial}
