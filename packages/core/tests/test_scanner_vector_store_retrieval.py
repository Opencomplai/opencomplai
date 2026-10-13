"""Vector-store SDKs stay AI present but no longer propose essential services."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from opencomplai_core.models import DiscrepancySeverity, SignalCategory
from opencomplai_core.scan_engine import run_scan

_DOCS = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "src"
    / "concepts"
    / "annex-iii-benchmark.md"
)
_MOVED = ["pinecone", "weaviate", "qdrant", "chromadb", "milvus", "lancedb"]

# The words embedding, rerank and similarity_search still map to area 5: keep
# them out of the fixture.
_APP = {
    "chromadb": (
        "import chromadb\n"
        "import openai\n"
        "def answer(question):\n"
        "    client = chromadb.Client()\n"
        "    docs = client.get_or_create_collection('faq')\n"
        "    hits = docs.query(query_texts=[question], n_results=3)\n"
        "    return openai.chat.completions.create(model='m', messages=[hits])\n"
    ),
    "pinecone": (
        "import pinecone\n"
        "import openai\n"
        "def answer(question):\n"
        "    pc = pinecone.Pinecone(api_key='k')\n"
        "    hits = pc.Index('faq').query(top_k=3, vector=[0.0])\n"
        "    return openai.chat.completions.create(model='m', messages=[hits])\n"
    ),
}


def _scan(tmp_path: Path, sdk: str):
    (tmp_path / "requirements.txt").write_text(f"{sdk}\nopenai\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(_APP[sdk], encoding="utf-8")
    return run_scan(
        system_id="test-sys",
        commit_ref="HEAD",
        repo_root=tmp_path,
        declared_purpose="customer support chatbot",
    )


@pytest.mark.parametrize("sdk", ["chromadb", "pinecone"])
def test_retrieval_chatbot_has_no_essential_services_finding(tmp_path: Path, sdk: str):
    report = _scan(tmp_path, sdk)
    assert "essential_services" not in report.detected_categories
    assert "essential_services" not in report.discrepancies
    for finding in report.findings:
        assert "essential_services" not in finding.mapped_taxonomy
    assert report.severity != DiscrepancySeverity.MAJOR


@pytest.mark.parametrize("sdk", ["chromadb", "pinecone"])
def test_retrieval_chatbot_still_counts_as_ai_present(tmp_path: Path, sdk: str):
    report = _scan(tmp_path, sdk)
    assert any(
        e.category == SignalCategory.ML_FRAMEWORK and e.token_label == sdk
        for e in report.evidence
    )


def test_docs_table_lists_every_moved_vector_store_token():
    text = _DOCS.read_text(encoding="utf-8")
    match = re.search(
        r"^## Signal changes in 1\.4\.0$(.*?)(?=^## |\Z)", text, re.M | re.S
    )
    assert match, "missing 1.4.0 section"
    rows = [r for r in match.group(1).splitlines() if r.startswith("|")]
    for token in _MOVED:
        assert any(
            f"`{token}`" in r
            and "ml_frameworks" in r
            and ("medium" in r or "low" in r)
            and re.search(r"\| yes \|\s*$", r)
            for r in rows
        ), token
