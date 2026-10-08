"""The native ISO/IEC 42001 pack: attestation-led, flagged data, no new enum member."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from opencomplai_core.control_catalog import get_catalog
from opencomplai_core.frameworks import (
    EU_AI_ACT,
    FRAMEWORKS,
    data_version,
    evaluate_targets,
    load_requirements_map,
)
from opencomplai_core.gap_probes import artifact_gap_status
from opencomplai_core.gap_report import STATUS_SEVERITY
from opencomplai_core.models import (
    Attestation,
    ComplianceTarget,
    ConfidenceLabel,
    FrameworkInputs,
    GapStatus,
    SystemManifest,
)

ISO = "ISO_IEC_42001"
_REPO = Path(__file__).resolve().parents[3]
_PACK = FRAMEWORKS[ISO]

_CLAUSES = (
    "4.1 4.2 4.3 4.4 5.1 5.2 5.3 6.1.1 6.1.2 6.1.3 6.1.4 6.2 6.3 7.1 7.2 7.3 7.4 7.5 "
    "8.1 8.2 8.3 8.4 9.1 9.2 9.3 10.1 10.2"
).split()
_CONTROLS = (
    "A.2.2 A.2.3 A.2.4 A.3.2 A.3.3 A.4.2 A.4.3 A.4.4 A.4.5 A.4.6 A.5.2 A.5.3 A.5.4 "
    "A.5.5 A.6.1.2 A.6.1.3 A.6.2.2 A.6.2.3 A.6.2.4 A.6.2.5 A.6.2.6 A.6.2.7 A.6.2.8 "
    "A.7.2 A.7.3 A.7.4 A.7.5 A.7.6 A.8.2 A.8.3 A.8.4 A.8.5 A.9.2 A.9.3 A.9.4 "
    "A.10.2 A.10.3 A.10.4"
).split()
IDS = {f"{ISO}:Clause {c}" for c in _CLAUSES} | {f"{ISO}:{c}" for c in _CONTROLS}

PROBE_BACKED = {
    f"{ISO}:Clause 6.1.2": "risk_register",
    f"{ISO}:Clause 6.1.3": "risk_register",
    f"{ISO}:A.8.2": "deployer_instructions",
    f"{ISO}:A.6.2.7": "provider_qms_bundle",
}


def _rows() -> dict[str, dict]:
    return load_requirements_map(_PACK.requirements)


def _manifest(**overrides: object) -> SystemManifest:
    return SystemManifest(
        system_id="sys", intended_purpose="credit scoring", **overrides
    )


def _attest(*ids: str) -> dict[str, FrameworkInputs]:
    attested = {
        i: Attestation(
            statement="Approved by the board.",
            attested_by="jane@example.com",
            attested_at="2026-09-01",
        )
        for i in ids
    }
    return {ISO: FrameworkInputs(attested=attested)}


def _report(manifest: SystemManifest, repo: Path | None = None):
    return evaluate_targets(manifest, [ISO], commit_ref="HEAD", repo_root=repo)[ISO]


def test_every_row_is_flagged_data():
    rows = _rows()
    assert set(rows) == IDS
    assert len(IDS) == 65
    assert sum(r.startswith(f"{ISO}:Clause ") for r in rows) == 27
    assert sum(r.startswith(f"{ISO}:A.") for r in rows) == 38
    for rid, row in rows.items():
        assert row["source"].strip(), rid
        assert row["confidence"] in {"low", "medium"}, rid
        assert row["needs_founder_review"] is True, rid


def test_rows_are_attestation_led():
    rows = _rows()
    artifact_rows = {}
    for rid, row in rows.items():
        kinds = {s["kind"] for s in row["sources"]}
        assert not kinds & {"rule", "obligation", "scan", "evaluator"}, rid
        assert {"kind": "attestation", "ref": rid} in row["sources"], rid
        for s in row["sources"]:
            if s["kind"] == "artifact":
                artifact_rows[rid] = s["ref"]
    assert artifact_rows == PROBE_BACKED
    assert sum(len(r["sources"]) == 1 for r in rows.values()) >= 60


def test_without_evidence_everything_is_unverified():
    report = _report(_manifest())
    assert report.derived_from is None
    assert report.disclaimer_ref == "DISCLAIMER_V2"
    rows = report.report.articles
    assert len(rows) == 65
    assert {r.status for r in rows} == {GapStatus.UNVERIFIED}
    assert all(r.article.startswith(f"{ISO}:") for r in rows)


def test_attestation_makes_an_attestation_only_row_met():
    rid = f"{ISO}:Clause 5.2"
    report = _report(_manifest(framework_inputs=_attest(rid)))
    row = {r.article: r for r in report.report.articles}[rid]
    assert row.status == GapStatus.MET
    assert row.confidence_label == ConfidenceLabel.ATTESTED
    with pytest.raises(ValueError, match="Clause 99"):
        _report(_manifest(framework_inputs=_attest(f"{ISO}:Clause 99")))


def test_probe_backed_row_stays_below_met_on_a_file_alone(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "risk_register.md").write_text(
        "# Risk register\n\nIdentified risks: biased scoring.\n"
        "Mitigation: quarterly review; residual risk accepted.\n",
        encoding="utf-8",
    )
    rid = f"{ISO}:Clause 6.1.2"
    report = _report(_manifest(framework_inputs=_attest(rid)), tmp_path)
    status = {r.article: r for r in report.report.articles}[rid].status
    probe = artifact_gap_status("risk_register", tmp_path).status
    # The attestation reads Met, so the worse of the two is the probe's status.
    assert STATUS_SEVERITY[status] == max(
        STATUS_SEVERITY[probe], STATUS_SEVERITY[GapStatus.MET]
    )
    # A file alone, without the attestation, never reads Met either.
    alone = {r.article: r for r in _report(_manifest(), tmp_path).report.articles}
    assert alone[rid].status != GapStatus.MET


def test_exclusion_moves_row_to_excluded_and_creates_waived_control():
    rid = f"{ISO}:Clause 4.3"
    inputs = {ISO: FrameworkInputs(excluded={rid: "Scope set by the parent AIMS."})}
    report = _report(_manifest(framework_inputs=inputs))
    assert rid not in {r.article for r in report.report.articles}
    assert report.excluded == {rid: "Scope set by the parent AIMS."}


def test_catalog_has_iso_entries():
    catalog = get_catalog()
    assert catalog[f"{ISO}:A.2.2"].title == "AI policy"
    assert catalog[f"{ISO}:A.2.2"].default_ttl_days == 365
    assert "Art. 9" in catalog


def test_compliance_target_enum_unchanged():
    assert {m.value for m in ComplianceTarget} == {"EU_AI_ACT", "NIST_AI_RMF"}


def test_adr_records_iso_42001_amendment():
    text = (_REPO / "docs" / "adr" / "ADR-framework-packs.md").read_text("utf-8")
    amendment = re.search(
        r"^## Amendment 2026-10 \(E-13\)$(.*?)(?=^## |\Z)", text, re.S | re.M
    )
    assert amendment
    assert ISO in amendment.group(1)
    assert "iso_42001.json" in amendment.group(1)
    status = next(ln for ln in text.splitlines() if ln.startswith("**Status:**"))
    assert "amended 2026-10" in status
    scope = text.split("## Out of scope", 1)[1]
    assert "ISO/IEC 42001" not in scope
    assert "Colorado" in scope


def test_eu_and_nist_data_versions_unchanged_by_registration():
    for key in (EU_AI_ACT, "NIST_AI_RMF"):
        pack = FRAMEWORKS[key]
        paths = ([pack.requirements] if pack.requirements else []) + list(
            pack.data_files
        )
        assert all("iso_42001" not in p.name for p in paths)
        blob = json.dumps(
            [json.loads(p.read_text(encoding="utf-8")) for p in paths],
            sort_keys=True,
        ).encode("utf-8")
        assert data_version(pack) == hashlib.sha256(blob).hexdigest()[:12]
