"""The scan and check pages say what the default scan covers.

The default path is the one the Annex III benchmark measured. Both pages must link
the benchmark, name the two flags that reach the other areas, quote only numbers the
benchmark page contains, and use no hosted-product words. The leads sections (the
default-scan leads, guarded here) carry the same kind of wording. Pure file reads.
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
SCAN = DOCS / "cli" / "scan.md"
HEADING = "## What the default scan covers"
LEADS_HEADING = "## Leads from the default scan"
LEADS_TERMS = ("proposal_leads", "opencomplai-ai", "exit code", "not a finding")
_LEADS_ANCHOR = "scan.md#leads-from-the-default-scan"
_FLAGS = ("--ai-intent", "--propose")
_BENCHMARK_LINK = re.compile(r"\]\(([^)\s]*annex-iii-benchmark\.md)\)")
_PERCENT = re.compile(r"\d+(?:\.\d+)?%")
_HOSTED_WORDS = re.compile(r"\b(?:dashboard|hosted|saas|tenant)\b", re.IGNORECASE)
_EPIC_ID = re.compile(r"\bV1[3]-\w+")
_PRIVATE_PATH = re.compile(r"PLA[N]/")


def _need_docs() -> None:
    if not DOCS.is_dir():
        pytest.skip("docs/src is absent (projection without docs)")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section_in(text: str, label: str, heading: str = HEADING) -> str:
    start = text.find(heading)
    if start < 0:
        raise AssertionError(f"{label} has no '{heading}' section")
    end = text.find("\n## ", start + len(heading))
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


_LEADS_PAGES = {
    "scan": (SCAN, LEADS_HEADING),
    "check": (CHECK, HEADING),
    "scanner": (SCANNER, HEADING),
}


def _leads_misses(section: str, *, anchor: bool) -> list[str]:
    misses = []
    if not _BENCHMARK_LINK.search(section):
        misses.append("benchmark link")
    misses.extend(term for term in LEADS_TERMS if term not in section)
    if anchor and _LEADS_ANCHOR not in section:
        misses.append("leads anchor")
    return misses


def _unknown_percents(section: str, benchmark: str) -> list[str]:
    known = set(_PERCENT.findall(benchmark))
    return [number for number in _PERCENT.findall(section) if number not in known]


@pytest.mark.parametrize("name", list(_LEADS_PAGES))
def test_leads_section_states_the_contract(name):
    _need_docs()
    page, heading = _LEADS_PAGES[name]
    section = _section_in(_text(page), page.relative_to(ROOT).as_posix(), heading)
    misses = _leads_misses(section, anchor=name != "scan")
    assert not misses, f"{name}: leads section misses {misses}"
    for target in _BENCHMARK_LINK.findall(section):
        assert (page.parent / target).resolve().exists(), (
            f"{name}: benchmark link {target} does not resolve"
        )


def test_percentages_in_leads_sections_appear_in_benchmark_page():
    _need_docs()
    benchmark = _text(BENCHMARK)
    for name, (page, heading) in _LEADS_PAGES.items():
        section = _section_in(_text(page), name, heading)
        unknown = _unknown_percents(section, benchmark)
        assert not unknown, f"{name}: {unknown} is not in the benchmark page"


def test_leads_sections_use_no_hosted_product_words():
    _need_docs()
    for name, (page, heading) in _LEADS_PAGES.items():
        section = _section_in(_text(page), name, heading)
        found = (
            _HOSTED_WORDS.findall(section)
            + _EPIC_ID.findall(section)
            + _PRIVATE_PATH.findall(section)
        )
        assert not found, f"{name}: forbidden words or paths {found}"


def test_scan_page_documents_coverage_field():
    _need_docs()
    section = _section_in(_text(SCAN), "scan.md", LEADS_HEADING)
    for term in ("default_scan_coverage", "compliance-artifact.json"):
        assert term in section, f"scan.md leads section does not name {term}"


_LEADS_SAMPLE = """# Sample

## Leads from the default scan

A lead is a pointer for a person to review, not a finding. Read the
[benchmark](../concepts/annex-iii-benchmark.md) or its
[leads section](../concepts/annex-iii-benchmark.md#leads-on-the-three-sets). Leads
sit in `eu_ai_scan.proposal_leads` and need `opencomplai-ai`. A lead never changes an
exit code. The floor is 73.3%. See [leads](scan.md#leads-from-the-default-scan).

## Next

Other text.
"""


def test_leads_guard_regexes_are_not_vacuous():
    sample = _section_in(_LEADS_SAMPLE, "sample page", LEADS_HEADING)
    assert _leads_misses(sample, anchor=True) == []
    no_link = sample.replace("(../concepts/annex-iii-benchmark.md)", "")
    assert _leads_misses(no_link, anchor=True) == ["benchmark link"]
    for term in LEADS_TERMS:
        assert _leads_misses(sample.replace(term, ""), anchor=True) == [term]
    no_anchor = sample.replace("scan.md#leads-from-the-default-scan", "")
    assert _leads_misses(no_anchor, anchor=True) == ["leads anchor"]
    assert _unknown_percents(sample, "no figures here") == ["73.3%"]
    assert _unknown_percents(sample, "Overall 73.3%") == []
