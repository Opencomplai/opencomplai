"""Package-name normalisation in the code-signal matcher.

``face-recognition`` (the PyPI distribution name), ``Face.Recognition`` and
``face_recognition`` (the module name) are one signal. The fallback is a
whole-name equality, so look-alikes that only contain a signal stay unmatched.
"""

from __future__ import annotations

import pytest
from opencomplai_core.scanner.detectors._signals import (
    match_code_signal,
    match_token_identifier,
    normalize_package_name,
)


@pytest.mark.parametrize(
    ("identifier", "signal"),
    [
        ("face-recognition", "face_recognition"),
        ("face_recognition", "face_recognition"),
        ("Face.Recognition", "face_recognition"),
        ("FACE__RECOGNITION", "face_recognition"),
        ("face-_recognition", "face_recognition"),
        ("face-recognition.encode", "face_recognition"),
        ("Facial-Recognition", "facial_recognition"),
        ("dlib.face_recognition", "dlib.face_recognition"),
        ("Dlib-Face_Recognition", "dlib.face_recognition"),
        ("sentence_transformers", "sentence-transformers"),
        ("Sentence.Transformers", "sentence-transformers"),
        ("face-recognition==1.3.0", "face_recognition"),
        ("opencv-python", "opencv_python"),
    ],
)
def test_spelling_variants_are_one_signal(identifier, signal):
    assert match_code_signal(identifier, signal) is True


@pytest.mark.parametrize(
    ("identifier", "signal"),
    [
        ("interface-recognition", "face_recognition"),
        ("interface_recognition", "face_recognition"),
        ("face-recognition-lite", "face_recognition"),
        ("face_recognition_lite", "face_recognition"),
        ("my.face.recognition.tool", "face_recognition"),
        ("surface-recognition", "face_recognition"),
        ("surface-recognition", "facial_recognition"),
        ("deepfaced", "deepface"),
        ("insightfaces", "insightface"),
        ("facenet2", "facenet"),
        ("transfer-learning", "fer"),
        ("transfer.learning", "fer"),
        ("my-dlib-face-recognition-helper", "dlib.face_recognition"),
        ("face-recognizer", "face_recognition"),
    ],
)
def test_lookalike_names_do_not_match(identifier, signal):
    assert match_code_signal(identifier, signal) is False


# Restated from test_code_signal_matching.py (copied, not imported).
_PREVIOUS_POSITIVES = [
    ("fer", "fer"),
    ("FER", "fer"),
    ("fer.detect", "fer"),
    ("import fer", "fer"),
    ("face_recognition.encode", "face_recognition"),
    ("predict_default", "predict_default"),
    ("deepface.analyze", "deepface.analyze"),
    ("detect_emotion", "detect_emotion"),
    ("emotion_recognition", "emotion_recognition"),
]
_PREVIOUS_NEGATIVES = [
    ("TransferSpeedColumn", "fer"),
    ("transfer_speed", "fer"),
    ("_has_inference_verb", "fer"),
    ("face_recognition_lite", "face_recognition"),
    ("interface_recognition", "face_recognition"),
]


_NEAR_MISS_NAMES = ("wandbox", "sagemakerish", "langfusion", "vertexaix")
_NEAR_MISS_CATEGORIES = ("ai_sdks", "ml_frameworks", "orchestration")


def test_previous_positives_and_negatives_are_unchanged():
    for identifier, signal in _PREVIOUS_POSITIVES:
        assert match_code_signal(identifier, signal) is True, (identifier, signal)
    for identifier, signal in _PREVIOUS_NEGATIVES:
        assert match_code_signal(identifier, signal) is False, (identifier, signal)
    for name in _NEAR_MISS_NAMES:
        for category in _NEAR_MISS_CATEGORIES:
            assert match_token_identifier(name, category) is None, (name, category)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("face-recognition", "face_recognition"),
        ("Face.Recognition", "face_recognition"),
        ("FACE__RECOGNITION", "face_recognition"),
        ("face-_.recognition", "face_recognition"),
        ("-face-", "face"),
        ("_face_", "face"),
        ("deepface", "deepface"),
        ("Dlib-Face_Recognition", "dlib_face_recognition"),
        ("", ""),
        ("___", ""),
        ("-", ""),
        ("a b", "a b"),
    ],
)
def test_normalize_package_name(text, expected):
    assert normalize_package_name(text) == expected
