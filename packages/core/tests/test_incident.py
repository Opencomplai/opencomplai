"""Incident register, deadline clocks, exports and the manifest contacts field."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import opencomplai_core.incident as inc
import pytest
from opencomplai_core.incident import (
    DEADLINE_RULES,
    IncidentClass,
    IncidentContact,
    IncidentRegister,
    Notification,
    PartyKind,
)
from opencomplai_core.models import SystemManifest

AWARE = "2026-03-01T08:00:00Z"
DECLARED = "2026-03-01T10:00:00Z"


def _reg(cls=IncidentClass.critical_infrastructure):
    reg = IncidentRegister()
    inc.declare(
        reg,
        system_id="sys-1",
        declared_at=DECLARED,
        aware_at=AWARE,
        description="model leaked data",
        incident_class=cls,
    )
    return reg


def _notice(sent_at, kind=PartyKind.authority, party="Market Authority"):
    return Notification(party=party, kind=kind, sent_at=sent_at)


def test_register_round_trip_and_sequential_ids(tmp_path: Path):
    reg = _reg()
    inc.declare(
        reg,
        system_id="s",
        declared_at=DECLARED,
        aware_at=DECLARED,
        description="second",
    )
    assert [r.id for r in reg.incidents] == ["INC-0001", "INC-0002"]
    path = tmp_path / "sub" / "incident-register.json"
    inc.save_register(path, reg)
    assert inc.load_register(path) == reg
    assert inc.load_register(tmp_path / "missing.json") == IncidentRegister()


def test_declare_rejects_aware_after_declared_and_empty_description():
    reg = IncidentRegister()
    with pytest.raises(ValueError, match=r"."):
        inc.declare(
            reg, system_id="s", declared_at=AWARE, aware_at=DECLARED, description="x"
        )
    with pytest.raises(ValueError, match=r"."):
        inc.declare(
            reg, system_id="s", declared_at=DECLARED, aware_at=AWARE, description="  "
        )
    with pytest.raises(ValueError, match=r"."):
        inc.declare(
            reg, system_id="s", declared_at="junk", aware_at=AWARE, description="x"
        )
    assert reg.incidents == []


def test_close_rejects_double_close_and_close_before_declare():
    reg = _reg()
    with pytest.raises(ValueError, match=r"."):
        inc.close(reg, "INC-0001", "2026-02-28T00:00:00Z", "n")
    inc.close(reg, "INC-0001", "2026-03-02T00:00:00Z", "fixed")
    assert reg.incidents[0].closed_at == "2026-03-02T00:00:00Z"
    with pytest.raises(ValueError, match=r"."):
        inc.close(reg, "INC-0001", "2026-03-03T00:00:00Z", "again")


def test_unknown_id_raises():
    reg = IncidentRegister()
    for call in (
        lambda: inc.classify(reg, "INC-9", IncidentClass.death),
        lambda: inc.add_notification(reg, "INC-9", _notice(AWARE)),
        lambda: inc.close(reg, "INC-9", AWARE, "n"),
    ):
        with pytest.raises(ValueError, match="unknown incident id"):
            call()


def test_corrupt_register_raises_not_resets(tmp_path: Path):
    p = tmp_path / "r.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match=r"."):
        inc.load_register(p)
    p.write_text(
        json.dumps({"version": 1, "incidents": [{"id": "x"}]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match=r"."):
        inc.load_register(p)
    assert p.read_text(encoding="utf-8").startswith('{"version"')


def test_save_is_byte_deterministic(tmp_path: Path):
    reg = _reg()
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    inc.save_register(a, reg)
    inc.save_register(b, reg)
    assert a.read_bytes() == b.read_bytes()
    assert a.read_bytes().endswith(b"}\n")
    assert b"\r" not in a.read_bytes()


def test_deadline_state_transitions_with_injected_now():
    rec = _reg().incidents[0]  # 2 days from aware: due 2026-03-03T08:00Z
    due = inc.parse_ts("2026-03-03T08:00:00Z")
    assert inc.deadline_at(rec) == due
    assert inc.deadline_state(rec, due - timedelta(days=1, hours=1)) == "open"
    assert inc.deadline_state(rec, due - timedelta(hours=23)) == "due_soon"
    assert inc.hours_remaining(rec, due - timedelta(hours=23)) == 23
    assert inc.deadline_state(rec, due + timedelta(hours=1)) == "overdue"
    assert inc.hours_remaining(rec, due + timedelta(minutes=30)) == -1
    # a closed incident still evaluates
    inc.close(
        IncidentRegister(incidents=[rec]), "INC-0001", "2026-03-10T00:00:00Z", "n"
    )
    assert inc.deadline_state(rec, due + timedelta(days=30)) == "overdue"
    inc.add_notification(
        IncidentRegister(incidents=[rec]), "INC-0001", _notice(fmt(due))
    )
    assert inc.deadline_state(rec, due + timedelta(days=30)) == "met"
    assert inc.hours_remaining(rec, due) is None
    rec.notifications.clear()
    rec.notifications.append(_notice(fmt(due + timedelta(minutes=1))))
    assert inc.deadline_state(rec, due) == "notified_late"


def fmt(dt: datetime) -> str:
    return inc.fmt_ts(dt)


def test_deadline_runs_from_aware_not_declared():
    rec = _reg(IncidentClass.death).incidents[0]
    assert inc.deadline_at(rec) == datetime(2026, 3, 11, 8, 0, tzinfo=UTC)


def test_deadline_days_per_class_are_flagged_data():
    assert set(DEADLINE_RULES) == set(IncidentClass)
    for rule in DEADLINE_RULES.values():
        assert rule["source"]
        assert rule["confidence"]
        assert rule["note"]
        assert rule["needs_founder_review"] is True


def test_unclassified_has_no_clock():
    rec = _reg(IncidentClass.unclassified).incidents[0]
    now = datetime(2030, 1, 1, tzinfo=UTC)
    assert inc.deadline_at(rec) is None
    assert inc.deadline_state(rec, now) == "no_clock"
    assert inc.hours_remaining(rec, now) is None


def test_incident_module_never_reads_the_clock():
    src = Path(inc.__file__).read_text(encoding="utf-8")
    for needle in ("datetime.now", "utcnow", "time.time", "date.today"):
        assert needle not in src


def _contacts():
    return [
        IncidentContact(
            kind=PartyKind.authority, party="Market Authority", contact="a@x.eu"
        ),
        IncidentContact(kind=PartyKind.deployer, party="Acme Bank"),
    ]


def test_pending_contacts_excludes_notified_parties():
    rec = _reg().incidents[0]
    rec.notifications.append(_notice(DECLARED, party="market authority"))
    assert [c.party for c in inc.pending_contacts(rec, _contacts())] == ["Acme Bank"]


def test_markdown_export_has_no_relative_or_current_dates():
    rec = _reg().incidents[0]
    rec.notifications.append(_notice(DECLARED))
    md = inc.render_markdown(rec, _contacts())
    assert not re.search(r"\bago\b|\bin \d+ days\b|today|overdue", md, re.I)
    assert "2026-03-03T08:00:00Z" in md


def test_export_is_deterministic():
    rec = _reg().incidents[0]
    assert inc.render_markdown(rec, _contacts()) == inc.render_markdown(
        rec, _contacts()
    )
    assert inc.render_json(rec, _contacts()) == inc.render_json(rec, _contacts())
    assert json.loads(inc.render_json(rec, _contacts()))["deadline"]["days"] == 2


def test_export_lists_review_flag():
    rec = _reg().incidents[0]
    assert "needs_founder_review" in inc.render_markdown(rec, [])
    assert (
        json.loads(inc.render_json(rec, []))["deadline"]["needs_founder_review"] is True
    )


def _manifest(**extra):
    return {"system_id": "s", "intended_purpose": "p", **extra}


def test_manifest_without_contacts_serialises_to_identical_bytes():
    m = SystemManifest.model_validate(_manifest())
    assert "incident_contacts" not in m.model_dump()
    assert "incident_contacts" not in m.model_dump(mode="json")
    assert "incident_contacts" not in m.model_dump_json()


def test_manifest_contacts_round_trip():
    raw = _manifest(
        incident_contacts=[{"kind": "authority", "party": "MA", "contact": "x"}]
    )
    m = SystemManifest.model_validate(raw)
    assert m.incident_contacts[0].kind is PartyKind.authority
    again = SystemManifest.model_validate_json(m.model_dump_json())
    assert again.incident_contacts == m.incident_contacts


def test_manifest_rejects_bad_contact_kind():
    with pytest.raises(ValueError, match=r"."):
        SystemManifest.model_validate(
            _manifest(incident_contacts=[{"kind": "regulator", "party": "MA"}])
        )
