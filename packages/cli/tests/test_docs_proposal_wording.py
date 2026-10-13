"""Docs and docstrings must describe the proposal gate as the code does.

Pure file reads: no CLI run, no network. Each guard names the claim it protects.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs" / "src"
PROPOSAL_PY = (
    ROOT / "packages" / "cli" / "src" / "opencomplai_cli" / "commands" / "proposal.py"
)
CI_DOCKER = ROOT / ".github" / "workflows" / "ci-docker.yml"

PREFIX = r"\bcheck\b[^.]{0,40}?\b(?:does not|doesn't|never)\b[^.]{0,40}?\b(?:read|use|consult)\b"
STALE_CLAIM = re.compile(PREFIX + r"[^.]{0,60}\bin this release\b", re.IGNORECASE)
NOT_READ_CLAIM = re.compile(
    PREFIX + r"[^.]{0,60}\b(?:proposal|confirmation)\b", re.IGNORECASE
)

# The three sentences as they read before this epic; the guard must catch each one.
PRE_FIX_SENTENCES = [
    "`check` does not read the proposal or the confirmation in this release, so no exit code or finding moves.",
    "`check` does not read it in this release. Neither the proposal nor the confirmation changes a verdict.",
    "Nothing here changes a verdict: `check` does not read either file in this release.",
]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("`", "").replace("**", "")).strip()


def _section(page: str, heading: str, until: str) -> str:
    start = page.index(heading)
    return page[start : page.index(until, start)]


def _fenced_blocks(page: str) -> list[str]:
    return re.findall(r"```.*?```", page, flags=re.DOTALL)


def test_no_page_says_check_ignores_a_proposal() -> None:
    # Self-check: the patterns must still catch the pre-fix wording, or the guard is vacuous.
    for sentence in PRE_FIX_SENTENCES:
        norm = _norm(sentence)
        assert STALE_CLAIM.search(norm) or NOT_READ_CLAIM.search(norm), sentence

    sources = [*sorted(DOCS.rglob("*.md")), PROPOSAL_PY]
    offenders = []
    for path in sources:
        norm = _norm(_text(path))
        if STALE_CLAIM.search(norm) or NOT_READ_CLAIM.search(norm):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, f"says check ignores or does not read a proposal: {offenders}"


def test_confirmed_proposal_row_is_documented_on_all_three_pages() -> None:
    check = _text(DOCS / "cli" / "check.md")
    scan = _section(
        _text(DOCS / "cli" / "scan.md"), "## Suggesting a classification", "\n## "
    )
    accept = _section(
        _text(DOCS / "cli" / "accept.md"),
        "## Confirming a classification proposal",
        "\n## ",
    )
    assert "confirmed_proposal" in check
    assert "confirmed_proposal" in scan or "check.md" in scan
    assert "confirmed_proposal" in accept or "check.md" in accept


def test_propose_section_shows_backend_flag_and_stale_state() -> None:
    section = _section(
        _text(DOCS / "cli" / "scan.md"), "## Suggesting a classification", "\n## "
    )
    assert "--ai-model" in section
    assert re.search(r"stale", section, flags=re.IGNORECASE)


def test_check_page_shows_a_resolved_commit_ref() -> None:
    page = _text(DOCS / "cli" / "check.md")
    assert not re.search(r"commit_ref:\s+HEAD\b", page)
    assert '"commit_ref": "HEAD"' not in page


def test_artifact_samples_show_resolved_ref_and_local_hash() -> None:
    pages = [
        DOCS / "cli" / "check.md",
        DOCS / "getting-started" / "quick-start.md",
        DOCS / "getting-started" / "first-project.md",
        DOCS / "concepts" / "scan-workflow.md",
    ]
    for path in pages:
        for block in _fenced_blocks(_text(path)):
            if '"failed_controls"' in block:
                assert '"commit_ref": "HEAD"' not in block, path.name
                assert '"evidence_hashes": []' not in block, path.name
            if "Opencomplai Compliance Check" in block:
                assert not re.search(r"commit_ref:\s+HEAD\b", block), path.name


def test_common_issues_does_not_use_hashes_as_service_signal() -> None:
    norm = _norm(_text(DOCS / "troubleshooting" / "common-issues.md"))
    assert not re.search(r"non-empty.{0,40}evidence_hashes", norm)


def test_scanner_page_documents_scope_by_whole_token() -> None:
    section = _section(
        _text(DOCS / "getting-started" / "scanner.md"), "### Scan scope", "\n##"
    )
    assert "token" in section
    assert "devices" in section


def test_error_handling_page_documents_the_schema_hint() -> None:
    page = _text(DOCS / "guides" / "error-handling.md")
    assert "SCHEMA_VIOLATION" in page
    assert "hint:" in page
    after = page[page.index("## A push rejected") :]
    assert not re.search(
        r"\b(dashboard|hosted|saas|tenant)\b", after, flags=re.IGNORECASE
    )


def test_testing_page_matches_the_ci_docker_workflow() -> None:
    if not CI_DOCKER.exists():
        pytest.skip("ci-docker.yml is absent (projection without .github)")
    norm = _norm(_text(DOCS / "contributing" / "testing.md"))
    assert "no ci-docker.yml" not in norm
    assert "ci-docker.yml" in norm


def test_exit_codes_page_lists_service_error_exit_3() -> None:
    lines = _text(DOCS / "cli" / "exit-codes.md").splitlines()
    row = next(line for line in lines if line.startswith("| `3`"))
    assert "service" in row.lower()
