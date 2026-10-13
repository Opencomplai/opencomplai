"""Candidate tier of the Annex III benchmark: pinned counts, kept apart.

A candidate is a lead for a person, never a finding. The numbers here are
measured on ``benchmark/candidate_fixtures.py`` and never enter the precision
and recall pins of ``test_annex_iii_benchmark.py``. A change to a pin below is a
deliberate re-pin together with ``annex-iii-benchmark.md``.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
from opencomplai_core.scan_engine import run_scan

_BENCH_DIR = Path(__file__).parent / "benchmark"
_DOCS = Path(__file__).resolve().parents[3] / "docs" / "src"
_BENCH_PAGE = _DOCS / "concepts" / "annex-iii-benchmark.md"
_SCAN_PAGE = _DOCS / "cli" / "scan.md"
_SCANNER_PAGE = _DOCS / "getting-started" / "scanner.md"
_SECTION_HEADING = (
    "Candidates (leads for a person; not findings, not part of precision or recall)"
)

# Intent path candidates and default-path areas of each candidate fixture.
CANDIDATES_PINNED = {
    "fixtures": 8,
    "total": 3,
    "by_library": {
        "facenet_pytorch": {"fixtures": 1, "candidates": 1},
        "mtcnn": {"fixtures": 1, "candidates": 1},
        "retinaface": {"fixtures": 1, "candidates": 1},
    },
    "rows": {
        "retinaface-import-only": {
            "candidates": [("retinaface", "src/face.py")],
            "scan_areas": [1],
        },
        "mtcnn-import-only": {
            "candidates": [("mtcnn", "src/detector.py")],
            "scan_areas": [],
        },
        "facenet-pytorch-import-only": {
            "candidates": [("facenet_pytorch", "src/embed.py")],
            "scan_areas": [],
        },
        "face-recognition-finding-not-candidate": {
            "candidates": [],
            "scan_areas": [1],
        },
        "requirements-hyphenated-face-recognition": {
            "candidates": [],
            "scan_areas": [1],
        },
        "requirements-dotted-face-recognition": {
            "candidates": [],
            "scan_areas": [1],
        },
        "lookalike-names": {"candidates": [], "scan_areas": []},
        "import-under-tests-directory": {"candidates": [], "scan_areas": []},
    },
}


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"annex_iii_candidates_{name}", _BENCH_DIR / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cand_mod = _load("candidate_fixtures")
bench = _load("run_benchmark")


@pytest.fixture(scope="module")
def measured() -> dict:
    return bench.measure_candidates()


def test_candidate_fixture_set_shape():
    names = [f["name"] for f in cand_mod.CANDIDATE_FIXTURES]
    assert len(set(names)) == len(names)
    for f in cand_mod.CANDIDATE_FIXTURES:
        for key in ("purpose", "why", "files"):
            assert f[key], (f["name"], key)
    meta = cand_mod.CANDIDATE_BENCHMARK_META
    assert meta["needs_founder_review"] is True
    assert meta["confidence"] == "low"
    for key in ("source", "labelled_by", "date"):
        assert meta[key], key


def test_candidate_numbers_are_pinned(measured):
    assert measured["fixtures"] == CANDIDATES_PINNED["fixtures"]
    assert measured["total"] == CANDIDATES_PINNED["total"]
    assert measured["by_library"] == CANDIDATES_PINNED["by_library"]
    assert measured["rows"] == CANDIDATES_PINNED["rows"]
    labelled = {f["name"]: f for f in cand_mod.CANDIDATE_FIXTURES}
    assert set(measured["rows"]) == set(labelled)
    for name, row in measured["rows"].items():
        assert row["candidates"] == labelled[name]["expected_candidates"], name
        assert row["scan_areas"] == labelled[name]["expected_scan_areas"], name
    assert measured["total"] == sum(
        len(f["expected_candidates"]) for f in cand_mod.CANDIDATE_FIXTURES
    )


def test_a_finding_is_never_also_a_candidate():
    fx = next(
        f
        for f in cand_mod.CANDIDATE_FIXTURES
        if f["name"] == "face-recognition-finding-not-candidate"
    )
    intent, _art5, scan = bench._scan_fixture(fx)
    assert intent == [1]
    assert scan == [1]
    assert fx["expected_candidates"] == []


def _counts(per_area: dict) -> dict:
    return {a: (c["tp"], c["fp"], c["fn"]) for a, c in per_area.items()}


def test_candidates_do_not_enter_the_pinned_metrics():
    first = bench.measure()
    assert not [k for k in first if "candidate" in k.lower()]
    assert first["fixtures"] == 46
    bench.measure_candidates()
    second = bench.measure()
    assert second["fixtures"] == 46
    assert _counts(second["per_area"]) == _counts(first["per_area"])
    assert _counts(second["scan_per_area"]) == _counts(first["scan_per_area"])
    assert second["overall"] == first["overall"]
    assert second["scan_overall"] == first["scan_overall"]
    assert second["predictions"] == first["predictions"]


def test_hyphenated_dependency_is_detected_end_to_end():
    names = (
        "requirements-hyphenated-face-recognition",
        "requirements-dotted-face-recognition",
    )
    for name in names:
        fx = next(f for f in cand_mod.CANDIDATE_FIXTURES if f["name"] == name)
        assert "import" not in "".join(fx["files"].values()), name
        with bench._fixture_root(fx) as root:
            report = run_scan(fx["name"], "HEAD", root, fx["purpose"])
        assert not report.scan_errors, name
        assert not report.detector_errors, name
        areas = sorted(
            {
                bench._TAXONOMY_TO_AREA[c]
                for c in report.detected_categories
                if c in bench._TAXONOMY_TO_AREA
            }
        )
        assert areas == [1], name


def test_script_prints_candidates_section(capsys, measured):
    assert bench.main([]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert _SECTION_HEADING in lines
    start = lines.index(_SECTION_HEADING)
    table = [ln for ln in lines[start + 1 :] if ln.startswith("|")]
    assert table == bench.format_candidates_table(measured).splitlines()
    for library in CANDIDATES_PINNED["by_library"]:
        assert any(ln.startswith(f"| {library} |") for ln in table), library
    assert f"candidate_fixtures: {CANDIDATES_PINNED['fixtures']}" in lines
    assert len([ln for ln in lines if ln.startswith("| Overall |")]) == 2
    for ln in table:
        assert "precision" not in ln.lower(), ln
        assert "recall" not in ln.lower(), ln


def _table_blocks(page: str) -> list[str]:
    blocks, current = [], []
    for line in [*page.splitlines(), ""]:
        if line.startswith("|"):
            current.append(line)
        elif current:
            blocks.append("\n".join(current))
            current = []
    return blocks


def _first_candidate_section(page: str) -> str:
    """Text under the first heading that contains ``andidate``, to the next
    heading of the same or a higher level."""
    lines = page.splitlines()
    in_fence = False
    start = level = None
    body: list[str] = []
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        heading = None if in_fence else re.match(r"(#{1,6}) (.*)", line)
        if start is None:
            if heading and "andidate" in heading.group(2):
                start, level = line, len(heading.group(1))
                body.append(line)
            continue
        if heading and len(heading.group(1)) <= level:
            break
        body.append(line)
    assert start is not None, "no heading containing 'andidate'"
    return "\n".join(body)


def test_docs_state_candidate_tier_without_accuracy_claim(measured):
    page = _BENCH_PAGE.read_text(encoding="utf-8")
    assert bench.format_candidates_table(measured) in _table_blocks(page)

    scanner = _SCANNER_PAGE.read_text(encoding="utf-8")
    assert '"candidates"' in scanner

    for path in (_BENCH_PAGE, _SCAN_PAGE):
        section = _first_candidate_section(path.read_text(encoding="utf-8"))
        text = " ".join(section.split()).lower()
        assert "lead" in text, path.name
        assert "not a finding" in text or "not findings" in text, path.name
        assert "precision" in text, path.name
        assert "excluded from precision and recall" in text, path.name
        assert not re.search(r"\d+(\.\d+)?\s*%", text), path.name
