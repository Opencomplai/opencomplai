"""
Draft incident templates: report to the authority, notice to downstream parties.

Plain ``{{token}}`` replacement, no clock (E-14). Wording is flagged data
(E-15): low confidence, needs founder review, no deadline day counts, no
authority names, no citation beyond the article pointer in ``source``.
A value that is missing renders ``_not provided_``, never a guess.
"""

from __future__ import annotations

import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "templates" / "incident"
_NOTE = "wording and required content fields not legally reviewed"
_SOURCE = "Regulation (EU) 2024/1689 Art. 73"
MISSING = "_not provided_"

TEMPLATE_META: dict[str, dict] = {
    tid: {
        "source": _SOURCE,
        "confidence": "low",
        "needs_founder_review": True,
        "note": _NOTE,
    }
    for tid in ("authority_report", "downstream_notice")
}

# token -> incident dict key (the operator's summary comes from `description`)
_INCIDENT_FIELDS = {
    "incident_id": "id",
    "system_id": "system_id",
    "incident_class": "incident_class",
    "declared_at": "declared_at",
    "aware_at": "aware_at",
    "summary": "description",
    "corrective_action": "corrective_action",
    "planned_action": "planned_action",
    "contact_name": "contact_name",
    "contact_email": "contact_email",
    "contact_phone": "contact_phone",
}
_PARTY_FIELDS = {"party_name": "name", "party_kind": "kind"}


def _render(template_id: str, values: dict[str, object]) -> str:
    text = (_DIR / f"{template_id}.md").read_text(encoding="utf-8")
    meta = json.dumps(TEMPLATE_META[template_id], sort_keys=True)
    text = text.replace("{{meta}}", meta)
    for token, value in values.items():
        shown = str(value).strip() if value not in (None, "") else ""
        text = text.replace("{{" + token + "}}", shown or MISSING)
    return text


def render_authority_report(incident: dict) -> str:
    return _render(
        "authority_report",
        {tok: incident.get(key) for tok, key in _INCIDENT_FIELDS.items()},
    )


def render_downstream_notice(incident: dict, party: dict) -> str:
    values = {tok: incident.get(key) for tok, key in _INCIDENT_FIELDS.items()}
    values.update({tok: party.get(key) for tok, key in _PARTY_FIELDS.items()})
    return _render("downstream_notice", values)
