"""Synthetic programs for the candidate tier of the Annex III benchmark.

A candidate is a lead for a person: an AI library is imported but yields no
Annex III signal. These programs are kept apart from ``fixtures.py`` so no
candidate can enter the 46-fixture precision and recall pins.

``expected_candidates`` (``(library, relative_file)``, in report order) and
``expected_scan_areas`` (Annex III areas on the default scan path) were written
from the import-candidate contract and the signal dictionary before any measurement, and
are not edited to make the scanner agree. The intent path is never expected to
report a finding for an import-only program.
"""

from __future__ import annotations

CANDIDATE_BENCHMARK_META = {
    "source": (
        "import-candidate contract (libraries and scope rule); synthetic "
        "programs written for this benchmark"
    ),
    "confidence": "low",
    "needs_founder_review": True,
    "labelled_by": "benchmark author, single labeller",
    "date": "2026-10-12",
}

_PURPOSE = "internal image tooling"

CANDIDATE_FIXTURES: list[dict] = [
    {
        "name": "retinaface-import-only",
        "purpose": _PURPOSE,
        "why": "imports a face detector and calls nothing: a lead, not a finding",
        "files": {"src/face.py": "import retinaface\n"},
        "expected_candidates": [("retinaface", "src/face.py")],
        "expected_scan_areas": [1],
    },
    {
        "name": "mtcnn-import-only",
        "purpose": _PURPOSE,
        "why": "imports a face detector and calls nothing: a lead, not a finding",
        "files": {"src/detector.py": "import mtcnn\n"},
        "expected_candidates": [("mtcnn", "src/detector.py")],
        "expected_scan_areas": [],
    },
    {
        "name": "facenet-pytorch-import-only",
        "purpose": _PURPOSE,
        "why": "imports a face-embedding library and calls nothing: a lead",
        "files": {"src/embed.py": "import facenet_pytorch\n"},
        "expected_candidates": [("facenet_pytorch", "src/embed.py")],
        "expected_scan_areas": [],
    },
    {
        "name": "face-recognition-finding-not-candidate",
        "purpose": _PURPOSE,
        "why": "a finding is never also a candidate: face_recognition is a signal",
        "files": {
            "requirements.txt": "face_recognition\n",
            "src/face.py": (
                "import face_recognition\n"
                "\n"
                "\n"
                "def identify(img):\n"
                "    return face_recognition.face_locations(img)\n"
            ),
        },
        "expected_candidates": [],
        "expected_scan_areas": [1],
    },
    {
        "name": "requirements-hyphenated-face-recognition",
        "purpose": _PURPOSE,
        "why": (
            "the PyPI distribution name face-recognition is the same signal as "
            "face_recognition; no import, so no candidate"
        ),
        "files": {
            "requirements.txt": "face-recognition\n",
            "src/app.py": "def main():\n    return 0\n",
        },
        "expected_candidates": [],
        "expected_scan_areas": [1],
    },
    {
        "name": "requirements-dotted-face-recognition",
        "purpose": _PURPOSE,
        "why": (
            "Face.Recognition is another spelling of the same distribution; no "
            "import, so no candidate"
        ),
        "files": {
            "requirements.txt": "Face.Recognition\n",
            "src/app.py": "def main():\n    return 0\n",
        },
        "expected_candidates": [],
        "expected_scan_areas": [1],
    },
    {
        "name": "lookalike-names",
        "purpose": _PURPOSE,
        "why": (
            "interface_recognition and deepfaced only contain a signal as part of "
            "a longer name: no candidate, no area"
        ),
        "files": {
            "requirements.txt": "deepfaced\n",
            "src/interface_recognition.py": "def run():\n    return 1\n",
        },
        "expected_candidates": [],
        "expected_scan_areas": [],
    },
    {
        "name": "import-under-tests-directory",
        "purpose": _PURPOSE,
        "why": "candidates are production scope only: a test import is not a lead",
        "files": {
            "src/app.py": "def main():\n    return 0\n",
            "tests/test_face.py": "import cv2\n",
        },
        "expected_candidates": [],
        "expected_scan_areas": [],
    },
]
