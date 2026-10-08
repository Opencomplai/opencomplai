"""Incident log: chain, state wiring, log-before-transition, failure paths."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from opencomplai_core import incident_log
from opencomplai_core.incident_log import (
    EVENT_CLASSIFIED,
    EVENT_CLOSED,
    EVENT_DECLARED,
    append_event,
    log_then_transition,
)
from opencomplai_core.models import SystemState
from opencomplai_core.signed_log import SignedLog, verify_log
from opencomplai_core.signing import SigningDomain, generate_keypair
from opencomplai_core.system_state_store import load_state, save_state

SYS = "sys-1"
T1, T2, T3 = "2026-03-01T10:00:00Z", "2026-03-01T11:00:00Z", "2026-03-01T12:00:00Z"


def _go(tmp_path: Path, event: str, ts: str, **kw):
    return log_then_transition(
        state_dir=tmp_path / "state",
        log_path=tmp_path / "incident-log.json",
        system_id=SYS,
        event=event,
        payload={"incident_id": "INC-0001", "system_id": SYS},
        ts=ts,
        commit_ref="HEAD",
        **kw,
    )


def _events(tmp_path: Path) -> list[str]:
    log = SignedLog(tmp_path / "incident-log.json", SigningDomain.INCIDENT_LOG)
    return [e["payload"]["event"] for e in log.entries()]


def _keys(tmp_path: Path) -> tuple[bytes, bytes]:
    generate_keypair(tmp_path / "keys")
    return (
        (tmp_path / "keys" / "signing.key").read_bytes(),
        (tmp_path / "keys" / "signing.pub").read_bytes(),
    )


def test_declare_moves_running_to_incident_mode(tmp_path: Path):
    out = _go(tmp_path, EVENT_DECLARED, T1)
    assert out.transitioned
    assert out.error is None
    assert out.new_state == SystemState.INCIDENT_MODE
    assert load_state(tmp_path / "state", SYS) == SystemState.INCIDENT_MODE


def test_close_moves_incident_mode_to_running(tmp_path: Path):
    _go(tmp_path, EVENT_DECLARED, T1)
    out = _go(tmp_path, EVENT_CLOSED, T2)
    assert out.transitioned
    assert load_state(tmp_path / "state", SYS) == SystemState.RUNNING


def test_declare_then_close_chain_verifies(tmp_path: Path):
    priv, pub = _keys(tmp_path)
    log = tmp_path / "incident-log.json"
    _go(tmp_path, EVENT_DECLARED, T1, private_pem=priv)
    append_event(
        log, EVENT_CLASSIFIED, {"incident_id": "INC-0001"}, ts=T2, private_pem=priv
    )
    _go(tmp_path, EVENT_CLOSED, T3, private_pem=priv)
    res = verify_log(
        log, SigningDomain.INCIDENT_LOG, public_pem=pub, require_signed=True
    )
    assert res.ok
    assert res.count == 3
    assert res.verified_signatures


def test_declare_from_halted_keeps_log_entry_and_state(tmp_path: Path):
    state = tmp_path / "state"
    save_state(
        state, SYS, SystemState.HALTED_PENDING_REVIEW, reason="x", commit_ref="c"
    )
    before = (state / "system-state.json").read_text()
    out = _go(tmp_path, EVENT_DECLARED, T1)
    assert not out.transitioned
    assert out.error
    assert out.new_state == SystemState.HALTED_PENDING_REVIEW
    assert (state / "system-state.json").read_text() == before
    assert _events(tmp_path) == ["incident_declared", "transition_rejected"]
    assert verify_log(tmp_path / "incident-log.json", SigningDomain.INCIDENT_LOG).ok


def test_close_when_running_keeps_log_entry(tmp_path: Path):
    out = _go(tmp_path, EVENT_CLOSED, T1)
    assert not out.transitioned
    assert load_state(tmp_path / "state", SYS) == SystemState.RUNNING
    assert _events(tmp_path) == ["incident_closed", "transition_rejected"]


def test_log_written_before_state_changes(tmp_path: Path, monkeypatch):
    seen: list[list[str]] = []
    real = incident_log.save_state

    def spy(*a, **kw):
        seen.append(_events(tmp_path))
        return real(*a, **kw)

    monkeypatch.setattr(incident_log, "save_state", spy)
    _go(tmp_path, EVENT_DECLARED, T1)
    assert seen == [["incident_declared"]]


def test_log_failure_does_not_change_state(tmp_path: Path):
    (tmp_path / "incident-log.json").mkdir()
    with pytest.raises((IsADirectoryError, PermissionError)):
        _go(tmp_path, EVENT_DECLARED, T1)
    assert load_state(tmp_path / "state", SYS) == SystemState.RUNNING


def test_state_save_failure_keeps_log_entry(tmp_path: Path, monkeypatch):
    def boom(*a, **kw):
        raise OSError("disk")

    monkeypatch.setattr(incident_log, "save_state", boom)
    with pytest.raises(OSError, match="disk"):
        _go(tmp_path, EVENT_DECLARED, T1)
    res = verify_log(tmp_path / "incident-log.json", SigningDomain.INCIDENT_LOG)
    assert res.ok
    assert res.count == 1


def test_unsigned_when_no_key_and_signed_with_key(tmp_path: Path):
    priv, _ = _keys(tmp_path)
    log = tmp_path / "incident-log.json"
    assert append_event(log, EVENT_CLASSIFIED, {}, ts=T1)["signature"] is None
    assert append_event(log, EVENT_CLASSIFIED, {}, ts=T2, private_pem=priv)["signature"]


def test_log_domain_is_incident_log(tmp_path: Path):
    _go(tmp_path, EVENT_DECLARED, T1)
    log = tmp_path / "incident-log.json"
    assert verify_log(log, SigningDomain.INCIDENT_LOG).ok
    assert not verify_log(log, SigningDomain.OVERSIGHT_LOG).ok


def test_unknown_event_raises(tmp_path: Path):
    with pytest.raises(ValueError, match="unsupported"):
        _go(tmp_path, EVENT_CLASSIFIED, T1)
    assert not (tmp_path / "incident-log.json").exists()


def test_incident_log_module_never_reads_the_clock():
    src = inspect.getsource(incident_log)
    assert "datetime.now" not in src
    assert "time.time" not in src
