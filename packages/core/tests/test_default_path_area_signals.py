"""The ``area_signals`` group of ai_signals.json: tokens that map to an area by name.

A token listed there is first in ``scoring`` and maps, on the default scan path,
to the taxonomy key of its list. Every other scoring token still maps to no area
unless the intent classifier resolved one.
"""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.models import SignalCategory
from opencomplai_core.scan_engine import run_scan
from opencomplai_core.scanner.detectors._signals import load_signals
from opencomplai_core.scanner.mapping import (
    _AREA_TO_TAXONOMY,
    signal_category_to_taxonomy,
)

_GROUPS: dict[str, list[str]] = load_signals().get("area_signals", {})
_PAIRS = [(key, token) for key, tokens in _GROUPS.items() for token in tokens]
_ALLOWED_KEYS = {"critical_infrastructure", "education", "employment"}
_SCORING = SignalCategory.SCORING_PROFILING


def test_area_signal_token_maps_to_its_area_on_scoring(tmp_path: Path):
    assert _PAIRS, "no token ships in area_signals"
    for key, token in _PAIRS:
        assert signal_category_to_taxonomy(_SCORING, token) == [key], token
        root = tmp_path / token
        root.mkdir()
        (root / "control.py").write_text(
            f"def push(client):\n    client.{token}(40001, 7)\n", encoding="utf-8"
        )
        report = run_scan("area-signal", "HEAD", root, "an unrelated purpose")
        assert key in report.detected_categories, token
        assert key in {k for f in report.findings for k in f.mapped_taxonomy}, token


def test_area_signal_token_with_category_suffix_maps():
    assert _PAIRS, "no token ships in area_signals"
    for key, token in _PAIRS:
        labelled = f"{token}@{_SCORING.value}"
        assert signal_category_to_taxonomy(_SCORING, labelled) == [key], labelled


def test_unlisted_scoring_token_still_maps_to_no_area():
    for token in ("score", "rank", "decision", "write_registers", "proctoring", ""):
        assert signal_category_to_taxonomy(_SCORING, token) == [], token
    # A listed token maps only as a scoring signal, never as another category.
    for _, token in _PAIRS:
        assert signal_category_to_taxonomy(SignalCategory.ML_FRAMEWORK, token) == []


def test_every_area_signal_token_is_in_scoring_before_generic_tokens():
    scoring = load_signals()["scoring"]
    shipped = [token for _, token in _PAIRS]
    assert len(set(shipped)) == len(shipped)
    assert set(scoring[: len(shipped)]) == set(shipped)
    assert [t for t in scoring if t not in shipped], "generic tokens must remain"


def test_area_signals_keys_are_known_taxonomy_keys():
    assert set(_GROUPS) <= _ALLOWED_KEYS
    assert set(_GROUPS) <= set(_AREA_TO_TAXONOMY.values())
    assert all(isinstance(tokens, list) for tokens in _GROUPS.values())
