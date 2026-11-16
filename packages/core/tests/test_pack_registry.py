"""Pack registry discovery: one directory per pack."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core import frameworks, pack_registry
from opencomplai_core.frameworks import FRAMEWORKS, data_version

BASELINE = Path(__file__).parent / "fixtures" / "pack_registry_baseline.json"


def test_registry_equals_baseline() -> None:
    """Key order and disclaimer_ref for every pack; label and data_version for
    the EU AI Act only (pack cards change the others)."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert list(FRAMEWORKS) == [row[0] for row in baseline]
    for row in baseline:
        pack = FRAMEWORKS[row[0]]
        if row[0] == "EU_AI_ACT":
            assert [pack.id, pack.label, pack.disclaimer_ref, data_version(pack)] == row
        else:
            assert [pack.id, pack.disclaimer_ref] == row
            assert pack.label == pack_registry.pack_label(
                pack_registry.load_pack_meta(row[0])
            )


def test_fifteen_packs_in_order() -> None:
    metas = pack_registry.discover_packs()
    assert len(metas) == 15
    assert list(FRAMEWORKS) == [m["id"] for m in metas]


def test_row_count_matches_data() -> None:
    for meta in pack_registry.discover_packs():
        base = pack_registry.pack_dir(meta["id"])
        if meta["requirements"]:
            data = json.loads((base / meta["requirements"]).read_text(encoding="utf-8"))
            rows = len([k for k in data if not k.startswith("_")])
        else:
            data = json.loads(
                (base / meta["data_files"][0]).read_text(encoding="utf-8")
            )
            rows = len(data["subcategories"])
        assert meta["row_count"] == rows, meta["id"]


def _write_pack(root: Path, key: str, **overrides: object) -> Path:
    meta = {
        "id": key,
        "order": 99,
        "kind": "native",
        "name": "Test pack",
        "short_name": "Test",
        "status": "attestation-led",
        "caveat": "a test",
        "disclaimer_ref": "DISCLAIMER_V2",
        "requirements": None,
        "data_files": [],
        "legacy_file": None,
        "copyright": "eu_law",
        "row_count": 0,
        "target_machine_share": 0,
        "timeline": "none",
        "catalogue": True,
    }
    meta.update(overrides)
    directory = root / key
    directory.mkdir(parents=True)
    path = directory / "pack.json"
    path.write_text(json.dumps(meta), encoding="utf-8")
    return path


def test_added_directory_is_discovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_pack(tmp_path, "EXTRA_PACK")
    monkeypatch.setattr(pack_registry, "PACKS_DIR", tmp_path)
    metas = pack_registry.discover_packs()
    assert [m["id"] for m in metas] == ["EXTRA_PACK"]
    assert pack_registry.pack_label(metas[0]) == "Test pack (attestation-led, a test)"
    assert pack_registry.pack_file("EXTRA_PACK", "pack.json") is not None
    assert pack_registry.pack_file("EXTRA_PACK", "nope.json") is None
    assert frameworks._build_registry()["EXTRA_PACK"].id == "EXTRA_PACK"


def test_id_must_match_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_pack(tmp_path, "ONE", id="TWO")
    monkeypatch.setattr(pack_registry, "PACKS_DIR", tmp_path)
    with pytest.raises(ValueError, match=r"pack.json"):
        pack_registry.load_pack_meta("ONE")


def test_missing_field_names_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_pack(tmp_path, "ONE")
    meta = json.loads(path.read_text(encoding="utf-8"))
    del meta["row_count"]
    path.write_text(json.dumps(meta), encoding="utf-8")
    monkeypatch.setattr(pack_registry, "PACKS_DIR", tmp_path)
    with pytest.raises(ValueError, match="row_count"):
        pack_registry.load_pack_meta("ONE")
