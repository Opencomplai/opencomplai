"""Pack-local probes of CRA: Annex VII technical documentation read point by point."""

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
    / "CRA"
    / "probes.json"
)
PREFIX = "cra"
REF = "cra.technical_documentation"
UNRELATED = "The canteen opens at nine and closes after the afternoon tea round."

CLAUSE_IDS = ("1", "2", "3", "4", "5", "6", "7", "8")

UI_REF = "cra.user_information"
SUPPORT_REF = "cra.support_period_statement"
NOTIFY_REF = "cra.vulnerability_notification_record"

# clause id -> a short realistic section body
REALISTIC = {
    "1": "This product is a smart thermostat; the overview lists its intended purpose, hardware, firmware and the users it serves.",
    "2": "The secure development lifecycle covers design reviews, and vulnerability disclosure leads to a patch in the next update.",
    "3": "Our risk assessment lists each threat, with the likelihood and severity of harm and the measures chosen to mitigate it.",
    "4": "The support period is five years, based on the expected use of the product and its lifetime in homes.",
    "5": "We applied the harmonised standards named here and followed a published specification for each solution we adopted.",
    "6": "The penetration test report is attached and its findings were closed; all functional tests passed before release.",
    "7": "A signed copy of the declaration of conformity is enclosed, dated with the release and issued by the manufacturer.",
    "8": "The software bill of materials lists every component and dependency in SPDX form, which is machine-readable.",
}


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _document(bodies: dict[str, str]) -> str:
    return "\n".join(f"<!-- clause: {c} -->\n{t}\n" for c, t in bodies.items())


def test_the_file_parses_with_the_pack_prefix():
    parsed = parse_probe_file(PROBE_FILE, prefix=PREFIX)
    assert tuple(parsed) == (REF, UI_REF, SUPPORT_REF, NOTIFY_REF)


def test_the_file_declares_the_family_and_every_clause():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))
    assert data["family"] == "cra"
    probe = data["probes"][REF]
    assert probe["type"] == "clause_document"
    assert tuple(probe["clauses"]) == CLAUSE_IDS
    prov = probe["provenance"]
    assert prov["source"].startswith("heuristic (no legal source):")
    assert prov["confidence"] == "low"
    assert prov["needs_founder_review"] is True


def test_every_glob_has_its_underscore_or_hyphen_twin_and_none_is_bare():
    patterns = json.loads(PROBE_FILE.read_text(encoding="utf-8"))["probes"][REF][
        "patterns"
    ]
    assert "**/*.md" not in patterns
    for pat in patterns:
        if "-" in pat:
            assert pat.replace("-", "_") in patterns


def test_the_ref_and_every_clause_ref_exist():
    assert probe_exists(REF)
    for clause in CLAUSE_IDS:
        assert probe_exists(f"{REF}#{clause}")
    assert not probe_exists(f"{REF}#99")


def test_realistic_text_covers_every_clause():
    assert tuple(REALISTIC) == CLAUSE_IDS


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_an_empty_repo_is_missing(tmp_path: Path, clause: str):
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.MISSING


def test_an_empty_repo_is_missing_for_the_whole_document(tmp_path: Path):
    # the bare ref is Partial with a count when the file is absent only if rows say so
    row = artifact_gap_status(REF, tmp_path)
    assert row.status != GapStatus.MET


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_a_section_with_one_unrelated_sentence_is_partial_035(
    tmp_path: Path, clause: str
):
    _write(tmp_path, "CRA_TECHNICAL_DOCUMENTATION.md", _document({clause: UNRELATED}))
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_a_file_without_the_clause_anchor_is_partial_035(tmp_path: Path, clause: str):
    _write(tmp_path, "CRA_TECHNICAL_DOCUMENTATION.md", UNRELATED)
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("clause", CLAUSE_IDS)
def test_a_short_realistic_section_is_partial_06_never_met(tmp_path: Path, clause: str):
    _write(
        tmp_path,
        "CRA_TECHNICAL_DOCUMENTATION.md",
        _document({clause: REALISTIC[clause]}),
    )
    row = artifact_gap_status(f"{REF}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


def test_a_full_document_is_partial_never_met(tmp_path: Path):
    _write(tmp_path, "CRA_TECHNICAL_DOCUMENTATION.md", _document(REALISTIC))
    row = artifact_gap_status(REF, tmp_path)
    assert row.status == GapStatus.PARTIAL


@pytest.mark.parametrize(
    "rel",
    [
        "CRA_TECHNICAL_DOCUMENTATION.md",
        "docs/cra-technical-documentation.md",
        "docs/cra_technical_documentation.md",
        "docs/ia/cra-technical-documentation-2026.md",
        "x/cra_technical_documentation.md",
    ],
)
def test_every_glob_spelling_finds_the_file(tmp_path: Path, rel: str):
    _write(tmp_path, rel, _document({"8": REALISTIC["8"]}))
    row = artifact_gap_status(f"{REF}#8", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


def test_an_ordinary_markdown_file_is_not_evidence(tmp_path: Path):
    _write(tmp_path, "README.md", _document(REALISTIC))
    row = artifact_gap_status(f"{REF}#8", tmp_path)
    assert row.status == GapStatus.MISSING


# ---- further probes: user information, support period, notification record ----

UI_IDS = tuple(str(n) for n in range(1, 10))
UI_REALISTIC = {
    "1": "The manufacturer is Example Devices Ltd; contact us by e-mail or at the postal address on our website.",
    "2": "Report a vulnerability through the security contact at security@example.org or the web form on our site.",
    "3": "This product is the Example Hub, identified by its model name, version number and serial label on the case.",
    "4": "The intended purpose is home heating control; it is designed for a domestic network behind a router.",
    "5": "Known risks include misuse with a default password and foreseeable exposure on an open network.",
    "6": "The declaration of conformity is published and available at https://example.org/declaration for download.",
    "7": "Support runs for five years and the end date is 2031-06-30, after which no updates are issued.",
    "8": "Install the device with a new password, apply updates when asked, and reset it before you dispose of it.",
    "9": "The software bill of materials is available as a file in the public repository; the link is in the manual.",
}
NOTIFY_IDS = ("early-warning", "notification", "final-report", "user-information")
NOTIFY_REALISTIC = {
    "early-warning": "Early warning sent within 24 hours to the national coordinator since the flaw was actively exploited.",
    "notification": "The notification followed within 72 hours and states the severity, the affected versions and the mitigation.",
    "final-report": "The final report gives the root cause, the severity, the patch released and the corrective measures taken.",
    "user-information": "Users were informed by advisory e-mail with the corrective update and a mitigation for older versions.",
}
SUPPORT_REALISTIC = (
    "Support period: five years from first sale, with an end date of 2031-06-30. "
    "Security updates are shipped throughout that period."
)

CLAUSE_CASES = [
    (UI_REF, c, UI_REALISTIC[c], "docs/security-information.md") for c in UI_IDS
] + [
    (NOTIFY_REF, c, NOTIFY_REALISTIC[c], "docs/vulnerability-notification-2026.md")
    for c in NOTIFY_IDS
]


def _ids(case):
    return f"{case[0]}#{case[1]}"


def test_new_probes_declare_provenance_and_globs():
    data = json.loads(PROBE_FILE.read_text(encoding="utf-8"))["probes"]
    for ref in (UI_REF, SUPPORT_REF, NOTIFY_REF):
        probe = data[ref]
        prov = probe["provenance"]
        assert prov["source"].startswith("heuristic (no legal source):")
        assert prov["confidence"] == "low"
        assert prov["needs_founder_review"] is True
        assert "**/*.md" not in probe["patterns"]
        for pat in probe["patterns"]:
            if "-" in pat:
                assert pat.replace("-", "_") in probe["patterns"]
    assert tuple(data[UI_REF]["clauses"]) == UI_IDS
    assert tuple(data[NOTIFY_REF]["clauses"]) == NOTIFY_IDS
    markers = data[SUPPORT_REF]["markers"]
    assert markers["body_only"] is True
    assert markers["forbid_scaffold"] is True
    assert len(markers["all"]) == 3


def test_new_refs_exist():
    for ref in (UI_REF, SUPPORT_REF, NOTIFY_REF):
        assert probe_exists(ref)
    for c in UI_IDS:
        assert probe_exists(f"{UI_REF}#{c}")
    for c in NOTIFY_IDS:
        assert probe_exists(f"{NOTIFY_REF}#{c}")


@pytest.mark.parametrize("case", CLAUSE_CASES, ids=_ids)
def test_clause_empty_repo_is_missing(tmp_path: Path, case):
    ref, clause, _, _ = case
    assert artifact_gap_status(f"{ref}#{clause}", tmp_path).status == GapStatus.MISSING


@pytest.mark.parametrize("case", CLAUSE_CASES, ids=_ids)
def test_clause_unrelated_sentence_is_partial_035(tmp_path: Path, case):
    ref, clause, _, rel = case
    _write(tmp_path, rel, _document({clause: UNRELATED}))
    row = artifact_gap_status(f"{ref}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("case", CLAUSE_CASES, ids=_ids)
def test_clause_realistic_section_is_partial_06(tmp_path: Path, case):
    ref, clause, text, rel = case
    _write(tmp_path, rel, _document({clause: text}))
    row = artifact_gap_status(f"{ref}#{clause}", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize(
    "rel",
    [
        "docs/security-information.md",
        "docs/security_information.md",
        "docs/x/security-information-2026.md",
        "cra-user-information.md",
        "pkg/cra_user_information.md",
    ],
)
def test_user_information_globs(tmp_path: Path, rel: str):
    _write(tmp_path, rel, _document({"9": UI_REALISTIC["9"]}))
    row = artifact_gap_status(f"{UI_REF}#9", tmp_path)
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize(
    "rel",
    [
        "vulnerability-notification.md",
        "docs/vulnerability_notification_log.md",
        "docs/cra-notification.md",
        "docs/a/cra_notification-2026.md",
    ],
)
def test_notification_globs(tmp_path: Path, rel: str):
    _write(tmp_path, rel, _document({"final-report": NOTIFY_REALISTIC["final-report"]}))
    row = artifact_gap_status(f"{NOTIFY_REF}#final-report", tmp_path)
    assert row.confidence == pytest.approx(0.6)


def test_new_clause_files_are_never_met(tmp_path: Path):
    _write(tmp_path, "docs/security-information.md", _document(UI_REALISTIC))
    _write(tmp_path, "docs/vulnerability-notification.md", _document(NOTIFY_REALISTIC))
    for ref in (UI_REF, NOTIFY_REF):
        assert artifact_gap_status(ref, tmp_path).status != GapStatus.MET


def test_support_empty_repo_is_missing(tmp_path: Path):
    assert artifact_gap_status(SUPPORT_REF, tmp_path).status == GapStatus.MISSING


@pytest.mark.parametrize(
    "rel",
    [
        "SUPPORT.md",
        "support-period.md",
        "docs/support_period.md",
        "docs/end-of-support.md",
        "docs/end_of_support-2026.md",
    ],
)
def test_support_unrelated_sentence_is_partial_035(tmp_path: Path, rel: str):
    _write(tmp_path, rel, UNRELATED)
    row = artifact_gap_status(SUPPORT_REF, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize(
    "rel",
    [
        "SUPPORT.md",
        "support-period.md",
        "docs/support_period.md",
        "docs/end-of-support.md",
    ],
)
def test_support_realistic_file_is_partial_06(tmp_path: Path, rel: str):
    _write(tmp_path, rel, SUPPORT_REALISTIC)
    row = artifact_gap_status(SUPPORT_REF, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


def test_support_file_missing_a_topic_is_partial_035(tmp_path: Path):
    _write(tmp_path, "SUPPORT.md", "The support period is five years from first sale.")
    row = artifact_gap_status(SUPPORT_REF, tmp_path)
    assert row.confidence == pytest.approx(0.35)
