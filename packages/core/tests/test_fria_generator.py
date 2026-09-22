"""CP-14: `opencomplai fria generate` populates Art. 27(1)(a)-(f) from real data.

Scenario extends the golden fixture `07_high_risk_deployer_fria.json`
(deployer, Annex III high-risk, r5_fria=true) with the manifest fields a real
deployer would have filled in, and exercises the generator end to end.
"""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_core.compliance_checker.engine import evaluate
from opencomplai_core.compliance_checker.models import CheckerSession
from opencomplai_core.fria import FRIA_POINTS, generate_fria, render_fria_markdown
from opencomplai_core.gap_report import build_gap_report, load_gap_article_map
from opencomplai_core.models import SystemManifest

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "checker_golden"
    / "07_high_risk_deployer_fria.json"
)


def _manifest() -> SystemManifest:
    return SystemManifest(
        system_id="credit-scoring-deployer",
        intended_purpose="Score loan applicants for a public housing authority",
        high_risk_presumption=True,
        operator_role="deployer",
        known_limitations=["May mis-score applicants near the credit threshold"],
        human_oversight_measures=[
            "A human reviewer confirms every denial before it is issued"
        ],
        incident_response_procedure=(
            "Complaints routed to the compliance officer within 2 business days"
        ),
    )


def test_generate_fria_populates_from_manifest_and_checker(tmp_path: Path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    session = CheckerSession.model_validate(payload["session"])
    checker_result = evaluate(session)
    assert "fria" in [item.id for item in checker_result.obligations]

    load_gap_article_map.cache_clear()
    report = build_gap_report("credit-scoring-deployer", "HEAD", repo_root=tmp_path)
    gap_row = next(r for r in report.articles if r.article == "Art. 27")

    document = generate_fria(
        _manifest(), gap_row=gap_row, checker_result=checker_result
    )

    assert document.system_id == "credit-scoring-deployer"
    assert document.entity_role == "deployer"
    assert document.is_high_risk is True
    assert "fria" in document.trigger_obligation_ids
    assert len(document.points) == len(FRIA_POINTS) == 6

    by_point = {p.point: p for p in document.points}
    assert by_point["a"].populated is True
    assert "Score loan applicants" in by_point["a"].assessment
    assert by_point["b"].populated is False  # no period/frequency source exists
    assert by_point["c"].populated is True  # checker's Annex III answer
    assert "Annex III" in by_point["c"].assessment
    assert by_point["d"].populated is True
    assert "mis-score applicants" in by_point["d"].assessment
    assert by_point["e"].populated is True
    assert "human reviewer" in by_point["e"].assessment
    assert by_point["f"].populated is True
    assert "compliance officer" in by_point["f"].assessment
    assert document.populated_point_count == 5

    # JSON output mirrors dossier.model_dump_json()'s pattern: a plain
    # pydantic model dump, round-trippable.
    dumped = document.model_dump_json(indent=2)
    assert document.model_validate_json(dumped) == document

    # Markdown output: every placeholder substituted, real content present,
    # not just the fill-in template CP-6 left behind.
    markdown = render_fria_markdown(document)
    assert "{{" not in markdown
    assert "Score loan applicants" in markdown
    assert "mis-score applicants" in markdown
    assert "human reviewer" in markdown
    assert "compliance officer" in markdown
    assert "_fill in_" in markdown  # (b)'s Assessment cell + every Owner cell


def test_generate_fria_with_no_checker_or_manifest_data_stays_honest():
    """No checker session, no manifest extras -- every point either uses the
    one field that's always present (intended_purpose) or stays "not
    captured", never a fabricated claim."""
    manifest = SystemManifest(
        system_id="bare-system",
        intended_purpose="Not specified",
    )
    document = generate_fria(manifest)
    by_point = {p.point: p for p in document.points}
    assert by_point["a"].populated is True  # intended_purpose is always set
    for letter in ("b", "c", "d", "e", "f"):
        assert by_point[letter].populated is False
        assert by_point[letter].source == "not_captured"
    assert document.gap_status is None
    assert document.trigger_obligation_ids == []
