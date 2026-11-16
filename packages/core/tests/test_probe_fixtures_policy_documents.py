"""The policy_documents probes against three fixture repositories.

``empty`` holds nothing, ``scaffolded`` holds each shared scaffold unchanged and
``evidenced`` holds the same paths with every open cell written. Never Met.
"""

from __future__ import annotations

import json
from pathlib import Path

import opencomplai_core
import pytest
from opencomplai_core.gap_probes import (
    SCAFFOLD_PLACEHOLDER,
    artifact_gap_status,
    run_artifact_probe,
)
from opencomplai_core.models import GapStatus
from opencomplai_core.probe_registry import parse_probe_file

CORE = Path(opencomplai_core.__file__).parent
PROBE_FILE = CORE / "probes" / "policy_documents.json"
SCAFFOLDS = CORE / "probes" / "scaffolds" / "policy_documents"
FIXTURES = Path(__file__).parent / "fixtures" / "probes" / "policy_documents"

INDEX: dict[str, dict[str, str]] = json.loads(
    (SCAFFOLDS / "index.json").read_text(encoding="utf-8")
)
REFS = sorted(parse_probe_file(PROBE_FILE))
DOC_REFS = sorted(INDEX)
CONFIG_REFS = [r for r in REFS if r not in INDEX]


def test_index_covers_the_document_probes():
    assert DOC_REFS == REFS
    assert CONFIG_REFS == []


@pytest.mark.parametrize("ref", REFS)
def test_empty_repo_is_missing(ref: str):
    row = artifact_gap_status(ref, FIXTURES / "empty")
    assert row.status == GapStatus.MISSING


@pytest.mark.parametrize("ref", REFS)
def test_scaffolded_repo(ref: str):
    row = artifact_gap_status(ref, FIXTURES / "scaffolded")
    if ref in INDEX:
        assert row.status == GapStatus.PARTIAL
        assert row.confidence == 0.35
        assert "unfilled" in row.rationale
    else:
        assert row.status == GapStatus.MISSING


@pytest.mark.parametrize("ref", REFS)
def test_evidenced_repo_is_partial_06_never_met(ref: str):
    row = artifact_gap_status(ref, FIXTURES / "evidenced")
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.6


@pytest.mark.parametrize("ref", DOC_REFS)
def test_scaffold_file_shape(ref: str):
    text = (SCAFFOLDS / f"{ref}.md").read_text(encoding="utf-8")
    assert SCAFFOLD_PLACEHOLDER in text
    assert len(text.splitlines()) <= 60


@pytest.mark.parametrize("ref", DOC_REFS)
def test_scaffolded_file_is_byte_equal_to_scaffold(ref: str):
    target = FIXTURES / "scaffolded" / INDEX[ref]["target"]
    assert target.read_bytes() == (SCAFFOLDS / f"{ref}.md").read_bytes()


@pytest.mark.parametrize("ref", DOC_REFS)
def test_target_is_found_in_evidenced(ref: str):
    result = run_artifact_probe(ref, FIXTURES / "evidenced")
    assert INDEX[ref]["target"] in [
        str(p).replace("\\", "/") for p in result.found_paths
    ]


def test_evidenced_has_no_placeholder():
    for path in (FIXTURES / "evidenced").rglob("*"):
        if path.is_file():
            assert SCAFFOLD_PLACEHOLDER not in path.read_text(encoding="utf-8")
