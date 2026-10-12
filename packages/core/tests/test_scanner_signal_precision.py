"""Signal dictionary precision: look-alike libraries and bare words are not biometric.

``opencv`` stays in the ``biometric`` list on purpose: one labelled benchmark
program (a face-attribute categorizer, whose only face signal is
``opencv-python``) is detected through it and nothing else, so removing it
would lose a true positive.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core.models import SignalCategory
from opencomplai_core.scanner.detectors._signals import (
    load_signals,
    match_token_identifier,
)
from opencomplai_core.scanner.features import ScanConfig, extract_features
from opencomplai_core.scanner.inventory import build_repo_inventory
from opencomplai_core.scanner.registry import DETECTOR_REGISTRY


def _all_evidence(root: Path) -> list:
    features = extract_features(build_repo_inventory(root), ScanConfig())
    out = []
    for det in DETECTOR_REGISTRY:
        out.extend(det.detect(features))
    return out


def test_look_alike_libraries_emit_no_biometric_evidence(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(
        "librosa\nfaster-whisper\nspeechbrain\npyannote.audio\nmediapipe\n",
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "audio.py").write_text(
        "import librosa\n"
        "import whisper\n"
        "import speechbrain\n"
        "import mediapipe as mp\n"
        "from faster_whisper import WhisperModel\n"
        "from pyannote.audio import Pipeline\n"
        "\n"
        "y, sr = librosa.load('a.wav')\n"
        "model = whisper.load_model('base')\n",
        encoding="utf-8",
    )
    evidence = _all_evidence(tmp_path)
    assert evidence, "the audio libraries should still be seen as AI present"
    assert [e for e in evidence if e.category == SignalCategory.BIOMETRIC] == []


@pytest.mark.parametrize("text", ["emotion", "speaker", "self.emotion_label"])
def test_bare_emotion_and_speaker_are_not_biometric(text: str):
    assert match_token_identifier(text, "biometric") is None


@pytest.mark.parametrize(
    "text",
    [
        "face_recognition",
        "deepface",
        "emotion_recognition",
        "speaker_verification",
        "gait_recognition",
        "fer",
    ],
)
def test_true_positive_biometric_signals_still_detected(text: str):
    assert match_token_identifier(text, "biometric") is not None


def test_fer_does_not_match_inside_a_longer_word():
    assert match_token_identifier("transfer_learning", "biometric") is None


@pytest.mark.parametrize("text", ["whisper", "speechbrain", "pyannote", "mediapipe"])
def test_moved_audio_models_stay_ai_present(text: str):
    assert match_token_identifier(text, "ml_frameworks") is not None


def test_signals_version_is_bumped():
    assert load_signals()["version"] == "1.3.0"


@pytest.mark.parametrize("text", ["faiss", "pgvector"])
def test_vector_index_libraries_stay_ai_present_without_an_area(text: str):
    assert match_token_identifier(text, "ml_frameworks") is not None
    assert match_token_identifier(text, "vector_embedding") is None
    assert match_token_identifier(text, "biometric") is None
