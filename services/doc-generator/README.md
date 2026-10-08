# doc-generator

Annex IV technical-documentation service, written in Python on FastAPI. It turns a system's
manifest and risk assessment into an EU AI Act Annex IV dossier using the generator in
`opencomplai-core`, then stores the result in [evidence-vault](../evidence-vault/README.md) so it
can be retrieved later.

It is an **internal service**. In the Docker Compose stack it has no host port and is reached
through [gateway-api](../gateway-api/README.md). doc-generator keeps no state of its own.

On `POST /v1/docs/generate` it:

1. Builds the dossier and validates it against the Annex IV schema.
2. Writes the dossier JSON to the evidence-vault CAS, appends a `dossier_generated` ledger event,
   and records an index row, so `GET /v1/docs/{dossier_id}` and `GET /v1/docs?system_id=...` can
   find it. If evidence-vault answers any of those writes with an error status, the request
   answers 502 with an `error_code` naming the step. If evidence-vault cannot be reached at all,
   the request answers 500 `SYSTEM_ERROR`.
3. Fails closed: a dossier that does not pass schema validation is still stored, but the request
   answers 422 unless the body sets `allow_incomplete` to `true`.

The dossier is anchored to the vault's current ledger root. That lookup is best-effort: if the
vault cannot be reached, the dossier is produced without the anchor.

## Endpoints

| Route | Auth | Purpose |
|---|---|---|
| `GET /health` | none | Liveness: `{"status":"ok","service":"doc-generator"}`. |
| `GET /metrics` | none | Prometheus metrics. |
| `POST /v1/docs/generate` | service token | Generate and store a dossier. |
| `GET /v1/docs/{dossier_id}` | service token | Fetch a stored dossier with its index metadata. |
| `GET /v1/docs?system_id=...` | service token | List the dossiers stored for a system. |

Every `/v1/*` route requires a signed internal service token (HMAC-SHA256 over
`INTERNAL_SERVICE_TOKEN_SECRET`). With the secret unset those routes answer 503.

## Run locally

From the repo root, with [uv](https://github.com/astral-sh/uv) and Python 3.11:

```bash
uv sync --all-packages
export INTERNAL_SERVICE_TOKEN_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export EVIDENCE_VAULT_URL=http://localhost:8002
uv run uvicorn opencomplai_doc_generator.main:app --port 8003
curl http://localhost:8003/health
```

Generating a dossier needs a running evidence-vault that shares the same
`INTERNAL_SERVICE_TOKEN_SECRET`. To run the whole stack instead, see
[Deployment quickstart](../../docs/src/deployment/quickstart.md).

## Tests

```bash
uv run pytest services/doc-generator -v --tb=short
```

CI runs this together with the other three Python services in the `test-services` job of
`.github/workflows/ci-python.yml`. Tests set their own service-token secret.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `INTERNAL_SERVICE_TOKEN_SECRET` | unset | **Required.** Verifies inbound service tokens and signs the tokens sent to evidence-vault. Must match the other services. |
| `EVIDENCE_VAULT_URL` | `http://evidence-vault:8002` | Where dossiers are stored and read back. |
| `DOSSIER_SIGNING_KEY_PATH` | unset | Path to an Ed25519 PEM private key. When set, dossiers are signed with it. |
| `SIGNING_KEY_PRIVATE` | unset | Base64-encoded PEM private key. When set it signs dossiers and takes precedence over the file at `DOSSIER_SIGNING_KEY_PATH`; either variable alone enables Ed25519 signing. |
| `LOCAL_SIGNING_KEY_PATH` | unset | Ignored: it signs nothing. Dossiers are signed only with an Ed25519 key (`DOSSIER_SIGNING_KEY_PATH` or `SIGNING_KEY_PRIVATE`) and are otherwise unsigned; with only this variable set, generation warns and the dossier is unsigned. |
| `LOG_RETENTION_DAYS` | n/a | Not read. The record-keeping section of the dossier holds only what the manifest's `record_keeping` block declares. |
| `OTEL_SERVICE_NAME` | `doc-generator` | Overrides the service name on telemetry. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | gRPC OTLP endpoint for traces; export is off when unset. |

The tenant is not configured here. The service relays the caller's `X-Tenant-Id` header to
evidence-vault, defaulting to `oss-default` when it is absent. The Compose file also sets `PORT`;
the code does not read it, and the listen port is the `--port 8003` in the image's command.

See [Configuration](../../docs/src/deployment/configuration.md) for the stack-wide variables and
[Observability](../../docs/src/deployment/observability.md) for metrics.

## Docker

Built by `infra/docker/doc-generator.Dockerfile`; the image listens on port 8003 and its
healthcheck calls `/health`.
