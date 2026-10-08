# risk-engine

Risk classification and human-oversight service, written in Python on FastAPI. It wraps the
deterministic rule engine in `opencomplai-core` behind HTTP: the same input always produces the same
classification. It also runs the pipeline evaluators, resolves verification claims, and manages the
human-in-the-loop (HITL) review queue.

It is an **internal service**. In the Docker Compose stack it has no host port and is called by
[gateway-api](../gateway-api/README.md), the only application service the stack publishes to the
host. risk-engine keeps no database of its own; HITL queue items, override records and cached eval
results are stored through [evidence-vault](../evidence-vault/README.md).

## Endpoints

| Route | Auth | Purpose |
|---|---|---|
| `GET /health` | none | Liveness: `{"status":"ok","service":"risk-engine"}`. |
| `GET /metrics` | none | Prometheus metrics. |
| `POST /v1/manifests/validate` | service token | Validate a system manifest, including its framework ids. |
| `POST /v1/risk/classify` | service token | Classify a system's risk tier. |
| `POST /v1/verify/claims` | service token | Resolve a verification claim to one terminal outcome. |
| `POST /v1/evals/run` | service token | Run the safety, bias and data-leakage evaluators. |
| `POST /v1/hitl/overrides`, `/v1/hitl/queue...` | service token | Submit overrides; list, assign and decide review items. |
| `POST /v1/controls/reassess` | service token | Detect stale controls and enqueue one review item per newly stale control. |
| `/v1/checker/evaluate`, `/help`, `/export`, `/email` | none | EU AI Act applicability checker used by the docs-site widget. Per-IP rate limited; CORS is limited to the docs origins. |

Every other `/v1/*` route requires a signed internal service token (HMAC-SHA256 over
`INTERNAL_SERVICE_TOKEN_SECRET`). With the secret unset those routes answer 503 rather than run
unauthenticated. There is no auth-disabled bypass.

## Run locally

From the repo root, with [uv](https://github.com/astral-sh/uv) and Python 3.11:

```bash
uv sync --all-packages
export INTERNAL_SERVICE_TOKEN_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uv run uvicorn opencomplai_risk_engine.main:app --port 8001
curl http://localhost:8001/health
```

The listen port is set by uvicorn's `--port`. To exercise the HITL and eval routes, also run
evidence-vault and point `EVIDENCE_VAULT_URL` at it; otherwise those calls fail. To run the whole
stack instead, see [Deployment quickstart](../../docs/src/deployment/quickstart.md).

## Tests

```bash
uv run pytest services/risk-engine -v --tb=short
```

CI runs this together with the other three Python services in the `test-services` job of
`.github/workflows/ci-python.yml`. Tests set their own service-token secret.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `INTERNAL_SERVICE_TOKEN_SECRET` | unset | **Required.** Shared secret that verifies inbound service tokens and signs the tokens this service sends to evidence-vault. Must match the other services. |
| `TENANT_ID` | `default` | Tenant id sent as `X-Tenant-Id` on every call to evidence-vault. risk-engine is single-tenant per deployment and does not read the tenant from the inbound request. |
| `EVIDENCE_VAULT_URL` | `http://evidence-vault:8002` | Where HITL, eval and control state is persisted. |
| `EGRESS_PROXY_URL` | `http://egress-proxy:8004` | Used by `/v1/verify/claims` when a claim's source is an `http://` or `https://` URL. |
| `REVIEWER_GROUP_MAP` | `{"default": "compliance-reviewers"}` | JSON object mapping a `system_id` to the reviewer group its review items are assigned to. The `default` key is the fallback. |
| `PORT` | `8001` | Read into a module constant but not used to bind; set the port with uvicorn's `--port`. |
| `OPENCOMPLAI_DOCS_ORIGINS` | `https://docs.opencomplai.com,http://localhost:8000,http://127.0.0.1:8000` | Comma-separated origins allowed by CORS on `/v1/checker/*`. |
| `OPENCOMPLAI_TRUSTED_PROXY_HOPS` | `0` | Trusted reverse-proxy hops in front of the service, for the checker's per-IP rate limit. Leave at `0` unless a proxy really sits in front. |
| `OPENCOMPLAI_SMTP_HOST` | unset | Enables the checker's "email a copy" endpoint. Unset means `/v1/checker/email` answers 503. |
| `OPENCOMPLAI_SMTP_PORT` | `587` | SMTP port. |
| `OPENCOMPLAI_SMTP_USERNAME` | empty | SMTP username; when empty no login is attempted. |
| `OPENCOMPLAI_SMTP_PASSWORD` | empty | SMTP password. |
| `OPENCOMPLAI_SMTP_FROM_ADDRESS` | `noreply@opencomplai.com` | From address. |
| `OPENCOMPLAI_SMTP_USE_TLS` | `true` | Use STARTTLS. |
| `OTEL_SERVICE_NAME` | `risk-engine` | Overrides the service name on telemetry. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | gRPC OTLP endpoint for traces; export is off when unset. |

The SMTP variables are explained further in [Configuration](../../docs/src/deployment/configuration.md).

## Docker

Built by `infra/docker/risk-engine.Dockerfile`; the image listens on port 8001 and its healthcheck
calls `/health`. Metrics and telemetry are covered in [Observability](../../docs/src/deployment/observability.md).
