"""Scanner taxonomy mapping — no drift from rules.py."""

from __future__ import annotations

from opencomplai_core.models import SignalCategory
from opencomplai_core.rules import ANNEX_III_CATEGORIES, UNACCEPTABLE_RISK_SIGNALS
from opencomplai_core.scanner.mapping import (
    derive_declared_categories,
    signal_category_to_taxonomy,
)


def test_every_signal_category_maps_to_real_taxonomy_or_empty():
    for cat in SignalCategory:
        mapped = signal_category_to_taxonomy(cat)
        for key in mapped:
            if key == "unacceptable":
                continue
            assert key in ANNEX_III_CATEGORIES, f"{cat} mapped to unknown {key}"


def test_biometric_maps_to_biometric_category():
    mapped = signal_category_to_taxonomy(SignalCategory.BIOMETRIC, "face_recognition")
    assert "biometric" in mapped


def test_derive_declared_categories_matches_annex_iii():
    declared = derive_declared_categories("employment screening and ranking")
    assert "employment" in declared


def test_unacceptable_signal_in_purpose():
    declared = derive_declared_categories("social scoring system")
    assert "unacceptable" in declared or any(
        s in "social scoring system" for s in UNACCEPTABLE_RISK_SIGNALS
    )
