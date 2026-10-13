"""The proposal_leads tier is a pointer for a person, never a finding.

The ADR, the closed schema, the signed-artifact guard and the scan summary field
are checked here: a lead has no finding fields and changes no hash, count,
proposal, SARIF output or artifact.
"""

from __future__ import annotations

import json
import re
import typing
from pathlib import Path
from typing import Any

import opencomplai_core
import pytest
import yaml
from jsonschema import Draft202012Validator
from opencomplai_core.json_schemas import build_artifact_schema
from opencomplai_core.models import (
    CorroborationReport,
    EuAiProposalLead,
    EuAiRegulatoryFinding,
    EuAiScanSummary,
    ScanStatusArtifact,
    ScanSummary,
)
from opencomplai_core.scanner._hashing import report_hash
from opencomplai_core.scanner.proposal import build_classification_proposal
from opencomplai_core.scanner.sarif import report_to_sarif
from pydantic import BaseModel

_ROOT = Path(__file__).resolve().parents[3]
_ADR = _ROOT / "docs" / "src" / "architecture" / "adr-proposal-leads.md"
_NAV = _ROOT / "docs" / "mkdocs.yml"
_SCHEMA = (
    Path(opencomplai_core.__file__).parent / "schemas" / "proposal_leads.schema.json"
)
_OPENAPI = _ROOT / "services" / "gateway-api" / "openapi.yaml"

_BANNED_IN_PUBLIC_TEXT = re.compile(
    r"V1[3][- ]|\bV-[D]\d|Saa[S]|dashboar[d]|tenan[t]", re.I
)
_FINDING_FIELDS = ("risk_tier", "severity", "eu_obligation", "rationale", "explanation")


def _lead(**over: Any) -> dict[str, Any]:
    lead: dict[str, Any] = {
        "reason": "deterministic_matcher",
        "file": "src/screening/rank.py",
        "line": 42,
        "function": "rank_candidates",
        "annex_iii_area": 4,
        "confidence_band": "medium",
        "signals": ["rank_candidates", "applicant"],
    }
    lead.update(over)
    return lead


def _without_file() -> dict[str, Any]:
    lead = _lead()
    del lead["file"]
    return lead


def _schema() -> dict[str, Any]:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _finding(location: str, area: int | None = 4) -> EuAiRegulatoryFinding:
    return EuAiRegulatoryFinding(
        location=location,
        function="rank_candidates",
        risk_tier="high_risk",
        annex_iii_area=area,
    )


def _report(summary: EuAiScanSummary) -> CorroborationReport:
    return CorroborationReport.model_validate(
        {
            "scan_id": "scan-1",
            "system_id": "test-sys",
            "commit_ref": "HEAD",
            "scanner_version": "0.1.0",
            "input_digest": "sha256:abc",
            "config_hash": "sha256:def",
            "detector_versions": {},
            "declared_purpose": "customer support chatbot",
            "declared_categories": [],
            "evidence": [],
            "findings": [],
            "detected_categories": ["scoring_profiling"],
            "discrepancies": ["scoring_profiling"],
            "score_breakdown": {},
            "severity": "major",
            "feature_summary": {},
            "cache_summary": {},
            "skipped_paths": [],
            "limits_hit": [],
            "warnings": [],
            "detector_errors": [],
            "baseline_ref": None,
            "generated_at": "2026-07-11T00:00:00Z",
            "report_hash": "sha256:ghi",
            "eu_ai_scan": summary.model_dump(),
        }
    )


def _summary(with_leads: bool) -> EuAiScanSummary:
    return EuAiScanSummary.model_validate(
        {
            "high_risk": [_finding("src/a.py:10").model_dump()],
            "gated_callsite_count": 1,
            "regulatory_finding_count": 1,
            "proposal_leads": (
                [_lead(), _lead(annex_iii_area=5, line=7)] if with_leads else []
            ),
        }
    )


def _field_names(model: type[BaseModel], seen: set[type] | None = None) -> set[str]:
    """Every field name of a model and of the models nested inside it."""
    seen = seen if seen is not None else set()
    if model in seen:
        return set()
    seen.add(model)
    names = set(model.model_fields)
    for info in model.model_fields.values():
        stack = [info.annotation]
        while stack:
            ann = stack.pop()
            stack.extend(typing.get_args(ann))
            if isinstance(ann, type) and issubclass(ann, BaseModel):
                names |= _field_names(ann, seen)
    return names


def test_adr_exists_and_is_in_nav() -> None:
    assert _ADR.is_file()
    rows = _NAV.read_text(encoding="utf-8").splitlines()
    assert any(r.rstrip().endswith("architecture/adr-proposal-leads.md") for r in rows)


def test_adr_states_the_tier_rules() -> None:
    text = _ADR.read_text(encoding="utf-8")
    for needle in (
        "proposal_leads",
        "compliance-artifact.json",
        "exit code",
        "73.3%",
        "needs_founder_review",
    ):
        assert needle in text, needle
    assert _BANNED_IN_PUBLIC_TEXT.search(text) is None
    assert "**Status:** Accepted" in text
    assert "produces `low` and `medium` only" in text
    assert "before the producer exists" not in text


def test_public_pages_state_bands_and_area_seven() -> None:
    scan = (_ROOT / "docs" / "src" / "cli" / "scan.md").read_text(encoding="utf-8")
    assert "produces `low` and `medium` only" in scan
    assert "run `scan --propose` and `accept --proposal` once" in scan
    bench = (_ROOT / "docs" / "src" / "concepts" / "annex-iii-benchmark.md").read_text(
        encoding="utf-8"
    )
    assert "areas 3, 4, 5, 6 and 8; area 7 is notice only" in bench


def test_schema_is_valid_and_closed() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    lead = schema["$defs"]["lead"]
    assert lead["additionalProperties"] is False
    assert set(lead["required"]) == set(lead["properties"])
    for name in _FINDING_FIELDS:
        assert name not in lead["properties"], name


def test_schema_accepts_a_lead() -> None:
    validator = Draft202012Validator(_schema())
    validator.validate([])
    for area in range(1, 9):
        validator.validate([_lead(annex_iii_area=area)])


@pytest.mark.parametrize(
    "bad",
    [
        _lead(risk_tier="high_risk"),
        _lead(severity="major"),
        _lead(line=0),
        _lead(annex_iii_area=0),
        _lead(annex_iii_area=9),
        _lead(confidence_band="critical"),
        _lead(reason="imported_not_classified"),
        _without_file(),
    ],
    ids=[
        "risk_tier",
        "severity",
        "line_0",
        "area_0",
        "area_9",
        "band_critical",
        "candidate_reason",
        "missing_file",
    ],
)
def test_schema_rejects_finding_shaped_leads(bad: dict[str, Any]) -> None:
    assert not Draft202012Validator(_schema()).is_valid([bad])


def test_signed_artifact_models_and_schema_have_no_leads() -> None:
    for model in (ScanStatusArtifact, ScanSummary):
        assert "proposal_leads" not in _field_names(model), model.__name__
    assert "proposal_leads" not in json.dumps(build_artifact_schema())


def test_summary_declares_proposal_leads() -> None:
    assert "proposal_leads" in EuAiScanSummary.model_fields
    assert EuAiScanSummary().model_dump()["proposal_leads"] == []


def test_leads_do_not_change_report_hash_or_counts() -> None:
    assert "proposal_leads" in EuAiScanSummary.model_fields
    plain = _report(_summary(with_leads=False))
    led = _report(_summary(with_leads=True))
    assert led.eu_ai_scan is not None
    assert plain.eu_ai_scan is not None
    assert len(led.eu_ai_scan.model_dump()["proposal_leads"]) == 2
    assert report_hash(led) == report_hash(plain)
    assert (
        led.eu_ai_scan.regulatory_finding_count
        == plain.eu_ai_scan.regulatory_finding_count
        == 1
    )
    assert led.severity == plain.severity
    assert led.detected_categories == plain.detected_categories
    assert led.discrepancies == plain.discrepancies


def test_leads_never_enter_the_proposal() -> None:
    assert "proposal_leads" in EuAiScanSummary.model_fields
    assert (
        build_classification_proposal(_summary(True)).model_dump()
        == build_classification_proposal(_summary(False)).model_dump()
    )


def test_sarif_ignores_leads() -> None:
    assert "proposal_leads" in EuAiScanSummary.model_fields
    assert report_to_sarif(_report(_summary(True))) == report_to_sarif(
        _report(_summary(False))
    )


def test_entries_validate_against_the_schema() -> None:
    assert "proposal_leads" in EuAiScanSummary.model_fields
    summary = EuAiScanSummary.model_validate({"proposal_leads": [_lead()]})
    entries = summary.model_dump()["proposal_leads"]
    assert len(entries) == 1
    Draft202012Validator(_schema()).validate(entries)
    assert set(entries[0]) == set(_schema()["$defs"]["lead"]["properties"])


def test_model_matches_the_schema() -> None:
    lead = _schema()["$defs"]["lead"]
    assert set(EuAiProposalLead.model_fields) == set(lead["properties"])
    assert set(lead["required"]) == set(lead["properties"])
    assert list(EuAiScanSummary.model_fields)[-1] == "proposal_leads"


def test_openapi_proposal_lead_schema_matches_models() -> None:
    if not _OPENAPI.exists():
        pytest.skip("gateway openapi.yaml not present in this checkout")
    schemas = yaml.safe_load(_OPENAPI.read_text(encoding="utf-8"))["components"][
        "schemas"
    ]
    lead = schemas["EuAiProposalLead"]
    assert set(lead["properties"]) == set(EuAiProposalLead.model_fields)
    assert set(lead["required"]) == set(EuAiProposalLead.model_fields)
    assert lead["additionalProperties"] is False
    assert lead["properties"]["reason"]["enum"] == ["deterministic_matcher"]
    assert lead["properties"]["confidence_band"]["enum"] == ["low", "medium", "high"]
    assert lead["properties"]["line"]["minimum"] == 1
    assert lead["properties"]["annex_iii_area"]["minimum"] == 1
    assert lead["properties"]["annex_iii_area"]["maximum"] == 8
    summary = schemas["EuAiScanSummary"]["properties"]["proposal_leads"]
    assert summary["type"] == "array"
    assert summary["items"]["$ref"] == "#/components/schemas/EuAiProposalLead"
