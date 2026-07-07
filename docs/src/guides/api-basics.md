# Gateway API Basics

The Opencomplai gateway API is a JSON-over-HTTP service that proxies requests to the internal Docker Compose services.

**Base URL:** `http://localhost:8080` (when the Docker Compose stack is running)

**All requests** send and receive `application/json`. No API key is required for the OSS stack.

## Quick reference

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/v1/manifests/validate` | Validate a system manifest |
| `POST` | `/v1/risk/classify` | Classify risk level |
| `POST` | `/v1/verify/claims` | Submit a ground-truth verification task |
| `POST` | `/v1/docs/generate` | Generate an Annex IV dossier |
| `POST` | `/v1/evidence/events` | Append a ledger event |
| `POST` | `/v1/sync/metadata` | Sync metadata to the dashboard |

For full request/response documentation, see [Gateway API — REST Reference](../api/rest-api.md).

## CLI vs direct API calls

The `opencomplai` CLI calls the gateway API automatically when `OPENCOMPLAI_API_URL` is set. You can also call the API directly with `curl` for testing or scripting:

=== "macOS / Linux"
    ```bash
    # Health check
    curl http://localhost:8080/health

    # Risk classification
    curl -s -X POST http://localhost:8080/v1/risk/classify \
      -H "Content-Type: application/json" \
      -d '{"system_id": "my-model", "intended_purpose": "customer support chatbot"}' | jq .
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Health check
    Invoke-WebRequest -Uri "http://localhost:8080/health"

    # Risk classification (install jq separately, or use ConvertFrom-Json)
    curl.exe -s -X POST http://localhost:8080/v1/risk/classify `
      -H "Content-Type: application/json" `
      -d '{\"system_id\": \"my-model\", \"intended_purpose\": \"customer support chatbot\"}' | ConvertFrom-Json | ConvertTo-Json -Depth 10
    ```
