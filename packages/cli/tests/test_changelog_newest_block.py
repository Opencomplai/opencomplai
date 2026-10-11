"""Structure and hygiene guard for the newest release block of CHANGELOG.md.

Text only: the newest ``## [x.y.z]`` block must match the CLI version, keep the
Keep a Changelog heading order, have its footer link, carry no internal words,
and share no bullet with the dashboard notes.
"""

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CHANGELOG = ROOT / "CHANGELOG.md"
SAAS_CHANGELOG = ROOT / "dashboard-saas" / "CHANGELOG.md"
CLI_PYPROJECT = ROOT / "packages" / "cli" / "pyproject.toml"

pytestmark = pytest.mark.skipif(
    not CHANGELOG.is_file(), reason="CHANGELOG.md is not in this tree"
)

ORDER = ["Breaking", "Added", "Changed", "Removed", "Fixed", "Security"]
FORBIDDEN = (
    r"dashboard|hosted|SaaS|tenant|\bSU-\d|\bCL-[A-Z]|HANDOFF|lawyer"
    r"|trust pack|enterprise|private"
)
BLOCK_START = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.M)


def _newest(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    first = BLOCK_START.search(text)
    assert first, f"no release block in {path}"
    nxt = BLOCK_START.search(text, first.end())
    end = nxt.start() if nxt else len(text)
    return first.group(1), text[first.start() : end]


def _bullets(block: str) -> set[str]:
    return {ln for ln in block.splitlines() if ln.startswith("- ")}


def test_newest_block_version_matches_cli():
    version, _ = _newest(CHANGELOG)
    cli = tomllib.loads(CLI_PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    assert version == cli


def test_newest_block_headings_in_order():
    _, block = _newest(CHANGELOG)
    headings = re.findall(r"^### (.+?)\s*$", block, re.M)
    assert len(headings) == len(set(headings)), f"duplicate headings: {headings}"
    unknown = [h for h in headings if h not in ORDER]
    assert not unknown, f"unknown headings: {unknown}"
    assert headings == sorted(headings, key=ORDER.index), headings


def test_footer_link_present():
    version, _ = _newest(CHANGELOG)
    link = (
        f"[{version}]: https://github.com/Opencomplai/opencomplai"
        f"/releases/tag/v{version}"
    )
    assert link in CHANGELOG.read_text(encoding="utf-8").splitlines()


def test_newest_release_has_no_forbidden_words():
    _, block = _newest(CHANGELOG)
    pattern = re.compile(FORBIDDEN, re.I)
    hits = [ln for ln in block.splitlines() if pattern.search(ln)]
    assert not hits, f"internal words in the newest block: {hits}"


def test_saas_notes_share_no_bullet_with_public():
    if not SAAS_CHANGELOG.is_file():
        pytest.skip("dashboard-saas/CHANGELOG.md is not in this tree")
    public_version, public = _newest(CHANGELOG)
    saas_version, saas = _newest(SAAS_CHANGELOG)
    assert saas_version == public_version
    shared = _bullets(public) & _bullets(saas)
    assert not shared, f"bullets in both blocks: {sorted(shared)}"
