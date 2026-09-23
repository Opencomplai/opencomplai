# check

Run a full compliance check against EU AI Act rules.

If the manifest has no `checker_session`, `check` prints a **non-blocking** warning recommending `opencomplai checker` or `opencomplai init --interactive`. When a session is present, human output includes a one-line applicability summary.

A `checker_session.verdict` of `prohibited_practice` fails the check with
`POLICY_BLOCK` (exit `3`, `EU_AIA_ART5_UNACCEPTABLE`); `high_risk_ai_system`
fails it with at least `CONTROL_FAIL` (exit `1`, `EU_AIA_ART6_HIGH_RISK`). The
verdict only ever raises the result: it never replaces `TRAP_DETECTED` or
`VALIDATION_FAIL`. Manifests written by 0.7.0 `opencomplai checker
--write-manifest` hold the verdict in `intended_purpose` instead; `check`
still applies it and warns you to replace `intended_purpose` with what the
system does.

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai check [OPTIONS]
    ```

=== "Windows (PowerShell)"
    ```powershell
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
| `--with-gaps` | off | Attach a per-article `gap_report` to the artifact (additive, informational only). Artifact-backed articles are probed under `--repo-root`, as in [`gaps`](gaps.md). |
| `--repo-root` | `.` | Repo root for the `--scan` code scan and the `--with-gaps` artifact path probes (Arts. 9/13/14/16/24/43). |
| `--output` / `-o` | `human` | Output format: `human` or `json`. |

## Environment variables

| Variable | Description |
|---|---|
| `OPENCOMPLAI_API_URL` | When set, `check` orchestrates all services via the gateway API at this URL (service-backed mode). When unset, runs locally. Example: `http://localhost:8080` |

## Examples

=== "macOS / Linux"
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

=== "Windows (PowerShell)"
    ```powershell
    # Local check with human-readable output (default)
    opencomplai check

    # Run pipeline evaluators against your own model outputs
    opencomplai check --sample-set eval-set.json

    # CI-mode with JSON output (pipe to ConvertFrom-Json for parsing)
    opencomplai check --scan-mode ci --output json | ConvertFrom-Json | Select-Object -ExpandProperty result

    # Service-backed mode (Docker Compose stack running)
    $env:OPENCOMPLAI_API_URL = "http://localhost:8080"; opencomplai check

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
populated only when `--sign` is supplied (and a signing key exists). The
signature is computed last, over the artifact exactly as written — including
the `--scan --fail-on` result, the checker verdict and the `--with-gaps`
blocks — so `compliance-artifact.json` verifies against `signing.pub` as-is.

`check` also writes `scan-report.json` / `eval-report.json` sidecars next to
`compliance-artifact.json` whenever a scan (`--scan`) or eval (`--sample-set`)
actually ran — these are what `opencomplai docs generate` picks up
automatically to populate the Annex IV dossier's wired-evidence fields. See
[Annex IV coverage ledger](../concepts/annex-iv-coverage.md).

## Halt on trap / unresolved HIGH-risk gap

A `TRAP_DETECTED` result, or a HIGH-risk system with an unresolved
corroboration gap (HIGH risk class plus a failed `--scan --fail-on ...`
gate), persists the system as `HALTED_PENDING_REVIEW`. While halted,
`opencomplai docs generate` for that `system_id` refuses outright (exit `4`,
no dossier written, no `--force`). Resume with `opencomplai approve` /
`opencomplai resume` — see
[Halt / resume gate](exit-codes.md#halt--resume-gate-opencomplai-check-opencomplai-docs-generate).

## Exit codes

See [Exit codes](exit-codes.md) for the full table.
