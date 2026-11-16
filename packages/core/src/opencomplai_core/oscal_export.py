"""OSCAL 1.1.2 assessment-results export of a compliance artifact.

A pure function of the artifact (no clock, no I/O): one ``results`` entry per
framework, one finding per requirement row. Rows that do not apply or are
excluded sit under ``exclude-controls`` and get no finding. The output is not
validated against the NIST OSCAL schema here.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from typing import Any

OSCAL_VERSION = "1.1.2"
PROP_NS = "https://opencomplai.com/ns/oscal"
EU_KEY = "EU_AI_ACT"
_NO_RATIONALE = "No rationale recorded."
_SATISFIED = "satisfied"
_NOT_SATISFIED = "not-satisfied"
_NON_TOKEN = re.compile(r"[^a-z0-9]+")


def control_token(requirement_id: str) -> str:
    """Lower-case, runs of characters outside a-z and 0-9 become one '-'."""
    return _NON_TOKEN.sub("-", requirement_id.lower()).strip("-")


def _state(status: str) -> str:
    return _SATISFIED if status == "met" else _NOT_SATISFIED


def _prop(name: str, value: Any) -> dict[str, str]:
    return {"name": name, "ns": PROP_NS, "value": str(value)}


def _text(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) and value else default


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _finding(
    row: dict[str, Any], make_uuid: Callable[[str], str], path: str
) -> dict[str, Any]:
    req = _text(row.get("article"))
    status = _enum_value(row.get("status", "unverified"))
    return {
        "uuid": make_uuid(path),
        "title": req,
        "description": _text(row.get("rationale"), _NO_RATIONALE),
        "target": {
            "type": "objective-id",
            "target-id": control_token(req),
            "status": {"state": _state(status)},
        },
        "props": [
            _prop("opencomplai-status", status),
            _prop("requirement-id", req),
            _prop("source", _enum_value(row.get("source", ""))),
            _prop("confidence-label", _enum_value(row.get("confidence_label", ""))),
            _prop("evidence-ref", row.get("evidence_ref", "")),
        ],
    }


def build_assessment_results(artifact: dict[str, Any]) -> dict[str, Any]:
    """Build the OSCAL document; raises ValueError when there is no gap report."""
    gap = artifact.get("gap_report")
    if not isinstance(gap, dict):
        raise ValueError("artifact has no gap report; run check --with-gaps")
    system_id = str(artifact.get("system_id") or gap.get("system_id") or "")
    commit_ref = str(artifact.get("commit_ref") or gap.get("commit_ref") or "")
    stamp = _text(artifact.get("timestamp")) or _text(gap.get("generated_at"))
    version = _text(artifact.get("rule_set_version"))

    def make_uuid(path: str) -> str:
        name = f"opencomplai:{system_id}:{commit_ref}:{path}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, name))

    frameworks: list[tuple[str, str, dict[str, Any], dict[str, str]]] = [
        (EU_KEY, "EU AI Act", gap, {})
    ]
    reports = artifact.get("framework_reports") or {}
    for key in sorted(reports):
        fr = reports[key]
        report = fr.get("report") if isinstance(fr, dict) else None
        if not isinstance(report, dict):
            continue
        frameworks.append(
            (key, _text(fr.get("label"), key), report, dict(fr.get("excluded") or {}))
        )

    results: list[dict[str, Any]] = []
    for key, label, report, excluded in frameworks:
        rpath = f"results/{key}"
        rows = [r for r in report.get("articles") or [] if isinstance(r, dict)]
        skipped = dict(report.get("not_applicable") or {})
        skipped.update(excluded)
        tokens = [control_token(_text(r.get("article"))) for r in rows]
        results.append(
            {
                "uuid": make_uuid(rpath),
                "title": f"{label} assessment",
                "description": (
                    f"{label}: {len(rows)} requirement rows assessed, "
                    f"{len(skipped)} not applicable or excluded."
                ),
                "start": stamp,
                "reviewed-controls": {
                    "control-selections": [
                        {
                            "include-controls": [{"control-id": t} for t in tokens],
                            "exclude-controls": [
                                {"control-id": control_token(rid), "remarks": reason}
                                for rid, reason in sorted(skipped.items())
                            ],
                        }
                    ]
                },
                "findings": [
                    _finding(r, make_uuid, f"{rpath}/findings/{i}")
                    for i, r in enumerate(rows)
                ],
            }
        )

    return {
        "assessment-results": {
            "uuid": make_uuid("assessment-results"),
            "metadata": {
                "title": f"OpenComplAI assessment results for {system_id}",
                "last-modified": stamp,
                "version": version,
                "oscal-version": OSCAL_VERSION,
            },
            "import-ap": {"href": "#no-assessment-plan"},
            "results": results,
        }
    }


def to_json(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"
