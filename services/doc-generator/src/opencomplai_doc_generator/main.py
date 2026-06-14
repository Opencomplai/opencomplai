"""
Documentation Generator FastAPI service.

Generates Annex IV technical documentation dossiers from system manifests
and risk assessment results (REQ-DOC-001).

On every generate, the dossier JSON is also persisted to the evidence-vault
CAS, a `dossier_generated` ledger event is appended, and a row is written to
the vault's dossier index so the document can be retrieved later via
GET /v1/docs/{dossier_id} or GET /v1/docs?system_id=...
"""

from __future__ import annotations

import base64
import json
import os
import time

import httpx
from fastapi import FastAPI, HTTPException
from opencomplai_core.engine import assess
from opencomplai_core.models import (
    AssessmentInput,
    ModelMetadata,
    SystemManifest,
)
from opencomplai_core.telemetry import configure_telemetry, metrics_response
from pydantic import BaseModel, Field

try:
    from prometheus_client import Counter as _Counter

    _DOSSIER_GENERATED = _Counter(
        "opencomplai_dossier_generated_total",
        "Annex IV dossiers generated",
        ["system_id"],
    )
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False

from opencomplai_doc_generator.generator import (
    generate_dossier,
    validate_dossier_schema,
)

EVIDENCE_VAULT_URL = os.environ.get("EVIDENCE_VAULT_URL", "http://evidence-vault:8002")

app = FastAPI(
    title="Opencomplai Documentation Generator",
    description="Annex IV technical documentation dossier generator (REQ-DOC-001).",
    version="0.1.0-dev",
)

configure_telemetry("doc-generator")


class GenerateDocsRequest(BaseModel):
    """Request body for POST /v1/docs/generate."""

    system_id: str
    commit_ref: str
    intended_purpose: str = "Not specified"
    provider_name: str = "Unknown Provider"
    compliance_target: str = "EU_AI_ACT"
    high_risk_presumption: bool = False
    # Optional Annex IV Section 2 overrides. HIGH-risk providers must set these
    # — defaults leave the section stubbed, which is acceptable only at
    # MINIMAL risk classification.
    training_data_description: str | None = None
    model_architecture: str | None = None
    performance_metrics: dict[str, float] = Field(default_factory=dict)
    known_limitations: list[str] = Field(default_factory=list)
    # Optional Annex IV Section 3 overrides. Same rationale as Section 2.
    human_oversight_measures: list[str] = Field(default_factory=list)
    monitoring_approach: str | None = None
    incident_response_procedure: str | None = None


class GenerateDocsResponse(BaseModel):
    """Response body for POST /v1/docs/generate."""

    dossier_id: str
    bundle_checksum: str
    status: str  # "generated" | "failed"
    duration_ms: int
    signature: str | None = None
    schema_valid: bool
    content_hash: str | None = None
    ledger_event_id: str | None = None


class DossierSummary(BaseModel):
    dossier_id: str
    system_id: str
    commit_ref: str
    bundle_checksum: str
    content_hash: str
    ledger_event_id: str
    created_at: str


async def _fetch_ledger_root() -> str | None:
    """
    Read the current Merkle chain tip from the evidence-vault.

    Returned hash is embedded in `section4.ledger_root_hash` so the dossier
    self-anchors to ledger state at issuance time. Returns None on any
    upstream failure so dossier generation degrades gracefully — the
    section4 field documents this case as a null value.
    """
    try:
        async with httpx.AsyncClient(
            base_url=EVIDENCE_VAULT_URL, timeout=5.0
        ) as client:
            resp = await client.get("/v1/evidence/ledger-root")
            if resp.status_code >= 400:
                return None
            return resp.json().get("ledger_root_hash")
    except httpx.HTTPError:
        return None


async def _persist_dossier(
    dossier_json: str,
    dossier_id: str,
    system_id: str,
    commit_ref: str,
    bundle_checksum: str,
) -> tuple[str, str]:
    """
    Write the dossier to the evidence-vault CAS, append a ledger event, and
    register it in the dossier index. Returns (content_hash, ledger_event_id).

    Best-effort: any failure here is raised as a 502 to the caller so the
    customer learns the dossier was generated but not persisted.
    """
    async with httpx.AsyncClient(base_url=EVIDENCE_VAULT_URL, timeout=10.0) as client:
        content_b64 = base64.b64encode(dossier_json.encode("utf-8")).decode("ascii")
        cas_resp = await client.post(
            "/v1/evidence/objects",
            json={"content_base64": content_b64},
        )
        if cas_resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail={
                    "error_code": "VAULT_CAS_WRITE_FAILED",
                    "upstream_status": cas_resp.status_code,
                    "upstream_body": cas_resp.text,
                },
            )
        content_hash = cas_resp.json()["content_hash"]

        event_resp = await client.post(
            "/v1/evidence/events",
            json={
                "event_type": "dossier_generated",
                "payload": {
                    "dossier_id": dossier_id,
                    "system_id": system_id,
                    "commit_ref": commit_ref,
                    "bundle_checksum": bundle_checksum,
                    "content_hash": content_hash,
                },
            },
        )
        if event_resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail={
                    "error_code": "VAULT_EVENT_APPEND_FAILED",
                    "upstream_status": event_resp.status_code,
                    "upstream_body": event_resp.text,
                },
            )
        ledger_event_id = event_resp.json()["event_id"]

        index_resp = await client.post(
            "/v1/dossiers",
            json={
                "dossier_id": dossier_id,
                "system_id": system_id,
                "commit_ref": commit_ref,
                "content_hash": content_hash,
                "bundle_checksum": bundle_checksum,
                "ledger_event_id": ledger_event_id,
            },
        )
        if index_resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail={
                    "error_code": "VAULT_DOSSIER_INDEX_FAILED",
                    "upstream_status": index_resp.status_code,
                    "upstream_body": index_resp.text,
                },
            )

    return content_hash, ledger_event_id


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "doc-generator"}


@app.get("/metrics")
async def metrics():
    """Prometheus text-format metrics for this service."""
    response = metrics_response()
    if response is None:
        raise HTTPException(status_code=503, detail="prometheus_client not installed")
    return response


@app.post("/v1/docs/generate", response_model=GenerateDocsResponse)
async def generate_docs(request: GenerateDocsRequest) -> GenerateDocsResponse:
    """
    Generate an Annex IV technical documentation dossier (REQ-DOC-001).

    Idempotent by (system_id, commit_ref): same inputs produce the same
    bundle_checksum (dossier content is deterministic).
    Target P95 generation time: <= 120 seconds (PRD SLO).

    The full dossier JSON is persisted to the evidence-vault CAS and indexed
    so it can be retrieved via GET /v1/docs/{dossier_id}.
    """
    start = time.monotonic()

    try:
        manifest = SystemManifest(
            system_id=request.system_id,
            intended_purpose=request.intended_purpose,
            compliance_target=request.compliance_target,
            high_risk_presumption=request.high_risk_presumption,
            commit_ref=request.commit_ref,
            training_data_description=request.training_data_description,
            model_architecture=request.model_architecture,
            performance_metrics=request.performance_metrics,
            known_limitations=request.known_limitations,
            human_oversight_measures=request.human_oversight_measures,
            monitoring_approach=request.monitoring_approach,
            incident_response_procedure=request.incident_response_procedure,
        )

        assessment_input = AssessmentInput(
            model=ModelMetadata(
                name=request.system_id,
                version=request.commit_ref,
                modality="text",
                use_case=request.intended_purpose,
                deployment_context="production",
            )
        )
        risk_result = assess(assessment_input)

        # Anchor the dossier to the current Merkle root so any future tampering
        # of older ledger events becomes detectable by re-fetching the root
        # and comparing. Best-effort: if the vault is unreachable we still
        # emit a dossier, just without the anchor.
        ledger_root_hash = await _fetch_ledger_root()

        dossier = generate_dossier(
            manifest=manifest,
            risk_result=risk_result,
            ledger_root_hash=ledger_root_hash,
            provider_name=request.provider_name,
        )

        schema_valid = validate_dossier_schema(dossier)
        dossier_json = dossier.model_dump_json()

        content_hash, ledger_event_id = await _persist_dossier(
            dossier_json=dossier_json,
            dossier_id=dossier.dossier_id,
            system_id=request.system_id,
            commit_ref=request.commit_ref,
            bundle_checksum=dossier.bundle_checksum or "",
        )

        duration_ms = int((time.monotonic() - start) * 1000)

        if _METRICS_AVAILABLE:
            _DOSSIER_GENERATED.labels(system_id=request.system_id).inc()

        return GenerateDocsResponse(
            dossier_id=dossier.dossier_id,
            bundle_checksum=dossier.bundle_checksum or "",
            status="generated",
            duration_ms=duration_ms,
            signature=dossier.signature,
            schema_valid=schema_valid,
            content_hash=content_hash,
            ledger_event_id=ledger_event_id,
        )

    except HTTPException:
        raise
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "SYSTEM_ERROR",
                "message": str(exc),
                "duration_ms": duration_ms,
            },
        ) from exc


@app.get("/v1/docs/{dossier_id}")
async def get_dossier(dossier_id: str) -> dict:
    """
    Retrieve a previously generated dossier by id.

    Returns the dossier JSON together with the index metadata that lets the
    caller verify the bundle_checksum and trace the anchoring ledger event.
    """
    async with httpx.AsyncClient(base_url=EVIDENCE_VAULT_URL, timeout=10.0) as client:
        idx_resp = await client.get(f"/v1/dossiers/{dossier_id}")
        if idx_resp.status_code == 404:
            raise HTTPException(
                status_code=404, detail=f"Dossier not found: {dossier_id}"
            )
        if idx_resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail={
                    "error_code": "VAULT_INDEX_READ_FAILED",
                    "upstream_status": idx_resp.status_code,
                    "upstream_body": idx_resp.text,
                },
            )
        index = idx_resp.json()
        content_hash: str = index["content_hash"]

        obj_resp = await client.get(f"/v1/evidence/objects/{content_hash}")
        if obj_resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail={
                    "error_code": "VAULT_CAS_READ_FAILED",
                    "upstream_status": obj_resp.status_code,
                    "upstream_body": obj_resp.text,
                },
            )
        body = obj_resp.json()
        try:
            decoded = base64.b64decode(body["content_base64"]).decode("utf-8")
            dossier_obj = json.loads(decoded)
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "error_code": "VAULT_CAS_DECODE_FAILED",
                    "message": str(exc),
                },
            ) from exc

    return {
        "dossier_id": index["dossier_id"],
        "system_id": index["system_id"],
        "commit_ref": index["commit_ref"],
        "bundle_checksum": index["bundle_checksum"],
        "content_hash": index["content_hash"],
        "ledger_event_id": index["ledger_event_id"],
        "created_at": index["created_at"],
        "dossier": dossier_obj,
    }


@app.get("/v1/docs")
async def list_dossiers(system_id: str) -> dict:
    """List all dossiers stored for a given system_id, newest first."""
    async with httpx.AsyncClient(base_url=EVIDENCE_VAULT_URL, timeout=10.0) as client:
        resp = await client.get("/v1/dossiers", params={"system_id": system_id})
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail={
                    "error_code": "VAULT_INDEX_LIST_FAILED",
                    "upstream_status": resp.status_code,
                    "upstream_body": resp.text,
                },
            )
        return resp.json()
