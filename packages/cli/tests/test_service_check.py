"""
Service-backed `check` path — FINDING 48.2(b) and FINDING 48.5.

`_run_service_check` talks to the gateway services via `_call_service`
rather than the local rule engine. These tests drive it directly with a
fake `_call_service` (no real network) to pin down:

  * FINDING 48.2(b): `--change-context` is forwarded to `/v1/risk/classify`,
    and a `trap_detected: true` response still produces
    `ScanResult.TRAP_DETECTED` (exit code 4 via `_exit_code`).
  * FINDING 48.5: the risk-engine's `evidence_event_id` (a locally-fabricated
    request digest, not a ledger event id) never lands in the SIGNED
    artifact's `evidence_hashes`, while `rationale_hash` still flows through
    untouched.
"""

from __future__ import annotations

from opencomplai_cli import main
from opencomplai_core.models import ScanResult, SystemManifest

_MANIFEST = SystemManifest(
    system_id="svc-check-sys",
    intended_purpose="Automated resume screening for job applicants",
    compliance_target="EU_AI_ACT",
    high_risk_presumption=False,
    commit_ref="HEAD",
)


def _fake_call_service(risk_response: dict):
    """Returns (fake_call_service, calls) — `calls` records every
    (path, payload) pair `_run_service_check` sent, so tests can assert on
    the exact outgoing classify payload."""
    calls: list[tuple[str, dict]] = []

    def fake(path: str, payload: dict) -> tuple[int, dict]:
        calls.append((path, dict(payload)))
        if path == "/v1/manifests/validate":
            return 200, {"valid": True}
        if path == "/v1/risk/classify":
            return 200, risk_response
        if path == "/v1/verify/claims":
            return 200, {"outcome": "verified"}
        if path == "/v1/docs/generate":
            return 200, {"bundle_checksum": "sha256:" + "b" * 64}
        if path == "/v1/evidence/events":
            return 200, {"event_id": None}
        raise AssertionError(f"unexpected _call_service path: {path}")

    return fake, calls


def test_change_context_forwarded_to_risk_classify_payload(monkeypatch):
    fake, calls = _fake_call_service(
        {
            "risk_class": "minimal",
            "profiling_detected": False,
            "trap_detected": False,
            "rationale_hash": "sha256:" + "a" * 64,
            "evidence_event_id": "evt_sha256:" + "c" * 64,
        }
    )
    monkeypatch.setattr(main, "_call_service", fake)

    main._run_service_check(
        _MANIFEST,
        "HEAD",
        "local",
        "install-1",
        change_context="model_retrain",
    )

    classify_calls = [payload for path, payload in calls if path == "/v1/risk/classify"]
    assert len(classify_calls) == 1
    assert classify_calls[0]["change_context"] == "model_retrain"


def test_service_trap_detected_maps_to_exit_code_4(monkeypatch):
    fake, _calls = _fake_call_service(
        {
            "risk_class": "high",
            "profiling_detected": False,
            "trap_detected": True,
            "rationale_hash": "sha256:" + "a" * 64,
            "evidence_event_id": "evt_sha256:" + "c" * 64,
        }
    )
    monkeypatch.setattr(main, "_call_service", fake)
    monkeypatch.setattr(main, "_emit_event", lambda *a, **kw: None)

    artifact, risk_high = main._run_service_check(
        _MANIFEST,
        "HEAD",
        "local",
        "install-1",
        change_context="model_retrain",
    )

    assert artifact.result == ScanResult.TRAP_DETECTED
    assert main._exit_code(artifact.result, "local") == 4
    assert risk_high is True
    assert "EU_AIA_ART25_MODIFICATION_TRAP" in artifact.failed_controls


def test_fabricated_evidence_event_id_excluded_from_signed_evidence_hashes(
    monkeypatch,
):
    fabricated_id = "evt_sha256:" + "d" * 64
    real_rationale_hash = "sha256:" + "e" * 64
    fake, _calls = _fake_call_service(
        {
            "risk_class": "minimal",
            "profiling_detected": False,
            "trap_detected": False,
            "rationale_hash": real_rationale_hash,
            "evidence_event_id": fabricated_id,
        }
    )
    monkeypatch.setattr(main, "_call_service", fake)
    monkeypatch.setattr(main, "_emit_event", lambda *a, **kw: None)

    artifact, _risk_high = main._run_service_check(
        _MANIFEST,
        "HEAD",
        "local",
        "install-1",
    )

    assert artifact.result == ScanResult.PASS
    assert fabricated_id not in artifact.evidence_hashes
    # rationale_hash is a real hash of the rule results, not the fabricated
    # request digest -- it must keep flowing through untouched.
    assert artifact.rationale_hash == real_rationale_hash


def test_answers_from_change_context_mirrors_risk_engine_keywords():
    """FINDING 48.2(a): `_answers_from_change_context` feeds
    `AssessmentInput.answers` for the local engine path -- exercised here at
    the unit level (the CLI end-to-end path is covered in test_halt_wire.py)."""
    assert main._answers_from_change_context("model_retrain") == {
        "substantial_modification": True
    }
    assert main._answers_from_change_context("purpose_change") == {
        "substantial_modification": True
    }
    assert main._answers_from_change_context("capability_extension") == {
        "substantial_modification": True
    }
    assert main._answers_from_change_context("refactor") == {}
    assert main._answers_from_change_context(None) == {}
