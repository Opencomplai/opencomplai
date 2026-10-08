# OpenComplAI GitHub Action

Runs `opencomplai check` on a system manifest, posts the result as one sticky pull request
comment, optionally uploads the SARIF verdict, and fails the job when the check fails.

The Action reports what the check found. It does not certify anything and is not legal advice.

Marketplace publication is pending. Until it is listed, reference the Action by path in this
repository or copy `integrations/github-action/` into yours.
The default `version` is the next release; it cannot be installed until that release is on PyPI,
so set `version` to a published release in the meantime.

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
```

Pin every `uses:` to a full commit SHA with a trailing version comment. The Action never passes
`--sign`: signing stays your decision (add `--sign-if-available` or `--sign` through `args`).

## Inputs

| Input | Default | Meaning |
|---|---|---|
| `manifest` | `system-manifest.json` | Path to the system manifest |
| `version` | the pinned release | Exact `opencomplai` release, installed with `uvx --from opencomplai==<version>` |
| `install-from` | empty | Path or package spec that replaces the pinned release (testing a checkout) |
| `with` | empty | Extra `uvx --with` specs, one per line |
| `args` | empty | Extra `opencomplai check` arguments, split on whitespace (for example `--change-context model_retrain`) |
| `comment` | `true` | Post or update one sticky comment on pull request events |
| `upload-sarif` | `false` | Upload the SARIF verdict to code scanning |
| `fail-on-error` | `true` | Fail the job when `check` exits non-zero |
| `github-token` | `github.token` | Token for the comment |

## Outputs

| Output | Meaning |
|---|---|
| `exit-code` | Exit code of `opencomplai check` |
| `summary-file` | Markdown summary, starting with the sticky comment marker |
| `sarif-file` | SARIF file path, empty when none was written |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | No gate failure |
| 1 | A control failed (for example a high-risk classification that is not accepted) |
| 2 | Validation failed (bad manifest or missing input) |
| 3 | Policy block (prohibited practice) |
| 4 | Modification trap: halted for human review |

## Permissions

- `contents: read` to check out the repository.
- `pull-requests: write` for the comment. A pull request from a fork has a read-only token: the
  comment is skipped with a warning and the gate result is unchanged.
- `security-events: write` for the SARIF upload.

Before each release, the maintainers' CI runs the five `examples/gate-demo` systems through this
Action and checks each exit code.
