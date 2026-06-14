"""Tests for the shared telemetry module (PRD Section 11.1)."""

from __future__ import annotations

from opencomplai_core import telemetry
from opencomplai_core.telemetry import (
    ALL_EVENTS,
    EVENT_BADGE_ISSUED,
    EVENT_COMPLIANCE_CHECK_COMPLETED,
    EVENT_COMPLIANCE_CHECK_STARTED,
    EVENT_DOSSIER_GENERATED,
    EVENT_EGRESS_BLOCKED,
    EVENT_FIRST_SCAN_COMPLETED,
    EVENT_INSTALL_COMPLETED,
    EVENT_OVERRIDE_SUBMITTED,
    EVENT_TRAP_DETECTED,
    EVENT_VERIFICATION_FAILED,
    configure_telemetry,
    emit_event,
    get_meter,
)


def test_all_prd_events_defined() -> None:
    """All 10 PRD Section 11.1 event names must be defined as constants."""
    expected = {
        EVENT_COMPLIANCE_CHECK_STARTED,
        EVENT_COMPLIANCE_CHECK_COMPLETED,
        EVENT_TRAP_DETECTED,
        EVENT_OVERRIDE_SUBMITTED,
        EVENT_VERIFICATION_FAILED,
        EVENT_DOSSIER_GENERATED,
        EVENT_EGRESS_BLOCKED,
        EVENT_INSTALL_COMPLETED,
        EVENT_FIRST_SCAN_COMPLETED,
        EVENT_BADGE_ISSUED,
    }
    assert set(ALL_EVENTS) == expected
    assert len(ALL_EVENTS) == 10
    for name in ALL_EVENTS:
        assert isinstance(name, str)
        assert name


def test_configure_telemetry_does_not_raise() -> None:
    """configure_telemetry must be safe to call even if OTel deps are absent."""
    configure_telemetry("test-service")


def test_emit_event_without_otel_is_noop() -> None:
    """emit_event must never raise, regardless of OTel availability."""
    emit_event(
        EVENT_COMPLIANCE_CHECK_STARTED,
        attributes={
            "install_id": "test-install",
            "system_id": "test-system",
            "trigger": "manual_check",
            "scan_mode": "local",
        },
    )


def test_emit_event_with_meter_does_not_raise() -> None:
    """emit_event with the meter returned by get_meter must not raise."""
    meter = get_meter("test-service")
    emit_event(EVENT_FIRST_SCAN_COMPLETED, attributes={"result": "pass"}, meter=meter)


def test_metrics_response_returns_response_or_none() -> None:
    """metrics_response returns None or a FastAPI Response; never raises."""
    result = telemetry.metrics_response()
    assert result is None or hasattr(result, "media_type")
