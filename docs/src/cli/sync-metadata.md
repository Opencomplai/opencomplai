# sync metadata

Sync allowlisted compliance metadata to the Premium Dashboard (Phase 18).

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai sync metadata --system-id <id> [OPTIONS]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai sync metadata --system-id <id> [OPTIONS]
    ```

!!! note "Service required"
    `sync metadata` requires the Docker Compose stack. Set `OPENCOMPLAI_API_URL` and ensure the `egress-proxy` service is running.

## Options

| Option | Default | Description |
|---|---|---|
| `--system-id` | *(required)* | System identifier whose metadata is synced. |
| `--endpoint` | *(unset)* | Override the egress-proxy sync endpoint. Defaults to `$OPENCOMPLAI_API_URL/v1/sync/metadata`. |

## What gets synced

Only fields on the `ALLOWED_FIELDS` allowlist pass through the egress proxy. No raw evidence, model weights, training data, or PII are ever transmitted. The sync payload is the `ScanStatusArtifact` shape (minus `signature`) filtered to metadata-only fields.

## Example

=== "macOS / Linux"
    ```bash
    export OPENCOMPLAI_API_URL=http://localhost:8080

    opencomplai sync metadata \
      --system-id "loan-decision-model"
    ```

=== "Windows (PowerShell)"
    ```powershell
    $env:OPENCOMPLAI_API_URL = "http://localhost:8080"

    opencomplai sync metadata --system-id "loan-decision-model"
    ```

## Output

Returns the gateway's sync response as JSON:

```json
{
  "synced": true,
  "system_id": "loan-decision-model",
  "fields_synced": ["install_id", "system_id", "commit_ref", "result", "duration_ms"]
}
```

## Air-gap behaviour

If `EGRESS_ALLOWED_DESTINATIONS=` (empty) in `.env`, the egress proxy blocks the outbound sync call. `sync metadata` will return exit code `3`. This is by design — in air-gap deployments, dashboard sync is intentionally disabled.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Metadata synced successfully. |
| 3 | Service unreachable, egress blocked, or policy enforcement rejected the call. |
