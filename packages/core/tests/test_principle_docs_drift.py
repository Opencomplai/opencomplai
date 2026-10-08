"""The committed principles page must equal what its generator renders."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "generate_principle_docs.py"
_DOC = _ROOT / "docs" / "src" / "concepts" / "eu-ai-act-principles.md"


def _render() -> str:
    spec = importlib.util.spec_from_file_location("generate_principle_docs", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render()


def _norm(text: str) -> str:
    return "\n".join(text.splitlines())


def _matches(committed: str, rendered: str) -> bool:
    return _norm(committed) == _norm(rendered)


def test_committed_doc_matches_generator():
    committed = _DOC.read_text(encoding="utf-8")
    assert _matches(committed, _render()), (
        "docs/src/concepts/eu-ai-act-principles.md is stale; run "
        "`python scripts/generate_principle_docs.py` and commit the result"
    )


def test_hand_edited_doc_is_detected():
    edited = _DOC.read_text(encoding="utf-8") + "\nhand edit\n"
    assert not _matches(edited, _render())
