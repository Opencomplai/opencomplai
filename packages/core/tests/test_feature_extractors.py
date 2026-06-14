"""Feature extractors — typed facts, no raw secrets."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.scanner.features import ScanConfig, extract_features
from opencomplai_core.scanner.inventory import build_repo_inventory


def _setup_repo(tmp_path: Path) -> Path:
    (tmp_path / "requirements.txt").write_text("openai>=1.0\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "import openai\nclient = openai.Client()\n", encoding="utf-8"
    )
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-secret123\n", encoding="utf-8")
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "model.onnx").write_bytes(b"\x00\x01")
    return tmp_path


def test_manifest_extractor_finds_packages(tmp_path: Path):
    repo = _setup_repo(tmp_path)
    inv = build_repo_inventory(repo)
    features = extract_features(inv, ScanConfig())
    names = {p.name for p in features.packages}
    assert "openai" in names


def test_ast_extractor_finds_imports(tmp_path: Path):
    repo = _setup_repo(tmp_path)
    inv = build_repo_inventory(repo)
    features = extract_features(inv, ScanConfig())
    modules = {i.module for i in features.imports}
    assert "openai" in modules


def test_config_extractor_finds_endpoint_keys_not_values(tmp_path: Path):
    repo = _setup_repo(tmp_path)
    inv = build_repo_inventory(repo)
    features = extract_features(inv, ScanConfig())
    keys = {c.key for c in features.configs}
    assert "openai_api_key" in keys
    assert not any("sk-secret" in c.key for c in features.configs)


def test_artifact_extractor_finds_model_files(tmp_path: Path):
    repo = _setup_repo(tmp_path)
    inv = build_repo_inventory(repo)
    features = extract_features(inv, ScanConfig())
    assert len(features.artifacts) >= 1
    assert features.artifacts[0].extension == ".onnx"
