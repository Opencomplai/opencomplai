"""Held-out Annex III and Article 5 benchmark: shape, pinned numbers, tables.

The numbers in ``HELDOUT_PINNED`` and ``TOP1_PINNED`` are as measured at this
commit, before any later dictionary change; they move only by a
deliberate re-pin that edits no fixture. They are separate from ``PINNED`` in
``test_annex_iii_benchmark.py``, which stays untouched. The held-out set is
never to be tuned against: a low number here is the result, not a defect to fix
by editing a program, a label or the signal dictionary.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import socket
from pathlib import Path

import pytest

_BENCH_DIR = Path(__file__).parent / "benchmark"
_DOCS_PAGE = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "src"
    / "concepts"
    / "annex-iii-benchmark.md"
)
_FORBIDDEN_PATH_PARTS = ("test", "spec", "doc", "dev", "vendor", "generated")
# Phrases the docs section must carry so the labelling status is stated plainly.
_STATUS_PHRASES = ("single author", "not a second review")
_SECTION_HEADING = "## Held-out set"

# Intent path and default scan path, as (tp, fp, fn); the held-out set has 24
# programs, 12 labelled with an Annex III area and 12 with no area (4 of those
# are Art. 5 positives).
HELDOUT_PINNED = {
    "fixtures": 24,
    "none_fixtures": 12,
    "none_clean": 10,
    "scan_none_clean": 9,
    "overall": (4, 4, 8),
    "scan_overall": (1, 3, 11),
    "per_area": {
        1: (1, 1, 0),
        2: (0, 0, 2),
        3: (0, 0, 1),
        4: (1, 0, 1),
        5: (0, 3, 2),
        6: (1, 0, 0),
        7: (1, 0, 1),
        8: (0, 0, 1),
    },
    "scan_per_area": {
        1: (1, 3, 0),
        2: (0, 0, 2),
        3: (0, 0, 1),
        4: (0, 0, 2),
        5: (0, 0, 2),
        6: (0, 0, 1),
        7: (0, 0, 2),
        8: (0, 0, 1),
    },
    # (tp, fp, fn) of the Art. 5 flag against the art5 label.
    "art5": (1, 0, 3),
    # language -> (programs, area-labelled programs detected on the intent path)
    "by_language": {
        "go": (2, 0),
        "java": (2, 0),
        "javascript": (2, 0),
        "python": (16, 3),
        "typescript": (2, 1),
    },
}

# (n, correct, none, tie, wrong) of the proposal's single pick per labelled program.
TOP1_PINNED = {
    "training": (29, 13, 9, 2, 5),
    "heldout": (12, 1, 9, 1, 1),
}

# sha256 of repr(sorted((name, area))) over fixtures.FIXTURES.
TRAINING_SHA256 = "7e6eec824d41b61bb508927a41ef2a37e9b6b0c10abb64063868bdff7a4249de"


def _load(name: str, tag: str):
    spec = importlib.util.spec_from_file_location(
        f"annex_iii_heldout_{tag}", _BENCH_DIR / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixtures_mod = _load("fixtures", "fixtures")
heldout_mod = _load("heldout_fixtures", "heldout")
bench = _load("run_benchmark", "bench")


@pytest.fixture(scope="module")
def heldout_measured() -> dict:
    return bench.measure_heldout()


@pytest.fixture(scope="module")
def top1_training() -> dict:
    return bench.measure_top1(fixtures_mod.FIXTURES)


@pytest.fixture(scope="module")
def top1_heldout() -> dict:
    return bench.measure_top1(heldout_mod.HELDOUT)


def _counts(per_area: dict) -> dict:
    return {a: (c["tp"], c["fp"], c["fn"]) for a, c in per_area.items()}


def _tuple(c: dict) -> tuple[int, int, int]:
    return (c["tp"], c["fp"], c["fn"])


def _top1_tuple(t: dict) -> tuple[int, int, int, int, int]:
    return (t["n"], t["correct"], t["none"], t["tie"], t["wrong"])


def test_heldout_set_shape():
    fixtures = heldout_mod.HELDOUT
    names = [f["name"] for f in fixtures]
    assert 20 <= len(fixtures) <= 30
    assert len(set(names)) == len(names)
    assert not set(names) & {f["name"] for f in fixtures_mod.FIXTURES}
    for f in fixtures:
        assert f["labeller"] in {"author", "second_pass"}, f["name"]
        assert f["purpose"], f["name"]
        assert f["why"], f["name"]
    areas = {f["area"] for f in fixtures}
    assert areas <= {None, *range(1, 9)}
    assert set(range(1, 9)) <= areas
    non_python = [
        f
        for f in fixtures
        if f["language"] in {"javascript", "typescript", "java", "go"}
    ]
    assert len(non_python) >= 6
    languages = {f["language"] for f in non_python}
    assert languages & {"javascript", "typescript"}
    assert "java" in languages
    assert "go" in languages
    art5 = [f for f in fixtures if f["art5"] and f["area"] is None]
    assert len(art5) >= 4
    points = set()
    for f in art5:
        match = re.match(r"Art\.5\(1\)\(([a-i])\)", f["why"])
        assert match, (f["name"], f["why"])
        points.add(match.group(1))
    assert len(points) >= 4
    for f in fixtures:
        assert 2 <= len(f["files"]) <= 4, f["name"]
        for rel, text in f["files"].items():
            assert len(text.splitlines()) < 30, (f["name"], rel)
            text.encode("ascii")
            for part in Path(rel).parts:
                for banned in _FORBIDDEN_PATH_PARTS:
                    assert banned not in part.lower(), (f["name"], rel, banned)
    assert heldout_mod.HELDOUT_META["needs_founder_review"] is True


def test_heldout_numbers_are_pinned(heldout_measured):
    m = heldout_measured
    assert m["fixtures"] == HELDOUT_PINNED["fixtures"]
    assert m["none_fixtures"] == HELDOUT_PINNED["none_fixtures"]
    assert m["none_clean"] == HELDOUT_PINNED["none_clean"]
    assert m["scan_none_clean"] == HELDOUT_PINNED["scan_none_clean"]
    assert _tuple(m["overall"]) == HELDOUT_PINNED["overall"]
    assert _tuple(m["scan_overall"]) == HELDOUT_PINNED["scan_overall"]
    assert _counts(m["per_area"]) == HELDOUT_PINNED["per_area"]
    assert _counts(m["scan_per_area"]) == HELDOUT_PINNED["scan_per_area"]
    assert (m["art5_tp"], m["art5_fp"], m["art5_fn"]) == HELDOUT_PINNED["art5"]
    assert {
        lang: (row["fixtures"], row["area_tp"])
        for lang, row in m["by_language"].items()
    } == HELDOUT_PINNED["by_language"]


def test_top1_numbers_are_pinned(top1_training, top1_heldout):
    assert _top1_tuple(top1_training) == TOP1_PINNED["training"]
    assert _top1_tuple(top1_heldout) == TOP1_PINNED["heldout"]


def test_training_fixtures_and_pins_are_untouched():
    fixtures = fixtures_mod.FIXTURES
    assert len(fixtures) == 46
    pairs = sorted((f["name"], f["area"]) for f in fixtures)
    digest = hashlib.sha256(repr(pairs).encode("utf-8")).hexdigest()
    assert digest == TRAINING_SHA256


def test_wilson_interval_known_values():
    assert bench.wilson_interval(0, 0) is None
    lo, hi = bench.wilson_interval(5, 10)
    assert abs(lo - 0.237) < 0.005
    assert abs(hi - 0.763) < 0.005
    lo, hi = bench.wilson_interval(10, 10)
    assert abs(hi - 1.0) < 1e-9
    assert abs(lo - 0.722) < 0.005
    for n in (1, 2, 5, 12, 29, 46):
        for k in range(n + 1):
            lo, hi = bench.wilson_interval(k, n)
            assert 0 <= lo <= k / n <= hi <= 1, (k, n)


def test_script_prints_training_heldout_and_top1_tables(capsys):
    assert bench.main([]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert any(ln.startswith("Training set (46 programs)") for ln in lines)
    assert any(ln.startswith("Held-out set (24 programs)") for ln in lines)
    assert "Proposal top-1" in lines
    for label in ("Training", "Held-out"):
        for path in ("Intent path", "Default scan path"):
            rows = [ln for ln in lines if ln.startswith(f"| {label} | {path} |")]
            assert len(rows) == 1, (label, path)
    top1 = [ln for ln in lines if ln.startswith("| Set | n | Correct |")]
    assert len(top1) == 1
    assert len([ln for ln in lines if re.match(r"\| Held-out \| \d+ \|", ln)]) == 1
    assert len([ln for ln in lines if re.match(r"\| Training \| \d+ \|", ln)]) == 1
    # Every interval cell carries a point estimate, n and a Wilson interval
    # (or "n/a (n=0)"); a bare "95% CI" in a header would not prove that.
    cell_re = re.compile(r"\d+\.\d% \(n=\d+, 95% CI \d+\.\d-\d+\.\d%\)|n/a \(n=0\)")
    set_rows = [
        ln
        for ln in lines
        if re.match(r"\| (Training|Held-out) \| (Intent path|Default scan path) \|", ln)
    ]
    top1_rows = [
        ln for ln in lines if re.match(r"\| (Training|Held-out) \| \d+ \|", ln)
    ]
    assert len(set_rows) == 4
    assert len(top1_rows) == 2
    for row in set_rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert len(cells) == 8, row
        assert all(cell_re.fullmatch(c) for c in cells[-2:]), row
    for row in top1_rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert len(cells) == 7, row
        assert cell_re.fullmatch(cells[-1]), row
        assert not cells[-1].startswith("n/a"), row
    # The existing test counts these prefixes; a new table must not add to them.
    assert len([ln for ln in lines if ln.startswith("| Overall |")]) == 2
    for area in range(1, 9):
        assert len([ln for ln in lines if ln.startswith(f"| {area} |")]) == 2, area
    assert any(ln.startswith("heldout_art5:") for ln in lines)
    assert any(ln.startswith("heldout_language_go:") for ln in lines)


def test_heldout_runs_offline_without_model(monkeypatch):
    import opencomplai_ai.downloader as downloader

    downloads: list[str] = []

    def no_socket(self, *args, **kwargs):
        raise OSError("sockets are disabled in this test")

    def no_download(model_id, *args, **kwargs):
        downloads.append(model_id)
        raise AssertionError("a model download was attempted")

    monkeypatch.setattr(socket.socket, "connect", no_socket)
    monkeypatch.setattr(downloader, "ensure_model", no_download)

    result = bench.measure_heldout()
    top1 = bench.measure_top1(heldout_mod.HELDOUT)

    assert result["fixtures"] == HELDOUT_PINNED["fixtures"]
    assert top1["n"] == TOP1_PINNED["heldout"][0]
    assert downloads == []


def _table_blocks(page: str) -> list[str]:
    blocks, current = [], []
    for line in [*page.splitlines(), ""]:
        if line.startswith("|"):
            current.append(line)
        elif current:
            blocks.append("\n".join(current))
            current = []
    return blocks


def test_docs_page_has_heldout_section_and_tables(
    heldout_measured, top1_training, top1_heldout
):
    page = _DOCS_PAGE.read_text(encoding="utf-8")
    assert any(ln.startswith(_SECTION_HEADING) for ln in page.splitlines())
    lower = page.lower()
    for phrase in _STATUS_PHRASES:
        assert phrase in lower, phrase
    blocks = _table_blocks(page)
    training = bench.measure()
    assert bench.format_set_table("Training", training) in blocks
    assert bench.format_set_table("Held-out", heldout_measured) in blocks
    assert bench.format_top1_table(top1_training, top1_heldout) in blocks
