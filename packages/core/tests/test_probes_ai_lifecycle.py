"""The ai_lifecycle probe family: what each probe finds, and what it must not."""

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
    / "ai_lifecycle.json"
)
REFS = (
    "model_card",
    "data_provenance_sheet",
    "evaluation_evidence",
    "ai_impact_assessment",
)
UNRELATED = "The canteen opens at nine and closes after the afternoon tea round."

IMPACT_CLAUSES = {
    "purpose": "The purpose of this system is to rank support tickets for the service desk team.",
    "affected parties": "Affected groups are customers who write in and the staff who answer them each day.",
    "impacts": "The impacts include faster replies, but also a harm if urgent tickets are ranked too low.",
    "mitigations": "We mitigate this with a daily sample check and a manual override on every ranked ticket.",
    "review": "The service owner will review this assessment every quarter and after each model change.",
}

# ref -> (path of a matching file, a short realistic body)
REALISTIC = {
    "model_card": (
        "MODEL_CARD.md",
        "# Ticket ranker\n\nIntended use: ranking inbound support tickets for human agents.\n\n"
        "Limitations: weak on tickets shorter than five words and on languages other than English.\n\n"
        "Evaluation: accuracy and F1 on a held-out month of tickets.\n",
    ),
    "data_provenance_sheet": (
        "docs/dataset-card.md",
        "# Ticket corpus\n\nSource: tickets collected from our own help desk between 2023 and 2024.\n\n"
        "Licence: internal data used under the customer terms of service, with consent recorded.\n\n"
        "Preparation: personal data removed, then each ticket labelled by two annotators.\n",
    ),
    "evaluation_evidence": (
        "reports/eval-report.md",
        "# Evaluation report\n\nMetric: macro F1 and recall for the urgent class.\n\n"
        "Dataset: a held-out test set of 4,000 tickets from the latest quarter.\n\n"
        "Result: F1 of 0.82 against a release threshold of 0.80, so the gate passed.\n",
    ),
    "ai_impact_assessment": (
        "AI_IMPACT_ASSESSMENT.md",
        "\n".join(f"<!-- clause: {c} -->\n{t}\n" for c, t in IMPACT_CLAUSES.items()),
    ),
}

# ref -> one path for each glob family that the probe is meant to catch
GLOB_SAMPLES = {
    "model_card": ["MODEL_CARD.md", "ml/model-card.md", "ml/model_card.md"],
    "data_provenance_sheet": [
        "data/datasheet.md",
        "data/data-provenance.md",
        "data/data_provenance.md",
        "data/dataset-card.md",
        "data/dataset_card.md",
    ],
    "evaluation_evidence": [
        "out/eval-report.md",
        "out/eval_report.md",
        "out/evaluation-report.md",
        "out/evaluation_report.md",
        "docs/ml/evaluation.md",
    ],
    "ai_impact_assessment": [
        "AI_IMPACT_ASSESSMENT.md",
        "docs/ai-impact-assessment.md",
        "docs/ai_impact_assessment.md",
        "x/ai-impact-assessment.md",
        "x/ai_impact_assessment.md",
    ],
}


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_the_file_parses_and_names_the_family():
    parsed = parse_probe_file(PROBE_FILE)
    assert tuple(parsed) == REFS


@pytest.mark.parametrize("ref", REFS)
def test_every_ref_is_registered(ref: str):
    assert probe_exists(ref)


@pytest.mark.parametrize("ref", REFS)
def test_an_empty_repo_is_missing(tmp_path: Path, ref: str):
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.MISSING


@pytest.mark.parametrize("ref", REFS)
def test_a_matching_file_with_one_unrelated_sentence_is_partial_035(
    tmp_path: Path, ref: str
):
    rel = REALISTIC[ref][0]
    _write(tmp_path, rel, UNRELATED)
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize("ref", REFS)
def test_a_short_realistic_file_is_partial_06_never_met(tmp_path: Path, ref: str):
    rel, text = REALISTIC[ref]
    _write(tmp_path, rel, text)
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize("ref", [r for r in REFS if r != "ai_impact_assessment"])
def test_an_unfilled_scaffold_stays_at_035(tmp_path: Path, ref: str):
    from opencomplai_core.gap_probes import SCAFFOLD_PLACEHOLDER

    rel, text = REALISTIC[ref]
    _write(tmp_path, rel, text + "\n" + SCAFFOLD_PLACEHOLDER + "\n")
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)


@pytest.mark.parametrize(
    ("ref", "rel"),
    [(ref, rel) for ref, rels in GLOB_SAMPLES.items() for rel in rels],
)
def test_every_glob_spelling_finds_the_file(tmp_path: Path, ref: str, rel: str):
    _write(tmp_path, rel, REALISTIC[ref][1])
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize("ref", REFS)
def test_an_ordinary_markdown_file_is_not_evidence(tmp_path: Path, ref: str):
    _write(tmp_path, "README.md", REALISTIC[ref][1])
    assert artifact_gap_status(ref, tmp_path).status == GapStatus.MISSING


def test_a_missing_impact_clause_reads_035_and_a_present_one_06(tmp_path: Path):
    body = "\n".join(
        f"<!-- clause: {c} -->\n{t}\n"
        for c, t in IMPACT_CLAUSES.items()
        if c != "review"
    )
    _write(tmp_path, "AI_IMPACT_ASSESSMENT.md", body)
    missing = artifact_gap_status("ai_impact_assessment#review", tmp_path)
    assert missing.status == GapStatus.PARTIAL
    assert missing.confidence == pytest.approx(0.35)
    present = artifact_gap_status("ai_impact_assessment#purpose", tmp_path)
    assert present.status == GapStatus.PARTIAL
    assert present.confidence == pytest.approx(0.6)
