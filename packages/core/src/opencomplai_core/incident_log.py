"""
Signed, hash-chained incident log and the log-first state wiring (Art. 73).

Every incident event is appended to the incident log file (one JSON object per
line, built on ``signed_log.SignedLog`` under ``SigningDomain.INCIDENT_LOG``).
Declaring and closing also drive the HITL state machine, with the log entry
written FIRST: a refused or failed transition never loses the entry.

Payloads carry structured fields only. Free text (the operator's description or
closure note) stays in the incident register and is never passed in here.

No clock, no CLI: callers pass ``ts`` (E-14). Wording of the events is not
legal text; the log is a record, not a filing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from opencomplai_core.gap_probes import INCIDENT_LOG_PATH
from opencomplai_core.models import SystemState
from opencomplai_core.signed_log import SignedLog
from opencomplai_core.signing import SigningDomain
from opencomplai_core.state_machine import (
    INCIDENT_DECLARED_EVENT,
    REMEDIATION_CLOSED_EVENT,
    transition,
)
from opencomplai_core.system_state_store import load_state, save_state

LOG_NAME = INCIDENT_LOG_PATH
EVENT_DECLARED = "incident_declared"
EVENT_CLASSIFIED = "incident_classified"
EVENT_NOTIFIED = "incident_notified"
EVENT_CLOSED = "incident_closed"
EVENT_TRANSITION_REJECTED = "transition_rejected"


@dataclass(frozen=True)
class IncidentOutcome:
    entry: dict
    transitioned: bool
    new_state: SystemState
    error: str | None = None


def append_event(
    log_path: Path,
    event: str,
    payload: dict,
    *,
    ts: str,
    private_pem: bytes | None = None,
) -> dict:
    """Append one entry. ``OSError`` propagates: the caller must not change state."""
    return SignedLog(log_path, SigningDomain.INCIDENT_LOG).append(
        {"event": event, **payload}, ts=ts, private_pem=private_pem
    )


def log_then_transition(
    *,
    state_dir: Path,
    log_path: Path,
    system_id: str,
    event: str,
    payload: dict,
    ts: str,
    commit_ref: str,
    private_pem: bytes | None = None,
) -> IncidentOutcome:
    """Write the log entry first, then drive the state machine (declare / close)."""
    if event not in (EVENT_DECLARED, EVENT_CLOSED):
        raise ValueError(f"unsupported incident event: {event!r}")
    current = load_state(state_dir, system_id)
    entry = append_event(
        log_path,
        event,
        {**payload, "state_before": current.value},
        ts=ts,
        private_pem=private_pem,
    )
    if event == EVENT_DECLARED:
        result = transition(current, INCIDENT_DECLARED_EVENT)
    else:
        # The closure entry just written is the remediation event.
        result = transition(
            current, REMEDIATION_CLOSED_EVENT, has_remediation_event=True
        )
    if result.success:
        save_state(
            state_dir, system_id, result.new_state, reason=event, commit_ref=commit_ref
        )
        return IncidentOutcome(entry, True, result.new_state, None)
    append_event(
        log_path,
        EVENT_TRANSITION_REJECTED,
        {"attempted": event, "state": current.value, "error": result.error},
        ts=ts,
        private_pem=private_pem,
    )
    return IncidentOutcome(entry, False, current, result.error)
