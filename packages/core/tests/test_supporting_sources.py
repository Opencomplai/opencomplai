"""Supporting artifact sources ("role": "supporting") in build_gap_report.

A supporting probe points at evidence it found and is silent otherwise: it never
lowers a row and never lifts one to Met, and an unattested row stays Unverified.
See ADR-framework-packs.md, 2026-11 amendment, point 7.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core import gap_report as gap_report_module
from opencomplai_core.gap_report import build_gap_report, load_gap_article_map
from opencomplai_core.models import Attestation, ConfidenceLabel, GapStatus

RID = "ACME:REQ-1"
THREAT_MODEL = (
    "# Threat model\n\nAn attacker can use prompt injection in retrieved documents "
    "to make the assistant call tools it should not call.\n"
)
SUPPORTING = {"kind": "artifact", "ref": "ai_threat_model", "role": "supporting"}
ATTESTATION = {"kind": "attestation", "ref": RID}
ATTESTED = {
    RID: Attestation(
        statement="Reviewed by the CISO.",
        attested_by="ciso@example.com",
        attested_at="2026-11-02",
    )
}


def _repo(tmp_path: Path, with_evidence: bool) -> Path:
    if with_evidence:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "threat-model.md").write_text(
            THREAT_MODEL, encoding="utf-8"
        )
    return tmp_path


def _row(sources: list[dict], repo_root: Path | None, attestations=None):
    report = build_gap_report(
        "sys",
        "HEAD",
        repo_root=repo_root,
        requirements={RID: {"sources": sources}},
        attestations=attestations,
    )
    (row,) = report.articles
    return row


def test_met_stays_met_and_names_the_file_in_the_rationale(tmp_path: Path):
    row = _row([ATTESTATION, SUPPORTING], _repo(tmp_path, True), ATTESTED)
    assert row.status == GapStatus.MET
    assert row.source.value == "attestation"
    assert row.evidence_ref == "attestation:ciso@example.com@2026-11-02"
    assert row.rationale == (
        "Reviewed by the CISO. Supporting evidence also found: "
        "docs/threat-model.md (ai_threat_model)."
    )


def test_unverified_stays_unverified_when_the_probe_found_evidence(tmp_path: Path):
    row = _row([ATTESTATION, SUPPORTING], _repo(tmp_path, True))
    # Finding a file is not a verdict, and Unverified never fails a gate.
    assert row.status == GapStatus.UNVERIFIED
    assert row.source.value == "artifact"
    assert row.evidence_ref == "docs/threat-model.md"
    assert row.confidence is None
    assert row.confidence_label == ConfidenceLabel.NOT_ASSESSED
    assert row.rationale.startswith(
        "Evidence found in docs/threat-model.md (ai_threat_model), not attested. "
    )
    assert row.rationale.endswith(
        "No attestation recorded. Add one under "
        "framework_inputs.ACME.attested in the manifest."
    )


@pytest.mark.parametrize("attestations", [None, ATTESTED])
def test_a_probe_that_finds_nothing_changes_nothing(tmp_path: Path, attestations):
    plain = _row([ATTESTATION], None, attestations)
    assert _row([ATTESTATION, SUPPORTING], None, attestations) == plain
    assert _row([ATTESTATION, SUPPORTING], _repo(tmp_path, False), attestations) == (
        plain
    )


def test_missing_and_partial_rows_are_left_alone(tmp_path: Path):
    repo = _repo(tmp_path, True)
    # A primary probe that finds no file is Missing; the supporting file must not hide it.
    primary = {"kind": "artifact", "ref": "risk_register"}
    row = _row([primary, SUPPORTING], repo)
    assert row.status == GapStatus.MISSING
    assert row.evidence_ref == "risk_register"
    # A primary probe that finds a file is Partial; nothing is appended.
    (repo / "risk_register.json").write_text("{}", encoding="utf-8")
    row = _row([primary, SUPPORTING], repo)
    assert row.status == GapStatus.PARTIAL
    assert row.evidence_ref == "risk_register.json"
    assert "Supporting" not in row.rationale


def test_a_row_with_only_a_supporting_source(tmp_path: Path):
    found = _row([SUPPORTING], _repo(tmp_path, True))
    assert found.status == GapStatus.UNVERIFIED
    assert found.source.value == "artifact"
    assert found.evidence_ref == "docs/threat-model.md"
    empty = _row([SUPPORTING], _repo(tmp_path / "empty", False))
    assert empty.status == GapStatus.UNVERIFIED
    assert empty.evidence_ref == "none"


def test_each_supporting_probe_runs_once_per_report(tmp_path: Path, monkeypatch):
    calls: list[str] = []
    real = gap_report_module.supporting_gap_status

    def counting(ref, repo_root):
        calls.append(ref)
        return real(ref, repo_root)

    monkeypatch.setattr(gap_report_module, "supporting_gap_status", counting)
    sources = [ATTESTATION, SUPPORTING]
    requirements = {f"ACME:REQ-{n}": {"sources": sources} for n in range(1, 4)}
    report = build_gap_report(
        "sys", "HEAD", repo_root=_repo(tmp_path, True), requirements=requirements
    )
    assert [row.evidence_ref for row in report.articles] == ["docs/threat-model.md"] * 3
    assert calls == ["ai_threat_model"]


def test_the_eu_ai_act_map_has_no_supporting_sources():
    load_gap_article_map.cache_clear()
    for article, config in load_gap_article_map().items():
        for source in config.get("sources", []):
            assert "role" not in source, article
