from __future__ import annotations

import pytest
from opencomplai_core.frameworks import FRAMEWORKS, pack_requirements
from opencomplai_core.impact_assessment import (
    DISCLAIMER,
    FILL_IN,
    build_assessment,
    render_assessment_markdown,
)
from opencomplai_core.models import SystemManifest

NOW = "2026-01-01T00:00:00+00:00"


def _manifest(**extra: object) -> SystemManifest:
    return SystemManifest.model_validate(
        {"system_id": "sys-1", "intended_purpose": "", **extra}
    )


def test_ai_system_one_section_per_pack_row() -> None:
    rows = pack_requirements(FRAMEWORKS["ISO_IEC_42005"]) or {}
    doc = build_assessment("ai-system", _manifest(), generated_at=NOW)
    assert [s.ref for s in doc.sections] == list(rows)
    assert len(doc.sections) > 0
    first = next(iter(rows.values()))
    assert doc.sections[0].title == first["title"]
    assert doc.sections[0].guidance == first["note"]


def test_dpia_has_four_sections_and_header() -> None:
    doc = build_assessment("dpia", _manifest(), generated_at=NOW)
    assert len(doc.sections) == 4
    assert len(doc.header) == 4
    assert set(doc.header.values()) == {FILL_IN}


def test_intended_purpose_fills_its_section() -> None:
    doc = build_assessment(
        "dpia", _manifest(intended_purpose="Rank job applicants"), generated_at=NOW
    )
    first = doc.sections[0]
    assert first.populated
    assert "Rank job applicants" in first.assessment
    assert first.owner == FILL_IN


def test_empty_manifest_leaves_every_cell_unfilled() -> None:
    for kind in ("ai-system", "dpia"):
        doc = build_assessment(kind, _manifest(), generated_at=NOW)
        assert all(s.assessment == FILL_IN and not s.populated for s in doc.sections)
        assert all(s.owner == FILL_IN for s in doc.sections)


def test_markdown_first_line() -> None:
    doc = build_assessment("dpia", _manifest(), generated_at=NOW)
    assert render_assessment_markdown(doc).splitlines()[0] == DISCLAIMER


def test_unknown_kind_raises() -> None:
    with pytest.raises(ValueError, match="unknown kind"):
        build_assessment("nope", _manifest(), generated_at=NOW)
