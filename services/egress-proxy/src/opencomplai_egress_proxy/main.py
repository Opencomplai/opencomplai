"""
Opencomplai egress-proxy service.

The only component allowed to make outbound network calls. Enforces:
  - Payload allowlist: only PRD §4.2 metadata fields pass through.
  - Destination allowlist: only configured URL prefixes are forwarded to.
  - Fail-closed: any violation blocks the request and emits an EGRESS_BLOCKED
    ledger event (REQ-ARC-001).
"""

from __future__ import annotations

import json
import os
import urllib.request

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from opencomplai_core.telemetry import configure_telemetry, metrics_response

from opencomplai_egress_proxy.allowlist import (
    compute_policy_hash,
    validate_destination,
    validate_payload,
)

try:
    from prometheus_client import Counter as _Counter

    _EGRESS_BLOCKED = _Counter(
        "opencomplai_egress_blocked_total",
        "Egress requests blocked by allowlist policy",
        ["destination"],
    )
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False

app = FastAPI(
    title="Opencomplai Egress Proxy",
    description=(
        "Allowlisted outbound traffic enforcer. No other service in the Docker Compose "
        "deployment has outbound network access. Implements REQ-ARC-001."
    ),
    version="0.1.0-dev",
)

configure_telemetry("egress-proxy")

GATEWAY_API_URL = os.environ.get("GATEWAY_API_URL", "http://gateway-api:8080")
EVIDENCE_VAULT_URL = os.environ.get("EVIDENCE_VAULT_URL", "http://evidence-vault:8002")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _emit_egress_blocked(
    field_name: str,
    destination: str,
    severity: str = "high",
) -> str | None:
    """
    Emit an EGRESS_BLOCKED ledger event to the Evidence Vault (non-blocking).

    Returns event_id or None if the vault is temporarily unavailable.
    """
    body = json.dumps(
        {
            "event_type": "egress_blocked",
            "payload": {
                "policy_hash": compute_policy_hash(),
                "field_name": field_name,
                "destination": destination,
                "severity": severity,
            },
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{EVIDENCE_VAULT_URL}/v1/evidence/events",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read()).get("event_id")
    except Exception:
        return None  # non-blocking; vault unavailability is logged separately


def _blocked_response(field_name: str, destination: str) -> JSONResponse:
    _emit_egress_blocked(field_name=field_name, destination=destination)
    if _METRICS_AVAILABLE:
        _EGRESS_BLOCKED.labels(destination=destination or "unknown").inc()
    return JSONResponse(
        status_code=403,
        content={
            "error_code": "EGRESS_BLOCKED",
            "message": (
                f"Egress blocked: field '{field_name}' or destination '{destination}' "
                "is not in the allowlist."
            ),
            "category": "policy",
            "retryable": False,
            "policy_hash": compute_policy_hash(),
        },
    )


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------


@app.get("/egress-health")
async def egress_health() -> dict:
    return {"status": "ok", "service": "egress-proxy"}


@app.get("/metrics")
async def metrics():
    """Prometheus text-format metrics for this service."""
    response = metrics_response()
    if response is None:
        raise HTTPException(status_code=503, detail="prometheus_client not installed")
    return response


@app.api_route("/health", methods=["GET"])
async def gateway_health() -> Response:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{GATEWAY_API_URL}/health")
            return Response(
                content=r.content,
                status_code=r.status_code,
                media_type=r.headers.get("content-type"),
            )
    except Exception:
        return JSONResponse(
            status_code=503, content={"status": "degraded", "service": "egress-proxy"}
        )


# ---------------------------------------------------------------------------
# Sync metadata endpoint (REQ-ARC-001 — DLP enforcement)
# ---------------------------------------------------------------------------


@app.post("/v1/sync/metadata")
async def sync_metadata(request: Request) -> Response:
    """
    Accept a metadata sync payload, validate it against the allowlist schema,
    and forward to the Pro dashboard if configured.

    Fail-closed: any forbidden field or disallowed destination → 403 + EGRESS_BLOCKED event.
    """
    pro_dashboard_url = os.environ.get("PRO_DASHBOARD_URL", "")

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "VALIDATION_ERROR",
                "message": "Request body must be JSON.",
                "retryable": False,
            },
        )

    # Step 1 — validate payload fields
    allowed, forbidden = validate_payload(payload)
    if not allowed:
        return _blocked_response(
            field_name=forbidden[0],
            destination=pro_dashboard_url or "unset",
        )

    # Step 2 — validate destination (only if a Pro dashboard is configured)
    if pro_dashboard_url:
        if not validate_destination(pro_dashboard_url):
            return _blocked_response(field_name="", destination=pro_dashboard_url)
        # Forward to Pro dashboard
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    f"{pro_dashboard_url}/ingest/metadata",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
            return Response(
                content=r.content,
                status_code=r.status_code,
                media_type="application/json",
            )
        except Exception as exc:
            return JSONResponse(
                status_code=503,
                content={
                    "error_code": "DEPENDENCY_UNAVAILABLE",
                    "message": f"Pro dashboard unreachable: {exc}",
                    "retryable": True,
                },
            )

    # No Pro dashboard configured — return success with validation confirmation
    return JSONResponse(
        content={
            "status": "synced",
            "destination": None,
            "fields_validated": True,
            "field_count": len(payload),
        }
    )


# ---------------------------------------------------------------------------
# Pro ingest routes — forward to evidence-vault (DLP-validated pipeline)
# ---------------------------------------------------------------------------


@app.api_route(
    "/v1/pro/ingest/{sub_path:path}",
    methods=["POST"],
)
async def pro_ingest(sub_path: str, request: Request) -> Response:
    """
    Accept a Pro ingest payload (status-artifact, dossier-metadata, metrics),
    and forward directly to evidence-vault.

    DLP payload validation is intentionally skipped here: these are internal
    ingest routes (gateway-api → egress-proxy → evidence-vault), not outbound
    external sync. The DLP allowlist applies only to /v1/sync/metadata.

    This route breaks the circular proxy loop: gateway-api → egress-proxy → evidence-vault.
    """
    body = await request.body()

    url = f"{EVIDENCE_VAULT_URL}/v1/pro/ingest/{sub_path}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                url,
                content=body,
                headers={"Content-Type": "application/json"},
            )
            return Response(
                content=r.content,
                status_code=r.status_code,
                media_type=r.headers.get("content-type", "application/json"),
            )
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "error_code": "DEPENDENCY_UNAVAILABLE",
                "message": f"Evidence vault unreachable: {exc}",
                "retryable": True,
            },
        )


# ---------------------------------------------------------------------------
# Catch-all proxy to gateway-api (internal traffic only)
# ---------------------------------------------------------------------------


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy_to_gateway(path: str, request: Request) -> Response:
    """
    Forward all other internal requests to the gateway-api.

    This catch-all handles internal service-to-service routing; it does NOT
    apply DLP validation since it is not an outbound metadata sync path.
    """
    url = f"{GATEWAY_API_URL}/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = dict(request.headers)
    headers.pop("host", None)

    body = await request.body()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.request(
                request.method,
                url,
                headers=headers,
                content=body if body else None,
            )
            return Response(
                content=r.content,
                status_code=r.status_code,
                media_type=r.headers.get("content-type"),
            )
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "error_code": "DEPENDENCY_UNAVAILABLE",
                "message": f"Gateway unavailable: {exc}",
                "retryable": True,
            },
        )
