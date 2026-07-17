"""Convert a CorroborationReport into SARIF 2.1.0 for GitHub code scanning / GHAS.

Pure export format, read-only — does not alter scan behavior, exit codes, or the
CorroborationReport itself. SARIF `level` is derived from `EvidenceItem.confidence`
(a heuristic, not a compliance verdict — the manifest declaration remains authoritative
per the existing "corroboration only" moat guarantee).
"""

from __future__ import annotations

from opencomplai_core.models import CorroborationReport, EvidenceItem

SARIF_SCHEMA_URI = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
)
SARIF_VERSION = "2.1.0"


def _location_to_sarif(location: str) -> dict:
    if ":" in location:
        path, _, line_str = location.rpartition(":")
        try:
            line = int(line_str)
        except ValueError:
            path, line = location, 1
    else:
        path, line = location, 1
    return {
        "physicalLocation": {
            "artifactLocation": {"uri": path},
            "region": {"startLine": max(line, 1)},
        }
    }


def _sarif_level(confidence: float) -> str:
    if confidence >= 0.8:
        return "warning"
    if confidence >= 0.5:
        return "note"
    return "note"


def _evidence_to_result(item: EvidenceItem) -> dict:
    rule_id = f"{item.detector_id}/{item.category.value}"
    locations = [_location_to_sarif(loc) for loc in item.locations] or [
        _location_to_sarif("unknown:1")
    ]
    return {
        "ruleId": rule_id,
        "level": _sarif_level(item.confidence),
        "message": {
            "text": (
                f"AI signal detected: category={item.category.value}, "
                f"kind={item.evidence_kind.value}, rationale={item.rationale_code} "
                f"(confidence={item.confidence:.2f}). Corroboration only — the declared "
                "manifest intended_purpose remains the authoritative source of truth."
            )
        },
        "locations": locations,
        "properties": {
            "evidence_id": item.evidence_id,
            "scope": item.scope.value,
            "reachability": item.reachability.value,
        },
    }


def _rule_definitions(evidence: list[EvidenceItem]) -> list[dict]:
    seen: dict[str, dict] = {}
    for item in evidence:
        rule_id = f"{item.detector_id}/{item.category.value}"
        if rule_id in seen:
            continue
        seen[rule_id] = {
            "id": rule_id,
            "name": rule_id,
            "shortDescription": {
                "text": f"Opencomplai AI-signal detector: {item.detector_id} ({item.category.value})"
            },
            "helpUri": "https://docs.opencomplai.com/getting-started/quick-start/",
        }
    return list(seen.values())


def report_to_sarif(report: CorroborationReport) -> dict:
    """Convert a CorroborationReport's evidence into a SARIF 2.1.0 document."""
    return {
        "$schema": SARIF_SCHEMA_URI,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "opencomplai",
                        "informationUri": "https://opencomplai.com",
                        "version": report.scanner_version,
                        "rules": _rule_definitions(report.evidence),
                    }
                },
                "results": [_evidence_to_result(item) for item in report.evidence],
            }
        ],
    }
