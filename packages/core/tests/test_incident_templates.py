"""Incident templates: render, missing values, review flags, banner."""

from __future__ import annotations

import re

from opencomplai_core import incident_templates as it

INC = {
    "id": "INC-0007",
    "system_id": "loan-model",
    "incident_class": "health_harm",
    "declared_at": "2026-03-01T10:00:00Z",
    "aware_at": "2026-03-01T08:00:00Z",
    "description": "operator typed summary",
    "corrective_action": "rolled back",
    "planned_action": "retrain",
    "contact_name": "Ada",
    "contact_email": "ada@example.test",
    "contact_phone": "000",
}
PARTY = {"name": "Acme Deploy", "kind": "deployer"}
BANNER = (
    "DRAFT TEMPLATE: not legally reviewed. "
    "Confirm required content and recipient with counsel before sending."
)


def test_authority_report_renders_fields():
    out = it.render_authority_report(INC)
    for v in (
        "INC-0007",
        "loan-model",
        "health_harm",
        "2026-03-01T08:00:00Z",
        "operator typed summary",
        "rolled back",
        "Ada",
    ):
        assert v in out


def test_downstream_notice_renders_fields():
    out = it.render_downstream_notice(INC, PARTY)
    for v in ("Acme Deploy", "deployer", "INC-0007"):
        assert v in out


def test_missing_value_renders_not_provided():
    out = it.render_authority_report({"id": "INC-1"})
    assert out.count(it.MISSING) >= 5
    assert "INC-1" in out
    assert it.MISSING in it.render_downstream_notice({"id": "INC-1"}, {})


def test_template_meta_flags_needs_founder_review():
    assert set(it.TEMPLATE_META) == {"authority_report", "downstream_notice"}
    for meta in it.TEMPLATE_META.values():
        assert meta["confidence"] == "low"
        assert meta["needs_founder_review"] is True
        assert meta["source"]


def test_templates_carry_draft_banner():
    for out in (
        it.render_authority_report(INC),
        it.render_downstream_notice(INC, PARTY),
    ):
        assert out.startswith("> " + BANNER)
        assert '"needs_founder_review": true' in out


def test_render_is_deterministic():
    assert it.render_authority_report(INC) == it.render_authority_report(INC)
    assert it.render_downstream_notice(INC, PARTY) == it.render_downstream_notice(
        INC, PARTY
    )


def test_no_unresolved_placeholders_when_all_fields_given():
    for out in (
        it.render_authority_report(INC),
        it.render_downstream_notice(INC, PARTY),
    ):
        assert not re.search(r"\{\{\w+\}\}", out)
