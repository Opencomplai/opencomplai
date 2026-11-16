"""Tests for pack_doc: fill, check and the marker rule on a temporary pack."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import pack_doc
from opencomplai_core import pack_registry

KEY = "TEST_PACK"
PAGE = "frameworks/test-pack.md"
SKELETON = (
    "# Test pack\n\nIntro.\n\n<!-- rows:start -->\nold\n<!-- rows:end -->\n\nOutro.\n"
)


def make(monkeypatch, tmp_path, page_text=SKELETON) -> Path:
    packs = tmp_path / "packs"
    (packs / KEY).mkdir(parents=True)
    rows = {
        f"{KEY}:1": {
            "title": "First | one",
            "evidence_class": "machine",
            "default_ttl_days": 90,
            "needs_founder_review": True,
            "sources": [
                {"kind": "attestation", "ref": f"{KEY}:1"},
                {"kind": "artifact", "ref": "SECURITY.md", "role": "supporting"},
            ],
        },
        f"{KEY}:2": {
            "title": "Second",
            "evidence_class": "organisational",
            "default_ttl_days": 365,
            "needs_founder_review": False,
            "sources": [{"kind": "attestation", "ref": f"{KEY}:2"}],
        },
    }
    (packs / KEY / "requirements.json").write_text(json.dumps(rows), encoding="utf-8")
    (packs / KEY / "pack.json").write_text(json.dumps({"id": KEY}), encoding="utf-8")
    monkeypatch.setattr(pack_registry, "PACKS_DIR", packs)
    docs = tmp_path / "docs" / "src"
    monkeypatch.setattr(pack_doc, "DOCS_SRC", docs)
    page = docs / PAGE
    page.parent.mkdir(parents=True)
    if page_text is not None:
        page.write_text(page_text, encoding="utf-8")
    return page


def test_default_page_name():
    assert pack_doc.docs_page("ISO_IEC_27001", {}) == "frameworks/iso-iec-27001.md"
    assert pack_doc.docs_page("CRA", {"docs_page": "x/y.md"}) == "x/y.md"


def test_render_rows_lists_every_row(monkeypatch, tmp_path):
    make(monkeypatch, tmp_path)
    lines = pack_doc.render_rows(KEY).split("\n")
    assert lines[0].startswith("| Requirement | Title | Evidence class | Sources")
    assert len(lines) == 4
    assert "First \\| one" in lines[2]
    assert "artifact: SECURITY.md (supporting)" in lines[2]
    assert "| 90 |" in lines[2]
    assert lines[2].count(pack_doc.UNREVIEWED) == 1
    assert pack_doc.UNREVIEWED not in lines[3]


def test_page_is_filled_and_surroundings_kept(monkeypatch, tmp_path):
    page = make(monkeypatch, tmp_path)
    assert pack_doc.main([KEY, "--check"]) == 1
    assert pack_doc.main([KEY]) == 0
    text = page.read_text(encoding="utf-8")
    assert text.startswith("# Test pack\n\nIntro.\n\n<!-- rows:start -->\n| Req")
    assert text.endswith("<!-- rows:end -->\n\nOutro.\n")
    assert "old" not in text
    assert pack_doc.main([KEY, "--check"]) == 0


def test_check_fails_after_a_title_changes(monkeypatch, tmp_path):
    make(monkeypatch, tmp_path)
    pack_doc.main([KEY])
    assert pack_doc.main([KEY, "--check"]) == 0
    path = pack_registry.pack_dir(KEY) / "requirements.json"
    path.write_text(path.read_text().replace("Second", "Renamed"), encoding="utf-8")
    assert pack_doc.main([KEY, "--check"]) == 1
    assert pack_doc.check(KEY)


def test_page_without_markers_is_an_error(monkeypatch, tmp_path, capsys):
    make(monkeypatch, tmp_path, "# no markers\n")
    assert pack_doc.main([KEY]) == 2
    assert pack_doc.main([KEY, "--check"]) == 2
    assert "rows:start" in capsys.readouterr().err
    assert pack_doc.check(KEY)


def test_page_with_one_marker_is_an_error(monkeypatch, tmp_path):
    make(monkeypatch, tmp_path, "<!-- rows:start -->\n")
    with pytest.raises(ValueError, match="rows:end"):
        pack_doc.fill("<!-- rows:start -->\n", "t")
    assert pack_doc.main([KEY]) == 2


def test_missing_page_is_an_error(monkeypatch, tmp_path):
    make(monkeypatch, tmp_path, None)
    assert pack_doc.main([KEY]) == 2
    assert pack_doc.check(KEY)
