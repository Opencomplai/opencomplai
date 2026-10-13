"""Import candidates on the real intent path: leads, never findings."""

from __future__ import annotations

import contextlib
import warnings
from pathlib import Path

from opencomplai_core import scan_engine
from opencomplai_core.models import EuAiScanSummary
from opencomplai_core.scan_engine import run_scan
from opencomplai_core.scanner.proposal import build_classification_proposal

_PURPOSE = "customer support chatbot"


def _write(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def _scan(root: Path, **kwargs):
    kwargs.setdefault("ai_intent", True)
    if kwargs["ai_intent"]:
        kwargs.setdefault("ai_model", "codebert-onnx")
    with contextlib.chdir(root), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return run_scan("cand-sys", "HEAD", root, _PURPOSE, **kwargs)


def _retinaface_repo(tmp_path: Path) -> Path:
    return _write(tmp_path, {"src/face.py": "import retinaface\n"})


def test_import_only_retinaface_repo_yields_one_candidate_and_no_finding(tmp_path):
    report = _scan(_retinaface_repo(tmp_path))
    scan = report.eu_ai_scan
    assert [(c.library, c.file, c.line, c.reason) for c in scan.candidates] == [
        ("retinaface", "src/face.py", 1, "imported_not_classified")
    ]
    assert scan.high_risk == []
    assert scan.prohibited == []
    assert scan.limited_risk == []


def test_face_recognition_repo_keeps_finding_and_has_no_candidate(tmp_path):
    root = _write(
        tmp_path,
        {
            "requirements.txt": "face_recognition\n",
            "src/face.py": (
                "import face_recognition\n"
                "def identify(img):\n"
                "    return face_recognition.face_locations(img)\n"
            ),
        },
    )
    scan = _scan(root).eu_ai_scan
    assert scan.high_risk
    assert any(f.annex_iii_area == 1 for f in scan.high_risk)
    assert scan.candidates == []


def test_import_in_test_directory_yields_no_candidate(tmp_path):
    root = _write(tmp_path, {"tests/test_face.py": "import cv2\n"})
    assert _scan(root).eu_ai_scan.candidates == []


def test_cv2_dlib_mtcnn_facenet_pytorch_repo_yields_four_candidates(tmp_path):
    root = _write(
        tmp_path,
        {
            "src/a.py": "import cv2\n",
            "src/b.py": "import dlib\n",
            "src/c.py": "import mtcnn\n",
            "src/d.py": "import facenet_pytorch\n",
        },
    )
    scan = _scan(root).eu_ai_scan
    assert [(c.library, c.file) for c in scan.candidates] == [
        ("cv2", "src/a.py"),
        ("dlib", "src/b.py"),
        ("mtcnn", "src/c.py"),
        ("facenet_pytorch", "src/d.py"),
    ]
    assert scan.high_risk == []
    assert scan.prohibited == []


def test_candidates_do_not_reach_proposal_or_counts(tmp_path, monkeypatch):
    root = _retinaface_repo(tmp_path)
    with_candidates = _scan(root)
    assert with_candidates.eu_ai_scan.candidates

    assert build_classification_proposal(
        with_candidates.eu_ai_scan
    ) == build_classification_proposal(EuAiScanSummary())

    monkeypatch.setattr(scan_engine, "find_import_candidates", lambda *a, **k: [])
    without = _scan(root)
    assert without.eu_ai_scan.candidates == []
    for field in (
        "gated_callsite_count",
        "regulatory_finding_count",
    ):
        assert getattr(with_candidates.eu_ai_scan, field) == getattr(
            without.eu_ai_scan, field
        )
    assert with_candidates.severity == without.severity
    assert with_candidates.discrepancies == without.discrepancies
    assert with_candidates.report_hash == without.report_hash
    assert with_candidates.evidence == without.evidence


def test_default_and_legacy_scans_have_no_candidates(tmp_path):
    root = _retinaface_repo(tmp_path)
    assert _scan(root, ai_intent=False).eu_ai_scan is None
    assert _scan(root, ai_legacy=True).eu_ai_scan is None
