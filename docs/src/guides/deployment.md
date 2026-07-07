# Deployment Guide

> This page covers production deployment considerations. For the quickstart, see [Deployment Quickstart](../deployment/quickstart.md).

## Deployment options

| Mode | Requirements | When to use |
|---|---|---|
| **Local CLI** | Python 3.11+, no Docker | Development, CI pipelines |
| **Docker Compose** | Docker 24+, 2 GB RAM | Single-machine deployments, staging |
| **Air-gap** | Docker Compose + no internet | Regulated environments, on-prem |

## Environment variables

All runtime configuration is in `infra/compose/.env`. See [Configuration](../deployment/configuration.md) for the full reference.

**Minimum required:**

```bash
POSTGRES_PASSWORD=use_a_strong_random_password
```

## Production checklist

- [ ] `POSTGRES_PASSWORD` is a strong random value, not the default.
- [ ] `.env` is not committed to version control.
- [ ] `EGRESS_ALLOWED_DESTINATIONS` is set to only the destinations you need.
- [ ] Signing key is backed up securely (or use a managed KMS).
- [ ] Prometheus and Grafana ports (`9090`, `3000`) are not exposed to the public internet.
- [ ] Docker Compose is pinned to specific image tags (replace `:latest` with version tags for stability).
- [ ] `docker compose health` shows all services healthy before routing traffic.

## Health checking

=== "macOS / Linux"
    ```bash
    curl http://localhost:8080/health
    # {"status":"ok","service":"gateway-api","version":"0.1.0-dev"}
    ```

=== "Windows (PowerShell)"
    ```powershell
    Invoke-WebRequest -Uri "http://localhost:8080/health"
    # {"status":"ok","service":"gateway-api","version":"0.1.0-dev"}
    ```

All services expose a `/health` endpoint for load balancer or monitoring integration.

## Air-gap deployment

See [Air-gap Deployment](../deployment/airgap.md) for the full guide, including image pre-pull and tarball transfer procedure.

## Observability

Prometheus scrapes metrics from all services; Grafana dashboards are pre-configured. Access:

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (or `GRAFANA_HOST_PORT` from `.env`)

Metrics are counters and histograms only — no payload sampling, no PII in metric labels.
