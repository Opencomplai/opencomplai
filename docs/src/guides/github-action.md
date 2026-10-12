# GitHub Action

The composite Action in `integrations/github-action/` runs [`opencomplai check`](../cli/check.md)
on a system manifest, posts the result as one sticky pull request comment, keeps the
`compliance-artifact.json` as a workflow artifact, optionally uploads the SARIF verdict to code
scanning, and fails the job when the check fails.

The Action reports what the check found. It does not certify anything and is not legal advice.

For a workflow you copy and edit yourself, built on the connector scripts, see
[CI integration](ci-integration.md). This page covers the Action only.

## Usage

```yaml
name: compliance
on: pull_request

permissions:
  contents: read
  pull-requests: write # sticky comment
  security-events: write # only with upload-sarif: "true"

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<40-hex commit SHA> # vN
      - uses: Opencomplai/opencomplai/integrations/github-action@<40-hex commit SHA> # vN
        with:
          manifest: system-manifest.json
          # version: <release>   # optional; defaults to the release pinned in action.yml
```

Pin every `uses:` to a full commit SHA with a trailing version comment. The Action installs
`opencomplai` through `uvx` at one exact release, pinned with `==`, so a run is reproducible.
Until the Action is listed on the Marketplace, reference it by path in this repository, or copy
`integrations/github-action/` into yours.

## Inputs

| Input | Default | Meaning |
|---|---|---|
| `manifest` | `system-manifest.json` | Path to the system manifest. |
| `version` | the release current when the Action was published; see `action.yml` | Exact `opencomplai` release, installed with `uvx --from opencomplai==<version>`. |
| `install-from` | empty | Path or package spec that replaces the pinned release, for testing a checkout. |
| `with` | empty | Extra `uvx --with` specs, one per line. |
| `args` | empty | Extra [`check`](../cli/check.md) arguments, split on whitespace, for example `--change-context model_retrain`. See [Passing extra check flags](#passing-extra-check-flags). |
| `comment` | `true` | Post or update one sticky comment on pull request events. |
| `upload-sarif` | `false` | Upload the SARIF verdict to code scanning. |
| `upload-artifact` | `true` | Upload `compliance-artifact.json` as a workflow artifact. |
| `artifact-name` | `compliance-artifact-<commit sha>` | Name of the uploaded artifact. Must be unique within a workflow run. |
| `sign` | `false` | Sign the artifact when a signing key is in the environment (`--sign-if-available`). |
| `with-gaps` | `false` | Add the per-article gap report to the artifact (`--with-gaps`). |
| `fail-on-error` | `true` | Fail the job when `check` exits non-zero. |
| `github-token` | `github.token` | Token used to post the comment. |

## Outputs

| Output | Meaning |
|---|---|
| `exit-code` | Exit code of `opencomplai check`. |
| `summary-file` | Markdown summary, starting with the sticky comment marker. |
| `sarif-file` | SARIF file path, empty when none was written. |
| `artifact-file` | Path of `compliance-artifact.json`, empty when none was written. |

The Action itself always completes the `check` step; the job fails in a later step when
`fail-on-error` is `true` and `exit-code` is not `0`. Read `exit-code` in a later step to act on
the result yourself.

## Exit codes

The job fails with the exit code of `check` when `fail-on-error` is `true`. The codes are the CLI's;
the full table is in [Exit codes](../cli/exit-codes.md).

| Code | Meaning |
|---|---|
| `0` | No gate failure. |
| `1` | A control failed, for example a high-risk classification that is not accepted. |
| `2` | Validation failed: a bad manifest or a missing input. |
| `3` | Policy block: a prohibited practice. |
| `4` | Modification trap: halted for human review. |

## Passing extra check flags

Use the `args` input for any other [`check` option](../cli/check.md#options):

```yaml
      - uses: Opencomplai/opencomplai/integrations/github-action@<40-hex commit SHA> # vN
        with:
          args: --scan --fail-on major --strict
```

`OPENCOMPLAI_CHECK_ARGS` is read by the connector scripts (`opencomplai-gha-connector` and
`opencomplai-gitlab-connector`), see [CI integration](ci-integration.md) and the
[`check` environment variables](../cli/check.md#environment-variables). It is not read by
this Action: set `args` instead.

## Evidence artifact and signing

Each run uploads `compliance-artifact.json` as one workflow artifact named by `artifact-name`
(default `compliance-artifact-<commit sha>`), retained 90 days. It is uploaded even when the gate
fails. Set `upload-artifact: "false"` to skip it. When the Action runs more than once in a workflow,
give each call its own `artifact-name`.

Signing needs the `sign` input set to `"true"` and a signing key in the job environment
(`SIGNING_KEY_PRIVATE`, from a secret). Without a key the artifact is written unsigned and the check
warns. Passing `--sign` through `args` is strict: a missing key then fails the check with exit `2`.

## Permissions

- `contents: read` to check out the repository.
- `pull-requests: write` for the comment. A pull request from a fork has a read-only token: the
  comment is skipped with a warning and the gate result is unchanged.
- `security-events: write` for the SARIF upload.
