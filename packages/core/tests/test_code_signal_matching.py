"""Regression tests for identifier-aware Annex III / Art. 5 code signal matching."""

from __future__ import annotations

import pytest
from opencomplai_core.scanner.ai_usage_gate import _matches_pack_code_signal
from opencomplai_core.scanner.detectors._signals import (
    match_any_code_signal,
    match_code_signal,
    tokenize_identifier,
)


def test_tokenize_transfer_speed_column():
    segments = tokenize_identifier("TransferSpeedColumn")
    assert "transfer" in segments
    assert "speed" in segments
    assert "column" in segments
    assert "fer" not in segments


def test_fer_does_not_match_transfer_speed_column():
    assert match_code_signal("TransferSpeedColumn", "fer") is False
    assert match_code_signal("transfer_speed", "fer") is False
    assert match_code_signal("_has_inference_verb", "fer") is False


def test_explicit_fer_still_matches():
    assert match_code_signal("fer", "fer") is True
    assert match_code_signal("FER", "fer") is True
    assert match_code_signal("fer.detect", "fer") is True
    assert match_code_signal("import fer", "fer") is True


def test_multipart_signals_still_match():
    assert match_code_signal("face_recognition.encode", "face_recognition") is True
    assert match_code_signal("predict_default", "predict_default") is True
    assert match_code_signal("deepface.analyze", "deepface.analyze") is True


def test_pack_code_signal_gate_rejects_transfer_speed_column():
    pytest.importorskip("opencomplai_ai")
    assert _matches_pack_code_signal("TransferSpeedColumn") is False


def test_pack_code_signal_gate_accepts_emotion_recognition():
    pytest.importorskip("opencomplai_ai")
    assert _matches_pack_code_signal("detect_emotion") is True
    assert _matches_pack_code_signal("emotion_recognition") is True


def test_match_any_code_signal_returns_first_hit():
    pytest.importorskip("opencomplai_ai")
    from opencomplai_ai.knowledge.annex_iii import all_code_signals

    matched = match_any_code_signal("detect_emotion", all_code_signals())
    assert matched == "detect_emotion"
