"""Intent snippets are read relative to the scan root, not the working directory."""

from __future__ import annotations

import importlib.util
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

from opencomplai_ai.detector import IntentDetector
from opencomplai_ai.models import IntentAnnotation
from opencomplai_core import scan_engine
from opencomplai_core.models import EvidenceScope
from opencomplai_core.scan_engine import run_scan
from opencomplai_core.scanner.feature_types import CallsiteRef, FeatureStore

_BENCH = Path(__file__).parent / "benchmark"


def _fixtures() -> list[dict]:
    spec = importlib.util.spec_from_file_location(
        "annex_iii_root_fixtures", _BENCH / "fixtures.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FIXTURES


def _build_repo(tmp_path: Path) -> tuple[Path, dict]:
    fixture = next(f for f in _fixtures() if f["area"] is not None)
    repo = tmp_path / "repo"
    for rel, text in fixture["files"].items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return repo, fixture


def _scan(repo: Path, fixture: dict):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return run_scan(
            fixture["name"],
            "HEAD",
            repo,
            fixture["purpose"],
            ai_intent=True,
            ai_model="codebert-onnx",
        )


def _keys(report) -> list[tuple]:
    return sorted((f.location, f.annex_iii_area) for f in report.eu_ai_scan.high_risk)


def test_intent_findings_same_from_foreign_cwd(tmp_path, monkeypatch):
    repo, fixture = _build_repo(tmp_path)
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(repo)
    inside = _scan(repo, fixture)
    monkeypatch.chdir(other)
    outside = _scan(repo, fixture)
    assert _keys(inside)
    assert _keys(inside) == _keys(outside)
    assert not any(w.startswith("snippet_unreadable") for w in outside.warnings)


def test_unreadable_snippet_warns_in_report(tmp_path, monkeypatch):
    repo, fixture = _build_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    real = scan_engine.extract_features

    def _extract_then_delete(*args, **kwargs):
        store = real(*args, **kwargs)
        targets = sorted(repo.rglob("*.py"))
        targets[0].unlink()
        _extract_then_delete.gone = targets[0].relative_to(repo).as_posix()
        return store

    monkeypatch.setattr(scan_engine, "extract_features", _extract_then_delete)
    report = _scan(repo, fixture)
    warns = [w for w in report.warnings if w.startswith("snippet_unreadable:")]
    assert warns
    assert _extract_then_delete.gone in warns[0]


def test_detector_exposes_unreadable(tmp_path):
    store = FeatureStore(repo_root=tmp_path)
    store.callsites.append(
        CallsiteRef(name="m.predict", location="gone.py:4", scope=EvidenceScope.PROD)
    )
    backend = MagicMock()
    backend.classify.return_value = IntentAnnotation(model_id="codebert-onnx")
    with patch("opencomplai_ai.detector.ModelRegistry") as registry:
        registry.resolve.return_value = backend
        detector = IntentDetector("codebert-onnx", repo_root=tmp_path)
        detector.detect(store)
    assert detector.unreadable_snippets == frozenset({"gone.py:4"})
