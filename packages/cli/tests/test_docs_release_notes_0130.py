"""Release notes and report-file pages for the next release block of CHANGELOG.md.

The notes are the body of ``## [Unreleased]`` while it holds a ``### `` heading,
otherwise the newest dated block. The scan and check pages must name the
written-files manifest and no longer carry the old report-file limit text. Pure
file reads; a missing file skips its tests with a reason.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CHANGELOG = ROOT / "CHANGELOG.md"
CLI_DOCS = ROOT / "docs" / "src" / "cli"

ORDER = ["Breaking", "Added", "Changed", "Removed", "Fixed", "Security"]
REQUIRED = ("Added", "Changed", "Fixed")
FORBIDDEN = (
    r"dashboard|hosted|SaaS|tenant|\bSU-\d|\bCL-[A-Z]|HANDOFF|lawyer"
    r"|trust pack|enterprise|private"
)
PRIVATE_IDS = r"\bV1[3]-|\bPLA[N]/|dashboard-sa[a]s/|\.summit|\.venv"
OLD_LIMIT = (
    "is part of the code digest",
    "is part of the digest",
    "reads stale on the next run",
)
MANIFEST = ".opencomplai/written-files.json"


def _norm(text: str) -> str:
    return " ".join(text.split())


def _notes() -> str:
    if not CHANGELOG.is_file():
        pytest.skip("CHANGELOG.md is not in this tree")
    text = CHANGELOG.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.search(r"^## \[Unreleased\]\n(.*?)(?=^## \[)", text, re.S | re.M)
    if m and re.search(r"^### ", m.group(1), re.M):
        return m.group(1)
    m = re.search(r"^## \[\d+\.\d+\.\d+\][^\n]*\n(.*?)(?=^## \[)", text, re.S | re.M)
    assert m, "no [Unreleased] notes and no dated block"
    return m.group(1)


def _page(name: str) -> str:
    path = CLI_DOCS / name
    if not path.is_file():
        pytest.skip(f"{name} is not in this tree")
    return _norm(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["scan.md", "check.md"])
def test_old_report_file_limit_wording_is_gone(name):
    page = _page(name)
    for phrase in OLD_LIMIT:
        assert phrase not in page, f"{name} still says: {phrase!r}"


@pytest.mark.parametrize("name", ["scan.md", "check.md"])
def test_pages_name_the_written_files_manifest(name):
    page = _page(name)
    assert MANIFEST in page, f"{name} does not name {MANIFEST}"
    assert "another tool" in page, f"{name} does not say what reads stale"
    assert "edited" in page, f"{name} does not say an edit reads stale"


def test_notes_headings_in_guard_order():
    heads = re.findall(r"^### (.+?)\s*$", _notes(), re.M)
    assert len(heads) == len(set(heads)), f"duplicate headings: {heads}"
    assert all(h in ORDER for h in heads), f"unknown heading in {heads}"
    assert heads == sorted(heads, key=ORDER.index), f"wrong order: {heads}"
    for name in REQUIRED:
        assert name in heads, f"missing '### {name}' heading"


def test_notes_are_public_safe():
    notes = _notes()
    for pattern in (FORBIDDEN, PRIVATE_IDS):
        hits = [ln for ln in notes.splitlines() if re.search(pattern, ln, re.I)]
        assert not hits, f"internal words in the notes: {hits}"
    assert not re.search(r"^## .*0\.13\.0", notes, re.M), "dated heading in notes"
    assert "[0.13.0]:" not in notes, "link reference in notes"


def test_pooled_area_figures_match_benchmark_row():
    bench = ROOT / "docs" / "src" / "concepts" / "annex-iii-benchmark.md"
    if not bench.is_file():
        pytest.skip("annex-iii-benchmark.md is not in this tree")
    rows = [
        ln
        for ln in bench.read_text(encoding="utf-8").splitlines()
        if "Overall without 5" in ln
    ]
    assert rows, "no 'Overall without 5' row in the benchmark page"
    row = _norm(rows[0])
    assert "areas 3, 4, 6, 7, 8 | 39 | 9 | 0 | 30 | 100.0% | 23.1%" in row
    notes = _norm(_notes())
    assert "Areas 3, 4, 6, 7 and 8 together (without area 5)" in notes
    assert "9 programs led, all labelled (precision 100.0%, recall 23.1%)" in notes


def test_notes_state_the_28_program_set_and_upgrade_path():
    notes = _norm(_notes())
    assert (
        "28 synthetic programs (19 labelled with an area 3 to 8 and 9 hard negatives)"
        in notes
    )
    assert (
        "On the 19 labelled programs of that set, no area 3 to 8 lead matched a label"
        in notes
    )
    assert "`scan --output json` and `scan --output-file`" in notes
    assert (
        "created only when a report flag writes a file inside the scanned tree" in notes
    )
    assert "`tree_dirty` to stay false" in notes
    assert "counted once more on the run that overwrites it" in notes
    assert (
        "After the first run that writes the report file (that run records it), run `scan --propose` and `accept --proposal` once"
        in notes
    )
    assert "no longer says the framework `data_version` changes" in notes


def test_check_page_has_the_upgrade_sentence():
    page = _page("check.md")
    assert "counted once more on the run that overwrites it" in page
    assert "`scan --propose` and `accept --proposal` once" in page


def test_export_page_has_the_0_13_upgrade_table():
    page = _page("export.md")
    assert "## Upgrading to 0.13" in page
    section = page.split("## Upgrading to 0.13", 1)[1].split("## Exit codes", 1)[0]
    for name in ("default_scan_coverage", "eu_ai_scan.proposal_leads", "eu_ai_scan"):
        assert name in section
    assert "additive and optional" in section


def test_openapi_corroboration_report_lists_default_scan_coverage():
    spec = ROOT / "services" / "gateway-api" / "openapi.yaml"
    if not spec.is_file():
        pytest.skip("openapi.yaml is not in this tree")
    import yaml

    doc = yaml.safe_load(spec.read_text(encoding="utf-8"))
    schema = doc["components"]["schemas"]["CorroborationReport"]
    prop = schema["properties"]["default_scan_coverage"]
    assert prop["type"] == "object"
    assert "default_scan_coverage" not in schema.get("required", [])


ORDER_SENTENCE = (
    "After the first run that writes the report file (that run records it), "
    "run `scan --propose` and `accept --proposal` once"
)


@pytest.mark.parametrize("name", ["check.md", "scan.md"])
def test_pages_name_the_upgrade_order_and_gitignore(name):
    page = _page(name)
    assert ORDER_SENTENCE in page
    assert "`.gitignore`" in page


def test_notes_name_gitignore_and_json_output_file():
    notes = _norm(_notes())
    assert ORDER_SENTENCE in notes
    assert "list it in `.gitignore`" in notes
    assert "list it in the ignore file" not in notes
    assert "`scan --output-file` (JSON)" in notes


def test_export_rows_name_the_files_and_null_rule():
    page = _page("export.md")
    section = page.split("## Upgrading to 0.13", 1)[1].split("## Exit codes", 1)[0]
    assert "`scan --output-file` (JSON) | `default_scan_coverage`" in section
    assert section.count("`scan-report.json` (from `scan` and `check --scan`)") == 2
    assert (
        "non-null only when the plugin is installed and at least one lead was found"
        in section
    )


def test_scan_page_lead_pointer_and_manifest_bullet():
    page = _page("scan.md")
    assert "adr-proposal-leads.md" in page
    bullet = page.split("A proposal written by 0.12.0 is still accepted.", 1)[1]
    assert bullet.lstrip().startswith("A report file that existed before upgrading")
    leads = page.split("## Leads from the default scan", 1)[1].split(
        "- **Switch.**", 1
    )[0]
    assert "run `scan --propose`" not in leads
    assert "in a `scan --output-file` that is JSON" in page


def test_openapi_default_scan_coverage_description():
    spec = ROOT / "services" / "gateway-api" / "openapi.yaml"
    if not spec.is_file():
        pytest.skip("openapi.yaml is not in this tree")
    import yaml

    doc = yaml.safe_load(spec.read_text(encoding="utf-8"))
    desc = _norm(
        doc["components"]["schemas"]["CorroborationReport"]["properties"][
            "default_scan_coverage"
        ]["description"]
    )
    assert "Set on every scan" in desc
    assert "never in compliance-artifact.json" in desc


def test_homebrew_script_header_matches_runbook():
    script = ROOT / "scripts" / "homebrew-release.sh"
    if not script.is_file():
        pytest.skip("homebrew-release.sh is not in this tree")
    head = _norm(
        " ".join(script.read_text(encoding="utf-8").splitlines()[:12]).replace("# ", "")
    )
    assert (
        "Nothing is written unless the index, digest and download checks passed; "
        "a lint failure leaves the patched formula for review." in head
    )
