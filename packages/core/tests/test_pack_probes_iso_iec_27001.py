"""Pack-local probes of ISO_IEC_27001: plan, inventory, applicability, procedures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.gap_probes import artifact_gap_status, probe_exists
from opencomplai_core.models import GapStatus
from opencomplai_core.probe_registry import parse_probe_file

PROBE_FILE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "opencomplai_core"
    / "packs"
    / "ISO_IEC_27001"
    / "probes.json"
)
PREFIX = "iso_iec_27001"
UNRELATED = "The canteen opens at nine and closes after the afternoon tea round."

# ref -> (matching file, short realistic body)
CASES = {
    "iso_iec_27001.risk_treatment_plan": (
        "docs/risk-treatment-plan.md",
        "Risk R-12, loss of the backup site: we decide to reduce it with a second "
        "region. Owner: head of infrastructure. Due date: 30 June.",
    ),
    "iso_iec_27001.asset_inventory": (
        "docs/asset-inventory.md",
        "Asset: customer database. Owner: data lead. Classification: confidential.",
    ),
    "iso_iec_27001.soa_annex_a": (
        "docs/statement-of-applicability.md",
        "A.5.1 included: policies are needed. A.6.3 included. A.7.2 excluded, no "
        "visitors. A.8.9 included. Justification: risk assessment result.",
    ),
    "iso_iec_27001.operating_procedures": (
        "ops/runbook-db.md",
        "Procedure: restore step 1, step 2. Owner: on-call engineer. Rollback to the "
        "last snapshot, then escalate to the lead.",
    ),
}
REFS = tuple(CASES)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_the_file_parses_with_the_pack_prefix():
    assert tuple(parse_probe_file(PROBE_FILE, prefix=PREFIX)) == REFS


def test_the_file_declares_family_and_provenance():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    assert data["family"] == "iso_iec_27001"
    for ref, probe in data["probes"].items():
        assert ref.startswith(PREFIX + ".")
        assert probe["markers"]["body_only"] is True
        assert probe["markers"]["forbid_scaffold"] is True
        prov = probe["provenance"]
        assert prov["source"].startswith("heuristic (no legal source):")
        assert prov["confidence"] == "low"
        assert prov["needs_founder_review"] is True


def test_every_glob_has_its_twin_and_none_is_bare():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    for probe in data["probes"].values():
        patterns = probe["patterns"]
        assert "**/*.md" not in patterns
        for pat in patterns:
            if "-" in pat:
                assert pat.replace("-", "_") in patterns


def test_pack_lists_the_probe_file():
    pack = PROBE_FILE.with_name("pack.json")
    assert "probes.json" in json.loads(pack.read_text(encoding="utf-8"))["data_files"]


@pytest.mark.parametrize("ref", REFS)
def test_every_ref_exists(ref: str):
    assert probe_exists(ref)


@pytest.mark.parametrize("ref", REFS)
def test_an_empty_repo_is_missing(tmp_path: Path, ref: str):
    assert artifact_gap_status(ref, tmp_path).status == GapStatus.MISSING


@pytest.mark.parametrize("ref", REFS)
def test_one_unrelated_sentence_is_partial_035(tmp_path: Path, ref: str):
    _write(tmp_path, CASES[ref][0], UNRELATED)
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("ref", REFS)
def test_a_short_realistic_file_is_partial_06_never_met(tmp_path: Path, ref: str):
    rel, body = CASES[ref]
    _write(tmp_path, rel, body)
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize(
    "rel",
    [
        "risk-treatment-plan.md",
        "docs/risk_treatment_plan.md",
        "docs/isms/treatment-2026.md",
        "docs/a/isms/risk_treatment.md",
    ],
)
def test_risk_treatment_plan_globs(tmp_path: Path, rel: str):
    ref = "iso_iec_27001.risk_treatment_plan"
    _write(tmp_path, rel, CASES[ref][1])
    assert artifact_gap_status(ref, tmp_path).confidence == pytest.approx(0.6)


@pytest.mark.parametrize(
    "rel",
    [
        "asset-inventory.csv",
        "x/asset_inventory.md",
        "asset-register.md",
        "asset_register.md",
    ],
)
def test_asset_inventory_globs(tmp_path: Path, rel: str):
    ref = "iso_iec_27001.asset_inventory"
    _write(tmp_path, rel, CASES[ref][1])
    assert artifact_gap_status(ref, tmp_path).confidence == pytest.approx(0.6)


def test_an_ordinary_markdown_file_is_not_evidence(tmp_path: Path):
    for ref, (_, body) in CASES.items():
        _write(tmp_path, "README.md", body)
        assert artifact_gap_status(ref, tmp_path).status == GapStatus.MISSING


@pytest.mark.parametrize(
    "rel",
    [
        "statement-of-applicability.md",
        "docs/statement_of_applicability.md",
        "docs/soa-2026.md",
        "docs/a/isms/applicability.md",
    ],
)
def test_soa_globs(tmp_path: Path, rel: str):
    ref = "iso_iec_27001.soa_annex_a"
    _write(tmp_path, rel, CASES[ref][1])
    assert artifact_gap_status(ref, tmp_path).confidence == pytest.approx(0.6)


@pytest.mark.parametrize(
    "rel", ["runbook-db.md", "x/runbook_db.md", "docs/operations/restore-procedure.md"]
)
def test_operating_procedures_globs(tmp_path: Path, rel: str):
    ref = "iso_iec_27001.operating_procedures"
    _write(tmp_path, rel, CASES[ref][1])
    assert artifact_gap_status(ref, tmp_path).confidence == pytest.approx(0.6)
