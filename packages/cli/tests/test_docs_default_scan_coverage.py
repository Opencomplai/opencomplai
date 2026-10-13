"""The scan and check pages say what the default scan covers.

The default path is the one the Annex III benchmark measured. Both pages must link
the benchmark, name the two flags that reach the other areas, quote only numbers the
benchmark page contains, and use no hosted-product words. Pure file reads.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs" / "src"
BENCHMARK = DOCS / "concepts" / "annex-iii-benchmark.md"
SCANNER = DOCS / "getting-started" / "scanner.md"
CHECK = DOCS / "cli" / "check.md"
HEADING = "## What the default scan covers"
_FLAGS = ("--ai-intent", "--propose")
_BENCHMARK_LINK = re.compile(r"\]\(([^)\s]*annex-iii-benchmark\.md)\)")
_PERCENT = re.compile(r"\d+(?:\.\d+)?%")
_HOSTED_WORDS = re.compile(r"\b(?:dashboard|hosted|saas|tenant)\b", re.IGNORECASE)


def _need_docs() -> None:
    if not DOCS.is_dir():
        pytest.skip("docs/src is absent (projection without docs)")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section_in(text: str, label: str) -> str:
    start = text.find(HEADING)
    if start < 0:
        raise AssertionError(f"{label} has no '{HEADING}' section")
    end = text.find("\n## ", start + len(HEADING))
    return text[start:] if end < 0 else text[start:end]


def _section(page: Path) -> str:
    return _section_in(_text(page), page.relative_to(ROOT).as_posix())


def _coverage_misses(section: str) -> list[str]:
    misses = []
    if not _BENCHMARK_LINK.search(section):
        misses.append("benchmark link")
    misses.extend(flag for flag in _FLAGS if flag not in section)
    return misses


def _assert_covered(page: Path) -> None:
    _need_docs()
    section = _section(page)
    name = page.relative_to(ROOT).as_posix()
    misses = _coverage_misses(section)
    assert not misses, f"{name}: default-scan section misses {misses}"
    for target in _BENCHMARK_LINK.findall(section):
        assert (page.parent / target).resolve().exists(), (
            f"{name}: benchmark link {target} does not resolve"
        )


def test_scanner_page_states_default_scan_coverage():
    _assert_covered(SCANNER)


def test_check_page_states_default_scan_coverage():
    _assert_covered(CHECK)


def test_percentages_in_sections_appear_in_benchmark_page():
    _need_docs()
    benchmark_numbers = set(_PERCENT.findall(_text(BENCHMARK)))
    for page in (SCANNER, CHECK):
        for number in _PERCENT.findall(_section(page)):
            assert number in benchmark_numbers, (
                f"{page.name}: {number} is not in the benchmark page"
            )


def test_sections_use_no_hosted_product_words():
    _need_docs()
    for page in (SCANNER, CHECK):
        found = _HOSTED_WORDS.findall(_section(page))
        assert not found, f"{page.name}: hosted-product words {found}"


_SAMPLE = """# Sample

Intro.

## What the default scan covers

Scan reads signals. See the [Annex III detection benchmark](../concepts/annex-iii-benchmark.md).
Use `opencomplai scan --ai-intent` or `opencomplai scan --propose` for other areas.

## Next

Other text.
"""


def test_guard_regexes_are_not_vacuous():
    sample = _section_in(_SAMPLE, "sample page")
    assert _coverage_misses(sample) == []
    no_link = sample.replace("(../concepts/annex-iii-benchmark.md)", "")
    assert _coverage_misses(no_link) == ["benchmark link"]
    no_intent = sample.replace("--ai-intent", "")
    assert _coverage_misses(no_intent) == ["--ai-intent"]
    no_propose = sample.replace("--propose", "")
    assert _coverage_misses(no_propose) == ["--propose"]
