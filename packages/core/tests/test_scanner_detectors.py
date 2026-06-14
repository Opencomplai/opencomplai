"""Scanner detectors — evidence with path:line, no source text."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.models import SignalCategory
from opencomplai_core.scanner.features import ScanConfig, extract_features
from opencomplai_core.scanner.inventory import build_repo_inventory
from opencomplai_core.scanner.registry import DETECTOR_REGISTRY


def _ai_repo(tmp_path: Path) -> Path:
    (tmp_path / "requirements.txt").write_text(
        "face_recognition\nopenai\n", encoding="utf-8"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "face.py").write_text(
        "import face_recognition\nimport openai\n", encoding="utf-8"
    )
    return tmp_path


def test_detectors_emit_evidence_with_path_line(tmp_path: Path):
    repo = _ai_repo(tmp_path)
    inv = build_repo_inventory(repo)
    features = extract_features(inv, ScanConfig())
    all_evidence = []
    for det in DETECTOR_REGISTRY:
        all_evidence.extend(det.detect(features))
    assert len(all_evidence) > 0
    for ev in all_evidence:
        assert ":" in ev.locations[0]
        assert ev.token_label
        assert "import face_recognition" not in str(ev.model_dump())


def test_clean_repo_emits_no_biometric_prod_evidence(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    inv = build_repo_inventory(tmp_path)
    features = extract_features(inv, ScanConfig())
    all_evidence = []
    for det in DETECTOR_REGISTRY:
        all_evidence.extend(det.detect(features))
    biometric = [e for e in all_evidence if e.category == SignalCategory.BIOMETRIC]
    assert len(biometric) == 0
