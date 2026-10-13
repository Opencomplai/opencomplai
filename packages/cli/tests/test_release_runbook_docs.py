"""Offline structural checks for the Homebrew tap and signing secret runbook."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_RUNBOOK = _ROOT / "docs" / "src" / "contributing" / "release-process.md"
_INSTALL_DOC = _ROOT / "docs" / "src" / "getting-started" / "installation.md"
_HEADING = "## Homebrew tap and signing secret"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section() -> str:
    text = _read(_RUNBOOK)
    start = text.index(_HEADING)
    end = text.find("\n## ", start + len(_HEADING))
    return text[start:] if end == -1 else text[start:end]


def test_runbook_section_has_ordered_steps() -> None:
    assert _HEADING in _read(_RUNBOOK)
    section = _section()
    for needle in (
        "homebrew-tap",
        "update-python-resources",
        "brew audit",
        "Formula/opencomplai.rb",
        "git push",
        "OPENCOMPLAI_SIGNING_KEY",
    ):
        assert needle in section, needle
    script_at = section.index("scripts/homebrew-release.sh")
    assert script_at < section.index("git push")
    assert script_at < section.index("What flips planned to live")


def test_runbook_does_not_claim_the_script_writes_nothing_on_failure() -> None:
    section = _section()
    assert "writes nothing unless" not in section
    assert (
        "patches the formula once the index, digest and download checks pass" in section
    )
    assert "a failure leaves the patched file for you to review" in section


def test_runbook_commands_name_real_scripts() -> None:
    section = _section()
    assert re.search(r"scripts/homebrew-release\.sh[ \t]+\S+", section)
    assert re.search(r"scripts/signing-secret\.sh[ \t]+\S+[ \t]+\S+", section)
    assert (_ROOT / "scripts" / "homebrew-release.sh").is_file()
    assert (_ROOT / "scripts" / "signing-secret.sh").is_file()


def test_installation_page_still_planned() -> None:
    text = _read(_INSTALL_DOC)
    assert "### Homebrew (planned)" in text
    assert "The tap is not yet published" in text


def test_runbook_has_no_key_material_or_dashboard_words() -> None:
    section = _section()
    assert "BEGIN " + "PRIVATE KEY" not in section
    assert "BEGIN OPENSSH" not in section
    assert not re.search(r"[A-Za-z0-9+/]{40,}={0,2}", section)
    lowered = section.lower()
    for word in ("dashboard", "tenant", "saas"):
        assert word not in lowered, word
