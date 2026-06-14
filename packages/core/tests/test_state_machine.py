"""Tests for the HITL deployment state machine (PRD Section 8.2)."""

from opencomplai_core.models import SystemState
from opencomplai_core.state_machine import (
    APPROVAL_GRANTED_EVENT,
    INCIDENT_DECLARED_EVENT,
    REMEDIATION_CLOSED_EVENT,
    TRAP_DETECTED_EVENT,
    transition,
)


def test_running_to_halted_on_trap():
    result = transition(SystemState.RUNNING, TRAP_DETECTED_EVENT)
    assert result.success is True
    assert result.new_state == SystemState.HALTED_PENDING_REVIEW


def test_halted_to_running_requires_approval_token():
    result = transition(
        SystemState.HALTED_PENDING_REVIEW,
        APPROVAL_GRANTED_EVENT,
        has_approval_token=False,
    )
    assert result.success is False
    assert result.required_evidence == "signed_approval_token"


def test_halted_to_running_with_approval_token():
    result = transition(
        SystemState.HALTED_PENDING_REVIEW,
        APPROVAL_GRANTED_EVENT,
        has_approval_token=True,
    )
    assert result.success is True
    assert result.new_state == SystemState.RUNNING


def test_running_to_incident_on_incident_declared():
    result = transition(SystemState.RUNNING, INCIDENT_DECLARED_EVENT)
    assert result.success is True
    assert result.new_state == SystemState.INCIDENT_MODE


def test_incident_to_running_requires_remediation():
    result = transition(
        SystemState.INCIDENT_MODE,
        REMEDIATION_CLOSED_EVENT,
        has_remediation_event=False,
    )
    assert result.success is False
    assert result.required_evidence == "remediation_closure_event"


def test_incident_to_running_with_remediation():
    result = transition(
        SystemState.INCIDENT_MODE,
        REMEDIATION_CLOSED_EVENT,
        has_remediation_event=True,
    )
    assert result.success is True
    assert result.new_state == SystemState.RUNNING


def test_invalid_transition_returns_current_state():
    result = transition(SystemState.RUNNING, "unknown_event")
    assert result.success is False
    assert result.new_state == SystemState.RUNNING


def test_trap_from_non_running_state_fails():
    result = transition(SystemState.HALTED_PENDING_REVIEW, TRAP_DETECTED_EVENT)
    assert result.success is False
    assert result.new_state == SystemState.HALTED_PENDING_REVIEW
