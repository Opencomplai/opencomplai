"""
HITL deployment state machine.

Implements the state transitions defined in PRD Section 8.2:
  RUNNING -> HALTED_PENDING_REVIEW: on trap_detected
  HALTED_PENDING_REVIEW -> RUNNING: on signed approval token
  RUNNING -> INCIDENT_MODE: on critical incident
  INCIDENT_MODE -> RUNNING: on remediation closure event

State transitions are recorded as LedgerEvents in the Evidence Vault.
This module defines the transition rules; the evidence-vault service
persists the events (Phase 11, Task 11.3).
"""

from __future__ import annotations

from dataclasses import dataclass

from opencomplai_core.models import SystemState

# ---------------------------------------------------------------------------
# Allowed state transitions
# ---------------------------------------------------------------------------
ALLOWED_TRANSITIONS: dict[SystemState, set[SystemState]] = {
    SystemState.RUNNING: {
        SystemState.HALTED_PENDING_REVIEW,
        SystemState.INCIDENT_MODE,
    },
    SystemState.HALTED_PENDING_REVIEW: {
        SystemState.RUNNING,  # requires signed approval token
    },
    SystemState.INCIDENT_MODE: {
        SystemState.RUNNING,  # requires remediation closure event
    },
}

# Events that trigger state transitions
TRAP_DETECTED_EVENT = "trap_detected"
APPROVAL_GRANTED_EVENT = "approval_granted"
INCIDENT_DECLARED_EVENT = "incident_declared"
REMEDIATION_CLOSED_EVENT = "remediation_closed"


@dataclass
class TransitionResult:
    """Result of a state transition attempt."""

    success: bool
    new_state: SystemState
    error: str | None = None
    required_evidence: str | None = None  # what evidence is needed to proceed


def transition(
    current_state: SystemState,
    trigger_event: str,
    has_approval_token: bool = False,
    has_remediation_event: bool = False,
) -> TransitionResult:
    """
    Attempt a state transition based on a trigger event.

    Args:
        current_state: The current system state.
        trigger_event: The event triggering the transition.
        has_approval_token: True if a signed approval token is present.
        has_remediation_event: True if a remediation closure event is present.

    Returns:
        TransitionResult indicating success and the resulting state.
    """
    if trigger_event == TRAP_DETECTED_EVENT:
        if current_state == SystemState.RUNNING:
            return TransitionResult(
                success=True,
                new_state=SystemState.HALTED_PENDING_REVIEW,
            )
        return TransitionResult(
            success=False,
            new_state=current_state,
            error=f"Cannot apply trap_detected from state {current_state}",
        )

    if trigger_event == APPROVAL_GRANTED_EVENT:
        if current_state == SystemState.HALTED_PENDING_REVIEW:
            if not has_approval_token:
                return TransitionResult(
                    success=False,
                    new_state=current_state,
                    error="Signed approval token is required to resume from HALTED_PENDING_REVIEW",
                    required_evidence="signed_approval_token",
                )
            return TransitionResult(
                success=True,
                new_state=SystemState.RUNNING,
            )

    if trigger_event == INCIDENT_DECLARED_EVENT:
        if current_state == SystemState.RUNNING:
            return TransitionResult(
                success=True,
                new_state=SystemState.INCIDENT_MODE,
            )

    if trigger_event == REMEDIATION_CLOSED_EVENT:
        if current_state == SystemState.INCIDENT_MODE:
            if not has_remediation_event:
                return TransitionResult(
                    success=False,
                    new_state=current_state,
                    error="Remediation closure event is required to exit INCIDENT_MODE",
                    required_evidence="remediation_closure_event",
                )
            return TransitionResult(
                success=True,
                new_state=SystemState.RUNNING,
            )

    return TransitionResult(
        success=False,
        new_state=current_state,
        error=f"Invalid transition: event '{trigger_event}' from state '{current_state}'",
    )
