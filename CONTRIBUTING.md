# Contributing to Opencomplai

## 1. Welcome

Thanks for helping improve Opencomplai. Contributions of all sizes and skill levels are welcome.

## 2. Ways to contribute

- Report bugs
- Request features
- Improve documentation
- Write code
- Review pull requests

## 3. Before you start

Check for issues labelled `good first issue` to find starter work. For anything larger, leave a comment on the issue before starting to avoid duplicate effort.

## 4. Development setup

```bash
git clone https://github.com/Opencomplai/opencomplai
cd opencomplai
./scripts/bootstrap.sh
```

`bootstrap.sh` installs all Python and Node.js dependencies, configures pre-commit hooks, and runs a doctor check.

## 5. Branch naming

- `feature/<area>-<short-name>` — e.g. `feature/core-risk-classifier`
- `fix/<area>-<short-name>` — e.g. `fix/cli-exit-codes`
- `chore/<area>-<short-name>` — e.g. `chore/core-update-deps`
- `docs/<short-name>` — e.g. `docs/update-quickstart`

## 6. Commit message format

Use semantic prefixes: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.

Example: `feat(core): add high-risk classifier for EU AI Act Article 6`

## 7. Pull request process

Open a draft pull request early. Fill in the pull request template, request review when ready, and use squash merges only.

## 8. Definition of done

Acceptance criteria are met, CI is green, at least one maintainer approves, docs are updated when needed, and there are no unresolved review comments.

## 9. Code style

Python:

```bash
ruff check . && ruff format .
```

Node.js (in `services/gateway-api`):

```bash
pnpm lint && pnpm format:check
```

## 10. Testing

Python:

```bash
pytest packages/
```

Node.js (in `services/gateway-api`):

```bash
pnpm test
```

New code should include new tests.

## 11. Legal: sign-off and CLA

Opencomplai is dual-licensed: the Community Edition is distributed under AGPL-3.0, and the
same code is offered under a commercial licence as part of the Enterprise Edition. So that
your contribution can ship in both, we require two things on every pull request:

1. **Developer Certificate of Origin (DCO).** Sign off each commit with `git commit -s`,
   which appends a `Signed-off-by: Your Name <you@example.com>` trailer certifying you have
   the right to submit the work under the project's licence.
2. **Contributor Licence Agreement (CLA).** On your first pull request, the CLA Assistant
   bot will ask you to sign the [CLA](CLA.md). This grants Opencomplai the rights needed to
   include your contribution in both the AGPL and the commercial editions. It is a one-time
   step.

By contributing, you agree that your contributions are licensed under AGPL-3.0 and under the
terms of the CLA.

## 12. Getting help

Use GitHub Discussions for questions. Use GitHub Issues for bugs and feature requests.
