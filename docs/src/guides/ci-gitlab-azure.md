# CI for GitLab and Azure Pipelines

Both templates call `opencomplai check` directly, so the CLI's exit code fails the pipeline
natively, and both publish a JUnit result even when the check fails. They need a
`system-manifest.json` in your repository root (see `opencomplai init`). The scan needs no key.

| Exit code | Meaning |
| --- | --- |
| 0 | pass |
| 1 | control_fail: a required control failed |
| 2 | validation_fail: manifest or input validation error |
| 3 | policy_block: prohibited system |
| 4 | trap_detected: substantial-modification freeze |

GitLab and Azure Pipelines fail the job on exits 1 to 4 without any extra step. The full table is in
[Exit codes](../cli/exit-codes.md).

## GitLab CI component

[`templates/opencomplai.yml`](https://github.com/Opencomplai/opencomplai/blob/main/templates/opencomplai.yml)
is a GitLab CI/CD component. Include it from a project that hosts it; the project path below is a
placeholder to replace with your own.

```yaml
include:
  - component: $CI_SERVER_FQDN/<GITLAB-GROUP>/<PROJECT>/opencomplai@<VERSION>
    inputs:
      manifest: system-manifest.json
```

| Input | Default | Meaning |
| --- | --- | --- |
| `stage` | `test` | Pipeline stage that runs the job |
| `image` | `python:3.11` | Container image |
| `version` | `0.9.0` | Exact opencomplai release to install; empty installs the latest |
| `manifest` | `system-manifest.json` | Path to the system manifest |
| `extra_args` | empty | Extra arguments for `opencomplai check` |
| `sarif` | `false` | Also write a SARIF file and keep it as a job artifact |
| `push` | `false` | Run `opencomplai push` when `OPENCOMPLAI_API_KEY` is set |

To publish, add `OPENCOMPLAI_API_KEY` and `OPENCOMPLAI_DASHBOARD_URL` as masked CI/CD variables
(Settings, CI/CD, Variables). The job keeps the JUnit report as a test report and the Markdown summary
as an artifact for 30 days, whether the check passes or fails.

## Azure Pipelines

Copy
[`docs/ci/azure-pipelines.yml`](https://github.com/Opencomplai/opencomplai/blob/main/docs/ci/azure-pipelines.yml)
to `azure-pipelines.yml` in your repository. It sets up Python, installs a pinned release, runs the
same `check` flags as the GitLab component and saves the exit code, publishes the JUnit file with
`PublishTestResults@2`, and then fails the job with the saved exit code. To publish to the dashboard,
add a secret pipeline variable named `OPENCOMPLAI_API_KEY`; it is mapped through `env:` and never
written in the file.

```yaml
# OpenComplAI compliance scan - Azure Pipelines
#
# Copy this file to azure-pipelines.yml in your AI system repository.
# Requires a system-manifest.json in your repo root (see the CLI's own
# `opencomplai init`).
#
# To publish to the dashboard (the scan itself needs no key), add a secret
# pipeline variable:
#   Pipelines -> your pipeline -> Edit -> Variables -> New variable
#   Name:  OPENCOMPLAI_API_KEY
#   Value: the key you issued on the project's page in the dashboard
#   Flags: Keep this value secret
#
# Exit-code contract (opencomplai check):
#   0 = pass             scan passed
#   1 = control_fail     a required control failed
#   2 = validation_fail  manifest or input validation error
#   3 = policy_block     prohibited system
#   4 = trap_detected    substantial-modification freeze
trigger:
  - main

pr:
  - main

pool:
  vmImage: ubuntu-latest

steps:
  - task: UsePythonVersion@0
    displayName: Set up Python
    inputs:
      versionSpec: "3.11"

  - script: pip install --quiet "opencomplai==0.9.0"
    displayName: Install OpenComplAI CLI

  - script: |
      set +e
      opencomplai check \
        --manifest system-manifest.json \
        --sign-if-available \
        --report-junit opencomplai-report.xml \
        --summary-md opencomplai-summary.md
      code=$?
      if [ -n "$OPENCOMPLAI_API_KEY" ] && [ "$OPENCOMPLAI_API_KEY" != '$(OPENCOMPLAI_API_KEY)' ]; then
        opencomplai push || echo "opencomplai push failed; the check verdict is unchanged"
      fi
      if [ -f opencomplai-summary.md ]; then
        echo "##vso[task.uploadsummary]$PWD/opencomplai-summary.md"
      fi
      echo "##vso[task.setvariable variable=OC_EXIT]$code"
    displayName: Run OpenComplAI compliance scan
    env:
      # This dashboard's own ingest endpoint: not a secret.
      OPENCOMPLAI_DASHBOARD_URL: https://YOUR-DASHBOARD-HOST/api/ingest
      # Secret pipeline variable; never commit the key itself.
      OPENCOMPLAI_API_KEY: $(OPENCOMPLAI_API_KEY)

  - task: PublishTestResults@2
    displayName: Publish JUnit result
    condition: succeededOrFailed()
    inputs:
      testResultsFormat: JUnit
      testResultsFiles: opencomplai-report.xml

  - script: exit $(OC_EXIT)
    displayName: Fail the job on a failed check
    condition: succeededOrFailed()
```
