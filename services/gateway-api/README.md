# gateway-api

The REST gateway for the Opencomplai service stack, written in TypeScript on Fastify. It is the
**only application service that publishes a port to the host** in the Docker Compose stack (the
stack also publishes Prometheus and Grafana, on 9090 and 3001 by default). The other four
services (`risk-engine`, `evidence-vault`, `doc-generator`, `egress-proxy`) sit on an internal
network behind it, and clients reach them through its `/v1/*` routes.

What it does on each request:

1. Authenticates the caller (API key or OIDC JWT) and applies rate limits.
2. Resolves the caller's tenant and forwards it downstream as `X-Tenant-Id`.
3. Mints a short-lived signed service token from `INTERNAL_SERVICE_TOKEN_SECRET` and forwards
   the request to the owning service.

| Gateway route | Forwarded to |
|---|---|
| `/v1/manifests/validate`, `/v1/risk/classify`, `/v1/verify/claims`, `/v1/hitl/*` | risk-engine |
| `/v1/evidence/*`, `/v1/portfolio`, `/v1/pro/badges/*` | evidence-vault |
| `/v1/docs/*` | doc-generator |
| `/v1/sync/metadata`, `/v1/pro/ingest/*` | egress-proxy |
| `/health`, `/v1/status` | answered by the gateway itself |

The full request and response contract is in [`openapi.yaml`](openapi.yaml) and the
[REST API reference](../../docs/src/api/rest-api.md).

## Run locally

Requires Node.js 24 and pnpm 9. The package is part of the repo's pnpm workspace, so install from
the repo root:

```bash
pnpm install
cd services/gateway-api
OPENCOMPLAI_AUTH_DISABLED=1 pnpm dev      # tsx watch src/server.ts, listens on :8080
```

On PowerShell set variables with `$env:NAME = "value"`. The default downstream addresses are the
Compose hostnames, so to talk to services you started on your own machine, point the `*_URL`
variables below at `http://localhost:<port>`. Use the same `INTERNAL_SERVICE_TOKEN_SECRET` for the
gateway and every service it calls. To run the whole stack instead, see
[Deployment quickstart](../../docs/src/deployment/quickstart.md).

Build and run the compiled output with `pnpm build` then `pnpm start`.

## Tests

CI (`.github/workflows/ci-node.yml`) runs these from `services/gateway-api`:

```bash
pnpm lint
pnpm format:check
pnpm exec tsc --noEmit
pnpm test            # vitest run, src/tests/**/*.test.ts
pnpm build
```

## Configuration

All configuration is read from environment variables.

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8080` | Listen port. |
| `HOST` | `0.0.0.0` | Listen address. |
| `NODE_ENV` | unset | Request logging is switched off when set to `test`. |

**Authentication** (see [Authentication Configuration](../../docs/src/deployment/authentication.md)).
The process exits at startup unless at least one mode is configured: OIDC, an API key, or
`OPENCOMPLAI_AUTH_DISABLED=1`. If more than one is set, OIDC takes priority over the API key, and
either one overrides `OPENCOMPLAI_AUTH_DISABLED`.

| Variable | Default | Purpose |
|---|---|---|
| `OPENCOMPLAI_API_KEY` | unset | API-key mode. Callers send it in the `x-api-key` header. Required unless OIDC or `OPENCOMPLAI_AUTH_DISABLED=1` is used. |
| `OPENCOMPLAI_API_KEY_TENANT_ID` | `oss-default` | Tenant that every API-key caller maps to. |
| `OIDC_JWKS_URI` | unset | Enables OIDC mode and takes priority over the API key. Callers send `Authorization: Bearer <jwt>`; RS256 only. |
| `OIDC_ISSUER` | unset | Required when `OIDC_JWKS_URI` is set. |
| `OIDC_AUDIENCE` | unset | Required when `OIDC_JWKS_URI` is set. |
| `OIDC_TENANT_CLAIM` | unset | Required when `OIDC_JWKS_URI` is set. Name of the JWT claim that carries the tenant id. |
| `OIDC_CLOCK_TOLERANCE_SEC` | `5` | Clock skew allowed on `exp` and `nbf`. |
| `OPENCOMPLAI_AUTH_DISABLED` | unset | Set to `1` to run with no authentication. Local development only. |
| `OPENCOMPLAI_RATE_LIMIT_MAX` | `300` | Requests per client per window. |
| `OPENCOMPLAI_RATE_LIMIT_WINDOW_MS` | `60000` | Rate-limit window. |
| `OPENCOMPLAI_AUTH_FAILURE_RATE_LIMIT_MAX` | `10` | Failed authentications per client per window before a 429. |
| `OPENCOMPLAI_AUTH_FAILURE_RATE_LIMIT_WINDOW_MS` | `60000` | Window for the failure budget. |

**Downstream services.**

| Variable | Default | Purpose |
|---|---|---|
| `INTERNAL_SERVICE_TOKEN_SECRET` | unset | Shared secret used to sign the service token sent to every downstream service. The gateway starts without it, but each downstream `/v1/*` route then rejects the call, so treat it as required. Must match the services' value. |
| `RISK_ENGINE_URL` | `http://risk-engine:8001` | risk-engine base URL. |
| `EVIDENCE_VAULT_URL` | `http://evidence-vault:8002` | evidence-vault base URL. |
| `DOC_GENERATOR_URL` | `http://doc-generator:8003` | doc-generator base URL. |
| `EGRESS_PROXY_URL` | `http://egress-proxy:8004` | egress-proxy base URL. |
| `STATUS_CHECK_TIMEOUT_MS` | `2000` | Per-downstream probe timeout for `/v1/status`. |
| `STATUS_CACHE_TTL_MS` | `5000` | How long a `/v1/status` result is reused. |

**Telemetry** (optional; a silent no-op when the `@opentelemetry/*` packages are not installed).

| Variable | Default | Purpose |
|---|---|---|
| `OTEL_SERVICE_NAME` | `gateway-api` | Service name on emitted telemetry. |
| `PROMETHEUS_METRICS_PORT` | `9464` | Separate port that serves Prometheus metrics. |

## Health

| Endpoint | Auth | Answers |
|---|---|---|
| `GET /health` | none | The gateway process is alive: `{"status":"ok","service":"gateway-api","version":"0.9.0"}`. Contacts nothing. Use for liveness and the Compose healthcheck. |
| `GET /v1/status` | required | Probes all four downstream services and reports each. Returns 200 even when degraded; add `?strict=1` to get 503 instead. |

See [Observability](../../docs/src/deployment/observability.md) for how to monitor these.

## Other entry points

`api/gateway/[...path].ts` at the repo root mounts this same app as a Vercel function. Its tests run
with `pnpm exec tsx --test ../../api/gateway/_lib/rewriteUrl.test.ts ../../api/gateway/handler.test.ts`.
