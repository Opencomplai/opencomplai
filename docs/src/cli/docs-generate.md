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

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Dossier generated successfully. |
| 1 | Dossier generation failed (local mode error). |
| 2 | Validation error (invalid options or missing `opencomplai-doc-generator`). |
| 3 | Service unreachable or policy blocked (service-backed mode only). |
