"""ML-platform and LLM-observability packages are detected in the right category."""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core.models import SignalCategory
from opencomplai_core.scanner.detectors._signals import (
    load_signals,
    match_token_identifier,
)
from opencomplai_core.scanner.detectors.ai_dependency import AiDependencyDetector
from opencomplai_core.scanner.detectors.ast_usage import AstUsageDetector
from opencomplai_core.scanner.features import ScanConfig, extract_features
from opencomplai_core.scanner.inventory import build_repo_inventory

# token: (json_key, category, pip_name, import_stmt)
EXPECTED = {
    "sagemaker": (
        "ml_frameworks",
        SignalCategory.ML_FRAMEWORK,
        "sagemaker",
        "import sagemaker",
    ),
    "wandb": ("ml_frameworks", SignalCategory.ML_FRAMEWORK, "wandb", "import wandb"),
    "databricks-sdk": (
        "ml_frameworks",
        SignalCategory.ML_FRAMEWORK,
        "databricks-sdk",
        "from databricks.sdk import WorkspaceClient",
    ),
    "langfuse": (
        "orchestration",
        SignalCategory.LLM_ORCHESTRATION,
        "langfuse",
        "import langfuse",
    ),
    "vertexai": ("ai_sdks", SignalCategory.AI_SDK, "vertexai", "import vertexai"),
}
IDS = list(EXPECTED)


def _features(repo: Path):
    return extract_features(build_repo_inventory(repo), ScanConfig())


@pytest.mark.parametrize("token", IDS)
def test_signal_in_expected_category(token: str):
    key = EXPECTED[token][0]
    signals = load_signals()
    assert token in signals[key]
    others = [
        k for k, v in signals.items() if k != key and isinstance(v, list) and token in v
    ]
    assert others == []


@pytest.mark.parametrize("token", IDS)
def test_dependency_detected(tmp_path: Path, token: str):
    _, category, pip_name, _ = EXPECTED[token]
    (tmp_path / "requirements.txt").write_text(pip_name + "\n", encoding="utf-8")
    items = AiDependencyDetector().detect(_features(tmp_path))
    assert len(items) == 1
    assert items[0].category == category
    assert items[0].token_label == token


@pytest.mark.parametrize("token", IDS)
def test_import_detected(tmp_path: Path, token: str):
    _, category, _, stmt = EXPECTED[token]
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(stmt + "\n", encoding="utf-8")
    items = AstUsageDetector().detect(_features(tmp_path))
    assert any(i.category == category for i in items)


def test_lookalikes_not_matched():
    for name in ("wandbox", "sagemakerish", "langfusion", "vertexaix"):
        for key in ("ai_sdks", "ml_frameworks", "orchestration"):
            assert match_token_identifier(name, key) is None, (name, key)
