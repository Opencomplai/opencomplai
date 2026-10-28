# Contributing to Opencomplai

## 1. Welcome

Thanks for helping improve Opencomplai. Contributions of all sizes and skill levels are welcome: a typo fix is as welcome as a new framework pack.

This is the single source for how to contribute. The docs site has a [short page](docs/src/contributing/index.md) that links here, and longer guides for [setup](docs/src/contributing/development-setup.md), [testing](docs/src/contributing/testing.md), [adding rules](docs/src/contributing/adding-rules.md) and [adding framework packs](docs/src/contributing/adding-framework-packs.md).

## 2. Your first pull request, step by step

1. **Pick something.** Open the [good first issues](https://github.com/Opencomplai/opencomplai/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22). Each one names the files to look at and what done looks like. Comment on the issue to claim it; a maintainer assigns it to you on the first reply.
2. **Set up.** Fork and clone the repository, then run `./sync/bootstrap.sh` (see section 5).
3. **Run a test.** Run the tests of the package you will touch, for example `pytest packages/core`, before you change anything, so you know what green looks like.
4. **Make the change** on a branch (section 6) and run the checks in section 11.
5. **Commit with a sign-off:** `git commit -s -m "docs: fix the quickstart secret step"`. The `-s` adds the `Signed-off-by:` line that the DCO check looks for (section 13).
6. **Open the pull request** and fill in the template. The CLA bot asks you to sign once on your first pull request (section 13).
7. **What happens next:** you get a first reply within 48 hours on working days. We review, you may get requested changes, and within 7 days we tell you whether the change will be applied. See section 8 for how an accepted change reaches `main`.

If you get stuck at any step, say so in the issue. That is useful information for us, not a failure on your side.

## 3. Ways to contribute

- Report bugs and request features, using the issue forms
- Improve documentation
- Write code and tests
- Review pull requests
- Answer questions in [Discussions](https://github.com/Opencomplai/opencomplai/discussions)
- Try the setup or a CI recipe on your own system and tell us what broke

## 4. Picking work

- Issues labelled `good first issue` are small and well described.
- Issues labelled `help wanted` are larger and welcome contributors.
- `mentor-available` means a maintainer will answer questions while you work on it.
- `framework-pack` marks work on compliance framework packs; start with [adding framework packs](docs/src/contributing/adding-framework-packs.md).
- For anything larger than an issue describes, open an issue or an Ideas discussion first and wait for a reply, so no effort is wasted.
- Claiming: comment on the issue. If there is no activity for 7 days it is released again. See [GOVERNANCE.md](GOVERNANCE.md).

## 5. Development setup

```bash
git clone https://github.com/Opencomplai/opencomplai
cd opencomplai
./sync/bootstrap.sh
```

`bootstrap.sh` installs all Python and Node.js dependencies, configures pre-commit hooks, and runs a doctor check.

`packages/cli/src/opencomplai_cli/data/checker-local.html` is a committed build artifact
(the offline EU AI Act Checker page), not hand-written source. Regenerate it after changing
anything under `docs/checker-widget/`:

```bash
cd docs/checker-widget && npm ci && node build.mjs && node build-local-html.mjs
```

CI verifies the committed file is up to date with the source.

## 6. Branch naming

- `feature/<area>-<short-name>`, for example `feature/core-risk-classifier`
- `fix/<area>-<short-name>`, for example `fix/cli-exit-codes`
- `chore/<area>-<short-name>`, for example `chore/core-update-deps`
- `docs/<short-name>`, for example `docs/update-quickstart`

## 7. Commit message format

Use semantic prefixes: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.

Example: `feat(core): add high-risk classifier for EU AI Act Article 6`

## 8. Pull request process

Open a draft pull request early. Fill in the pull request template, request review when ready, and link the issue it closes.

Accepted pull requests are applied to `main` by a maintainer and ship in the next release (about every two weeks). Your authorship is kept: the release commit lists you as a co-author, and the changelog credits you. Because the change reaches `main` as part of the release, GitHub may show your pull request as closed rather than merged. When that happens we comment on it with the release it shipped in.

## 9. Evidence we expect

- New behaviour comes with new tests; a bug fix comes with a test that fails without the fix.
- Changes to the scanner, the evaluators or the intent path come with the benchmark numbers before and after (`python packages/ai/tests/benchmark/run_benchmark.py`). A change that raises one number and lowers another is discussed in the issue first.
- Changes to documented behaviour come with the docs change in the same pull request.

## 10. Definition of done

Acceptance criteria are met, CI is green, at least one maintainer approves, docs are updated when needed, and there are no unresolved review comments.

## 11. Code style

Python:

```bash
ruff check . && ruff format .
```

Node.js (in `services/gateway-api`):

```bash
pnpm lint && pnpm format:check
```

## 12. Testing

Python:

```bash
pytest packages/
```

With coverage:

```bash
uv run pytest packages/core --cov=opencomplai_core --cov-report=term-missing
uv run pytest packages/cli --cov=opencomplai_cli --cov-report=term-missing
```

Node.js (in `services/gateway-api`):

```bash
pnpm test
```

New code should include new tests.

## 13. Legal: sign-off and CLA

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

## 14. Getting help

See [SUPPORT.md](SUPPORT.md). Questions and ideas go to [GitHub Discussions](https://github.com/Opencomplai/opencomplai/discussions); bugs and feature requests go to the issue forms; vulnerabilities go through the [security policy](SECURITY.md).

## 15. Maintainers and growing the team

OpenComplAI is currently maintained by [@OpenComplaiCTO](https://github.com/OpenComplaiCTO),
who reviews and applies all pull requests. We expect a first response within 48 hours on working
days; if a pull request or issue has gone quiet for over a week, a bump comment or a note in
[GitHub Discussions](https://github.com/Opencomplai/opencomplai/discussions) is welcome.

We are actively looking to grow the reviewer pool. [GOVERNANCE.md](GOVERNANCE.md) describes the roles and how to reach them: triage rights are offered after three merged changes, and reviewer rights are discussed after about eight.
