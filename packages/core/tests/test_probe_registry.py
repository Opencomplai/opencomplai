"""Probes declared as JSON: parsing, registration and the pinned snapshot."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core import gap_probes
from opencomplai_core.gap_probes import (
    _CODE_HINTS,
    _CONTENT_MARKERS,
    _PROBE_PATTERNS,
    PROBE_PROVENANCE,
    _register_probe_files,
    artifact_gap_status,
    registry_snapshot,
)
from opencomplai_core.models import GapStatus
from opencomplai_core.probe_registry import iter_probe_files, parse_probe_file

FIXTURE = Path(__file__).parent / "fixtures" / "probe_registry_snapshot.json"

PROBE = {
    "family": "unit_test",
    "probes": {
        "unit_test_probe": {
            "patterns": ["docs/unit_test_probe*.md"],
            "markers": {
                "all": [
                    {"re": "^owner:", "flags": "im"},
                    {"re": "review cadence"},
                ],
                "found_label": "an owner and a review cadence",
                "lacks_label": "owner or review cadence",
                "noun": "unit test record",
            },
            "provenance": {
                "source": "heuristic (no legal source): unit test",
                "confidence": "low",
                "needs_founder_review": True,
            },
        }
    },
}


@pytest.fixture
def tables():
    """Restore the four registry tables after a test that registers probes."""
    saved = [
        (table, dict(table))
        for table in (_PROBE_PATTERNS, _CONTENT_MARKERS, _CODE_HINTS, PROBE_PROVENANCE)
    ]
    yield
    for table, copy in saved:
        table.clear()
        table.update(copy)


def _write_json(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_snapshot_fixture_refs_are_unchanged():
    pinned = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert pinned
    current = registry_snapshot()
    for ref, entry in pinned.items():
        assert ref in current, ref
        assert current[ref] == entry, ref


def test_snapshot_is_json_serialisable():
    assert json.loads(json.dumps(registry_snapshot())) == registry_snapshot()


def test_shipped_probe_files_parse():
    for path, prefix in iter_probe_files():
        parse_probe_file(path, prefix)


def test_temp_shared_file_registers_a_probe(tmp_path: Path, tables):
    probe_file = _write_json(tmp_path / "shared" / "unit_test.json", PROBE)
    _register_probe_files([(probe_file, None)])
    ref = "unit_test_probe"
    assert ref in registry_snapshot()
    assert PROBE_PROVENANCE[ref]["confidence"] == "low"

    repo = tmp_path / "repo"
    repo.mkdir()
    assert artifact_gap_status(ref, repo).status == GapStatus.MISSING

    (repo / "docs").mkdir()
    (repo / "docs" / "unit_test_probe.md").write_text("short note", encoding="utf-8")
    row = artifact_gap_status(ref, repo)
    assert (row.status, row.confidence) == (GapStatus.PARTIAL, 0.35)

    (repo / "docs" / "unit_test_probe.md").write_text(
        "Owner: the platform team\nThe review cadence is quarterly.\n",
        encoding="utf-8",
    )
    row = artifact_gap_status(ref, repo)
    assert (row.status, row.confidence) == (GapStatus.PARTIAL, 0.6)


def test_pack_local_file_registers_with_prefix(tmp_path: Path, tables):
    local = {
        "family": "local",
        "probes": {"unit_pack.impact_assessment": {"patterns": ["docs/ia.md"]}},
    }
    path = _write_json(tmp_path / "probes.json", local)
    _register_probe_files([(path, "unit_pack")])
    assert _PROBE_PATTERNS["unit_pack.impact_assessment"] == ("docs/ia.md",)


def test_duplicate_ref_raises(tmp_path: Path, tables):
    first = _write_json(tmp_path / "a.json", PROBE)
    second = _write_json(tmp_path / "b.json", PROBE)
    _register_probe_files([(first, None)])
    with pytest.raises(ValueError, match="unit_test_probe"):
        _register_probe_files([(second, None)])


def test_ref_already_in_python_literals_raises(tmp_path: Path, tables):
    existing = next(iter(_PROBE_PATTERNS))
    path = _write_json(
        tmp_path / "x.json",
        {"family": "x", "probes": {existing: {"patterns": ["a.md"]}}},
    )
    with pytest.raises(ValueError, match="already registered"):
        _register_probe_files([(path, None)])
    assert gap_probes._PROBE_PATTERNS[existing]


@pytest.mark.parametrize("ref", ["Bad_Name", "1abc", "has.dot", "has-dash"])
def test_bad_shared_name_raises(tmp_path: Path, ref: str):
    path = _write_json(
        tmp_path / "bad.json", {"family": "x", "probes": {ref: {"patterns": ["a"]}}}
    )
    with pytest.raises(ValueError, match=r"bad.json"):
        parse_probe_file(path)


@pytest.mark.parametrize(
    "ref", ["impact_assessment", "other_pack.impact", "iso_iec_42005."]
)
def test_unprefixed_pack_local_ref_raises(tmp_path: Path, ref: str):
    path = _write_json(
        tmp_path / "probes.json", {"family": "x", "probes": {ref: {"patterns": ["a"]}}}
    )
    with pytest.raises(ValueError, match="iso_iec_42005"):
        parse_probe_file(path, "iso_iec_42005")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"patterns": []},
        {"patterns": ["a"], "extra": 1},
        {"patterns": ["a"], "markers": {"all": []}},
        {"patterns": ["a"], "code_hint": {"re": "(", "flags": ""}},
        {"patterns": ["a"], "code_hint": {"re": "x", "flags": "z"}},
    ],
)
def test_format_faults_name_file_and_ref(tmp_path: Path, body: dict):
    path = _write_json(tmp_path / "f.json", {"family": "x", "probes": {"ref_a": body}})
    with pytest.raises(ValueError, match=r"f\.json.*ref_a"):
        parse_probe_file(path)


SEED_DIR = Path(__file__).resolve().parents[1] / "src" / "opencomplai_core" / "probes"
# Upper case with no patterns: kept in the Python provenance table.
PROVENANCE_ONLY_REFS = {"EVAL_ADVERSARIAL_V1"}
SEED_FILES = {"eu_ai_act": "eu_ai_act.json", "ai_security": "ai_security.json"}


def test_seed_files_parse_and_cover_the_fixture() -> None:
    refs: set[str] = set()
    for family, name in SEED_FILES.items():
        path = SEED_DIR / name
        assert json.loads(path.read_text(encoding="utf-8"))["family"] == family
        parsed = parse_probe_file(path)
        assert parsed
        assert not refs & set(parsed)
        refs |= set(parsed)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert refs == set(fixture) - PROVENANCE_ONLY_REFS


def test_registry_snapshot_holds_every_fixture_ref() -> None:
    from opencomplai_core.gap_probes import registry_snapshot

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snapshot = registry_snapshot()
    for ref, content in fixture.items():
        assert snapshot[ref] == content, ref
