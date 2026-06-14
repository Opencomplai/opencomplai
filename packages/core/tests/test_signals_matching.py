"""Unit tests for signal token matching."""

from __future__ import annotations

from opencomplai_core.scanner.detectors._signals import (
    match_token,
    match_token_identifier,
)


def test_recommended_does_not_match_scoring():
    assert match_token("recommended", "scoring") is None


def test_standalone_recommend_matches_scoring():
    assert match_token("recommend", "scoring") == "recommend"


def test_recommend_in_sentence_matches_scoring():
    assert match_token("we recommend this approach", "scoring") == "recommend"


def test_identifier_substring_preserved():
    assert match_token_identifier("recommend_user", "scoring") == "recommend"


def test_empty_category_returns_none():
    assert match_token("anything", "nonexistent_category_xyz") is None
