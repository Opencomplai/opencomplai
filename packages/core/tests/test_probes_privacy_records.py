"""The privacy_records probe family: Missing, Partial 0.35 and Partial 0.6 per probe."""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core import gap_probes
from opencomplai_core.gap_probes import artifact_gap_status, probe_exists
from opencomplai_core.models import GapStatus
from opencomplai_core.probe_registry import parse_probe_file

PROBE_FILE = Path(gap_probes.__file__).parent / "probes" / "privacy_records.json"

THIN = "This file exists but says nothing that bears on the topic at hand today.\n"

CASES = {
    "dpia_document": (
        "DPIA.md",
        "# DPIA\n\nThe processing is necessary and proportionate to the stated aim.\n"
        "The main risk to individuals is unwanted disclosure of their records.\n"
        "Measures: encryption at rest and role based access for the support team.\n",
    ),
    "record_of_processing": (
        "docs/ropa.md",
        "# Record of processing\n\nPurpose: customer support and billing for accounts.\n"
        "Data subjects: customers. Categories of data: name, email, invoices.\n"
        "Recipients: the payment provider. Retention: six years after closure.\n",
    ),
    "privacy_notice": (
        "PRIVACY.md",
        "# Privacy\n\nThe controller is Example Ltd and you can contact privacy@example.org.\n"
        "We use your data for the purpose of running your account, on a contract basis.\n"
        "You have rights of access, erasure and rectification over your data.\n",
    ),
    "data_subject_request_procedure": (
        "docs/dsar.md",
        "# Requests\n\nA person may ask for access, erasure or rectification of their data.\n"
        "We answer within one month of receiving the request in writing.\n"
        "Staff verify the identity of the requester before any data is released.\n",
    ),
    "processor_register": (
        "docs/processor-register.md",
        "# Processors\n\nProcessor: Hostco provides cloud hosting for the product.\n"
        "Agreement: a signed data processing agreement is held on file for them.\n"
        "Location: servers sit in Ireland, with no transfer outside the region.\n",
    ),
    "breach_register": (
        "docs/breach-register.md",
        "# Breach register\n\nBreach 1: a laptop with customer exports was lost on a train.\n"
        "Date detected: 2026-02-03 by the finance team during a routine stock check.\n"
        "Notification: the supervisory authority was notified the next working day.\n",
    ),
    "transfer_record": (
        "docs/transfer-impact.md",
        "# Transfer impact\n\nThe transfer of support tickets goes to a vendor in a third country.\n"
        "Safeguard: standard contractual clauses are signed and a risk review is kept.\n",
    ),
}


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_file_parses_and_has_seven_probes():
    probes = parse_probe_file(PROBE_FILE)
    assert set(probes) == set(CASES)


@pytest.mark.parametrize("ref", CASES)
def test_ref_is_registered(ref: str):
    assert probe_exists(ref)


@pytest.mark.parametrize("ref", CASES)
def test_empty_repo_is_missing(tmp_path: Path, ref: str):
    assert artifact_gap_status(ref, tmp_path).status == GapStatus.MISSING


@pytest.mark.parametrize("ref", CASES)
def test_unrelated_sentence_is_partial_035(tmp_path: Path, ref: str):
    _write(tmp_path, CASES[ref][0], THIN)
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.35


@pytest.mark.parametrize("ref", CASES)
def test_realistic_file_is_partial_06(tmp_path: Path, ref: str):
    _write(tmp_path, *CASES[ref])
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.6


@pytest.mark.parametrize("ref", CASES)
def test_underscore_spelling_is_found(tmp_path: Path, ref: str):
    rel, text = CASES[ref]
    if "-" not in rel:
        pytest.skip("no hyphenated path")
    _write(tmp_path, rel.replace("-", "_"), text)
    assert artifact_gap_status(ref, tmp_path).confidence == 0.6
