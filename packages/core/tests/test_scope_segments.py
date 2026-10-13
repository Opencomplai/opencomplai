"""Scope classification is by whole path token, not substring."""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core.models import EvidenceScope as S
from opencomplai_core.scan_engine import run_scan
from opencomplai_core.scanner import constants
from opencomplai_core.scanner.cache import FeatureCache
from opencomplai_core.scanner.inventory import _classify_scope, build_repo_inventory


@pytest.mark.parametrize(
    "path",
    [
        "src/devices/camera.py",
        "documents/loader.py",
        "inspection/runner.py",
        "latest/model.py",
        "special_cases.py",
        "src/protest/handler.py",
        "src/developer/api.py",
    ],
)
def test_substring_lookalikes_are_prod(path):
    assert _classify_scope(path) == S.PROD


@pytest.mark.parametrize(
    ("path", "scope"),
    [
        ("tests/test_x.py", S.TEST),
        ("test_x.py", S.TEST),
        ("pkg/x_test.py", S.TEST),
        ("docs/guide.py", S.DOCS),
        ("dev/tool.py", S.DEV),
        ("spec/a.py", S.TEST),
        ("src/foo.spec.ts", S.TEST),
        ("requirements-dev.txt", S.DEV),
        ("Dockerfile.dev", S.DEV),
        ("vendor/lib.py", S.VENDOR),
        ("generated/api.py", S.GENERATED),
        ("__tests__/a.js", S.TEST),
        ("conftest.py", S.TEST),
        ("testing/h.py", S.TEST),
        ("specs/a.py", S.TEST),
        ("documentation/a.md", S.DOCS),
        ("development/a.py", S.DEV),
        ("unittests/a.py", S.TEST),
        ("unittest/a.py", S.TEST),
        ("pkg/testdata/a.json", S.TEST),
        ("testutils/h.py", S.TEST),
        ("tests\\test_x.py", S.TEST),
    ],
)
def test_true_positives_keep_scope(path, scope):
    assert _classify_scope(path) == scope


def test_scope_classifier_version_is_part_of_the_cache_key(tmp_path, monkeypatch):
    assert constants.SCOPE_CLASSIFIER_VERSION != "1.0.0"
    cache = FeatureCache(cache_dir=tmp_path, config_hash="c", detector_versions={})
    before = cache.cache_key("h")
    monkeypatch.setattr(
        "opencomplai_core.scanner.cache.SCOPE_CLASSIFIER_VERSION", "9.9.9"
    )
    assert cache.cache_key("h") != before


def test_lookalike_import_is_prod_evidence_through_inventory(tmp_path: Path):
    paths = ["documents/loader.py", "src/devices/camera.py"]
    for rel in paths:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("import openai\n", encoding="utf-8")
    inv = build_repo_inventory(tmp_path)
    scopes = {e.rel_path: e.scope for e in inv.entries}
    for rel in paths:
        assert scopes[rel] == S.PROD
    report = run_scan("s", "HEAD", tmp_path, "analytics dashboard")
    for rel in paths:
        items = [
            e
            for e in report.evidence
            if any(loc.startswith(f"{rel}:") for loc in e.locations)
        ]
        assert items, rel
        assert any(e.scope == S.PROD for e in items), rel
