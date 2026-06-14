# Code Review

## For pull request authors

### Before requesting review

1. All CI checks are green (`ci-python.yml`, `ci-node.yml`, `ci-docker.yml`).
2. The PR description explains *what* changed and *why* — not just *how*.
3. Breaking changes are documented in the description and noted in `CHANGELOG.md`.
4. Self-review: read your own diff carefully before adding reviewers.

### Keeping PRs small

- One logical change per PR. Split unrelated changes into separate PRs.
- Aim for ≤ 400 lines of diff for reviewable PRs. Larger changes should be discussed in an issue first.
- Documentation-only PRs are always welcome and merge faster.

### Responding to feedback

- Address every comment, either by making the requested change or explaining why not.
- Use "Resolve conversation" only after the change is made — not to dismiss feedback.
- Mark trivial self-merges (`s/typo/fix`) as `Resolved` without a reply to avoid noise.

---

## For reviewers

### What to check

| Area | Questions |
|---|---|
| **Correctness** | Does the code do what the description says? Are edge cases handled? |
| **Tests** | Is new behaviour covered? Do tests verify the right thing (not just that code runs)? |
| **Rule design** | Is the rule deterministic? Does it avoid side effects? Is the rationale user-facing and informative? |
| **Types** | Are type hints present and accurate? Does Pydantic validation cover the inputs? |
| **Documentation** | Does user-visible behaviour have a corresponding doc update? |
| **Security** | Does anything touch egress, signing, or the allowlist? Apply extra scrutiny. |

### SLA

- **First response within 2 business days** for small PRs (≤ 200 lines).
- **Draft PRs** do not require a review response until the author marks "Ready for review".

### Approving

A PR requires **at least one maintainer approval** before merge. Squash merge only. The squash commit message must follow the [Conventional Commits](coding-standards.md) format.

---

## Escalation

If a PR is blocked by disagreement, open a GitHub Discussion linked from the PR and cc the maintainers. Decisions are recorded in the Discussion, not in PR comments.
