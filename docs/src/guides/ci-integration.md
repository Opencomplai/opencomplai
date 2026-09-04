# CI integration

OpenComplAI runs in GitHub Actions and GitLab CI via the CLI and connector scripts.

Setup starts on the dashboard, not in this guide: open **`/connect`** for your project
(**Projects → your project → Connect**) and it generates the two snippets below with your
own dashboard host already filled in — copy the tab for your platform, add
`OPENCOMPLAI_API_KEY` as a secret, and you're done. The copies here use
`https://YOUR-DASHBOARD-HOST` as a placeholder for that value.

## GitHub Actions

Copy this file to `.github/workflows/opencomplai-scan.yml` in your AI system repository.
Requires a `system-manifest.json` in your repo root (see the CLI's own `opencomplai init`).

Before this runs, add your API key as a repository secret:
Settings → Secrets and variables → Actions → New repository secret — name it
`OPENCOMPLAI_API_KEY`, value is the key you issued on the project's page in the dashboard.

```yaml
# OpenComplAI compliance scan — GitHub Actions
#
# Copy this file to .github/workflows/opencomplai-scan.yml in your AI system
# repository. Requires a manifest.yaml in your repo root (see the CLI's own
# `opencomplai init`).
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

Before this runs, add your API key as a masked CI/CD variable: Settings → CI/CD →
Variables → Add variable — key `OPENCOMPLAI_API_KEY`, value is the key you issued on the
project's page in the dashboard, flags Protect variable + Mask variable.

```yaml
# OpenComplAI compliance scan — GitLab CI
#
# Copy this into your .gitlab-ci.yml (or `include:` it) in your AI system
# repository. Requires a manifest.yaml in your repo root (see the CLI's own
# `opencomplai init`).
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

No dedicated connector script — run the CLI directly and either let it push for you, or
POST the artifact yourself:

```bash
pip install opencomplai
opencomplai check --sign
CHECK_EXIT=$?

# Push the signed artifact to the dashboard via the CLI:
OPENCOMPLAI_API_KEY="$OPENCOMPLAI_API_KEY" \
OPENCOMPLAI_DASHBOARD_URL="https://YOUR-DASHBOARD-HOST/api/ingest" \
  opencomplai push

# ...or the equivalent raw HTTP request, if you'd rather not install the CLI:
curl -X POST "https://YOUR-DASHBOARD-HOST/api/ingest/v1/ingest/scan-status" \
  -H "Authorization: Bearer $OPENCOMPLAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d @compliance-artifact.json

exit "$CHECK_EXIT"
```

## Scope

v1 focuses on the EU AI Act. OpenComplAI produces structured evidence, not legal sign-off.
Pipeline evaluators (safety, bias, data-leakage) require a customer-supplied `EvalSampleSet`
JSON; when omitted, evals are skipped and rule checks still run.
