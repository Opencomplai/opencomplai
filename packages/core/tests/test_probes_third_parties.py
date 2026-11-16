"""The shared third_parties probe family: missing, unfilled and filled documents."""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core.gap_probes import artifact_gap_status, probe_exists
from opencomplai_core.models import GapStatus
from opencomplai_core.probe_registry import parse_probe_file

FILE = Path(__file__).parents[1] / "src/opencomplai_core/probes/third_parties.json"
UNRELATED = (
    "# Notes\n\nThe team meets on Tuesdays to discuss the weather and lunch plans.\n"
)

CASES = {
    "vendor_register": (
        "docs/vendor-register.md",
        "# Vendor register\n\n| Provider | Service | Criticality |\n|---|---|---|\n"
        "| Acme Cloud | Hosting function for the API | High, critical |\n",
    ),
    "contract_checklist": (
        "docs/compliance/contract-checklist.md",
        "# Contract checklist\n\n- Audit and access rights granted to us\n"
        "- Termination and exit assistance defined\n- Security and service level terms agreed\n",
    ),
    "exit_plan": (
        "docs/exit-plan.md",
        "# Exit plan\n\nWe will exit the hosting provider by migrating to an alternative provider.\n"
        "Trigger: repeated outages; timeline: within 90 days of the decision.\n",
    ),
}


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_file_parses_and_refs_exist():
    probes = parse_probe_file(FILE)
    assert set(probes) == set(CASES)
    for ref in CASES:
        assert probe_exists(ref)


@pytest.mark.parametrize("ref", CASES)
def test_empty_repo_is_missing(tmp_path: Path, ref: str):
    assert artifact_gap_status(ref, tmp_path).status == GapStatus.MISSING


@pytest.mark.parametrize("ref", CASES)
def test_unrelated_document_is_partial_035(tmp_path: Path, ref: str):
    rel, _ = CASES[ref]
    _write(tmp_path, rel, UNRELATED)
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("ref", CASES)
def test_realistic_document_is_partial_06(tmp_path: Path, ref: str):
    rel, text = CASES[ref]
    _write(tmp_path, rel, text)
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize("ref", CASES)
def test_underscore_spelling_is_found(tmp_path: Path, ref: str):
    rel, text = CASES[ref]
    _write(tmp_path, rel.replace("-", "_"), text)
    assert artifact_gap_status(ref, tmp_path).confidence == pytest.approx(0.6)
