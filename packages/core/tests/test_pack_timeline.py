"""Per-pack timelines: parse, load, merge with the EU timeline, backlog deadline."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from opencomplai_core import pack_registry, regulatory_timeline
from opencomplai_core.backlog import deadline_for
from opencomplai_core.regulatory_timeline import (
    format_entry,
    load_pack_timeline,
    parse_pack_timeline,
    timeline_for_articles,
    timeline_for_requirements,
    timeline_ids,
)

ROWS = {"TST:Art. 1", "TST:Art. 2", "TST:Art. 3"}


def _entry(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "tst.first",
        "title": "First duty",
        "applies_from": "2030-01-01",
        "scope_note": "Applies to test systems.",
        "source": "Test source",
        "confidence": "medium",
        "needs_founder_review": True,
        "requirements": ["TST:Art. 1"],
    }
    base.update(over)
    return base


def _doc(*entries: dict[str, Any]) -> dict[str, Any]:
    return {"entries": list(entries)}


def _make_pack(
    root: Path, key: str, mode: str, timeline: Any = None, **meta: Any
) -> None:
    folder = root / key
    folder.mkdir()
    body = {
        "id": key,
        "order": 1,
        "kind": "native",
        "name": "Test pack",
        "short_name": key,
        "status": "attestation-led",
        "disclaimer_ref": "DISCLAIMER_V2",
        "requirements": "requirements.json",
        "data_files": [],
        "legacy_file": "x.json",
        "copyright": "eu_law",
        "row_count": 3,
        "target_machine_share": 0,
        "timeline": mode,
        "catalogue": False,
    }
    body.update(meta)
    (folder / "pack.json").write_text(json.dumps(body), encoding="utf-8")
    (folder / "requirements.json").write_text(
        json.dumps({r: {} for r in sorted(ROWS)}), encoding="utf-8"
    )
    if timeline is not None:
        (folder / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")


@pytest.fixture
def packs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setattr(pack_registry, "PACKS_DIR", tmp_path)
    load_pack_timeline.cache_clear()
    yield tmp_path
    load_pack_timeline.cache_clear()


@pytest.mark.parametrize(
    ("entry", "needle"),
    [
        (_entry(requirements=["TST:Art. 9"]), "TST:Art. 9"),
        (_entry(id="other.first"), "id must start with tst."),
        (_entry(high_risk_basis="annex_i"), "high_risk_basis"),
        (_entry(knowledge_ref="x"), "knowledge_ref"),
        (_entry(articles=["Art. 5"]), "articles"),
        (_entry(applies_from="2030-13-40"), "ISO date"),
        (_entry(requirements=[]), "requirements"),
        (_entry(duration=""), "duration"),
    ],
)
def test_parse_errors_name_the_entry(entry: dict[str, Any], needle: str) -> None:
    with pytest.raises(ValueError, match=needle) as err:
        parse_pack_timeline(_doc(entry), "TST", ROWS)
    assert repr(entry["id"]) in str(err.value)


def test_duplicate_id_refused() -> None:
    with pytest.raises(ValueError, match="duplicate id"):
        parse_pack_timeline(_doc(_entry(), _entry()), "TST", ROWS)


def test_parse_accepts_null_date_and_duration() -> None:
    (entry,) = parse_pack_timeline(
        _doc(_entry(applies_from=None, duration="24 hours after becoming aware")),
        "TST",
        ROWS,
    )
    assert entry.framework == "TST"
    assert entry.requirements == ("TST:Art. 1",)
    assert entry.articles == ()
    assert entry.duration == "24 hours after becoming aware"
    assert "(24 hours after becoming aware)" in format_entry(entry)


def test_format_unchanged_without_duration() -> None:
    (entry,) = parse_pack_timeline(_doc(_entry()), "TST", ROWS)
    assert format_entry(entry) == (
        "2030-01-01 - First duty [Test source; confidence medium; "
        "pending founder review]"
    )


def test_none_pack_returns_nothing(packs: Path) -> None:
    _make_pack(packs, "TST", "none", timeline_reason="No dated duties yet.")
    assert load_pack_timeline("TST") == ()
    assert timeline_for_requirements(["TST:Art. 1"]) == []
    assert timeline_ids("TST:Art. 1") == []


def test_none_without_reason_and_file_without_file(packs: Path) -> None:
    _make_pack(packs, "NOR", "none", timeline_reason=" ")
    _make_pack(packs, "NOF", "file")
    with pytest.raises(ValueError, match="timeline_reason"):
        load_pack_timeline("NOR")
    with pytest.raises(ValueError, match=r"timeline.json is missing"):
        load_pack_timeline("NOF")


def test_core_pack_returns_nothing(packs: Path) -> None:
    _make_pack(packs, "COR", "core")
    assert load_pack_timeline("COR") == ()


def test_unknown_pack_prefix_is_empty(packs: Path) -> None:
    assert timeline_for_requirements(["CUSTOM:Rule 1"]) == []


def test_file_pack_loads_and_merges_in_date_order(packs: Path) -> None:
    doc = _doc(
        _entry(id="tst.early", applies_from="2001-01-01"),
        _entry(id="tst.undated", applies_from=None),
        _entry(id="tst.late", applies_from="2099-01-01", requirements=["TST:Art. 2"]),
    )
    _make_pack(packs, "TST", "file", doc)
    assert [e.id for e in load_pack_timeline("TST")] == [
        "tst.early",
        "tst.undated",
        "tst.late",
    ]
    eu = timeline_for_articles(["Art. 9"])
    assert eu
    merged = timeline_for_requirements(["Art. 9", "TST:Art. 1"])
    dated = [e.applies_from for e in merged if e.applies_from]
    assert dated == sorted(dated)
    ids = [e.id for e in merged]
    assert {e.id for e in eu} <= set(ids)
    assert {"tst.early", "tst.undated"} <= set(ids)
    assert "tst.late" not in ids
    assert merged[-1].applies_from is None
    assert len(ids) == len(set(ids))
    assert timeline_ids("TST:Art. 2") == ["tst.late"]
    assert timeline_for_requirements(["TST:Art. 1", "TST:Art. 1"]) == (
        timeline_for_requirements(["TST:Art. 1"])
    )


def test_pack_row_gets_backlog_deadline(packs: Path) -> None:
    doc = _doc(
        _entry(id="tst.one", applies_from="2031-02-03"),
        _entry(id="tst.two", applies_from=None, requirements=["TST:Art. 2"]),
        _entry(id="tst.a", applies_from="2031-02-03", requirements=["TST:Art. 3"]),
        _entry(id="tst.b", applies_from="2032-02-03", requirements=["TST:Art. 3"]),
    )
    _make_pack(packs, "TST", "file", doc)
    assert deadline_for("TST:Art. 1") == date(2031, 2, 3)
    assert deadline_for("TST:Art. 2") is None
    assert deadline_for("TST:Art. 3") is None  # two dates disagree
    assert deadline_for("CUSTOM:Rule 1") is None


def test_eu_lookup_equal_before_and_after_pack_timeline(packs: Path) -> None:
    before = {a: timeline_for_articles([a]) for a in ("Art. 5", "Art. 9", "Art. 50")}
    eu_before = regulatory_timeline.load_timeline()
    _make_pack(packs, "TST", "file", _doc(_entry()))
    load_pack_timeline("TST")
    timeline_for_requirements(["Art. 9", "TST:Art. 1"])
    after = {a: timeline_for_articles([a]) for a in before}
    assert after == before
    assert regulatory_timeline.load_timeline() == eu_before
    assert all(e.framework == "EU_AI_ACT" and not e.requirements for e in eu_before)
    assert timeline_for_requirements(["Art. 9"]) == before["Art. 9"]
