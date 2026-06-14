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

### Egress proxy

| Variable | Default | Description |
|---|---|---|
| `EGRESS_ALLOWED_DESTINATIONS` | *(empty)* | Comma-separated list of allowed outbound destinations for metadata sync. Leave empty for fully air-gapped mode. Example: `https://dashboard.opencomplai.org` |

### Signing

| Variable | Default | Description |
|---|---|---|
| `LOCAL_SIGNING_KEY_PATH` | *(unset)* | Path to an Ed25519 signing key for signed status artifacts. Leave unset for unsigned OSS mode. |

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

## Minimum `.env` for a quickstart

```bash
POSTGRES_PASSWORD=use_a_strong_random_password_here
```

All other variables have safe defaults.
