"""The incident_continuity probe family: what each probe finds and what it must not."""

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
    / "probes"
    / "incident_continuity.json"
)

# ref -> (path of a matching file, a short realistic body)
CASES: dict[str, tuple[str, str]] = {
    "incident_response_plan": (
        "INCIDENT_RESPONSE.md",
        "# Incident response\n\n"
        "The on-call engineer will detect and classify each incident by severity.\n"
        "The incident lead will contain the problem and recover the affected service.\n"
        "Roles are listed in the rota and unresolved cases escalate to the security manager.\n",
    ),
    "incident_notification_template": (
        "docs/incident-notification.md",
        "# Incident notification\n\n"
        "Send the early warning notification to the supervisory authority and to affected\n"
        "customers within 24 hours of becoming aware of the incident.\n"
        "A final report follows within 30 days.\n",
    ),
    "continuity_plan": (
        "docs/disaster-recovery.md",
        "# Continuity plan\n\n"
        "The recovery time objective is four hours and the recovery point objective is one hour.\n"
        "Critical services are the API, the database and the login service.\n"
        "We run a failover exercise every quarter and record the outcome.\n",
    ),
    "restore_test_report": (
        "docs/restore-test.md",
        "# Restore test\n\n"
        "On 2026-03-14 the team ran a full restore of the production database backup.\n"
        "Result: passed, the restore took 42 minutes and the data matched the source.\n",
    ),
}
REFS = tuple(CASES)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_the_file_parses_and_holds_the_four_refs():
    assert set(parse_probe_file(PROBE_FILE)) == set(REFS)


@pytest.mark.parametrize("ref", REFS)
def test_every_ref_is_registered(ref: str):
    assert probe_exists(ref)


def test_globs_have_underscore_twins_and_provenance_is_a_heuristic():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    assert data["family"] == "incident_continuity"
    for ref, spec in data["probes"].items():
        patterns = spec["patterns"]
        assert "**/*.md" not in patterns, ref
        for pat in patterns:
            if "-" in pat:
                assert pat.replace("-", "_") in patterns, (ref, pat)
        prov = spec["provenance"]
        assert prov["source"].startswith("heuristic (no legal source):")
        assert prov["confidence"] == "low"
        assert prov["needs_founder_review"] is True


@pytest.mark.parametrize("ref", REFS)
def test_an_empty_repo_is_missing(tmp_path: Path, ref: str):
    assert artifact_gap_status(ref, tmp_path).status == GapStatus.MISSING


@pytest.mark.parametrize("ref", REFS)
def test_one_unrelated_sentence_is_partial_035(tmp_path: Path, ref: str):
    _write(tmp_path, CASES[ref][0], "The office kitchen is cleaned every Friday.\n")
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.35


@pytest.mark.parametrize("ref", REFS)
def test_an_unfilled_scaffold_is_partial_035(tmp_path: Path, ref: str):
    rel, body = CASES[ref]
    _write(tmp_path, rel, body + "\n_fill in_\n")
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.35


@pytest.mark.parametrize("ref", REFS)
def test_a_short_realistic_file_is_partial_06_never_met(tmp_path: Path, ref: str):
    rel, body = CASES[ref]
    _write(tmp_path, rel, body)
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.6


@pytest.mark.parametrize(
    ("ref", "rel"),
    [
        ("incident_response_plan", "docs/ops/incident_response_plan.md"),
        ("incident_notification_template", "legal/breach_notification.md"),
        ("continuity_plan", "docs/dr/continuity_plan.md"),
        ("restore_test_report", "ops/backup_test_2026.md"),
    ],
)
def test_the_underscore_spelling_is_found(tmp_path: Path, ref: str, rel: str):
    _write(tmp_path, rel, CASES[ref][1])
    assert artifact_gap_status(ref, tmp_path).confidence == 0.6
