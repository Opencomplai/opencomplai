"""Art. 13(3) instructions-for-use generator and its recommend template."""

from __future__ import annotations

import json
import re
from pathlib import Path

import opencomplai_core
from opencomplai_core.instructions_for_use import (
    IFU_POINTS,
    generate_instructions_for_use,
    render_instructions_for_use_markdown,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
    SystemManifest,
)
from opencomplai_core.recommend_engine import load_template_map, render_recommendations

CLOCK = "2026-10-07T12:00:00+00:00"
NOT_CAPTURED_PREFIX = "Not captured by the system manifest"
ALWAYS_UNCAPTURED = ["b_iv", "b_v", "b_vii"]


def _minimal() -> SystemManifest:
    return SystemManifest(
        system_id="sys-1", intended_purpose="credit scoring", commit_ref="abc123"
    )


def _full() -> SystemManifest:
    return SystemManifest(
        system_id="sys-1",
        intended_purpose="credit scoring",
        commit_ref="abc123",
        provider_contact="Acme AI, ops@example.com",
        foreseeable_misuse=["used on minors"],
        input_data_specifications="PDF, UTF-8",
        predetermined_changes=["quarterly recalibration"],
        expected_lifetime_and_maintenance="5 years",
        log_interpretation="JSON lines",
        performance_metrics={"recall": 0.9},
        metrics_appropriateness_rationale="recall matters for screening",
        known_limitations=["thin-file applicants"],
        human_oversight_measures=["reviewer confirms every denial"],
    )


def test_every_uncaptured_point_is_listed_explicitly():
    doc = generate_instructions_for_use(_minimal(), generated_at=CLOCK)
    assert doc.total_points == len(IFU_POINTS) == 13
    expected = [d.point for d in IFU_POINTS if d.point != "b_i"]
    assert len(expected) == 12
    assert doc.not_captured_points == expected
    for p in doc.points:
        if p.point != "b_i":
            assert p.populated is False
            assert p.source == "not_captured"
            assert p.content.startswith(NOT_CAPTURED_PREFIX)


def test_fully_populated_manifest_has_no_uncaptured_points():
    # b_iv, b_v and b_vii have no manifest field, so they stay not captured:
    # nothing else is left uncaptured once every manifest field is set.
    doc = generate_instructions_for_use(_full(), generated_at=CLOCK)
    assert doc.not_captured_points == ALWAYS_UNCAPTURED
    assert doc.populated_point_count == 10
    by_id = {p.point: p for p in doc.points}
    assert (
        by_id["b_ii"].content == "recall=0.9; Rationale: recall matters for screening"
    )


def test_every_point_carries_source_confidence_and_review_flag():
    doc = generate_instructions_for_use(_full(), generated_at=CLOCK)
    dumped = json.loads(doc.model_dump_json())
    assert len(dumped["points"]) == 13
    for p in dumped["points"]:
        assert p["legal_ref"].startswith("Regulation (EU) 2024/1689 Art. 13(3)")
        assert p["confidence"] == "medium"
        assert p["needs_founder_review"] is True
        assert p["source"]


def test_generation_is_deterministic_with_injected_clock():
    a = generate_instructions_for_use(_full(), generated_at=CLOCK).model_dump_json()
    b = generate_instructions_for_use(_full(), generated_at=CLOCK).model_dump_json()
    assert a == b
    assert CLOCK in a
    assert re.findall(r"\d{4}-\d{2}-\d{2}", a) == ["2026-10-07"]


def test_markdown_lists_every_point_and_every_uncaptured_item():
    doc = generate_instructions_for_use(_minimal(), generated_at=CLOCK)
    md = render_instructions_for_use_markdown(doc)
    for d in IFU_POINTS:
        assert d.element in md
    tail = md.split("## Not captured", 1)[1]
    bullets = [ln for ln in tail.splitlines() if ln.startswith("- ")]
    assert len(bullets) == len(doc.not_captured_points)
    assert doc.disclaimer in md
    assert CLOCK in md


def test_art13_recommend_template_is_instructions_for_use():
    entry = load_template_map()["Art. 13"]
    assert entry["template_id"] == "instructions_for_use"
    assert entry["file"] == "instructions_for_use.md"
    path = (
        Path(opencomplai_core.__file__).parent
        / "templates"
        / "recommend"
        / entry["file"]
    )
    text = path.read_text(encoding="utf-8")
    for d in IFU_POINTS:
        assert d.element in text


def test_art13_recommend_render_replaces_all_placeholders(tmp_path):
    report = GapReport(
        system_id="test-sys",
        commit_ref="HEAD",
        generated_at=CLOCK,
        articles=[
            ArticleGapStatus(
                article="Art. 13",
                status=GapStatus.MISSING,
                source=ArticleGapSource.ARTIFACT,
                evidence_ref="deployer_instructions",
                rationale="no instructions file",
            )
        ],
    )
    written = render_recommendations(report, tmp_path)
    assert [p.name for p in written] == ["art13-instructions_for_use.md"]
    assert "{{" not in written[0].read_text(encoding="utf-8")
