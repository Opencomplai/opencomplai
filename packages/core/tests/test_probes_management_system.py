"""The management_system probe family: each ref reads Missing, Partial 0.35 or Partial 0.6.

Artifact probes never give Met. A matching file with no marker topics (or an
unfilled scaffold) is Partial 0.35; a short realistic file is Partial 0.6.
"""

from __future__ import annotations

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
    / "management_system.json"
)
UNRELATED = (
    "The garden was quiet and the weather stayed mild for the whole of that long week."
)

# ref -> (path matched by the probe, a short realistic body)
CASES: dict[str, tuple[str, str]] = {
    "scope_statement": (
        "docs/scope-statement.md",
        "# Scope\nThe management system covers the model training pipeline and the "
        "hosted inference service. The boundary is the production cloud account. "
        "Office IT is out of scope and the pilot lab is excluded.\n",
    ),
    "statement_of_applicability": (
        "statement-of-applicability.md",
        "# Statement of applicability\nAccess control is applicable. Justification: "
        "customer data is processed. Implementation status: implemented. Physical "
        "media handling is not applicable, we hold no media.\n",
    ),
    "objectives_record": (
        "docs/objectives.md",
        "# Objectives\nObjective: reduce open high-severity vulnerabilities. Target: "
        "fewer than five by year end, measured monthly. Owner: head of engineering, "
        "due date 2027-03-31.\n",
    ),
    "internal_audit_report": (
        "docs/internal-audit-2026.md",
        "# Internal audit\nAuditor: a staff member from the support team, "
        "independent of the area. Date: 2026-09-15. Findings: two minor observations "
        "on access reviews and one on the change log.\n",
    ),
    "management_review_minutes": (
        "docs/management-review-q3.md",
        "# Management review\nThis management review covered the third quarter. Attendees: the leadership team. Date: 2026-10-02. "
        "Decisions: approve the revised objectives. Actions: schedule a supplier "
        "review before the next meeting.\n",
    ),
    "corrective_action_log": (
        "corrective-action-log.md",
        "# Corrective actions\nNonconformity: access review missed in Q2. Root cause: "
        "no reminder in the calendar. Corrective action: add a recurring task and "
        "check it each quarter.\n",
    ),
    "competence_training_record": (
        "training-record.md",
        "# Training record\nTraining: secure coding course. Date completed: 2026-06-10. "
        "Role: backend engineer. Attendees: four engineers from the platform team.\n",
    ),
}

DOC_FILES = {
    "scope_statement": [
        "docs/scope-statement.md",
        "docs/scope_statement.md",
        "management-system-scope.md",
        "management_system_scope.md",
        "isms-scope.md",
        "isms_scope.md",
        "aims-scope.md",
        "aims_scope.md",
    ],
    "statement_of_applicability": [
        "statement-of-applicability.md",
        "statement_of_applicability.md",
        "soa.md",
        "soa.csv",
    ],
    "objectives_record": [
        "docs/objectives.md",
        "security-objectives.md",
        "security_objectives.md",
        "ai-objectives.md",
        "ai_objectives.md",
    ],
    "internal_audit_report": [
        "docs/internal-audit.md",
        "docs/internal_audit.md",
        "audit-report.md",
        "audit_report.md",
    ],
    "management_review_minutes": [
        "docs/management-review.md",
        "docs/management_review.md",
        "mgmt-review.md",
        "mgmt_review.md",
    ],
    "corrective_action_log": [
        "corrective-action.md",
        "corrective_action.md",
        "capa-log.md",
        "capa_log.md",
        "nonconformities.md",
    ],
    "competence_training_record": [
        "training-record.md",
        "training_record.md",
        "training-log.md",
        "training_log.md",
        "competence-record.md",
        "competence_record.md",
    ],
}


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return root


def test_the_file_parses_and_holds_seven_probes():
    defs = parse_probe_file(PROBE_FILE)
    assert set(defs) == set(CASES)
    assert len(defs) == 7


@pytest.mark.parametrize("ref", sorted(CASES))
def test_every_ref_is_registered(ref: str):
    assert probe_exists(ref)


@pytest.mark.parametrize("ref", sorted(CASES))
def test_provenance_is_a_low_confidence_heuristic(ref: str):
    prov = parse_probe_file(PROBE_FILE)[ref]
    text = repr(prov)
    assert "heuristic (no legal source):" in text
    assert "low" in text


@pytest.mark.parametrize("ref", sorted(CASES))
def test_an_empty_repo_is_missing(tmp_path: Path, ref: str):
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.MISSING


@pytest.mark.parametrize("ref", sorted(CASES))
def test_an_unrelated_sentence_is_partial_035(tmp_path: Path, ref: str):
    rel, _ = CASES[ref]
    row = artifact_gap_status(ref, _write(tmp_path, rel, UNRELATED + "\n"))
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.35


@pytest.mark.parametrize("ref", sorted(CASES))
def test_a_short_realistic_file_is_partial_06_never_met(tmp_path: Path, ref: str):
    rel, body = CASES[ref]
    row = artifact_gap_status(ref, _write(tmp_path, rel, body))
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.6


@pytest.mark.parametrize("ref", sorted(CASES))
def test_a_bare_heading_is_partial_035(tmp_path: Path, ref: str):
    rel, body = CASES[ref]
    heading = body.splitlines()[0] + "\n"
    row = artifact_gap_status(ref, _write(tmp_path, rel, heading))
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.35


@pytest.mark.parametrize(
    ("ref", "rel"), [(r, p) for r, paths in DOC_FILES.items() for p in paths]
)
def test_each_file_name_spelling_is_found(tmp_path: Path, ref: str, rel: str):
    _, body = CASES[ref]
    row = artifact_gap_status(ref, _write(tmp_path, rel, body))
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.6


def test_no_pattern_is_a_bare_markdown_glob():
    raw = PROBE_FILE.read_text(encoding="utf-8")
    assert '"**/*.md"' not in raw
