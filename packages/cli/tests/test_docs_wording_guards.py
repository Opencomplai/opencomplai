"""Wording guards (CL-F13): docs must not claim more than the code does.

Pure file reads: no network, no subprocess.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]

_GATE_PAGES = ["README.md", "docs/src/concepts/annex-iv-coverage.md"]
_CHECKER_PAGE = "docs/src/getting-started/eu-ai-act-checker.md"
_GOLDEN_DIR = "packages/core/tests/fixtures/checker_golden"
_SHARED_VECTORS = "packages/core/tests/fixtures/checker_golden_vectors_shared.json"


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def _sentences(text: str) -> list[str]:
    """Split into sentences, joining wrapped lines inside each paragraph."""
    out: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        joined = " ".join(para.split())
        out.extend(s for s in re.split(r"(?<=[.!?])\s+", joined) if s)
    return out


def test_no_merkle_word_in_docs_readme_openapi() -> None:
    files = [
        *sorted((_ROOT / "docs/src").rglob("*.md")),
        _ROOT / "README.md",
        _ROOT / "services/gateway-api/openapi.yaml",
    ]
    hits = [
        f"{path.relative_to(_ROOT).as_posix()}:{n}"
        for path in files
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search("merkle", line, re.I)
    ]
    assert not hits, (
        "the ledger is a linear hash chain, not a Merkle tree: " + ", ".join(hits)
    )


def test_dossier_gate_wording_names_docs_generate() -> None:
    bad: list[str] = []
    for rel in _GATE_PAGES:
        text = _read(rel)
        assert "docs generate" in text, f"{rel}: must name `docs generate`"
        assert "--allow-incomplete" in text, f"{rel}: must name --allow-incomplete"
        for sentence in _sentences(text):
            if "release gate" not in sentence:
                continue
            if "docs generate" not in sentence:
                bad.append(f"{rel}: release gate without `docs generate`: {sentence!r}")
            if "`opencomplai check`" in sentence and not re.search(
                r"does not validate|never validates", sentence
            ):
                bad.append(f"{rel}: release gate attributed to check: {sentence!r}")
    assert not bad, "\n".join(bad)


def test_checker_page_counts_match_fixtures() -> None:
    text = _read(_CHECKER_PAGE)
    golden = re.search(r"(\d+) golden fixtures", text)
    shared = re.search(r"(\d+) shared (?:parity )?vectors", text)
    assert golden is not None, "checker page no longer states '<n> golden fixtures'"
    assert shared is not None, "checker page no longer states '<n> shared vectors'"
    n_golden = len(list((_ROOT / _GOLDEN_DIR).glob("*.json")))
    n_shared = len(json.loads(_read(_SHARED_VECTORS))["vectors"])
    assert int(golden.group(1)) == n_golden
    assert int(shared.group(1)) == n_shared
