# Observability Setup

**Compliance mapping:** ISO 27001 A.8.16 · SOC 2 CC7.2 · NIST DE.CM · FedRAMP AU-6/SI-4

---

## Overview

Opencomplai emits OpenTelemetry (OTel) traces and Prometheus metrics from every service. The Docker Compose stack bundles a full observability pipeline:

| Component | Role |
|---|---|
| `otel-collector` | Receives OTLP from all services; exports metrics to Prometheus |
| `prometheus` | Stores time-series metrics; scraped by Grafana |
| `grafana` | Visualises metrics; hosts the Opencomplai compliance health dashboard |

---

## Logs

The Python services write logs to standard output as one JSON object per line. Each line carries `ts`, `level`, `logger`, `service`, `msg` and, for logged exceptions, `exc_info`. `trace_id` appears only when an OpenTelemetry span is active, for example with external OpenTelemetry instrumentation, so you can match a log line to its trace. `OTEL_SERVICE_NAME` sets the `service` field. uvicorn's own startup and access lines keep its plain-text format.

### Configuration

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Log level name (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`, case-insensitive) or number. An unrecognised value falls back to `INFO` and logs a warning. |

---

## Quick Start

1. Copy the env template and enable OTel:

   ```bash
   cp infra/compose/.env.example infra/compose/.env
   # OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_SERVICE_NAME are enabled by default
   ```

2. Start the stack:

   ```bash
   docker compose -f infra/compose/docker-compose.yml up -d
   ```

3. Open Grafana at `http://localhost:3001`. Anonymous Viewer access is on, so no login is
   needed to see the dashboards. Grafana and Prometheus listen on this machine's loopback
   only by default; see [Network exposure](#network-exposure).

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | gRPC OTLP endpoint for trace/metric export |
| `OTEL_SERVICE_NAME` | `opencomplai` | Service name tag on all telemetry |
| `OBSERVABILITY_BIND_ADDR` | `127.0.0.1` | Host address the Prometheus and Grafana ports are published on. Loopback by default; `0.0.0.0` publishes on every IPv4 interface and `::` is the IPv6 equivalent (see [Network exposure](#network-exposure)) |
| `PROMETHEUS_HOST_PORT` | `9090` | Host port for Prometheus UI |
| `GRAFANA_HOST_PORT` | `3001` | Host port for Grafana UI |

Leave `OTEL_EXPORTER_OTLP_ENDPOINT` unset to disable trace export. Prometheus metrics are always exposed via each service's `/metrics` endpoint regardless.

### Network exposure

Prometheus and Grafana are operator tools, not part of the API surface, so their host
ports are published on `127.0.0.1` unless you say otherwise. From the Docker host
`http://localhost:3001` and `http://localhost:9090` work as usual; other machines cannot
reach them (see the Docker Engine note below). The gateway (`GATEWAY_PORT`) is unaffected:
it is the stack's entry point and stays published on all interfaces behind its own
authentication.

To reach them from other hosts, set `OBSERVABILITY_BIND_ADDR=0.0.0.0` in `infra/compose/.env`
(every IPv4 interface; `::` is the IPv6 equivalent) or the address of a single interface,
and recreate the containers. The setting covers both ports.

!!! note "Docker Engine on Linux"
    Docker Engine releases before 28.0 may let other hosts on the same network segment
    reach ports published on `127.0.0.1`; 28.0 added a filter for this. If you run an
    older engine on Linux, also block the Prometheus and Grafana ports with a host
    firewall.

!!! warning "Before you expose Grafana or Prometheus"
    - Grafana runs with **anonymous Viewer access enabled**, and its admin login is the stock
      `admin` / `admin`. Change the admin password (sign in, then profile → change
      password) before binding it to anything other than loopback.
    - Prometheus has **no authentication at all**. If other hosts need it, restrict access with
      a firewall or put it behind an authenticating reverse proxy.

---

## Instrumented Events

All services emit the following canonical events (PRD Section 11.1):

| Event | Metric Counter | Meaning |
|---|---|---|
| `compliance_check_started` | `opencomplai_compliance_check_started_total` | A compliance scan was initiated |
| `compliance_check_completed` | `opencomplai_compliance_check_completed_total` | A compliance scan finished (with `status` label) |
| `trap_detected` | `opencomplai_trap_detected_total` | Substantial modification trap fired |
| `override_submitted` | `opencomplai_override_submitted_total` | Break-glass / HITL override submitted |
| `verification_failed` | `opencomplai_verification_failed_total` | Claim verification or auth failure |
| `dossier_generated` | `opencomplai_dossier_generated_total` | Annex IV dossier produced |
| `egress_blocked` | `opencomplai_egress_blocked_total` | Outbound request blocked by egress-proxy |
| `badge_issued` | `opencomplai_badge_issued_total` | Compliance badge issued |

---

## Grafana Dashboard Panels

The provisioned `Opencomplai — Compliance Health` dashboard includes:

- **Time to first scan (P95 ms)** — latency gauge
- **Control pass rate** — percentage of scans that pass all controls
- **Trap detection frequency** — rate of `trap_detected` events by system
- **Override rate** — rate of `override_submitted` events
- **Egress blocked events** — total `EGRESS_BLOCKED` count (red alert threshold: ≥10)
- **BREAK_GLASS_ACTIVATED count** — total override activations (red alert threshold: ≥1)
- **Audit Events Rate** — rate of audit events entering the ledger
- **Auth Failure Rate** — rate of verification/auth failures (brute-force indicator)

---

## Health Endpoints

Three distinct endpoints answer three different questions. Pointing a monitor at
the wrong one is the most common way to get misleading signals here.

| Endpoint | Auth | Answers | Use for |
|---|---|---|---|
| `GET /health` (gateway-api) | none | Is the gateway process alive? Contacts nothing. | Kubernetes liveness/readiness, load-balancer checks |
| `GET /v1/status` | required | Is the *system* healthy? Probes every downstream. | Status pages, dashboards, human diagnosis |
| `GET /metrics` (each service) | none | Prometheus time series | Scraping |

### `GET /v1/status`

Probes `risk-engine`, `evidence-vault`, `doc-generator`, and `egress-proxy`
concurrently and reports each one. Results are cached briefly
(`STATUS_CACHE_TTL_MS`, default 5000) so polling does not fan out to the
backend on every request.

```json
{
  "status": "degraded",
  "service": "gateway-api",
  "version": "0.9.1",
  "checked_at": "2026-07-30T20:35:00Z",
  "services": {
    "risk-engine":    { "status": "ok", "latency_ms": 12 },
    "evidence-vault": { "status": "ok", "latency_ms": 9 },
    "doc-generator":  { "status": "unreachable", "latency_ms": 2000, "reason": "timeout" },
    "egress-proxy":   { "status": "ok", "latency_ms": 7 }
  }
}
```

Per-service `status` is one of `ok`, `degraded` (answered, but reported itself
unhealthy), or `unreachable` (no answer). `reason` is one of `timeout`,
`connection_error`, or `http_error`. A service entry carries a `version` only
when that service's health response includes one; the four internal services'
health responses currently do not, so none appears above.

**Monitor this URL, with the `strict` flag:**

```
GET /v1/status?strict=1
```

By default `/v1/status` returns **200 even when degraded** — the request
succeeded and the body is an accurate answer, and many clients discard the body
of a non-2xx response, which would throw away the per-service detail exactly
when it matters. `?strict=1` returns **503 whenever anything is not `ok`**, so a
monitor that only inspects the status code still sees the problem. The body is
identical either way.

The failure mode of the default is silent green: a monitor configured *without*
`?strict=1` reports healthy while the system is degraded. Use the strict URL for
automated monitoring and the plain URL for dashboards that render the detail.

!!! warning "Do not use `/v1/status` as a liveness probe"
    It reflects downstream state, so a single dead backend would restart a
    perfectly healthy gateway. Liveness is `GET /health`, which contacts nothing.

| Variable | Default | Description |
|---|---|---|
| `STATUS_CHECK_TIMEOUT_MS` | `2000` | Per-downstream probe timeout. Probes run concurrently, so this bounds the whole request. |
| `STATUS_CACHE_TTL_MS` | `5000` | How long an aggregate result is reused before re-probing. |

---

## Alert Routing

For production deployments, configure alert routing in Grafana or your SIEM:

| Alert | Threshold | Response |
|---|---|---|
| `EGRESS_BLOCKED` ≥ 10 in 5 min | High | Investigate potential exfiltration |
| `BREAK_GLASS_ACTIVATED` ≥ 1 | Critical | Verify HITL approval exists |
| Auth failures > 5/min | High | Potential brute-force — review source IP |
| Compliance check error rate > 5% | Medium | Service degradation — check service health |

---

## Air-Gapped Deployments

In air-gapped environments where OTel export is not possible:

1. Leave `OTEL_EXPORTER_OTLP_ENDPOINT` unset.
2. Prometheus still scrapes each service's `/metrics` endpoint directly.
3. Traces are emitted locally but not forwarded to the collector.

See [Air-Gap Deployment](airgap.md) for full configuration.
