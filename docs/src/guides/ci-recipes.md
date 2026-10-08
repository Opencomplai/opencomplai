# CI recipes for other systems

Every recipe here is the same three steps:

1. `pip install opencomplai`
2. `opencomplai check --commit-ref "$<CI SHA variable>"`, and keep the exit code
3. Optionally `opencomplai push`, then fail the job with the saved exit code

The scan and the exit code need no key. Only `push` needs `OPENCOMPLAI_API_KEY` and
`OPENCOMPLAI_DASHBOARD_URL` (your ingest base URL, for example
`https://YOUR-DASHBOARD-HOST/api/ingest`). Store the key as a CI secret, never in the file.

Each recipe runs the push before it fails the job, so a failing check still reaches the dashboard.
The meaning of each exit code is in [Exit codes](../cli/exit-codes.md). GitHub Actions and GitLab CI
are covered in [CI Integration](ci-integration.md).

These recipes use plain `check`. To sign the artifact, add `--sign` and provide `SIGNING_KEY_PRIVATE`
as described in [CI Integration](ci-integration.md#any-other-ci-platform).

## Jenkins

A declarative `Jenkinsfile`. Create a "Secret text" credential with the id `opencomplai-api-key`.

```groovy
pipeline {
  agent any
  environment {
    OPENCOMPLAI_DASHBOARD_URL = 'https://YOUR-DASHBOARD-HOST/api/ingest'
  }
  stages {
    stage('Check') {
      steps {
        sh 'pip install opencomplai'
        script {
          env.CHECK_EXIT = sh(
            returnStatus: true,
            script: 'opencomplai check --commit-ref "$GIT_COMMIT" --report-junit report.xml'
          ).toString()
        }
      }
      post {
        always {
          archiveArtifacts artifacts: 'compliance-artifact.json', allowEmptyArchive: true
          junit allowEmptyResults: true, testResults: 'report.xml'
        }
      }
    }
    stage('Push') {
      steps {
        withCredentials([string(credentialsId: 'opencomplai-api-key', variable: 'OPENCOMPLAI_API_KEY')]) {
          sh 'opencomplai push'
        }
      }
    }
    stage('Gate') {
      steps {
        script {
          if (env.CHECK_EXIT != '0') {
            error("opencomplai check exited with ${env.CHECK_EXIT}")
          }
        }
      }
    }
  }
}
```

## Bitbucket Pipelines

`bitbucket-pipelines.yml`. Add `OPENCOMPLAI_API_KEY` as a secured repository variable.

```yaml
image: python:3.11

pipelines:
  default:
    - step:
        name: OpenComplAI check
        script:
          - pip install opencomplai
          - |
            CHECK_EXIT=0
            opencomplai check --commit-ref "$BITBUCKET_COMMIT" || CHECK_EXIT=$?
            OPENCOMPLAI_DASHBOARD_URL="https://YOUR-DASHBOARD-HOST/api/ingest" opencomplai push || true
            exit "$CHECK_EXIT"
        artifacts:
          - compliance-artifact.json
```

## CircleCI

`.circleci/config.yml`. Add `OPENCOMPLAI_API_KEY` as a project environment variable.

```yaml
version: 2.1

jobs:
  opencomplai-check:
    docker:
      - image: cimg/python:3.11
    environment:
      OPENCOMPLAI_DASHBOARD_URL: "https://YOUR-DASHBOARD-HOST/api/ingest"
    steps:
      - checkout
      - run: pip install opencomplai
      - run:
          name: Check, push, then gate
          command: |
            CHECK_EXIT=0
            opencomplai check --commit-ref "$CIRCLE_SHA1" --report-junit test-results/opencomplai.xml || CHECK_EXIT=$?
            opencomplai push || true
            exit "$CHECK_EXIT"
      - store_artifacts:
          path: compliance-artifact.json
      - store_test_results:
          path: test-results

workflows:
  compliance:
    jobs:
      - opencomplai-check
```

## Notify from the exit code

Save the exit code, then tell people what it means. The Slack webhook URL and the Jira token come
from CI secrets.

```bash
opencomplai check --commit-ref "$CI_COMMIT_SHA"
CHECK_EXIT=$?

slack() {
  curl -sS -X POST -H "Content-Type: application/json" \
    -d "{\"text\": \"$1\"}" "$SLACK_WEBHOOK_URL"
}

jira() {
  curl -sS -X POST -u "$JIRA_USER:$JIRA_API_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"fields\": {\"project\": {\"key\": \"COMP\"}, \"summary\": \"$1\", \"issuetype\": {\"name\": \"Task\"}}}" \
    "$JIRA_BASE_URL/rest/api/3/issue"
}

case "$CHECK_EXIT" in
  0) slack "OpenComplAI check passed: all critical controls passed." ;;
  1) slack "OpenComplAI check failed: a critical control failed."
     jira "OpenComplAI: a critical control failed" ;;
  2) slack "OpenComplAI check could not run: the manifest or an input is invalid." ;;
  3) slack "OpenComplAI check blocked: a prohibited (Article 5) practice was detected."
     jira "OpenComplAI: a prohibited practice was detected" ;;
  4) slack "OpenComplAI check found an Article 25 trap: the change makes you a provider."
     jira "OpenComplAI: Article 25 substantial modification" ;;
esac

exit "$CHECK_EXIT"
```

!!! note
    The Slack and Jira request bodies follow those vendors' public APIs. They are examples to adapt
    and are not tested by OpenComplAI.

## Archive the artifact

`check` writes `compliance-artifact.json` in the working directory, plus `scan-report.json` and
`eval-report.json` when those reports ran. These files are the evidence record of the run. CI
workspaces are deleted after the job, so archive them: `archiveArtifacts` in Jenkins, `artifacts` in
Bitbucket Pipelines, `store_artifacts` in CircleCI and `artifacts:` in GitLab CI.
