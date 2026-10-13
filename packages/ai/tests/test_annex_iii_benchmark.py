"""Labelled Annex III code-signal benchmark: shape, pinned numbers, offline run.

The numbers in ``PINNED`` are the baseline measured on the synthetic fixtures in
``benchmark/fixtures.py``. They move on purpose when the signals change: update
``PINNED`` and the tables in docs/src/concepts/annex-iii-benchmark.md together.
"""

from __future__ import annotations

import importlib.util
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
_NAMED_LOOK_ALIKES = (
    "opencv-photo-filter",
    "speech-notes",
    "internal-analytics-dashboard",
    "loan-calculator",
)
_FORBIDDEN_PATH_PARTS = ("test", "spec", "doc", "dev", "vendor", "generated")

# (tp, fp, fn) measured on both paths before the signal dictionary was tightened.
# Never edited when the signals move again: the precision and recall test below
# compares the live measurement with these constants, not with PINNED.
BASELINE = {
    "per_area": {
        1: (4, 0, 0),
        2: (1, 0, 2),
        3: (4, 0, 0),
        4: (3, 1, 1),
        5: (5, 8, 0),
        6: (2, 0, 1),
        7: (0, 0, 3),
        8: (2, 0, 1),
    },
    "overall": (21, 9, 8),
    "scan_per_area": {
        1: (4, 9, 0),
        2: (0, 0, 3),
        3: (0, 0, 4),
        4: (0, 0, 4),
        5: (0, 3, 5),
        6: (0, 0, 3),
        7: (0, 0, 3),
        8: (0, 0, 3),
    },
    "scan_overall": (4, 12, 25),
}

# (tp, fp, fn) per Annex III area 1 to 8.
PINNED = {
    "fixtures": 46,
    "none_fixtures": 17,
    "none_clean": 16,
    "scan_none_clean": 14,
    "art5_on_non_art5": 0,
    "per_area": {
        1: (4, 0, 0),
        2: (1, 0, 2),
        3: (4, 0, 0),
        4: (3, 0, 1),
        5: (5, 8, 0),
        6: (2, 0, 1),
        7: (1, 0, 2),
        8: (2, 0, 1),
    },
    "scan_per_area": {
        1: (4, 5, 0),
        2: (2, 0, 1),
        3: (0, 0, 4),
        4: (0, 0, 4),
        5: (0, 0, 5),
        6: (0, 0, 3),
        7: (0, 0, 3),
        8: (0, 0, 3),
    },
}


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"annex_iii_benchmark_{name}", _BENCH_DIR / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixtures_mod = _load("fixtures")
bench = _load("run_benchmark")


@pytest.fixture(scope="module")
def measured() -> dict:
    return bench.measure()


def _counts(per_area: dict) -> dict:
    return {a: (c["tp"], c["fp"], c["fn"]) for a, c in per_area.items()}


def test_fixture_set_shape():
    fixtures = fixtures_mod.FIXTURES
    names = [f["name"] for f in fixtures]
    assert 40 <= len(fixtures) <= 60
    assert len(set(names)) == len(names)
    assert {f["area"] for f in fixtures} <= {None, *range(1, 9)}
    for area in range(1, 9):
        assert sum(1 for f in fixtures if f["area"] == area) >= 3, area
    assert sum(1 for f in fixtures if f["area"] is None) >= 12
    for f in fixtures:
        assert f["purpose"], f["name"]
        assert f["why"], f["name"]
        assert 2 <= len(f["files"]) <= 4, f["name"]
        for rel, text in f["files"].items():
            assert len(text.splitlines()) < 30, (f["name"], rel)
            for part in Path(rel).parts:
                for banned in _FORBIDDEN_PATH_PARTS:
                    assert banned not in part.lower(), (f["name"], rel, banned)
    assert fixtures_mod.BENCHMARK_META["needs_founder_review"] is True


def test_named_look_alikes_are_present():
    by_name = {f["name"]: f for f in fixtures_mod.FIXTURES}
    for name in _NAMED_LOOK_ALIKES:
        assert name in by_name, name
        assert by_name[name]["area"] is None, name


def test_benchmark_numbers_are_pinned(measured):
    assert measured["fixtures"] == PINNED["fixtures"]
    assert measured["none_fixtures"] == PINNED["none_fixtures"]
    assert measured["none_clean"] == PINNED["none_clean"]
    assert measured["scan_none_clean"] == PINNED["scan_none_clean"]
    assert measured["art5_on_non_art5"] == PINNED["art5_on_non_art5"]
    assert _counts(measured["per_area"]) == PINNED["per_area"]
    assert _counts(measured["scan_per_area"]) == PINNED["scan_per_area"]


def _precision(tp: int, fp: int) -> float:
    return tp / (tp + fp) if tp + fp else 0.0


def test_precision_and_recall_against_pre_change_baseline(measured):
    base_scan = BASELINE["scan_overall"]
    now_scan = tuple(measured["scan_overall"][k] for k in ("tp", "fp", "fn"))
    assert _precision(now_scan[0], now_scan[1]) > _precision(base_scan[0], base_scan[1])
    base_intent = BASELINE["overall"]
    now_intent = tuple(measured["overall"][k] for k in ("tp", "fp", "fn"))
    assert _precision(now_intent[0], now_intent[1]) >= _precision(
        base_intent[0], base_intent[1]
    )
    for key in ("scan_per_area", "per_area"):
        now = _counts(measured[key])
        for area, (b_tp, _b_fp, b_fn) in BASELINE[key].items():
            n_tp, _n_fp, n_fn = now[area]
            assert n_tp / (n_tp + n_fn) >= b_tp / (b_tp + b_fn), (key, area)


def test_benchmark_runs_offline_without_model(monkeypatch):
    import opencomplai_ai.downloader as downloader

    downloads: list[str] = []

    def no_socket(self, *args, **kwargs):
        raise OSError("sockets are disabled in this test")

    def no_download(model_id, *args, **kwargs):
        downloads.append(model_id)
        raise AssertionError("a model download was attempted")

    monkeypatch.setattr(socket.socket, "connect", no_socket)
    monkeypatch.setattr(downloader, "ensure_model", no_download)

    result = bench.measure()

    assert result["fixtures"] == PINNED["fixtures"]
    assert downloads == []


def test_named_look_alikes_have_scan_path_predictions(measured):
    # The speech, loan and analytics look-alikes were cleaned by the signal
    # tightening; the photo filter still over-fires on the default scan path.
    cleaned = ("speech-notes", "loan-calculator", "internal-analytics-dashboard")
    for name in _NAMED_LOOK_ALIKES:
        if name in cleaned:
            assert not measured["predictions"][name]["scan"], name
        else:
            assert measured["predictions"][name]["scan"], name


def test_script_prints_per_area_and_overall_table(capsys):
    assert bench.main([]) == 0
    lines = capsys.readouterr().out.splitlines()
    overall = [ln for ln in lines if ln.startswith("| Overall |")]
    assert len(overall) == 2
    for area in range(1, 9):
        assert len([ln for ln in lines if ln.startswith(f"| {area} |")]) == 2, area
    assert any(ln.startswith("none_clean:") for ln in lines)
    assert any(ln.startswith("scan_none_clean:") for ln in lines)


def test_docs_page_shows_measured_table_and_says_synthetic(measured):
    page = _DOCS_PAGE.read_text(encoding="utf-8")
    # Whole table blocks, so a table with a row missing or a digit changed fails.
    blocks, current = [], []
    for line in [*page.splitlines(), ""]:
        if line.startswith("|"):
            current.append(line)
        elif current:
            blocks.append("\n".join(current))
            current = []
    assert bench.format_table(measured, "intent") in blocks
    assert bench.format_table(measured, "scan") in blocks
    assert "synthetic" in page.lower()


def test_failed_intent_analysis_is_an_error(monkeypatch):
    from opencomplai_ai.detector import IntentDetector

    def boom(self, *args, **kwargs):
        raise ValueError("backend exploded")

    monkeypatch.setattr(IntentDetector, "detect", boom)

    with pytest.raises(RuntimeError):
        bench.measure(fixtures=fixtures_mod.FIXTURES[:1])
