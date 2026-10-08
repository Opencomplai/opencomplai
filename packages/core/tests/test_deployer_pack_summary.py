"""SU-21b: metadata-only `summaries.packs` built from the packs in a directory."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_core.deployer_pack import (
    build_pack,
    build_packs_summary,
    with_pack_summary,
)
from opencomplai_core.models import ScanResult, ScanStatusArtifact
from opencomplai_core.summaries import (
    ArtifactSummaries,
    OversightSummary,
    PackIssuance,
)

SENTINEL = "SENTINEL-sys-text-7f3a"


def _write_pack(directory: Path, day: str, text: str = "x", tag: str = "") -> dict:
    directory.mkdir(exist_ok=True)
    pack = build_pack(
        {"points": [{"point": "a", "populated": True, "content": text + tag}]},
        system_id=SENTINEL,
        issued_on=day,
        generator_version="1",
    ).model_dump(mode="json")
    h = pack["integrity"]["pack_sha256"]
    (directory / f"deployer_pack_{h[:12]}.json").write_text(
        json.dumps(pack), encoding="utf-8"
    )
    return pack


def _artifact(**kw) -> ScanStatusArtifact:
    return ScanStatusArtifact(
        install_id="i",
        system_id="s",
        commit_ref="c",
        result=ScanResult.PASS,
        rationale_hash="sha256:a",
        duration_ms=1,
        **kw,
    )


def test_no_pack_dir_returns_none(tmp_path):
    assert build_packs_summary(tmp_path / "missing") is None
    assert build_packs_summary(tmp_path) is None


def test_summary_from_valid_packs(tmp_path):
    pack = _write_pack(tmp_path, "2026-10-07")
    s = build_packs_summary(tmp_path)
    assert s.issued == 1
    item = s.items[0]
    assert item.pack_sha256 == pack["integrity"]["pack_sha256"]
    assert (item.issued_on, item.kind.value) == ("2026-10-07", "deployer")
    assert (item.signer_key_id, item.items_provided, item.items_not_captured) == (
        None,
        1,
        0,
    )


def test_tampered_pack_is_not_counted(tmp_path):
    pack = _write_pack(tmp_path, "2026-10-07")
    path = next(tmp_path.glob("deployer_pack_*.json"))
    pack["content"]["points"][0]["content"] = "changed"
    path.write_text(json.dumps(pack), encoding="utf-8")
    assert build_packs_summary(tmp_path) is None


def test_items_capped_at_50_newest_first(tmp_path):
    for i in range(55):
        _write_pack(tmp_path, f"2026-01-{i % 28 + 1:02d}", tag=str(i))
    s = build_packs_summary(tmp_path)
    assert s.issued == 55
    assert len(s.items) == 50
    keys = [(i.issued_on, i.pack_sha256) for i in s.items]
    assert keys == sorted(keys, reverse=True)


def test_summary_has_no_content_keys(tmp_path):
    _write_pack(tmp_path, "2026-10-07", text=SENTINEL)
    dumped = build_packs_summary(tmp_path).model_dump(mode="json")
    assert set(dumped) == {"issued", "items"}
    for item in dumped["items"]:
        assert set(item) <= set(PackIssuance.model_fields)
    assert SENTINEL not in json.dumps(dumped)


def test_merge_preserves_other_summaries(tmp_path):
    _write_pack(tmp_path, "2026-10-07")
    other = ArtifactSummaries(
        oversight=OversightSummary(entries=1, approvals=1, resumes=0, roles=1)
    )
    merged = with_pack_summary(_artifact(summaries=other), tmp_path)
    assert merged.summaries.oversight == other.oversight
    assert merged.summaries.packs.issued == 1


def test_artifact_without_packs_is_byte_identical(tmp_path):
    art = _artifact()
    out = with_pack_summary(art, tmp_path)
    assert out is art
    assert out.model_dump_json() == art.model_dump_json()
