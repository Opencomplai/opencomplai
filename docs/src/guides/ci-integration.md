# CI integration

OpenComplAI runs in GitHub Actions and GitLab CI via the CLI and connector scripts, no
dashboard account required: `pip install opencomplai`, run `opencomplai init` to write a
`system-manifest.json`, then copy the workflow file for your platform below as a CI step —
it runs `opencomplai check` on every push/PR and fails the build on a control failure.
The scan needs no key; `OPENCOMPLAI_API_KEY` is only needed to publish results to the dashboard.

> **Optional — hosted dashboard:** if you also use the dashboard, open **`/connect`** for
> your project (**Projects → your project → Connect**) instead of copying the snippet by
> hand — it generates the same file with your own dashboard host already filled in, so to
> publish you only need to add `OPENCOMPLAI_API_KEY` as a secret. The copies below use
> `https://YOUR-DASHBOARD-HOST` as a placeholder for that value; without it, drop the
> `OPENCOMPLAI_DASHBOARD_URL`/`push` step and rely on the CLI's own exit code as the CI gate.

Looking for a GitLab CI/CD component that calls `opencomplai check` directly, or an Azure Pipelines template? See [CI for GitLab and Azure Pipelines](ci-gitlab-azure.md).

## GitHub Actions

Copy this file to `.github/workflows/opencomplai-scan.yml` in your AI system repository.
Requires a `system-manifest.json` in your repo root (see the CLI's own `opencomplai init`).

To publish to the dashboard (the scan itself needs no key), add your API key as a repository secret:
Settings → Secrets and variables → Actions → New repository secret — name it
`OPENCOMPLAI_API_KEY`, value is the key you issued on the project's page in the dashboard.

```yaml
# OpenComplAI compliance scan — GitHub Actions
#
# Copy this file to .github/workflows/opencomplai-scan.yml in your AI system
# repository. Requires a system-manifest.json in your repo root (see the
# CLI's own `opencomplai init`).
#
# Before this runs, add your API key as a repository secret:
#   Settings -> Secrets and variables -> Actions -> New repository secret
#   Name:  OPENCOMPLAI_API_KEY
#   Value: the key you issued on the project's page in this dashboard
name: OpenComplAI compliance scan

on:
  push:
    branches: [main]
  pull_request:

jobs:
  opencomplai-scan:
    name: OpenComplAI compliance scan
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v6

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.11"

      - name: Install OpenComplAI CLI
        run: pip install opencomplai

      - name: Run OpenComplAI compliance scan
        run: opencomplai-gha-connector
        env:
          # Exit-code contract (opencomplai check / opencomplai-gha-connector):
          #   0 = pass             scan passed (or degraded_complete in local scan mode)
          #   1 = control_fail     a required control failed
          #   2 = validation_fail  manifest or input validation error
          #   3 = policy_block     prohibited system (EU AI Act Article 5)
          #   4 = trap_detected    Article 25 substantial-modification freeze
          #
          # This dashboard's own ingest endpoint — safe to commit as plain
          # text, it is not a secret.
          OPENCOMPLAI_DASHBOARD_URL: https://YOUR-DASHBOARD-HOST/api/ingest
          # Set in this repository's (or organization's) Actions secrets —
          # never commit the key itself.
          OPENCOMPLAI_API_KEY: ${{ secrets.OPENCOMPLAI_API_KEY }}
```

## GitLab CI

Copy this into your `.gitlab-ci.yml` (or `include:` it) in your AI system repository.
Requires a `system-manifest.json` in your repo root (see the CLI's own `opencomplai init`).

To publish to the dashboard (the scan itself needs no key), add your API key as a masked CI/CD variable: Settings → CI/CD →
Variables → Add variable — key `OPENCOMPLAI_API_KEY`, value is the key you issued on the
project's page in the dashboard, flags Protect variable + Mask variable.

```yaml
# OpenComplAI compliance scan — GitLab CI
#
# Copy this into your .gitlab-ci.yml (or `include:` it) in your AI system
# repository. Requires a system-manifest.json in your repo root (see the
# CLI's own `opencomplai init`).
#
# Before this runs, add your API key as a masked CI/CD variable:
#   Settings -> CI/CD -> Variables -> Add variable
#   Key:   OPENCOMPLAI_API_KEY
#   Value: the key you issued on the project's page in this dashboard
#   Flags: Protect variable, Mask variable
opencomplai-scan:
  image: python:3.11
  before_script:
    - pip install opencomplai
  script:
    - opencomplai-gitlab-connector
  artifacts:
    reports:
      junit: opencomplai-report.xml
    dotenv: opencomplai.env
  variables:
    # Exit-code contract (opencomplai check / opencomplai-gitlab-connector):
    #   0 = pass             scan passed (or degraded_complete in local scan mode)
    #   1 = control_fail     a required control failed
    #   2 = validation_fail  manifest or input validation error
    #   3 = policy_block     prohibited system (EU AI Act Article 5)
    #   4 = trap_detected    Article 25 substantial-modification freeze
    #
    # This dashboard's own ingest endpoint — safe to commit as plain text,
    # it is not a secret. OPENCOMPLAI_API_KEY is NOT declared here — it
    # comes from the masked/protected CI/CD variable set above, which
    # GitLab injects into the job environment automatically.
    OPENCOMPLAI_DASHBOARD_URL: "https://YOUR-DASHBOARD-HOST/api/ingest"
    GL_ENV_FILE: opencomplai.env
```

## Any other CI platform

No dedicated connector script — run the CLI directly and let it push for you.

`--sign` needs a signing key: `~/.opencomplai/signing.key` (created by `opencomplai init`) or
`SIGNING_KEY_PRIVATE` (the base64-encoded PEM, stored as a CI secret). With neither, it exits `2`.

```bash
pip install opencomplai
opencomplai check --sign
# Keyless CI: write the artifact without a signature and print a warning instead of exiting 2:
# opencomplai check --sign-if-available
CHECK_EXIT=$?

# Push the scan artifact to the dashboard via the CLI:
OPENCOMPLAI_API_KEY="$OPENCOMPLAI_API_KEY" \
OPENCOMPLAI_DASHBOARD_URL="https://YOUR-DASHBOARD-HOST/api/ingest" \
  opencomplai push

exit "$CHECK_EXIT"
```

A raw POST to the ingest endpoint is rejected (HTTP 422) because the CLI shapes the artifact
first, so always use `opencomplai push`.

Recipes for other systems are in [CI recipes for other systems](ci-recipes.md):

- [Jenkins](ci-recipes.md#jenkins), [Bitbucket Pipelines](ci-recipes.md#bitbucket-pipelines) and [CircleCI](ci-recipes.md#circleci)
- [Notifications from the exit code](ci-recipes.md#notify-from-the-exit-code)
- [Archiving the artifact](ci-recipes.md#archive-the-artifact)

The GitHub Actions and GitLab CI connectors choose the flag for you: `--sign` when
`SIGNING_KEY_PRIVATE` is set, `--sign-if-available` otherwise.

## Reports from check

`opencomplai check` can write three extra files from the same verdict as `compliance-artifact.json`,
so any CI can show results without a connector:

- `--report-junit PATH` writes JUnit XML (one test case, a failure when the check fails).
- `--sarif-output PATH` writes SARIF 2.1.0 of the check verdict (failed controls and gap rows).
- `--summary-md PATH` writes the Markdown job summary the GitHub connector shows.

```text
opencomplai check --with-gaps --report-junit report.xml --sarif-output check.sarif --summary-md summary.md
```

Hand them to your platform: in GitLab CI list `report.xml` under `artifacts: reports: junit:`; in
GitHub Actions pass `check.sarif` to `github/codeql-action/upload-sarif` as `sarif_file`.

The exit code is the same with or without these flags. A report that cannot be written prints a
`WARN` on stderr and the run carries on. The files hold no dates. With several `--manifest` values
every system writes the same path, so use one manifest per report.

## Scope

v1 focuses on the EU AI Act. OpenComplAI produces structured evidence, not legal sign-off.
Pipeline evaluators (safety, bias, data-leakage) require a customer-supplied `EvalSampleSet`
JSON; when omitted, evals are skipped and rule checks still run.
