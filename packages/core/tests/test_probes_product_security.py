"""The shared `product_security` probe family: what each probe finds, and what it must not.

Artifact probes never give Met: a file with its markers is Partial 0.6, no file is Missing.
"""

from __future__ import annotations

import json
from pathlib import Path

import opencomplai_core
import pytest
from opencomplai_core.gap_probes import artifact_gap_status, probe_exists
from opencomplai_core.models import GapStatus
from opencomplai_core.probe_registry import parse_probe_file

PROBE_FILE = Path(opencomplai_core.__file__).parent / "probes" / "product_security.json"
REFS = (
    "sbom_file",
    "security_policy_file",
    "vulnerability_handling_policy",
    "signed_release_config",
    "update_mechanism_note",
    "secure_defaults_config",
)
UNRELATED = "This page lists the lunch menu and the seating plan for the team outing."

# ref -> (path, a short realistic file)
REAL: dict[str, tuple[str, str]] = {
    "sbom_file": (
        "sbom.json",
        '{"bomFormat": "CycloneDX", "specVersion": "1.5", "components": []}',
    ),
    "security_policy_file": (
        "SECURITY.md",
        "# Security policy\n\n## Reporting a vulnerability\n\n"
        "Please report a vulnerability privately by email to security@example.org "
        "and do not open a public issue.\n",
    ),
    "vulnerability_handling_policy": (
        "docs/vulnerability-handling.md",
        "# Vulnerability handling\n\nWe triage each report and set a severity. "
        "A fix or patch for a high severity issue ships within 30 days of triage.\n",
    ),
    "signed_release_config": (
        ".github/workflows/release.yml",
        "name: release\non: push\njobs:\n  sign:\n    steps:\n"
        "      - run: cosign sign-blob dist/app.tar.gz\n",
    ),
    "update_mechanism_note": (
        "UPDATES.md",
        "# Updates\n\nEach security update is published as a new release. Users get it "
        "with the package manager or by download. Each major version is "
        "supported for 3 years.\n",
    ),
    "secure_defaults_config": (
        "HARDENING.md",
        "# Hardening\n\nBy default the admin console is disabled and the API "
        "requires a token out of the box. Remote access is off until you opt in.\n",
    ),
}
# ref -> (path, content that matches the glob but holds none of the markers)
NO_MARKER_CONFIG = {
    "sbom_file": ("sbom.json", '{"parts": ["bolt", "nut"]}'),
    "signed_release_config": (
        ".github/workflows/ci.yml",
        "name: ci\non: push\njobs:\n  test:\n    steps:\n      - run: pytest\n",
    ),
}
CONFIG_REFS = tuple(NO_MARKER_CONFIG)
DOC_REFS = tuple(r for r in REFS if r not in CONFIG_REFS)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_the_file_parses_with_the_family_and_six_probes():
    parsed = parse_probe_file(PROBE_FILE)
    assert set(parsed) == set(REFS)
    assert (
        json.loads(PROBE_FILE.read_text(encoding="utf-8"))["family"]
        == "product_security"
    )


@pytest.mark.parametrize("ref", REFS)
def test_ref_is_registered(ref: str):
    assert probe_exists(ref)


@pytest.mark.parametrize("ref", REFS)
def test_provenance_is_a_low_confidence_heuristic(ref: str):
    prov = json.loads(PROBE_FILE.read_text(encoding="utf-8"))["probes"][ref][
        "provenance"
    ]
    assert prov["source"].startswith("heuristic (no legal source):")
    assert prov["confidence"] == "low"
    assert prov["needs_founder_review"] is True


@pytest.mark.parametrize("ref", REFS)
def test_every_dash_glob_has_an_underscore_twin_and_none_is_a_bare_markdown_glob(
    ref: str,
):
    patterns = json.loads(PROBE_FILE.read_text(encoding="utf-8"))["probes"][ref][
        "patterns"
    ]
    assert "**/*.md" not in patterns
    for pat in patterns:
        if "-" in pat:
            assert pat.replace("-", "_") in patterns, pat


@pytest.mark.parametrize("ref", REFS)
def test_an_empty_repo_is_missing(tmp_path: Path, ref: str):
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.MISSING


@pytest.mark.parametrize("ref", DOC_REFS)
def test_a_matching_document_with_an_unrelated_sentence_is_partial_035(
    tmp_path: Path, ref: str
):
    _write(tmp_path, REAL[ref][0], UNRELATED + "\n")
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.35


@pytest.mark.parametrize("ref", DOC_REFS)
def test_a_bare_heading_is_partial_035(tmp_path: Path, ref: str):
    _write(tmp_path, REAL[ref][0], "# Title\n")
    row = artifact_gap_status(ref, tmp_path)
    assert (row.status, row.confidence) == (GapStatus.PARTIAL, 0.35)


@pytest.mark.parametrize("ref", CONFIG_REFS)
def test_a_matching_config_file_without_the_marker_is_missing(tmp_path: Path, ref: str):
    rel, text = NO_MARKER_CONFIG[ref]
    _write(tmp_path, rel, text)
    assert artifact_gap_status(ref, tmp_path).status == GapStatus.MISSING


@pytest.mark.parametrize("ref", REFS)
def test_a_short_realistic_file_is_partial_06_never_met(tmp_path: Path, ref: str):
    rel, text = REAL[ref]
    _write(tmp_path, rel, text)
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.6
    assert row.evidence_ref == rel


@pytest.mark.parametrize("ref", DOC_REFS)
def test_an_unfilled_scaffold_is_not_a_policy(tmp_path: Path, ref: str):
    rel, text = REAL[ref]
    _write(tmp_path, rel, text + "\n_fill in_ the rest.\n")
    row = artifact_gap_status(ref, tmp_path)
    assert row.confidence == 0.35
