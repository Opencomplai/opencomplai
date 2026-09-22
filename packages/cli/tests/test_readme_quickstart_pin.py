"""
CP-9 (D-9): pin README's Quick Start code blocks byte-for-byte against
deployment-journey.md's corresponding blocks, so the two guides can never
silently drift apart the way they had before this epic -- README documented
editable-install instructions and a checker-local.html rebuild step inline
while quick-start.md only linked out, the pre-commit `rev:` pin was stale in
README and absent from quick-start.md, and the two guides ordered their
steps differently.

Same technique test_ci_integration_guide.py uses for the CI YAML blocks:
regex-extract fenced code blocks and assert byte-identical. This is a
net-new file, not an extension of test_readme_command_table.py -- that file
pins packages/cli/README.md's CLI command table against
app.registered_commands and has no relationship to root README.md's Quick
Start prose.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_README = _REPO_ROOT / "README.md"
_JOURNEY = _REPO_ROOT / "docs" / "src" / "getting-started" / "deployment-journey.md"
_QUICK_START_DOC = _REPO_ROOT / "docs" / "src" / "getting-started" / "quick-start.md"


def _quick_start_section(markdown: str) -> str:
    """README's '## Quick Start' section body, up to the next '## ' heading."""
    match = re.search(r"## Quick Start\n(.*?)\n## ", markdown, re.S)
    assert match, "README has no '## Quick Start' section"
    return match.group(1)


def _bash_blocks(markdown: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)```", markdown, re.S)


def _bash_block_after(markdown: str, heading: str) -> str:
    """The first fenced ```bash block that follows the given heading line."""
    pattern = re.escape(heading) + r".*?```bash\n(.*?)```"
    match = re.search(pattern, markdown, re.S)
    assert match, f"no ```bash block found after heading {heading!r}"
    return match.group(1)


def test_readme_exists():
    assert _README.exists(), f"missing {_README}"


def test_journey_page_exists():
    assert _JOURNEY.exists(), f"missing {_JOURNEY}"


def test_readme_quick_start_has_exactly_two_bash_blocks():
    section = _quick_start_section(_README.read_text(encoding="utf-8"))
    blocks = _bash_blocks(section)
    assert len(blocks) == 2, (
        f"expected exactly 2 fenced bash blocks in README's Quick Start "
        f"(install, init+check), found {len(blocks)}"
    )


def test_readme_install_block_matches_journey_page():
    readme_section = _quick_start_section(_README.read_text(encoding="utf-8"))
    readme_install = _bash_blocks(readme_section)[0]
    journey_install = _bash_block_after(
        _JOURNEY.read_text(encoding="utf-8"), "## 1. Install"
    )
    assert readme_install == journey_install


def test_readme_init_check_block_matches_journey_page():
    readme_section = _quick_start_section(_README.read_text(encoding="utf-8"))
    readme_init_check = _bash_blocks(readme_section)[1]
    journey_init_check = _bash_block_after(
        _JOURNEY.read_text(encoding="utf-8"), "## 2. Initialise and check"
    )
    assert readme_init_check == journey_init_check


def test_readme_quick_start_links_to_journey_page():
    section = _quick_start_section(_README.read_text(encoding="utf-8"))
    assert "deployment-journey.md" in section


def test_quick_start_doc_no_longer_claims_missing_version_flag():
    """The factual error D-9 also fixes: quick-start.md used to claim
    'there is **no** `--version` flag', which was false (main.py's eager
    --version/-V option, plus the version/info subcommands)."""
    text = _QUICK_START_DOC.read_text(encoding="utf-8")
    assert "there is **no**" not in text
    assert "--version" in text
