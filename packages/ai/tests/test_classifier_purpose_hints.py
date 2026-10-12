"""The declared-purpose hint matches whole words, not substrings."""

from __future__ import annotations

import pytest
from opencomplai_ai.classifier import _purpose_suggests_area


@pytest.mark.parametrize(
    ("purpose", "area"),
    [
        ("interface layout", None),
        ("example report", None),
        ("unemployment statistics", None),
        ("face unlock", 1),
        ("exam proctoring tool", 3),
        ("recruitment screening", 4),
        ("recruiter shortlist", 4),
        ("entrance examination", 3),
        ("students grading", 3),
    ],
)
def test_purpose_hint_needs_a_whole_word(purpose: str, area: int | None):
    assert _purpose_suggests_area(purpose) == area
