"""
Risk Engine FastAPI service.

Exposes the deterministic risk classification engine as an HTTP service.
All responses are deterministic: the same input always produces the same output.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request as urlreq

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from opencomplai_core.engine import assess
from opencomplai_core.frameworks import resolve_targets
from opencomplai_core.models import (
    AssessmentInput,
    FrameworkInputs,
    ModelMetadata,
    SystemManifest,
)
from opencomplai_core.service_auth import load_shared_secret, mint_service_token
from opencomplai_core.telemetry import (
    configure_telemetry,
    metrics_response,
)
from pydantic import BaseModel, Field

from opencomplai_risk_engine.service_auth_dependency import require_service_principal

try:
    from prometheus_client import Counter as _Counter

    _TRAP_DETECTED = _Counter(
        "opencomplai_trap_detected_total",
        "Modification traps detected during risk classification",
        ["system_id"],
    )
    _OVERRIDE_SUBMITTED = _Counter(
        "opencomplai_override_submitted_total",
        "HITL overrides submitted",
        ["decision"],
    )
    _HITL_AUDIT_FAILURES = _Counter(
        "opencomplai_hitl_audit_failures_total",
        "HITL actions rejected because the evidence vault ledger write failed",
    )
    _EVALS_FAILED = _Counter(
        "opencomplai_evals_failed_total",
        "Pipeline evaluators that failed",
        ["category"],
    )
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False

TENANT_ID = os.environ.get("TENANT_ID", "default")

EVIDENCE_VAULT_URL = os.environ.get("EVIDENCE_VAULT_URL", "http://evidence-vault:8002")

PORT = int(os.environ.get("PORT", "8001"))

app = FastAPI(
    title="Opencomplai Risk Engine",
    description=(
        "Deterministic risk classification service for EU AI Act compliance. "
        "Implements REQ-RISK-001 (Annex III), REQ-RISK-002 (profiling), "
        "REQ-RISK-003 (modification trap)."
    ),
    version="0.1.0-dev",
)

configure_telemetry("risk-engine")

# The public docs-site checker widget calls POST /v1/checker/email directly
# from the browser — the only cross-origin caller of this service today.
# CORSMiddleware applies to the whole ASGI app once added via app.add_middleware
# with no way to scope it to one router, so scoping is done by path prefix
# inside the middleware itself: every other route requires a service token and
# has no browser caller to permit CORS for.
_CHECKER_CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "OPENCOMPLAI_DOCS_ORIGINS",
        "https://docs.opencomplai.com,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
]


class _CheckerScopedCORSMiddleware(CORSMiddleware):
    """CORSMiddleware that only processes requests under /v1/checker/*."""

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and not scope["path"].startswith("/v1/checker"):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


app.add_middleware(
    _CheckerScopedCORSMiddleware,
    allow_origins=_CHECKER_CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

from opencomplai_risk_engine.checker_routes import (  # noqa: E402 — imported after app init to avoid a circular import
    router as checker_router,
)

app.include_router(checker_router)

# Every other /v1/* route requires a valid internal service token
# (SEC-SERVICE-AUTH) — only /health, /metrics, and /v1/checker/* (public by
# design, CORS-scoped above) stay reachable without one.
router = APIRouter(dependencies=[Depends(require_service_principal)])


class ManifestValidateRequest(BaseModel):
    system_id: str
    intended_purpose: str
    compliance_target: str = "EU_AI_ACT"
    compliance_targets: list[str] | None = None
    framework_inputs: dict[str, FrameworkInputs] = {}
    high_risk_presumption: bool = False
    commit_ref: str = "HEAD"


class RiskClassifyRequest(BaseModel):
    system_id: str
    intended_purpose: str
    features: list[str] = []
    change_context: str | None = None


class RiskClassifyResponse(BaseModel):
    risk_class: str
    profiling_detected: bool
    trap_detected: bool
    score: float
    rationale_hash: str
    evidence_event_id: str = Field(
        ...,
        description=(
            "Deterministic sha256 digest of the classification request "
            "(evt_sha256:<hex>) — NOT the id of a ledger event. classify_risk "
            "does not write to the evidence-vault ledger."
        ),
    )


def _rationale_hash(result) -> str:
    rationale = json.dumps(
        [
            {"rule_id": r.rule_id, "passed": r.passed, "rationale": r.rationale}
            for r in result.rule_results
        ],
        sort_keys=True,
    )
    return f"sha256:{hashlib.sha256(rationale.encode()).hexdigest()}"


def _score(result) -> float:
    if result.rules_evaluated == 0:
        return 1.0
    return result.rules_passed / result.rules_evaluated


def _deterministic_event_id(payload: dict) -> str:
    """
    Deterministic SHA-256 digest of `payload`, formatted as `evt_sha256:<hex>`.

    This is NOT a ledger event id — no evidence-vault write happens here. It
    exists so identical requests are trivially content-addressable/comparable
    without a ledger round-trip. Callers that need an actual ledger event id
    must append one explicitly (see `_record_hitl_event*` below) and use the
    id the vault returns.
    """
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"evt_sha256:{digest}"


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "risk-engine"}


@app.get("/metrics")
async def metrics():
    """Prometheus text-format metrics for this service."""
    response = metrics_response()
    if response is None:
        raise HTTPException(status_code=503, detail="prometheus_client not installed")
    return response


@router.post("/v1/manifests/validate")
async def validate_manifest(request: ManifestValidateRequest) -> dict:
    try:
        manifest = SystemManifest.model_validate(request.model_dump(exclude_none=True))
        resolve_targets(manifest)  # rejects unknown framework ids
        return {"valid": True, "manifest": manifest.model_dump()}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/v1/risk/classify", response_model=RiskClassifyResponse)
async def classify_risk(request: RiskClassifyRequest) -> RiskClassifyResponse:
    answers: dict = {}
    if "profiling" in [f.lower() for f in request.features]:
        answers["profiling_detected"] = True
    if request.change_context in (
        "model_retrain",
        "purpose_change",
        "capability_extension",
    ):
        answers["substantial_modification"] = True

    assessment_input = AssessmentInput(
        model=ModelMetadata(
            name=request.system_id,
            version="1.0.0",
            modality="text",
            use_case=request.intended_purpose,
            deployment_context="production",
        ),
        answers=answers,
    )

    result = assess(assessment_input)

    profiling_detected = any(
        r.rule_id == "EU_AIA_ART6_PROFILING" and not r.passed
        for r in result.rule_results
    )
    trap_detected = any(
        r.rule_id == "EU_AIA_ART25_MODIFICATION_TRAP" and not r.passed
        for r in result.rule_results
    )

    rationale_hash = _rationale_hash(result)
    # NOTE: classify_risk makes no evidence-vault/ledger call — only the HITL
    # override paths (submit_override, run_evals_endpoint) append ledger
    # events. `evidence_event_id` below is a deterministic digest of this
    # request, not the id of any appended ledger event; the field name is
    # kept for API compatibility (see docs/src/api/rest-api.md).
    evidence_event_id = _deterministic_event_id(
        {
            "system_id": request.system_id,
            "intended_purpose": request.intended_purpose,
            "features": [f.lower() for f in request.features],
            "change_context": request.change_context,
            "rationale_hash": rationale_hash,
        }
    )

    if _METRICS_AVAILABLE and trap_detected:
        _TRAP_DETECTED.labels(system_id=request.system_id).inc()

    return RiskClassifyResponse(
        risk_class=result.risk_level.value,
        profiling_detected=profiling_detected,
        trap_detected=trap_detected,
        score=_score(result),
        rationale_hash=rationale_hash,
        evidence_event_id=evidence_event_id,
    )


class OverrideRequest(BaseModel):
    """Request body for POST /v1/hitl/overrides."""

    case_id: str
    actor_id: str
    rationale: str = Field(
        ..., description="Non-empty rationale is mandatory (REQ-HITL-001)"
    )
    decision: str  # "approved" | "rejected"
    requires_dual_approval: bool = False
    idempotency_key: str | None = Field(
        None,
        description="Client-supplied key; same key + same payload returns cached 201",
    )


class OverrideResponse(BaseModel):
    """Response body for POST /v1/hitl/overrides."""

    override_id: str
    rationale_hash: str
    status: str  # "accepted" | "pending_second_approval"
    vault_event_id: str | None = None


def _evidence_vault_headers() -> dict[str, str]:
    """
    Signed service-token header for calls to evidence-vault (SEC-SERVICE-AUTH),
    plus X-Tenant-Id (TEN-VAULT) so evidence-vault's RLS fence scopes ledger
    writes to this deployment's tenant. risk-engine is still single-tenant-
    per-deployment (TENANT_ID env var, not per-request) — PERSIST-RISK is the
    epic that moves the review queue itself to real per-request tenancy; this
    only forwards the deployment's own tenant to the vault it writes to.
    """
    headers = {"Content-Type": "application/json", "X-Tenant-Id": TENANT_ID}
    secret = load_shared_secret()
    if secret is not None:
        token = mint_service_token("risk-engine", secret)
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _vault_request(method: str, path: str, body: dict | None = None) -> dict | None:
    """Non-blocking GET/POST against evidence-vault's HITL persistence routes."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urlreq.Request(
        f"{EVIDENCE_VAULT_URL}{path}",
        data=data,
        headers=_evidence_vault_headers(),
        method=method,
    )
    try:
        with urlreq.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _lookup_accepted_override(idempotency_key: str) -> tuple[str, dict] | None:
    """
    Durable override-idempotency lookup (PERSIST-RISK). Returns None both on a
    genuine cache miss and on vault unavailability — submit_override's
    subsequent fail-closed ledger write is what actually protects correctness
    when the vault is down; a lookup miss here at worst re-runs an override
    that would otherwise have been served from cache.
    """
    result = _vault_request("GET", f"/v1/hitl/overrides/{idempotency_key}")
    if result is None or not result.get("found"):
        return None
    return result["payload_fingerprint"], result["response_json"]


def _store_accepted_override(
    idempotency_key: str, payload_fingerprint: str, response_json: dict
) -> None:
    _vault_request(
        "POST",
        "/v1/hitl/overrides",
        {
            "idempotency_key": idempotency_key,
            "payload_fingerprint": payload_fingerprint,
            "response_json": response_json,
        },
    )


def _lookup_completed_eval(run_key: str) -> dict | None:
    result = _vault_request("GET", f"/v1/evals/cache/{run_key}")
    if result is None or not result.get("found"):
        return None
    return result["result_json"]


def _store_completed_eval(run_key: str, result_json: dict) -> None:
    _vault_request(
        "POST", "/v1/evals/cache", {"eval_run_id": run_key, "result_json": result_json}
    )


async def _record_hitl_event(
    event_type: str, payload: dict, actor_id: str
) -> str | None:
    """
    Record a HITL action as a signed ledger event in the Evidence Vault (REQ-EV-003).

    Non-blocking: returns None if the vault is temporarily unavailable.
    Used for non-critical telemetry (e.g. bias_alert from verify).
    """
    body = json.dumps(
        {"event_type": event_type, "payload": payload, "signer_id": actor_id}
    ).encode("utf-8")
    req = urlreq.Request(
        f"{EVIDENCE_VAULT_URL}/v1/evidence/events",
        data=body,
        headers=_evidence_vault_headers(),
        method="POST",
    )
    try:
        with urlreq.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read()).get("event_id")
    except Exception:
        return None


async def _record_hitl_event_strict(
    event_type: str, payload: dict, actor_id: str
) -> str:
    """
    Fail-closed ledger write for HITL decisions (REQ-HITL-001 / REQ-EV-003).

    Raises HTTPException 503 AUDIT_UNAVAILABLE when the vault is unreachable.
    """
    event_id = await _record_hitl_event(event_type, payload, actor_id)
    if event_id is None:
        if _METRICS_AVAILABLE:
            _HITL_AUDIT_FAILURES.inc()
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "AUDIT_UNAVAILABLE",
                "message": "Evidence vault unavailable — decision not recorded",
                "category": "server",
                "retryable": True,
            },
        )
    return event_id


def _default_idempotency_key(
    case_id: str, actor_id: str, decision: str, rationale_hash: str
) -> str:
    raw = f"{case_id}|{actor_id}|{decision}|{rationale_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _derive_override_id(
    tenant_id: str,
    case_id: str,
    actor_id: str,
    decision: str,
    rationale_hash: str,
    idempotency_key: str,
) -> str:
    raw = "|".join(
        [tenant_id, case_id, actor_id, decision, rationale_hash, idempotency_key]
    )
    return f"ovr_sha256:{hashlib.sha256(raw.encode()).hexdigest()}"


def _override_payload_fingerprint(
    case_id: str,
    actor_id: str,
    decision: str,
    rationale_hash: str,
    requires_dual_approval: bool,
) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "case_id": case_id,
                "actor_id": actor_id,
                "decision": decision,
                "rationale_hash": rationale_hash,
                "requires_dual_approval": requires_dual_approval,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


@router.post("/v1/hitl/overrides", response_model=OverrideResponse, status_code=201)
async def submit_override(request: OverrideRequest) -> OverrideResponse:
    """
    Submit a HITL override action (REQ-HITL-001).

    Rationale is mandatory and non-empty. The rationale is hashed before
    storage — the plaintext is never stored. For biometric confirmation paths,
    dual approval is required (requires_dual_approval=True).
    """
    if not request.rationale.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "VALIDATION_ERROR",
                "message": "human_oversight.override_logic is required — rationale must be non-empty",
                "category": "client",
                "retryable": False,
            },
        )

    rationale_hash = f"sha256:{hashlib.sha256(request.rationale.encode()).hexdigest()}"
    idempotency_key = request.idempotency_key or _default_idempotency_key(
        request.case_id, request.actor_id, request.decision, rationale_hash
    )
    payload_fp = _override_payload_fingerprint(
        request.case_id,
        request.actor_id,
        request.decision,
        rationale_hash,
        request.requires_dual_approval,
    )

    cached = _lookup_accepted_override(idempotency_key)
    if cached is not None:
        cached_fp, cached_body = cached
        if cached_fp != payload_fp:
            raise HTTPException(
                status_code=409,
                detail={
                    "error_code": "IDEMPOTENCY_CONFLICT",
                    "message": "Idempotency key reused with a different payload",
                    "category": "client",
                    "retryable": False,
                },
            )
        return OverrideResponse(**cached_body)

    override_id = _derive_override_id(
        TENANT_ID,
        request.case_id,
        request.actor_id,
        request.decision,
        rationale_hash,
        idempotency_key,
    )
    status = "pending_second_approval" if request.requires_dual_approval else "accepted"

    # Fail-closed: ledger write must succeed before the decision is accepted.
    vault_event_id = await _record_hitl_event_strict(
        event_type="override_submitted",
        payload={
            "override_id": override_id,
            "case_id": request.case_id,
            "decision": request.decision,
            "rationale_hash": rationale_hash,
            "requires_dual_approval": request.requires_dual_approval,
            "status": status,
            "tenant_id": TENANT_ID,
            "idempotency_key": idempotency_key,
        },
        actor_id=request.actor_id,
    )

    if _METRICS_AVAILABLE:
        _OVERRIDE_SUBMITTED.labels(decision=request.decision).inc()

    response = OverrideResponse(
        override_id=override_id,
        rationale_hash=rationale_hash,
        status=status,
        vault_event_id=vault_event_id,
    )
    _store_accepted_override(idempotency_key, payload_fp, response.model_dump())
    return response


class EvalRunRequest(BaseModel):
    system_id: str
    commit_ref: str = "HEAD"
    sample_set: dict


@router.post("/v1/evals/run")
async def run_evals_endpoint(request: EvalRunRequest) -> dict:
    """Run safety, bias, and data-leakage evaluators (Workstream A)."""
    from opencomplai_core.eval_engine import (
        eval_run_id,
        run_evals,
        threshold_policy_hash,
    )
    from opencomplai_core.evaluators.registry import EVAL_SET_VERSION
    from opencomplai_core.models import EvalSampleSet

    try:
        sample_set = EvalSampleSet.model_validate(request.sample_set)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "VALIDATION_ERROR",
                "message": str(exc),
                "category": "client",
                "retryable": False,
            },
        ) from exc

    policy_hash = threshold_policy_hash(sample_set)
    run_key = eval_run_id(
        TENANT_ID,
        request.system_id,
        request.commit_ref,
        sample_set.eval_set_id,
        EVAL_SET_VERSION,
        policy_hash,
    )

    cached_eval = _lookup_completed_eval(run_key)
    if cached_eval is not None:
        return cached_eval

    try:
        report = run_evals(request.system_id, request.commit_ref, sample_set)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "VALIDATION_ERROR",
                "message": str(exc),
                "category": "client",
                "retryable": False,
            },
        ) from exc

    for result in report.results:
        if result.outcome.value == "fail" and _METRICS_AVAILABLE:
            _EVALS_FAILED.labels(category=result.category.value).inc()

    payload = {
        "eval_run_id": run_key,
        "system_id": report.system_id,
        "commit_ref": report.commit_ref,
        "overall_outcome": report.overall_outcome.value,
        "evaluators_failed": report.evaluators_failed,
        "evidence_hashes": [r.evidence_hash for r in report.results],
    }
    await _record_hitl_event_strict(
        "eval_completed",
        payload,
        actor_id="system",
    )

    if report.evaluators_failed > 0:
        from opencomplai_core.models import ReviewReason

        from opencomplai_risk_engine.review_queue import (
            build_redacted_context,
            enqueue_review,
        )

        for result in report.results:
            if result.outcome.value != "fail":
                continue
            payload_ref = result.evidence_hash
            ctx = build_redacted_context(
                review_id="pending",
                reason=ReviewReason.EVALUATOR_FAIL,
                detector_ids=[result.evaluator_id],
                aggregate_counts={"failed": 1},
                evidence_hashes=[result.evidence_hash],
            )
            enqueue_review(
                tenant_id=TENANT_ID,
                system_id=request.system_id,
                commit_ref=request.commit_ref,
                reason=ReviewReason.EVALUATOR_FAIL,
                payload_ref=payload_ref,
                context=ctx,
            )

    body = report.model_dump()
    body["eval_run_id"] = run_key
    _store_completed_eval(run_key, body)
    return body


# ---------------------------------------------------------------------------
# HITL reviewer queue (Workstream B)
# ---------------------------------------------------------------------------


@router.get("/v1/hitl/queue")
async def list_hitl_queue(
    state: str | None = None,
    assigned_to: str | None = None,
) -> dict:
    from opencomplai_core.models import ReviewItemState

    from opencomplai_risk_engine.review_queue import list_review_items

    state_enum = ReviewItemState(state) if state else None
    items = list_review_items(TENANT_ID, state=state_enum, assigned_to=assigned_to)
    return {"items": [i.model_dump() for i in items]}


@router.get("/v1/hitl/queue/{review_id}")
async def get_hitl_queue_item(review_id: str) -> dict:
    from opencomplai_risk_engine.review_queue import (
        get_review_context,
        get_review_item,
    )

    item = get_review_item(TENANT_ID, review_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    context = get_review_context(item.context_ref)
    return {
        "item": item.model_dump(),
        "context": context.model_dump() if context else None,
    }


class AssignReviewRequest(BaseModel):
    reviewer_id: str


@router.post("/v1/hitl/queue/{review_id}/assign")
async def assign_hitl_queue_item(review_id: str, request: AssignReviewRequest) -> dict:
    from opencomplai_risk_engine.review_queue import assign_review

    try:
        item = assign_review(TENANT_ID, review_id, request.reviewer_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Review item not found") from exc
    return {"item": item.model_dump()}


class DecideReviewRequest(BaseModel):
    actor_id: str
    decision: str
    rationale: str
    idempotency_key: str | None = None


@router.post("/v1/hitl/queue/{review_id}/decide", status_code=201)
async def decide_hitl_queue_item(review_id: str, request: DecideReviewRequest) -> dict:
    from opencomplai_risk_engine.review_queue import get_review_item, mark_decided

    item = get_review_item(TENANT_ID, review_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")

    override = await submit_override(
        OverrideRequest(
            case_id=review_id,
            actor_id=request.actor_id,
            rationale=request.rationale,
            decision=request.decision,
            idempotency_key=request.idempotency_key or f"decide-{review_id}",
        )
    )
    updated = mark_decided(TENANT_ID, review_id, override.override_id)
    return {"item": updated.model_dump(), "override": override.model_dump()}


class ReassessRequest(BaseModel):
    system_id: str
    commit_ref: str = "HEAD"
    current_fingerprint: str


@router.post("/v1/controls/reassess")
async def reassess_controls_endpoint(request: ReassessRequest) -> dict:
    """Detect TTL-expiry / manifest-change staleness for a system's controls
    and enqueue exactly one `ReviewItem` per newly-stale control (CTRL-FRESH)."""
    from opencomplai_risk_engine.control_reassessment import reassess_controls

    return reassess_controls(
        request.system_id, request.commit_ref, request.current_fingerprint
    )


class VerifyClaimRequest(BaseModel):
    claim_ref: str = ""
    source_ref: str = "offline://default"
    expected_value: str | None = None
    metric: str = "verification_mismatch"
    threshold: float = 0.0
    severity: str = "high"
    system_id: str | None = None


@router.post("/v1/verify/claims")
async def verify_claim(request: VerifyClaimRequest) -> dict:
    """
    Resolve a claim to exactly one terminal outcome (REQ-GTVG-001).

    Uses the offline adapter by default (safe for airgap/CI). HTTP adapter
    is selected automatically when source_ref starts with http:// or https://.
    """
    from opencomplai_core.adapters import get_adapter
    from opencomplai_core.verification import resolve_claim

    egress_proxy_url = os.environ.get("EGRESS_PROXY_URL", "http://egress-proxy:8004")
    adapter = get_adapter(request.source_ref, egress_proxy_url=egress_proxy_url)

    claim = {
        "claim_ref": request.claim_ref,
        "source_ref": request.source_ref,
        "expected_value": request.expected_value,
        "metric": request.metric,
        "threshold": request.threshold,
        "severity": request.severity,
    }

    try:
        task, proof, alert = await resolve_claim(claim, adapter)
    except RuntimeError as exc:
        # DEPENDENCY_UNAVAILABLE — return pending so caller can queue for retry
        task_id = _deterministic_event_id(claim)
        request_hash = f"sha256:{hashlib.sha256(json.dumps(claim, sort_keys=True).encode()).hexdigest()}"
        return {
            "outcome": "pending",
            "task_id": task_id,
            "request_hash": request_hash,
            "error": str(exc),
        }

    # Record alert in evidence vault (non-blocking)
    if alert is not None:
        await _record_hitl_event(
            "bias_alert",
            {
                "alert_id": alert.alert_id,
                "severity": alert.severity.value,
                "metric": alert.metric,
                "threshold": alert.threshold,
                "linked_event_id": alert.linked_event_id,
                "system_id": request.system_id,
            },
            actor_id="system",
        )

    response: dict = {
        "outcome": task.outcome.value,
        "task_id": task.task_id,
        "claim_ref": task.claim_ref,
        "source_ref": task.source_ref,
        "request_hash": task.request_hash,
        "response_hash": task.response_hash,
    }
    if proof is not None:
        response["evidence_hash"] = proof.evidence_hash
        response["verified_at"] = proof.verified_at
    if alert is not None:
        response["alert_id"] = alert.alert_id
        response["alert_severity"] = alert.severity.value
    return response


app.include_router(router)
