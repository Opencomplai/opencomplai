# CI recipes for other systems

The Jenkins, Bitbucket Pipelines, CircleCI and Notify recipes follow the same three steps:

1. `pip install opencomplai`
2. `opencomplai check --commit-ref "$<CI SHA variable>"`, and keep the exit code
3. Optionally `opencomplai push`, then fail the job with the saved exit code

The four sections after Notify are different jobs (a scheduled re-run, a release upload, a decision
log and an offline scoring run), and each has its own steps.

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

## Scheduled re-run

A rule-set change or a regulatory date can change your result without any change to your code, and
a newer `opencomplai` release is how those changes arrive. There is no server-side scheduler, so the
cron runs in your own CI. This workflow runs `check` on a schedule, compares the result with the last
artifact it kept, and fails the job when `diff` finds a regression. The first run has no baseline,
so it only records one.

```yaml
name: OpenComplAI re-run

on:
  schedule:
    - cron: "0 6 * * 1,4"
  workflow_dispatch:

permissions:
  contents: read

jobs:
  opencomplai-rerun:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v6

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.11"

      - name: Install OpenComplAI CLI
        run: pip install --upgrade opencomplai

      - name: Restore the last baseline
        uses: actions/cache@v4
        with:
          path: baseline
          key: opencomplai-baseline-${{ github.run_id }}
          restore-keys: opencomplai-baseline-

      - name: Check, diff against the baseline, keep the new baseline
        run: |
          CHECK_EXIT=0
          opencomplai check --with-gaps || CHECK_EXIT=$?
          DIFF_EXIT=0
          if [ -f baseline/compliance-artifact.json ] && [ -f compliance-artifact.json ]; then
            opencomplai diff baseline/compliance-artifact.json compliance-artifact.json --fail-on-regression || DIFF_EXIT=$?
          fi
          if [ -f compliance-artifact.json ]; then
            mkdir -p baseline
            cp compliance-artifact.json baseline/compliance-artifact.json
          fi
          if [ "$DIFF_EXIT" -ne 0 ]; then exit "$DIFF_EXIT"; fi
          exit "$CHECK_EXIT"
```

The baseline is kept in an Actions cache, and the cache is saved only when the job succeeds. A
regression therefore keeps the job failing until you fix it, or until a person accepts the new state
by deleting the cached baseline so that the next run records a new one.

On Jenkins or GitLab CI, keep the `baseline/` directory in your own artifact store (for example
`archiveArtifacts` with the Copy Artifact plugin, or a GitLab `cache:` or job artifact from the
default branch) and run the same two commands. The recipe needs the system manifest in the repository
and no API key. See [diff](../cli/diff.md) and [exit codes](../cli/exit-codes.md).

## Attach the artifact to a release

This workflow runs when a release is published or a `v*` tag is pushed. It attaches the artifact to
the release. The artifact is unsigned unless `SIGNING_KEY_PRIVATE` is set, as described in
[any other CI platform](ci-integration.md#any-other-ci-platform). On other platforms, attach the same
file with the platform's own release or package upload.

```yaml
name: OpenComplAI release artifact

on:
  release:
    types: [published]
  push:
    tags: ["v*"]

permissions:
  contents: write

jobs:
  opencomplai-release:
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

      - name: Check and attach the artifact
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          CHECK_EXIT=0
          opencomplai check --with-gaps --sign-if-available --commit-ref "$GITHUB_SHA" || CHECK_EXIT=$?
          if [ -f compliance-artifact.json ] && gh release view "$GITHUB_REF_NAME" >/dev/null 2>&1; then
            gh release upload "$GITHUB_REF_NAME" compliance-artifact.json --clobber
          fi
          exit "$CHECK_EXIT"
```

## Record agent decisions

`AgentDecisionLog` writes one record per tool call. Record the call in a `finally` block, so a
failing tool is recorded too. The loop below stands in for your own agent loop, and no framework is
named.

```python
from opencomplai import AgentDecisionLog

log = AgentDecisionLog("agent-log.jsonl")

for step in agent_steps():  # your agent loop
    outcome = "failure"
    try:
        call = tools[step.tool]
        call(step.input)
        outcome = "success"
    finally:
        log.record(
            agent_id="support-agent",
            tool=step.tool,
            intent=step.intent,
            tool_input=step.input,
            outcome=outcome,
        )
```

After the run, verify the chain and write a dispute report from the same file:

```bash
opencomplai agents verify-log agent-log.jsonl
opencomplai agents dispute-report --log agent-log.jsonl --source native --from 2026-01-01 --to 2026-12-31 --output dispute-report.md
```

`check --agent-log` reads the same `agent-log.jsonl` by default. The log is evidence. Store its head
and record count somewhere outside the CI workspace, so that a truncated file can be detected (see
[Agents](../concepts/agents.md)). The raw tool input is hashed, not stored. For logs from the Agent
Governance Toolkit, see [AGT import](../concepts/agt-import.md).

## Score recorded model responses offline

The work has two phases. Phase A records the model's responses once, or again after a model or prompt
change. It needs network access and a provider key in a CI secret, exposed to the command as
`OPENCOMPLAI_PROVIDER_API_KEY`. `eval` exits 1 when an evaluator fails, so the command ends with
`|| true` and the next step reads its output.

```bash
opencomplai eval --manifest system-manifest.json --sample-set prompts.json --provider openai --model <model> --output json > eval-live.out || true
```

`eval` prints two JSON documents. The first is the evaluator summary. The second has a `completions`
key, with one `prompt` and `completion` per item. The following script keeps that second document and
writes `eval-set.json`. `prompts.json` is a sample set with `eval_set_id`, `system_id` (equal to the
manifest's) and `prompts`.

```python
import json

text = open("eval-live.out", encoding="utf-8").read()
decoder = json.JSONDecoder()
docs = []
pos = 0
while pos < len(text):
    if text[pos].isspace():
        pos += 1
        continue
    doc, pos = decoder.raw_decode(text, pos)
    docs.append(doc)

completions = next(d["completions"] for d in docs if "completions" in d)
source = json.load(open("prompts.json", encoding="utf-8"))
eval_set = {
    "eval_set_id": source["eval_set_id"],
    "system_id": source["system_id"],
    "prompts": [c["prompt"] for c in completions],
    "outputs": [c["completion"] for c in completions],
}
with open("eval-set.json", "w", encoding="utf-8") as f:
    json.dump(eval_set, f, indent=2)
```

Phase B runs on every CI run. It needs no key and no network:

```bash
opencomplai check --sample-set eval-set.json
opencomplai eval --sample-set eval-set.json
```

Keep in mind these limits. The adversarial evaluator pairs `prompts[i]` with `outputs[i]`, and it is
skipped when the two lists differ in length. The recorded responses are a snapshot, so re-record them
after a model or prompt change. The result is heuristic evidence, and this recipe does not establish
whether a control is met. See [eval](../cli/eval.md) and [evaluators](../concepts/evaluators.md).

## Archive the artifact

`check` writes `compliance-artifact.json` in the working directory, plus `scan-report.json` and
`eval-report.json` when those reports ran. These files are the evidence record of the run. CI
workspaces are deleted after the job, so archive them: `archiveArtifacts` in Jenkins, `artifacts` in
Bitbucket Pipelines, `store_artifacts` in CircleCI and `artifacts:` in GitLab CI.
