# docs generate

Generate an EU AI Act Annex IV technical documentation dossier (REQ-DOC-001).

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai docs generate --system-id <id> [OPTIONS]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai docs generate --system-id <id> [OPTIONS]
    ```

## Options

| Option | Default | Description |
|---|---|---|
| `--system-id` | *(required)* | System identifier from the manifest. |
| `--commit-ref` | `HEAD` | Git commit reference for this dossier. |
| `--intended-purpose` | `Not specified` | Primary intended purpose (free-text; copies the manifest value). |
| `--provider-name` | `Unknown Provider` | Legal name of the AI system provider for the dossier cover page. |
| `--output-dir` | `.` | Directory where the generated `dossier_<id>.json` file is written (local mode only). |
| `--output` / `-o` | `human` | Output format: `human` or `json`. |
| `--allow-incomplete` | off | Exit `0` even when the generated dossier fails Annex IV schema validation. Off by default — see [Fail-closed dossier gate](#fail-closed-dossier-gate) below. |

## Modes

**Service-backed mode** (when `OPENCOMPLAI_API_URL` is set): sends `POST /v1/docs/generate` to the `doc-generator` service. The dossier is stored server-side and its metadata is returned.

**Local mode** (when `OPENCOMPLAI_API_URL` is unset): generates the dossier using the local `opencomplai-doc-generator` package and writes `dossier_<id>.json` to `--output-dir`.

## Examples

=== "macOS / Linux"
    ```bash
    # Service-backed (Docker Compose stack running)
    OPENCOMPLAI_API_URL=http://localhost:8080 opencomplai docs generate \
      --system-id "loan-decision-model" \
      --commit-ref "$(git rev-parse HEAD)" \
      --intended-purpose "automated credit scoring for retail lending" \
      --provider-name "ACME Financial AI"

    # Local generation
    opencomplai docs generate \
      --system-id "loan-decision-model" \
      --intended-purpose "automated credit scoring for retail lending" \
      --provider-name "ACME Financial AI" \
      --output-dir ./compliance-docs/
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Service-backed (Docker Compose stack running)
    $env:OPENCOMPLAI_API_URL = "http://localhost:8080"; opencomplai docs generate --system-id "loan-decision-model" --commit-ref (git rev-parse HEAD) --intended-purpose "automated credit scoring for retail lending" --provider-name "ACME Financial AI"

    # Local generation
    opencomplai docs generate --system-id "loan-decision-model" --intended-purpose "automated credit scoring for retail lending" --provider-name "ACME Financial AI" --output-dir ./compliance-docs/
    ```

## Output (human)

```text
Annex IV Dossier Generated
  dossier_id:      d4f9c2a1-...
  bundle_checksum: sha256:3e2f1a...
  schema:          valid
  duration_ms:     142
```

## Output (JSON)

```json
{
  "dossier_id": "d4f9c2a1-...",
  "bundle_checksum": "sha256:3e2f1a...",
  "schema_valid": true,
  "duration_ms": 142
}
```

## Sidecar reports (D10)

`--scan-report` and `--eval-report` default to `scan-report.json` and
`eval-report.json` in the current directory — the same files `opencomplai
check`/`opencomplai gaps` write automatically when a scan or eval actually
ran. If either file exists, `generate` loads it and populates the
corresponding wired-evidence fields on the dossier (Section 5 scanner
fields, eval-merged metrics). If neither exists, those fields stay exactly
as empty as they are without them — nothing is fabricated to fill the gap.
See the [Annex IV coverage ledger](../concepts/annex-iv-coverage.md) for
which dossier fields are automated, wired evidence, or provider attestation.

## Fail-closed dossier gate

An invalid Annex IV dossier (`schema_valid: false` — see
[`validate_dossier_schema`](../concepts/annex-iv-coverage.md)) is refused by
default: the dossier is still written to `--output-dir` (or persisted
server-side in service-backed mode) so an auditor can see exactly what
failed, but the process exits `2` (`VALIDATION_FAIL`) instead of `0`. This
also applies to the doc-generator service, which returns HTTP `422` instead
of `200` for the same case.

Existing CI pipelines that relied on `docs generate` always exiting `0` must
add `--allow-incomplete` (CLI) or `allow_incomplete: true` (service request
body) to restore the old behaviour — the dossier is generated and written
identically either way; only the exit code / HTTP status changes.

## Halt / resume

If the system is currently `HALTED_PENDING_REVIEW` (see
[check](check.md#halt-on-trap--unresolved-high-risk-gap)), `generate` refuses
outright and exits `4` — no dossier is written, and there is no `--force`
bypass. Resume with `opencomplai approve` then `opencomplai resume` before
retrying.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Dossier generated successfully (or generated-but-invalid with `--allow-incomplete`). |
| 1 | Dossier generation failed (local mode error). |
| 2 | Validation error (invalid options, missing `opencomplai-doc-generator`, **or** the generated dossier failed Annex IV schema validation without `--allow-incomplete` — see [Fail-closed dossier gate](#fail-closed-dossier-gate)). |
| 3 | Service unreachable or policy blocked (service-backed mode only). |
| 4 | The system is `HALTED_PENDING_REVIEW` — dossier generation refused until resumed. |
