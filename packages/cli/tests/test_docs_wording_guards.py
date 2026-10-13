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


_PROVENANCE_TESTS = [
    "packages/cli/tests/test_provenance_stamp.py",
    "packages/core/tests/test_tree_digest.py",
]
_LEDGER_SOURCES = [
    "packages/core/src/opencomplai_core/models.py",
    "packages/core/src/opencomplai_core/dossier_generator.py",
    "infra/compose/docker-compose.yml",
    "sync/reset_demo.py",
]
_CUSTOMER_CI_SNIPPETS = [
    "docs/ci/github-actions.yml",
    "dashboard-saas/docs/ci/github-actions.yml",
    "docs/src/guides/ci-integration.md",
    "docs/src/guides/ci-recipes.md",
    "dashboard-saas/services/web/src/lib/ciSnippets.ts",
    "docs/src/examples/basic-usage.md",
    "docs/src/examples/integrations.md",
    "docs/src/getting-started/first-project.md",
]


def _existing(rels: list[str]) -> list[str]:
    """Paths present in this checkout; the public checkout lacks some of them."""
    return [rel for rel in rels if (_ROOT / rel).exists()]


def test_no_epic_id_in_provenance_and_digest_tests() -> None:
    pattern = re.compile(r"\b(?:SU|CL)-[A-Z]?\d+[a-z]?\b")
    present = _existing(_PROVENANCE_TESTS)
    assert present, "none of the provenance/digest test files exist"
    hits = [
        f"{rel}:{n}"
        for rel in present
        for n, line in enumerate(_read(rel).splitlines(), 1)
        if pattern.search(line)
    ]
    assert not hits, "internal epic ids in public test comments: " + ", ".join(hits)


def test_no_merkle_word_in_ledger_sources() -> None:
    present = _existing(_LEDGER_SOURCES)
    assert present, "none of the ledger source files exist"
    hits = [
        f"{rel}:{n}"
        for rel in present
        for n, line in enumerate(_read(rel).splitlines(), 1)
        if re.search("merkle", line, re.I)
    ]
    assert not hits, (
        "the ledger is a linear hash chain, not a Merkle tree: " + ", ".join(hits)
    )


def test_customer_ci_snippets_pin_checkout_v7() -> None:
    seen = 0
    bad: list[str] = []
    for rel in _existing(_CUSTOMER_CI_SNIPPETS):
        for n, line in enumerate(_read(rel).splitlines(), 1):
            if "actions/checkout@" not in line:
                continue
            seen += 1
            if not line.strip().endswith("actions/checkout@v7"):
                bad.append(f"{rel}:{n}: {line.strip()}")
    assert seen >= 6, f"expected at least six checkout lines, saw {seen}"
    assert not bad, "customer snippets must pin actions/checkout@v7: " + "; ".join(bad)


_PLANNING_ID = re.compile("V" + "12-[A-Za-z]+[0-9]*" + "|" + "V" + "-D[0-9]+")


def test_no_planning_ids_in_package_sources_and_tests() -> None:
    """Public trees carry no internal planning ids."""
    roots = [
        *sorted((_ROOT / "packages").glob("*/src")),
        *sorted((_ROOT / "packages").glob("*/tests")),
        *([_ROOT / "integrations"] if (_ROOT / "integrations").exists() else []),
    ]
    assert roots, "none of the package source or test trees exist"
    me = Path(__file__).resolve()
    hits: list[str] = []
    for root in roots:
        for path in sorted(root.rglob("*")):
            if (
                not path.is_file()
                or path.resolve() == me
                or {"__pycache__", "node_modules"} & set(path.parts)
            ):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if _PLANNING_ID.search(line):
                    hits.append(f"{path.relative_to(_ROOT).as_posix()}:{n}")
    assert not hits, "planning ids in public sources or tests: " + ", ".join(hits)
