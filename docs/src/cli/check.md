# check

Run a full compliance check against EU AI Act rules.

If the manifest has no `checker_session`, `check` prints a **non-blocking** warning recommending `opencomplai checker` or `opencomplai init --interactive`. When a session is present, human output includes a one-line applicability summary.

## Synopsis

```bash
opencomplai check [OPTIONS]
```

## Options

| Option | Default | Description |
|---|---|---|
| `--manifest` / `-m` | `system-manifest.json` | Path to the system manifest JSON file. |
| `--commit-ref` | `HEAD` | Git commit reference for the assessment. |
| `--scan-mode` | `local` | Scan mode: `ci`, `local`, or `airgap`. |
| `--sample-set` | *(none)* | Path to an `EvalSampleSet` JSON to run the safety / bias / data-leakage evaluators. Its `system_id` must match the manifest. |
| `--sign` / `--no-sign` | `--no-sign` | Sign the status artifact using `~/.opencomplai/signing.key`. |
| `--output` / `-o` | `human` | Output format: `human` or `json`. |

## Environment variables

| Variable | Description |
|---|---|
| `OPENCOMPLAI_API_URL` | When set, `check` orchestrates all services via the gateway API at this URL (service-backed mode). When unset, runs locally. Example: `http://localhost:8080` |

## Examples

```bash
# Local check with human-readable output (default)
opencomplai check

# Run pipeline evaluators against your own model outputs
opencomplai check --sample-set eval-set.json

# CI-mode with JSON output piped to jq
opencomplai check --scan-mode ci --output json | jq .result

# Service-backed mode (Docker Compose stack running)
OPENCOMPLAI_API_URL=http://localhost:8080 opencomplai check

# Air-gap mode
opencomplai check --scan-mode airgap
```

## Output

After every run, `compliance-artifact.json` is written to the current directory.
This is the canonical `ScanStatusArtifact` for CI consumption.

**Human output example** (a passing, minimal-risk system):

```text
Evals: no eval sample set supplied (skipped)

Opencomplai Compliance Check
  system_id:    my-model
  commit_ref:   HEAD
  result:       PASS
  duration_ms:  0
  signed:       no (OSS unsigned)

  Artifact written to compliance-artifact.json
```

When a control fails, a `failed_controls:` line is added, e.g. for a high-risk
use case:

```text
Opencomplai Compliance Check
  system_id:    hiring
  commit_ref:   HEAD
  result:       CONTROL_FAIL
  duration_ms:  0
  signed:       no (OSS unsigned)
  failed_controls: EU_AIA_ART6_HIGH_RISK

  Artifact written to compliance-artifact.json
```

With `--sample-set`, the `Evals: ...skipped` line is replaced by an
`eval_outcome:` line (`pass`, `warn`, or `fail`).

**JSON output (`ScanStatusArtifact` schema):**

```json
{
  "install_id": "a1b2c3d4-...",
  "system_id": "my-model",
  "commit_ref": "HEAD",
  "result": "pass",
  "failed_controls": [],
  "evidence_hashes": [],
  "rationale_hash": "sha256:...",
  "duration_ms": 0,
  "pending_verifications_count": 0,
  "signature": null,
  "eval_summary": null
}
```

`eval_summary` is populated only when `--sample-set` is supplied; `signature` is
populated only when `--sign` is supplied (and a signing key exists).

## Exit codes

See [Exit codes](exit-codes.md) for the full table.
