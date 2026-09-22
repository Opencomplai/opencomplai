# Configuration

All runtime configuration is provided through environment variables in `infra/compose/.env` (copied from `infra/compose/.env.example`).

## Environment variable reference

### PostgreSQL (required)

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_DB` | `opencomplai` | Database name. |
| `POSTGRES_USER` | `opencomplai` | Database user. |
| `POSTGRES_PASSWORD` | *(none — required)* | Database password. **The stack will not start without this.** |

### Gateway API

| Variable | Default | Description |
|---|---|---|
| `GATEWAY_PORT` | `8080` | Host port for the gateway API. Change if 8080 is in use. |

### Internal service auth (required)

| Variable | Default | Description |
|---|---|---|
| `INTERNAL_SERVICE_TOKEN_SECRET` | *(none — required)* | Shared secret for internal service-to-service authentication between evidence-vault, risk-engine, doc-generator, egress-proxy, and gateway-api. **The stack will not start without this** — docker compose fails closed via `${INTERNAL_SERVICE_TOKEN_SECRET:?...}` before any service starts. Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. |

### Egress proxy

| Variable | Default | Description |
|---|---|---|
| `EGRESS_ALLOWED_DESTINATIONS` | *(empty)* | Comma-separated list of allowed outbound destinations for metadata sync. Leave empty for fully air-gapped mode. Example: `https://dashboard.opencomplai.org` |

### Signing

| Variable | Default | Description |
|---|---|---|
| `LOCAL_SIGNING_KEY_PATH` | *(unset)* | Path to an Ed25519 signing key for signed status artifacts. Leave unset for unsigned OSS mode. |

### Risk engine — checker email delivery

The EU AI Act checker's "email a copy" feature posts to the risk engine's
`POST /v1/checker/email`. Every other part of the checker runs entirely in the
browser and needs none of this.

`OPENCOMPLAI_SMTP_HOST` is the switch: with it unset the endpoint returns
`503 MAILER_NOT_CONFIGURED` and nothing else in the stack is affected.

| Variable | Default | Description |
|---|---|---|
| `OPENCOMPLAI_SMTP_HOST` | *(unset)* | SMTP server hostname. **Required to enable email delivery** — unset means the feature is off, not broken. |
| `OPENCOMPLAI_SMTP_PORT` | `587` | SMTP port. |
| `OPENCOMPLAI_SMTP_USERNAME` | *(empty)* | SMTP username. When empty, no `LOGIN` is attempted — use for relays that authenticate by IP. |
| `OPENCOMPLAI_SMTP_PASSWORD` | *(empty)* | SMTP password. |
| `OPENCOMPLAI_SMTP_FROM_ADDRESS` | `noreply@opencomplai.com` | Envelope/From address. Set this to a domain you control, or your mail will fail SPF/DKIM. |
| `OPENCOMPLAI_SMTP_USE_TLS` | `true` | STARTTLS. Only set false for a trusted local relay. |
| `OPENCOMPLAI_TRUSTED_PROXY_HOPS` | `0` | Number of reverse proxies in front of the risk engine. The checker's per-IP rate limits read the Nth-from-last `X-Forwarded-For` entry. Default `0` trusts nothing and keys on the socket peer — raising it without an actual proxy in front lets clients spoof their way past the rate limit. |

Configuring SMTP is **not sufficient** to enable the button on the public docs
site. That also requires the browser to be allowed to reach the risk engine —
see [the checker email section](#eu-ai-act-checker-email-on-the-docs-site).

### Observability (Phase 15)

| Variable | Default | Description |
|---|---|---|
| `PROMETHEUS_HOST_PORT` | `9090` | Host port for the Prometheus UI. |
| `GRAFANA_HOST_PORT` | `3001` | Host port for the Grafana dashboards. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | *(unset)* | OpenTelemetry collector endpoint. Leave unset to disable trace export. |
| `OTEL_SERVICE_NAME` | *(unset)* | Service name reported to the OTel collector. |

## CLI environment variables

The `opencomplai` CLI also reads one environment variable:

| Variable | Description |
|---|---|
| `OPENCOMPLAI_API_URL` | When set, `opencomplai check` routes through the gateway API instead of running locally. Set to the gateway-api URL, e.g. `http://localhost:8080`. |
| `OPENCOMPLAI_OFFLINE` | Fail-closed network kill switch for the AI plugin. When set (`1`/`true`/`yes`/`on`), no code snippet is sent anywhere and no model is downloaded — operations that would need the network raise instead of degrading quietly. Overrides configuration and any recorded consent. |

### AI plugin data egress

The optional `opencomplai-ai` plugin classifies detected AI usage. **Every model
in the catalog except `saas` runs entirely on this machine and sends nothing.**

The `saas` backend posts code snippets to `https://api.opencomplai.com`. It is
gated three ways:

1. **Offline mode.** With `OPENCOMPLAI_OFFLINE` set it never runs, whatever else
   is configured.
2. **One-time consent.** `opencomplai ai configure --model saas` shows what
   would leave the machine and records an explicit opt-in in
   `~/.opencomplai/ai-config.yaml`. Without a current grant the backend sends
   nothing and reports why. Non-interactive runs are refused rather than
   defaulted in either direction.
3. **Redaction.** Snippets are scrubbed for secret- and PII-shaped content
   before transmission. This is a mitigation, **not a guarantee** — pattern
   matching cannot catch a credential that reads like ordinary text. For a
   regulated deployment the real control is `OPENCOMPLAI_OFFLINE=1` or a local
   model.

Model downloads are pinned to an immutable upstream revision and checksum-
verified where the catalog records one — on download **and** on every cache hit,
so a later local modification of a cached model is caught. An unpinned model is
refused outright when stdin is not interactive: unattended is exactly where an
upstream substitution would go unnoticed.

## EU AI Act checker email on the docs site

Enabling "email a copy" on a hosted docs site takes **three** independent
changes. Any one of them alone leaves the feature non-functional, so they are
listed together here:

1. **Give the risk engine an SMTP server** — see
   [Risk engine — checker email delivery](#risk-engine-checker-email-delivery)
   above. Without `OPENCOMPLAI_SMTP_HOST` the endpoint returns
   `503 MAILER_NOT_CONFIGURED`.

2. **Tell the widget where the risk engine is.** Set the origin in
   `docs/src/assets/js/checker-config.js`:

   ```js
   window.OCOC_RISK_ENGINE_URL = "https://api.example.com";
   ```

   While this is empty the widget **hides the email form** rather than showing a
   button that cannot work. The JSON, Markdown, and print exports are
   unaffected and need no backend.

3. **Allow the browser to reach that origin.** Add it to `connect-src` in the
   `Content-Security-Policy` header in `vercel.json`:

   ```
   connect-src 'self' https://api.example.com;
   ```

   Without this the browser blocks the request no matter what step 2 says.

There is no public risk-engine deployment today, so all three are deliberately
left unset and the email form does not render on the published docs.

When the docs are served from `localhost` (e.g. `mkdocs serve`), the widget
falls back to `http://localhost:8001` on the assumption that a developer is
running the stack locally. It does **not** do this on any other host — that
address would be the visitor's own machine.

## Minimum `.env` for a quickstart

```bash
POSTGRES_PASSWORD=use_a_strong_random_password_here
INTERNAL_SERVICE_TOKEN_SECRET=use_a_strong_random_secret_here
```

These two are fail-closed with no default — the stack will not start without
them. All other variables have safe defaults.
