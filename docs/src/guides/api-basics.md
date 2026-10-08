# Gateway API Basics

The Opencomplai gateway API is a JSON-over-HTTP service that proxies requests to the internal Docker Compose services.

**Base URL:** `http://localhost:8080` (when the Docker Compose stack is running)

**All requests** send and receive `application/json`.

**Authentication.** Every endpoint except `GET /health` requires credentials. The gateway is fail-closed: it refuses to start unless authentication is configured (`OPENCOMPLAI_API_KEY`, or the `OIDC_*` settings), or explicitly disabled for local development with `OPENCOMPLAI_AUTH_DISABLED=1`. Send the key in an `x-api-key` header; if the deployment uses OIDC, send `Authorization: Bearer <jwt>` instead. A request without valid credentials gets `401`. See [Authentication](../deployment/authentication.md) and the [REST reference](../api/rest-api.md#authentication).

## Quick reference

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health check (no credentials) |
| `POST` | `/v1/manifests/validate` | Validate a system manifest |
| `POST` | `/v1/risk/classify` | Classify risk level |
| `POST` | `/v1/verify/claims` | Submit a ground-truth verification task |
| `POST` | `/v1/hitl/overrides` | Submit a human override with a rationale |
| `POST` | `/v1/hitl/overrides/{override_id}/second-approval` | Complete a dual-control override with a second approver |
| `GET` | `/v1/hitl/queue` | List the human-review queue |
| `GET` | `/v1/hitl/queue/{id}` | Get a review item with its redacted context |
| `POST` | `/v1/hitl/queue/{id}/assign` | Assign a review item to a reviewer |
| `POST` | `/v1/hitl/queue/{id}/decide` | Record the decision on a review item |
| `POST` | `/v1/docs/generate` | Generate an Annex IV dossier |
| `GET` | `/v1/docs` | List a system's dossiers |
| `GET` | `/v1/docs/{dossier_id}` | Retrieve a dossier |
| `POST` | `/v1/evidence/events` | Append a ledger event |
| `GET` | `/v1/evidence/verify-chain` | Verify the ledger chain |
| `GET` | `/v1/evidence/ledger-root` | Current ledger Merkle tip |
| `GET` | `/v1/evidence/ledger-history-tips` | Merkle tip after every event |
| `POST` | `/v1/sync/metadata` | Sync metadata to the dashboard |
| `GET` | `/v1/status` | Aggregate status of the downstream services |
| `GET` | `/v1/portfolio` | Systems on record with their latest badge |
| `POST` | `/v1/pro/badges/issue` | Issue a compliance badge |
| `GET` | `/v1/pro/badges/verify/{badgeId}` | Badge metadata |
| `GET` | `/v1/pro/badges/{badgeId}/svg` | Badge SVG markup, wrapped in JSON |
| `POST` | `/v1/pro/ingest/status-artifact` | Record a scan status artifact |
| `POST` | `/v1/pro/ingest/dossier-metadata` | Record dossier metadata |
| `POST` | `/v1/pro/ingest/metrics` | Record compliance metrics |

For full request/response documentation, see [Gateway API — REST Reference](../api/rest-api.md).

## CLI vs direct API calls

The `opencomplai` CLI calls the gateway API automatically when `OPENCOMPLAI_API_URL` is set. You can also call the API directly with `curl` for testing or scripting:

=== "macOS / Linux"
    ```bash
    # Health check
    curl http://localhost:8080/health

    # Risk classification (API-key mode; send your OPENCOMPLAI_API_KEY)
    curl -s -X POST http://localhost:8080/v1/risk/classify \
      -H "x-api-key: $OPENCOMPLAI_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"system_id": "my-model", "intended_purpose": "customer support chatbot"}' | jq .
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Health check
    Invoke-WebRequest -Uri "http://localhost:8080/health"

    # Risk classification (API-key mode; install jq separately, or use ConvertFrom-Json)
    curl.exe -s -X POST http://localhost:8080/v1/risk/classify `
      -H "x-api-key: $env:OPENCOMPLAI_API_KEY" `
      -H "Content-Type: application/json" `
      -d '{\"system_id\": \"my-model\", \"intended_purpose\": \"customer support chatbot\"}' | ConvertFrom-Json | ConvertTo-Json -Depth 10
    ```
