"""Tests for the generated pack index."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import build_index
from opencomplai_core.pack_registry import discover_packs

INDEX = build_index.build()["packs"]


def test_check_passes() -> None:
    assert build_index.main(["--check"]) == 0


def test_fifteen_entries_in_registry_order() -> None:
    assert len(INDEX) == 15
    assert [e["key"] for e in INDEX] == [m["id"] for m in discover_packs()]


def test_rows_equal_row_count() -> None:
    counts = {m["id"]: m["row_count"] for m in discover_packs()}
    assert {e["key"]: e["rows"] for e in INDEX} == counts


def test_class_counts_add_up_to_rows() -> None:
    for entry in INDEX:
        total = (
            entry["machine"]
            + entry["hybrid"]
            + entry["organisational"]
            + entry["unclassified"]
        )
        assert total == entry["rows"], entry["key"]


def test_the_file_ends_with_one_newline_and_has_no_path() -> None:
    text = build_index.OUT.read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert "\r" not in text
    assert "C:" not in text
    assert "\\" not in text
