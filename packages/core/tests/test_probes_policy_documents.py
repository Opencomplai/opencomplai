"""The policy_documents probe family: nine artifact probes read from data.

A matching file whose text holds no marker, or that is a scaffold, is Partial 0.35;
a short realistic file is Partial 0.6; no file is Missing. Never Met.
"""

from __future__ import annotations

from pathlib import Path

import opencomplai_core
import pytest
from opencomplai_core.gap_probes import (
    SCAFFOLD_PLACEHOLDER,
    artifact_gap_status,
    probe_exists,
)
from opencomplai_core.models import GapStatus
from opencomplai_core.probe_registry import parse_probe_file

PROBE_FILE = Path(opencomplai_core.__file__).parent / "probes" / "policy_documents.json"

# ref -> (file name that matches a glob, a short realistic policy)
CASES: dict[str, tuple[str, str]] = {
    "policy_information_security": (
        "docs/policies/information-security.md",
        "# Policy\nThis information security policy sets how the company protects its data.\n"
        "The security lead reviews it every year and reports to the board.\n",
    ),
    "policy_access_control": (
        "docs/policies/access-control.md",
        "# Policy\nAccess is granted on a least privilege basis and reviewed every quarter.\n"
        "Managers approve each request before an account is created.\n",
    ),
    "policy_cryptography": (
        "docs/policies/cryptography.md",
        "# Policy\nData at rest and in transit uses encryption with approved algorithms.\n"
        "Key management is run by the platform team and keys rotate yearly.\n",
    ),
    "policy_backup": (
        "docs/policies/backup.md",
        "# Policy\nBackups run every night and a restore test is carried out each quarter.\n"
        "Backup copies are kept for ninety days before deletion.\n",
    ),
    "policy_change_management": (
        "docs/policies/change-management.md",
        "# Policy\nEvery production change follows change control and needs a reviewer.\n"
        "Emergency changes are recorded and reviewed after the event.\n",
    ),
    "policy_supplier": (
        "docs/policies/supplier.md",
        "# Policy\nEach supplier is assessed before onboarding and again every year.\n"
        "Contracts state the security duties of the vendor and its staff.\n",
    ),
    "policy_acceptable_use": (
        "docs/policies/acceptable-use.md",
        "# Policy\nThis acceptable use policy covers laptops, accounts and the network.\n"
        "Sharing passwords and installing unlicensed software is not allowed.\n",
    ),
    "policy_continuity": (
        "docs/policies/continuity.md",
        "# Policy\nThe continuity plan names the critical services and their recovery goals.\n"
        "Disaster recovery exercises are held once a year with a written report.\n",
    ),
    "policy_ai": (
        "docs/policies/ai-policy.md",
        "# Policy\nEach AI system is registered, owned by a named lead and risk rated.\n"
        "Responsible AI reviews happen before any release to customers.\n",
    ),
}
UNRELATED = "The office kitchen is cleaned every Friday afternoon by the whole team.\n"


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return root


def test_file_parses_with_nine_refs():
    defs = parse_probe_file(PROBE_FILE)
    assert set(defs) == set(CASES)


@pytest.mark.parametrize("ref", CASES)
def test_ref_is_registered(ref: str):
    assert probe_exists(ref)


@pytest.mark.parametrize("ref", CASES)
def test_empty_repo_is_missing(tmp_path: Path, ref: str):
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.MISSING


@pytest.mark.parametrize("ref", CASES)
def test_unrelated_sentence_is_partial_035(tmp_path: Path, ref: str):
    rel, _ = CASES[ref]
    row = artifact_gap_status(ref, _write(tmp_path, rel, UNRELATED))
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.35


@pytest.mark.parametrize("ref", CASES)
def test_unfilled_scaffold_is_partial_035(tmp_path: Path, ref: str):
    rel, text = CASES[ref]
    row = artifact_gap_status(
        ref, _write(tmp_path, rel, text + f"{SCAFFOLD_PLACEHOLDER}\n")
    )
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.35


@pytest.mark.parametrize("ref", CASES)
def test_realistic_file_is_partial_06_never_met(tmp_path: Path, ref: str):
    rel, text = CASES[ref]
    row = artifact_gap_status(ref, _write(tmp_path, rel, text))
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.6


@pytest.mark.parametrize("ref", CASES)
def test_underscore_spelling_and_nested_path(tmp_path: Path, ref: str):
    _, text = CASES[ref]
    name = {
        "policy_information_security": "information_security_policy.md",
        "policy_access_control": "access_control_policy.md",
        "policy_cryptography": "encryption_policy.md",
        "policy_backup": "backup_policy.md",
        "policy_change_management": "change_management_policy.md",
        "policy_supplier": "third_party_policy.md",
        "policy_acceptable_use": "acceptable_use_policy.md",
        "policy_continuity": "business_continuity_policy.md",
        "policy_ai": "responsible_ai_policy.md",
    }[ref]
    row = artifact_gap_status(ref, _write(tmp_path, f"gov/{name}", text))
    assert row.confidence == 0.6
