"""Generic embedding tokens stay AI present but no longer propose essential services."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from opencomplai_core.models import DiscrepancySeverity, SignalCategory
from opencomplai_core.scan_engine import run_scan
from opencomplai_core.scanner.detectors._signals import load_signals

_DOCS = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "src"
    / "concepts"
    / "annex-iii-benchmark.md"
)
_MOVED = ["voyageai", "jina", "embedding", "rerank", "similarity_search"]
_PII = ["email", "ssn", "passport", "patient_id", "phi", "pii", "biometric_id"]

# No pii_hints word, score, rank, recommend or decision: those would raise area 5
# on their own once a file counts as a model file.
_TAIL = "    return openai.chat.completions.create(model='m', messages=[{}])\n"
_APP = {
    "embedding": "import openai\ndef answer(q):\n    v = get_embedding(q)\n"
    + _TAIL.format("v"),
    "rerank": "import openai\ndef answer(q):\n    hits = rerank(q)\n"
    + _TAIL.format("hits"),
    "similarity_search": "import openai\ndef answer(q):\n    hits = store.similarity_search(q)\n"
    + _TAIL.format("hits"),
    "voyageai": "import voyageai\nimport openai\ndef answer(q):\n" + _TAIL.format("q"),
    "jina": "import jina\nimport openai\ndef answer(q):\n" + _TAIL.format("q"),
}


def _chatbot(tmp_path: Path, token: str):
    (tmp_path / "requirements.txt").write_text("openai\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(_APP[token], encoding="utf-8")
    return run_scan(
        system_id="test-sys",
        commit_ref="HEAD",
        repo_root=tmp_path,
        declared_purpose="customer support chatbot",
    )


@pytest.mark.parametrize("token", _MOVED)
def test_retrieval_chatbot_has_no_essential_services_finding(
    tmp_path: Path, token: str
):
    report = _chatbot(tmp_path, token)
    assert "essential_services" not in report.detected_categories
    assert "essential_services" not in report.discrepancies
    for finding in report.findings:
        assert "essential_services" not in finding.mapped_taxonomy
    assert report.severity != DiscrepancySeverity.MAJOR


@pytest.mark.parametrize("token", _MOVED)
def test_moved_tokens_still_count_as_ai_present(tmp_path: Path, token: str):
    report = _chatbot(tmp_path, token)
    assert report.evidence
    assert token in load_signals()["ml_frameworks"]
    if token in ("voyageai", "jina"):
        assert any(
            e.category == SignalCategory.ML_FRAMEWORK and e.token_label == token
            for e in report.evidence
        )


def test_docs_table_lists_every_reviewed_token():
    text = _DOCS.read_text(encoding="utf-8")
    match = re.search(
        r"^## Generic token review in [\d.]+$(.*?)(?=^## |\Z)", text, re.M | re.S
    )
    assert match, "missing generic token review section"
    rows = [r for r in match.group(1).splitlines() if r.startswith("|")]
    for token in _MOVED + _PII:
        assert any(
            f"`{token}`" in r
            and re.search(r"\| (moved|kept) \|", r)
            and ("medium" in r or "low" in r)
            and re.search(r"\| yes \|\s*$", r)
            for r in rows
        ), token
