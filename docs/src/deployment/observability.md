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

3. Open Grafana at `http://localhost:3001` (default credentials: anonymous viewer).

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | gRPC OTLP endpoint for trace/metric export |
| `OTEL_SERVICE_NAME` | `opencomplai` | Service name tag on all telemetry |
| `PROMETHEUS_HOST_PORT` | `9090` | Host port for Prometheus UI |
| `GRAFANA_HOST_PORT` | `3001` | Host port for Grafana UI |

Leave `OTEL_EXPORTER_OTLP_ENDPOINT` unset to disable trace export. Prometheus metrics are always exposed via each service's `/metrics` endpoint regardless.

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
