"""Tests for the GPAI training-summary template and Code of Practice map."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest
from opencomplai_core import gpai_training_pack as mod
from opencomplai_core.gpai_training_pack import (
    get_gpai_training_pack,
    render_training_summary_markdown,
    validate_gpai_training_pack,
)

_RAW = json.loads(mod._DATA_PATH.read_text(encoding="utf-8"))
_LISTS = ("training_summary_sections", "code_of_practice_chapters")
_STATUS_NOTE = (
    "Voluntary code; adherence is not a legal determination of compliance "
    "and this tool grants no presumption of conformity."
)


def _rows():
    return [r for name in _LISTS for r in _RAW[name]]


def _mut(fn):
    raw = copy.deepcopy(_RAW)
    fn(raw)
    return raw


def test_shipped_pack_validates_with_no_errors():
    assert validate_gpai_training_pack(_RAW) == []
    pack = get_gpai_training_pack()
    assert len(pack.sections) == 10
    assert len(pack.chapters) == 3


def test_every_row_is_flagged_with_source_confidence_and_review():
    for r in _rows():
        assert r["source"].strip()
        assert "source_url" in r
        assert r["confidence"] in {"low", "medium"}
        assert r["needs_founder_review"] is True


def test_no_row_is_high_confidence():
    assert all(r["confidence"] != "high" for r in _rows())


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (
            lambda d: d["training_summary_sections"][0].pop("prompt"),
            "missing key 'prompt'",
        ),
        (
            lambda d: d["training_summary_sections"][1].update(id="ts_general"),
            "duplicate id",
        ),
        (
            lambda d: d["training_summary_sections"][0].update(source=" "),
            "empty source",
        ),
        (
            lambda d: d["training_summary_sections"][0].update(confidence="high"),
            "invalid confidence",
        ),
        (
            lambda d: d["training_summary_sections"][0].update(
                needs_founder_review=False
            ),
            "needs_founder_review=true",
        ),
        (
            lambda d: d["code_of_practice_chapters"][0].update(article_refs=[]),
            "'article_refs'",
        ),
        (lambda d: d.update(training_summary_sections="nope"), "missing or empty"),
    ],
)
def test_validator_reports_each_defect_class(mutate, needle):
    errs = validate_gpai_training_pack(_mut(mutate))
    assert any(needle in e for e in errs), errs


def test_validator_rejects_non_object_payload():
    assert validate_gpai_training_pack([]) == ["pack is not a JSON object"]


def test_loader_raises_on_invalid_json_or_missing_file(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    unflagged = _mut(
        lambda d: d["code_of_practice_chapters"][0].update(needs_founder_review=False)
    )
    flagged = tmp_path / "flag.json"
    flagged.write_text(json.dumps(unflagged), encoding="utf-8")
    try:
        for path in (bad, tmp_path / "missing.json", flagged):
            monkeypatch.setattr(mod, "_DATA_PATH", path)
            get_gpai_training_pack.cache_clear()
            with pytest.raises(ValueError, match="gpai_training_pack"):
                get_gpai_training_pack()
    finally:
        monkeypatch.undo()
        get_gpai_training_pack.cache_clear()


def test_rendered_summary_lists_every_section_and_flags_it():
    pack = get_gpai_training_pack()
    out = render_training_summary_markdown(pack)
    assert out == render_training_summary_markdown(pack)
    assert "every section below needs founder review" in out
    assert not re.search(r"20\d\d", out)
    for s in pack.sections:
        assert f"## {s.title}" in out
    assert out.count("Provider entry:") == len(pack.sections)
    assert out.count("Draft, needs founder review.") == len(pack.sections)


def test_cop_map_has_three_chapters_with_article_refs():
    chapters = {c.id: c for c in get_gpai_training_pack().chapters}
    assert set(chapters) == {"cop_transparency", "cop_copyright", "cop_safety_security"}
    for c in chapters.values():
        assert c.article_refs
        assert c.status_note == _STATUS_NOTE
    with_55 = {i for i, c in chapters.items() if "Art. 55" in c.article_refs}
    assert with_55 == {"cop_safety_security"}
    assert chapters["cop_safety_security"].applies_to == "systemic_risk_only"


def test_docs_page_is_in_nav():
    root = Path(__file__).resolve().parents[3]
    page = "frameworks/gpai-training-summary-and-cop.md"
    assert (root / "docs" / "src" / page).is_file()
    nav = (root / "docs" / "mkdocs.yml").read_text(encoding="utf-8").splitlines()
    assert any(page in ln and not ln.lstrip().startswith("#") for ln in nav)
