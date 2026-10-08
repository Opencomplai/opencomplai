"""Incident register: declaration, class, notifications, closure and deadline clocks.

A plain JSON current-state register (Art. 73 serious-incident records). It does not
write the signed chain, drive the state machine or render authority templates.

Privacy: ``description`` and ``closure_note`` are free text and stay local; nothing
projects them to the dashboard. Only class, dates and party kinds may leave.

Clock rule (E-14): nothing in this module reads the system clock. Every deadline
function takes ``now`` explicitly. Timestamps are UTC ``YYYY-MM-DDTHH:MM:SSZ``
strings; a naive input is taken as UTC.

Deadline day counts are the spec author's unverified reading of the Regulation,
shipped as low-confidence data flagged for founder review (E-15).

This module must not import ``models.py`` (``models.py`` imports it).
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

_NonEmptyStr = Annotated[str, Field(min_length=1)]
_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"


class IncidentClass(StrEnum):
    unclassified = "unclassified"
    death = "death"
    health_harm = "health_harm"
    critical_infrastructure = "critical_infrastructure"
    fundamental_rights = "fundamental_rights"
    property_environment = "property_environment"
    widespread_infringement = "widespread_infringement"


class PartyKind(StrEnum):
    authority = "authority"
    deployer = "deployer"
    importer = "importer"
    distributor = "distributor"


def parse_ts(s: str) -> datetime:
    """ISO 8601 to an aware UTC datetime (naive means UTC). ValueError on junk."""
    if not isinstance(s, str):
        raise ValueError(f"invalid timestamp: {s!r}")
    try:
        dt = datetime.fromisoformat(s.strip())
    except ValueError:
        raise ValueError(f"invalid timestamp: {s!r}") from None
    return _utc(dt)


def fmt_ts(dt: datetime) -> str:
    return _utc(dt).strftime(_TS_FMT)


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _norm_ts(v: str | None) -> str | None:
    return None if v is None else fmt_ts(parse_ts(v))


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Notification(_Model):
    party: _NonEmptyStr
    kind: PartyKind
    sent_at: str
    ref: str | None = None

    check_ts = field_validator("sent_at")(_norm_ts)


class IncidentContact(_Model):
    """Manifest type: who to notify for an incident."""

    kind: PartyKind
    party: _NonEmptyStr
    contact: str | None = None


class IncidentRecord(_Model):
    id: str
    system_id: _NonEmptyStr
    declared_at: str
    aware_at: str
    incident_class: IncidentClass = IncidentClass.unclassified
    description: str
    notifications: list[Notification] = Field(default_factory=list)
    closed_at: str | None = None
    closure_note: str | None = None

    check_ts = field_validator("declared_at", "aware_at", "closed_at")(_norm_ts)


class IncidentRegister(_Model):
    version: int = 1
    incidents: list[IncidentRecord] = Field(default_factory=list)


# --- deadline clocks -------------------------------------------------------

_SRC = "Regulation (EU) 2024/1689 Art. 73 (reading unverified)"


def _rule(days: int | None, note: str) -> dict[str, Any]:
    return {
        "days": days,
        "source": _SRC,
        "confidence": "low",
        "needs_founder_review": True,
        "note": note,
    }


DEADLINE_RULES: dict[IncidentClass, dict[str, Any]] = {
    IncidentClass.death: _rule(10, "Proposed day count; lawyer to confirm."),
    IncidentClass.critical_infrastructure: _rule(
        2, "Proposed day count; lawyer to confirm."
    ),
    IncidentClass.widespread_infringement: _rule(
        2, "Proposed day count; lawyer to confirm."
    ),
    IncidentClass.health_harm: _rule(15, "Proposed day count; lawyer to confirm."),
    IncidentClass.fundamental_rights: _rule(
        15, "Proposed day count; lawyer to confirm."
    ),
    IncidentClass.property_environment: _rule(
        15, "Proposed day count; lawyer to confirm."
    ),
    IncidentClass.unclassified: _rule(
        None, "No clock until the incident is classified."
    ),
}
DUE_SOON_HOURS = 24


def deadline_at(record: IncidentRecord) -> datetime | None:
    """``aware_at`` plus the class's days; the clock runs from awareness."""
    days = DEADLINE_RULES[record.incident_class]["days"]
    if days is None:
        return None
    return parse_ts(record.aware_at) + timedelta(days=days)


def _first_authority_notice(record: IncidentRecord) -> datetime | None:
    sent = [
        parse_ts(n.sent_at)
        for n in record.notifications
        if n.kind == PartyKind.authority
    ]
    return min(sent) if sent else None


def deadline_state(record: IncidentRecord, now: datetime) -> str:
    due = deadline_at(record)
    if due is None:
        return "no_clock"
    notified = _first_authority_notice(record)
    if notified is not None:
        return "met" if notified <= due else "notified_late"
    now = _utc(now)
    if now > due:
        return "overdue"
    if due - now <= timedelta(hours=DUE_SOON_HOURS):
        return "due_soon"
    return "open"


def hours_remaining(record: IncidentRecord, now: datetime) -> int | None:
    due = deadline_at(record)
    if due is None or _first_authority_notice(record) is not None:
        return None
    return int((due - _utc(now)).total_seconds() // 3600)


# --- register operations ---------------------------------------------------


def get_incident(register: IncidentRegister, incident_id: str) -> IncidentRecord:
    for rec in register.incidents:
        if rec.id == incident_id:
            return rec
    raise ValueError("unknown incident id")


def declare(
    register: IncidentRegister,
    *,
    system_id: str,
    declared_at: str,
    aware_at: str,
    description: str,
    incident_class: IncidentClass = IncidentClass.unclassified,
) -> IncidentRecord:
    if not description.strip():
        raise ValueError("description must not be empty")
    if parse_ts(aware_at) > parse_ts(declared_at):
        raise ValueError("aware_at must not be after declared_at")
    nums = [
        int(m.group(1))
        for r in register.incidents
        if (m := re.fullmatch(r"INC-(\d+)", r.id))
    ]
    rec = IncidentRecord(
        id=f"INC-{max(nums, default=0) + 1:04d}",
        system_id=system_id,
        declared_at=declared_at,
        aware_at=aware_at,
        incident_class=incident_class,
        description=description,
    )
    register.incidents.append(rec)
    return rec


def classify(
    register: IncidentRegister, incident_id: str, cls: IncidentClass
) -> IncidentRecord:
    rec = get_incident(register, incident_id)
    rec.incident_class = cls
    return rec


def add_notification(
    register: IncidentRegister, incident_id: str, notification: Notification
) -> IncidentRecord:
    rec = get_incident(register, incident_id)
    rec.notifications.append(notification)
    return rec


def close(
    register: IncidentRegister, incident_id: str, closed_at: str, note: str
) -> IncidentRecord:
    rec = get_incident(register, incident_id)
    if rec.closed_at is not None:
        raise ValueError("incident is already closed")
    if parse_ts(closed_at) < parse_ts(rec.declared_at):
        raise ValueError("closed_at must not be before declared_at")
    rec.closed_at = fmt_ts(parse_ts(closed_at))
    rec.closure_note = note
    return rec


def load_register(path: Path) -> IncidentRegister:
    """Missing file is an empty register; a corrupt one raises, never resets."""
    path = Path(path)
    if not path.exists():
        return IncidentRegister()
    try:
        return IncidentRegister.model_validate(json.loads(path.read_bytes()))
    except (ValueError, ValidationError) as exc:
        raise ValueError(f"incident register {path} is unreadable: {exc}") from None


def save_register(path: Path, register: IncidentRegister) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(register.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    os.replace(tmp, path)


# --- contacts and export ---------------------------------------------------


def pending_contacts(
    record: IncidentRecord, contacts: list[IncidentContact]
) -> list[IncidentContact]:
    done = {n.party.casefold() for n in record.notifications}
    return [c for c in contacts if c.party.casefold() not in done]


def _deadline_view(record: IncidentRecord) -> dict[str, Any]:
    rule = DEADLINE_RULES[record.incident_class]
    due = deadline_at(record)
    return {**rule, "deadline_at": None if due is None else fmt_ts(due)}


def render_json(record: IncidentRecord, contacts: list[IncidentContact]) -> str:
    data = {
        "incident": record.model_dump(mode="json"),
        "deadline": _deadline_view(record),
        "pending_contacts": [
            c.model_dump(mode="json") for c in pending_contacts(record, contacts)
        ],
    }
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


def render_markdown(record: IncidentRecord, contacts: list[IncidentContact]) -> str:
    dl = _deadline_view(record)
    out = [
        f"# Incident {record.id}",
        "",
        "## Summary",
        "",
        f"- System: {record.system_id}",
        f"- Declared at: {record.declared_at}",
        f"- Aware at: {record.aware_at}",
        f"- Description: {record.description}",
        "",
        "## Classification",
        "",
        f"- Class: {record.incident_class.value}",
        "",
        "## Deadline",
        "",
    ]
    if dl["deadline_at"] is None:
        out.append("- No deadline clock until the incident is classified.")
    else:
        out += [
            f"- Deadline at: {dl['deadline_at']}",
            f"- Days from awareness: {dl['days']}",
        ]
    out += [
        f"- Source: {dl['source']}",
        f"- Confidence: {dl['confidence']}",
        "- Deadlines are provisional: needs_founder_review",
        "",
        "## Notifications",
        "",
    ]
    if record.notifications:
        out += ["| Party | Kind | Sent at | Ref |", "| --- | --- | --- | --- |"]
        out += [
            f"| {n.party} | {n.kind.value} | {n.sent_at} | {n.ref or ''} |"
            for n in record.notifications
        ]
    else:
        out.append("None recorded.")
    out += ["", "## Pending contacts", ""]
    pending = pending_contacts(record, contacts)
    out += [
        f"- {c.party} ({c.kind.value}) {c.contact or ''}".rstrip() for c in pending
    ] or ["None."]
    out += ["", "## Closure", ""]
    if record.closed_at is None:
        out.append("Not closed.")
    else:
        out += [
            f"- Closed at: {record.closed_at}",
            f"- Note: {record.closure_note or ''}",
        ]
    return "\n".join(out) + "\n"
