# egress-proxy

The outbound-traffic enforcer, written in Python on FastAPI. In the Docker Compose stack it is the
**only application service attached to the `external` network**. risk-engine, evidence-vault,
doc-generator and the data stores sit on the `internal` network only, which Compose marks
`internal: true`, so they have no route to the internet. The isolation is not total: gateway-api,
Prometheus and Grafana are also attached to the `frontend` network, an ordinary bridge network
that is not internal, so Compose does not cut them off (gateway-api fetches the OIDC JWKS itself
when OIDC is configured). Metadata that is meant to leave the deployment goes through this
service, and it fails closed: a forbidden field or a destination that is not allowlisted is
blocked, and nothing is sent.

It is an **internal service**. It has no host port and is reached through
[gateway-api](../gateway-api/README.md).

Two allowlists apply to `POST /v1/sync/metadata`:

- **Payload fields.** Only the fields in `ALLOWED_FIELDS` in
  [`allowlist.py`](src/opencomplai_egress_proxy/allowlist.py) may appear in the payload. Any other
  key blocks the request.
- **Destinations.** The configured destination URL must start with one of the prefixes in
  `EGRESS_ALLOWLIST`. An empty list blocks every destination.

A blocked request answers 403 `EGRESS_BLOCKED` and appends an `egress_blocked` event to the
[evidence-vault](../evidence-vault/README.md) ledger (best effort), carrying a hash of the policy
that was in force.

If `PRO_DASHBOARD_URL` is set and passes the destination check, the validated payload is posted to
`{PRO_DASHBOARD_URL}/ingest/metadata`. If it is unset, nothing is sent: the proxy validates the
payload and answers `{"status": "synced", "destination": null, ...}`.

## Endpoints

| Route | Auth | Purpose |
|---|---|---|
| `GET /egress-health` | none | Liveness of this service: `{"status":"ok","service":"egress-proxy"}`. Contacts nothing. Used by the Docker healthcheck and by gateway-api's `/v1/status`. |
| `GET /health` | none | Proxies `GET /health` on `GATEWAY_API_URL`. Answers 503 `degraded` when the gateway is unreachable, so it does not report this service's own state. |
| `GET /metrics` | none | Prometheus metrics. |
| `POST /v1/sync/metadata` | service token | Validate and forward a metadata sync payload, as described above. |
| `POST /v1/pro/ingest/{sub_path}` | service token | Forward Pro ingest payloads (`status-artifact`, `dossier-metadata`, `metrics`) to evidence-vault, relaying `X-Tenant-Id`. Internal traffic, so the field allowlist is not applied. |
| any other path | service token | Forwarded to gateway-api. Internal traffic, so no allowlist is applied. |

Every route other than the three marked "none" requires a signed internal service token
(HMAC-SHA256 over `INTERNAL_SERVICE_TOKEN_SECRET`). With the secret unset those routes answer 503.

## Run locally

From the repo root, with [uv](https://github.com/astral-sh/uv) and Python 3.11:

```bash
uv sync --all-packages
export INTERNAL_SERVICE_TOKEN_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export EVIDENCE_VAULT_URL=http://localhost:8002
export GATEWAY_API_URL=http://localhost:8080
uv run uvicorn opencomplai_egress_proxy.main:app --port 8004
curl http://localhost:8004/egress-health
```

To run the whole stack instead, see [Deployment quickstart](../../docs/src/deployment/quickstart.md).

## Tests

```bash
uv run pytest services/egress-proxy -v --tb=short
```

CI runs this in the `test-services` job of `.github/workflows/ci-python.yml`. The `python-checks`
job also runs the data-loss-prevention suite on its own, `services/egress-proxy/tests/test_dlp.py`,
and asserts that known-forbidden fields are rejected by `validate_payload`.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `INTERNAL_SERVICE_TOKEN_SECRET` | unset | **Required.** Verifies inbound service tokens and signs the tokens sent to evidence-vault. Must match the other services. |
| `EGRESS_ALLOWLIST` | empty | Allowed destination URL prefixes, **one per line**. Empty blocks all outbound destinations. |
| `PRO_DASHBOARD_URL` | empty | Destination for `POST /v1/sync/metadata`. Read on each request. Empty means no outbound call is made. |
| `EVIDENCE_VAULT_URL` | `http://evidence-vault:8002` | Target of `/v1/pro/ingest/*` and of the `egress_blocked` ledger events. |
| `GATEWAY_API_URL` | `http://gateway-api:8080` | Target of `GET /health` and of the catch-all forwarding. |
| `OTEL_SERVICE_NAME` | `egress-proxy` | Overrides the service name on telemetry. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | gRPC OTLP endpoint for traces; export is off when unset. |

The allowlist is read from `EGRESS_ALLOWLIST`. The Compose file instead passes the destinations as
`ALLOWED_DESTINATIONS` (filled from `EGRESS_ALLOWED_DESTINATIONS` in `.env`), a name this service
does not read, so a destination set that way does not reach the allowlist. The service also does
not read `PORT`, which the Compose file sets; the listen port is the `--port 8004` in the image's
command. Compose does not set `PRO_DASHBOARD_URL` either.

See [Air-gap](../../docs/src/deployment/airgap.md) for running with no outbound access,
[Configuration](../../docs/src/deployment/configuration.md) for the stack-wide variables, and
[Observability](../../docs/src/deployment/observability.md) for metrics.

## Docker

Built by `infra/docker/egress-proxy.Dockerfile`; the image listens on port 8004 and its healthcheck
calls `/egress-health`.
