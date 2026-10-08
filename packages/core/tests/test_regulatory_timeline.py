"""Regulatory timeline data, loader, lookup and wiring (SU-11)."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date

import pytest
from opencomplai_core import regulatory_timeline as rt
from opencomplai_core.frameworks import EU_AI_ACT, FRAMEWORKS, data_version


def _raw() -> dict:
    return json.loads(rt.TIMELINE_PATH.read_text(encoding="utf-8"))


def test_every_entry_has_source_confidence_and_review_flag():
    entries = rt.load_timeline()
    assert entries
    for e in entries:
        assert e.source.strip(), e.id
        assert e.confidence in {"medium", "low"}, e.id  # never above medium
        assert e.needs_founder_review is True, e.id
        if e.applies_from is None:
            assert e.confidence == "low", e.id
            assert (e.note or "").startswith("unverified:"), e.id


def test_unverified_entries_are_low_confidence():
    for e in rt.load_timeline():
        note = (e.note or "").lower()
        if note.startswith("unverified:") or "single secondary source" in note:
            assert e.confidence == "low", e.id


def test_omnibus_and_statutory_dates_are_present():
    dates = {e.id: e.applies_from for e in rt.load_timeline()}
    assert dates["art5_prohibitions"] == "2025-02-02"
    assert dates["art5_ninth_prohibition"] == "2026-12-02"
    assert dates["gpai_obligations"] == "2025-08-02"
    assert dates["art50_transparency"] == "2026-08-02"
    assert dates["annex_iii_high_risk"] == "2027-12-02"
    assert dates["annex_i_high_risk"] == "2028-08-02"
    assert dates["art50_2_transition"] is None
    assert dates["art49_2_registration"] is None


def test_loader_rejects_malformed_entries():
    good = _raw()["entries"][0]
    mutations = {
        "source": {"source": " "},
        "confidence": {"confidence": "certain"},
        "date": {"applies_from": "2027-13-40"},
        "flag": {"needs_founder_review": "yes"},
        "articles": {"articles": ["no article here"]},
    }
    for label, change in mutations.items():
        with pytest.raises(ValueError, match="art5_prohibitions"):
            rt.parse_timeline({"entries": [{**good, **change}]})
        assert label
    with pytest.raises(ValueError, match="duplicate"):
        rt.parse_timeline({"entries": [good, good]})


def test_knowledge_applies_from_agrees_with_timeline():
    known = rt.knowledge_dates()
    assert set(known) == {
        "prohibited:*:min",
        "prohibited:Art.5(1)(i)",
        "limited_risk:*",
    }
    by_ref = {e.knowledge_ref: e for e in rt.load_timeline() if e.knowledge_ref}
    assert set(by_ref) == set(known)
    for ref, applies_from in known.items():
        assert by_ref[ref].applies_from == applies_from, ref


def test_eu_pack_data_version_changes_with_timeline(tmp_path):
    pack = FRAMEWORKS[EU_AI_ACT]
    assert rt.TIMELINE_PATH in pack.data_files
    edited = _raw()
    edited["entries"][0]["note"] = "edited"
    path = tmp_path / "regulatory_timeline.json"
    path.write_text(json.dumps(edited), encoding="utf-8")
    other = replace(pack, data_files=(path,))
    assert data_version(other) != data_version(pack)


def test_articles_in_ref_handles_ranges():
    assert rt.articles_in_ref("Art. 16–21, Art. 43") == [  # noqa: RUF001
        *(f"Art. {n}" for n in range(16, 22)),
        "Art. 43",
    ]
    assert rt.articles_in_ref("Art. 9-11") == ["Art. 9", "Art. 10", "Art. 11"]
    assert rt.articles_in_ref("Art. 26, Art. 27") == ["Art. 26", "Art. 27"]
    assert rt.articles_in_ref("Art. 50") == ["Art. 50"]
    assert rt.articles_in_ref("nothing") == []


def test_timeline_for_articles_orders_by_date():
    got = [e.id for e in rt.timeline_for_articles(["Art. 6", "Art. 50"])]
    assert got == [
        "art50_transparency",
        "annex_iii_high_risk",
        "annex_i_high_risk",
        "art49_2_registration",
        "art50_2_transition",
    ]
    assert rt.timeline_for_articles(["Art. 4"]) == []
    # a range in the data covers a single article in the argument
    assert "annex_iii_high_risk" in [
        e.id for e in rt.timeline_for_articles(["Art. 24"])
    ]


def test_status_uses_injected_clock():
    by_id = {e.id: e for e in rt.load_timeline()}
    annex = by_id["annex_iii_high_risk"]
    assert rt.status_on(annex, date(2027, 12, 1)) == "upcoming"
    assert rt.status_on(annex, date(2027, 12, 2)) == "in_force"
    assert (
        rt.status_on(by_id["art49_2_registration"], date(2030, 1, 1)) == "unconfirmed"
    )
    assert rt.format_entry(annex, date(2026, 10, 5)).endswith("(upcoming)")
    assert rt.format_entry(annex, date(2028, 1, 1)).endswith("(in force)")
    assert "(" not in rt.format_entry(annex).rsplit("]", 1)[1]


def test_rendered_blocks_have_no_relative_days():
    lines = rt.timeline_lines(["Art. 5", "Art. 6", "Art. 50", "Art. 53"])
    assert lines
    blob = "\n".join(lines)
    assert "date unconfirmed" in blob
    assert not re.search(r"\b(days?|ago|in \d+)\b", blob)
    assert "pending founder review" in blob


def test_timeline_file_loads_through_the_package_path():
    from importlib import resources

    text = (
        resources.files("opencomplai_core")
        .joinpath("data/regulatory_timeline.json")
        .read_text(encoding="utf-8")
    )
    assert json.loads(text)["schema_version"] == 1
