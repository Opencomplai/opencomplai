"""Doc-truth checks for docs/src/guides/works-alongside.md and the README audience section."""

import re
from pathlib import Path

from opencomplai_cli.main import app

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / "docs/src/guides/works-alongside.md"
README = ROOT / "README.md"
AFFIL = "OpenComplAI is not affiliated with, endorsed by or a partner of any tool named on this page."


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _readme_section() -> str:
    m = re.search(r"^## Who it is for\n(.*?)(?=^## )", _read(README), re.S | re.M)
    assert m, "README has no '## Who it is for' section"
    return m.group(1)


def _check_links(text: str, base: Path) -> None:
    for target in re.findall(r"\]\(([^)\s]+)\)", text):
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            continue
        assert (base.parent / target.split("#")[0]).resolve().exists(), target


def test_page_in_nav_and_file_exists():
    assert PAGE.is_file()
    assert any(
        "guides/works-alongside.md" in line
        for line in _read(ROOT / "docs/mkdocs.yml").splitlines()
    )


def test_every_cited_command_is_registered():
    known = {c.name for c in app.registered_commands} | {
        g.name for g in app.registered_groups
    }
    cited = set(re.findall(r"opencomplai ([a-z][a-z-]*)", _read(PAGE)))
    assert cited
    assert cited <= known, cited - known


def test_relative_links_resolve():
    _check_links(_read(PAGE), PAGE)
    _check_links(_readme_section(), README)


def test_page_states_no_bridges_and_accepted_pass():
    text = _read(PAGE)
    m = re.search(r"^## What is not built\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m
    new = "No bridge or importer to Promptfoo or any GRC platform is built; you move files by hand."
    old = "No bridge or importer to Promptfoo, the Agent Governance Toolkit or any GRC platform"
    assert new in m.group(1)
    assert old not in text
    assert not re.search(r"(?i)no (bridge|importer)[^.]*agent governance toolkit", text)
    for s in ("agents import-log", "Partial", "../concepts/agt-import.md"):
        assert s in text, s
    assert "exit-codes.md#high-risk-acceptance" in text
    assert "accept.md" in text


def test_import_log_is_registered_under_agents():
    group = next(g for g in app.registered_groups if g.name == "agents")
    names = {
        c.name or c.callback.__name__.replace("_", "-")
        for c in group.typer_instance.registered_commands
    }
    assert {"import-log", "dispute-report"} <= names


def test_page_uses_reads_files_written_by_wording():
    text = _read(PAGE)
    assert "reads files written by" in text
    for w in ("integrates with", "compatible with", "powered by"):
        assert w not in text.lower()


def test_no_stale_high_risk_claim():
    text = _read(PAGE)
    assert not re.search(r"always exits? 1|exits? 1 (on|for) every", text, re.I)


def test_trademark_safe_wording():
    text = _read(PAGE)
    assert AFFIL in text
    rest = text.replace(AFFIL, "")
    for word in ("certified", "official partner", "endorsed by"):
        assert word not in rest.lower()
    assert text.count("Promptfoo") <= 3
    assert text.count("Agent Governance Toolkit") <= 3


def test_readme_who_it_is_for_links_page():
    assert "docs/src/guides/works-alongside.md" in _readme_section()
