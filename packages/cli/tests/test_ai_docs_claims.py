"""The AI-intent docs must not revive the false ONNX story.

codebert-onnx is a deterministic code-signal matcher: no ONNX Runtime, no
optimum, no download, fixed confidence values. These pages once told users to
install optimum[onnxruntime], expect a ~440 MB export, and read ``conf`` as a
cosine similarity. Skipped where a file is absent (public checkout layouts
differ).

The package READMEs, NOTICE and the AI inventory legitimately name
``optimum[onnxruntime]`` as the ``[onnx]`` extra's dependency (it backs the
optional export function), so for those files only the claims that were
actually false are forbidden.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_PAGES = [
    "docs/src/cli/scan.md",
    "docs/src/cli/ai.md",
    "docs/src/getting-started/scanner.md",
    "docs/src/guides/customer-workflow.md",
]
_STALE = ["440 MB", "cosine similarity", "optimum[onnxruntime]"]

_ALSO_CHECKED = [
    "README.md",
    "packages/ai/README.md",
    "packages/ai/NOTICE",
    "docs/security/ai-inventory.md",
]
_STALE_EVERYWHERE = [
    "440 MB",
    "cosine similarity",
    # Wordings the README and the AI inventory carried before the correction.
    "ONNX/transformers intent classifier",
    "Runs the exported ONNX",
]


def _assert_phrases_absent(rel: str, phrases: list[str]) -> None:
    path = _ROOT / rel
    if not path.exists():
        pytest.skip(f"{path} not present in this checkout")

    text = path.read_text(encoding="utf-8").lower()
    for phrase in phrases:
        assert phrase.lower() not in text, f"{rel} mentions {phrase!r} again"


@pytest.mark.parametrize("page", _PAGES)
def test_ai_intent_docs_do_not_reintroduce_stale_onnx_claims(page):
    _assert_phrases_absent(page, _STALE)


@pytest.mark.parametrize("rel", _ALSO_CHECKED)
def test_readmes_notice_and_inventory_do_not_reintroduce_stale_onnx_claims(rel):
    _assert_phrases_absent(rel, _STALE_EVERYWHERE)


def test_cli_ai_page_describes_codebert_onnx_as_the_deterministic_matcher():
    path = _ROOT / "docs/src/cli/ai.md"
    if not path.exists():
        pytest.skip(f"{path} not present in this checkout")
    pytest.importorskip("opencomplai_ai")
    from opencomplai_ai.models import MODEL_CATALOG

    spec = MODEL_CATALOG["codebert-onnx"]
    assert spec.runtime == "deterministic"
    text = path.read_text(encoding="utf-8").lower()
    for phrase in [
        "codebert-onnx",
        "deterministic",
        "fixed confidence",
        "no download",
        spec.license.lower(),
    ]:
        assert phrase in text, f"docs/src/cli/ai.md no longer says {phrase!r}"
