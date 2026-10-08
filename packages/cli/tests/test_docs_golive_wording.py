"""Go-live wording guards: ISO/IEC 42001 pack, CLI index, accepted exit 0."""

from __future__ import annotations

import re
from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

_ROOT = Path(__file__).resolve().parents[3]
_DOCS = _ROOT / "docs" / "src"
_STALE = (
    "mapped, not evaluated",
    "no verdict is computed",
    "mapped only, not a target",
    "never as an assessment target",
)
_OVERCLAIM = re.compile(r"ISO[^.\n]{0,40}\b(certified|evaluated)\b", re.I)


def _read(rel: str) -> str:
    return (_DOCS / rel).read_text(encoding="utf-8")


def test_iso_wording_matches_the_shipped_pack() -> None:
    for rel in ("troubleshooting/faq.md", "cli/gaps.md", "architecture/data-model.md"):
        text = _read(rel)
        for phrase in _STALE:
            assert phrase not in text, f"{rel}: stale {phrase!r}"
        assert not _OVERCLAIM.search(text), f"{rel}: {_OVERCLAIM.search(text)}"
        assert "ISO_IEC_42001" in text, rel
        if rel != "architecture/data-model.md":
            assert "attestation-led" in text, rel


def test_gaps_help_names_the_iso_pack() -> None:
    result = CliRunner().invoke(app, ["gaps", "--help"], env={"COLUMNS": "300"})
    assert result.exit_code == 0, result.output
    assert "ISO_IEC_42001" in result.output
    assert "attestation-led" in result.output


def test_cli_index_links_every_cli_page() -> None:
    index = _read("cli/index.md")
    linked = {
        m.split("#")[0]
        for m in re.findall(r"\]\(([^)\s]+)\)", index)
        if not m.startswith(("http://", "https://")) and m.split("#")[0].endswith(".md")
    }
    pages = {p.name for p in (_DOCS / "cli").glob("*.md")} - {"index.md"}
    assert linked == pages


def test_accepted_section_states_the_exit_0_condition() -> None:
    text = _read("guides/works-alongside.md")
    assert "## Accepted high-risk systems pass" not in text
    heading = "## When an accepted high-risk system exits 0"
    assert heading in text
    section = text.split(heading, 1)[1].split("\n## ", 1)[0]
    assert "only when no other EU AI Act row is Missing" in section
    assert "examples/gate-demo" in section
