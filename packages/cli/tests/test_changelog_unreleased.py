"""Structure and coverage guard for the release-notes block of CHANGELOG.md."""

import re
from pathlib import Path

import pytest

CHANGELOG = Path(__file__).resolve().parents[3] / "CHANGELOG.md"
ROOT = CHANGELOG.parent
GUIDE = ROOT / "docs" / "src" / "getting-started" / "upgrading-to-0.9.md"
GUIDE_URL = "https://docs.opencomplai.com/getting-started/upgrading-to-0.9/"

ORDER = [
    "Breaking",
    "Added",
    "Changed",
    "Removed",
    "Fixed",
    "Security",
]

THEMES = {
    "keyless signing": r"sign-if-available",
    "rule-set 1.6.0": r"1\.6\.0",
    "rule changelog and diff": r"rules? (changelog|diff)|diff command",
    "scan never Met alone": r"scan.{0,40}(never|no longer).{0,40}Met|false Met",
    "not-applicable articles": r"not_applicable",
    "roles": r"operator_roles",
    "multi-system check": r"portfolio|several manifests|multiple manifests",
    "regulatory timeline": r"timeline",
    "high-risk acceptance": r"accept(ed|ance).{0,40}high-risk|high-risk.{0,40}accept",
    "SARIF": r"SARIF",
    "GitHub Action": r"GitHub Action",
    "install paths": r"install\.sh|Homebrew|pipx",
    "human oversight": r"oversight",
    "deployer pack": r"deployer pack|instructions for use",
    "QMS": r"QMS",
    "agents": r"agent",
    "attestations": r"attestation",
    "incidents": r"incident",
    "ISO 42001": r"42001",
    "DORA mapping": r"DORA",
    "GPAI": r"GPAI",
    "ingest summaries": r"summaries",
    "register": r"register",
    "report shares": r"share",
    "account export and closure": r"export.{0,60}(organisation|tenant)|erasure|purge",
    "alerts": r"alert",
    "audit log": r"audit",
}


def _text() -> str:
    if not CHANGELOG.is_file():
        pytest.skip("CHANGELOG.md not present")
    return CHANGELOG.read_text(encoding="utf-8").replace("\r\n", "\n")


def _unreleased() -> str:
    text = _text()
    m = re.search(r"^## \[Unreleased\]\n(.*?)(?=^## \[)", text, re.S | re.M)
    # A bare "### Fixed" added after the release is not the release-notes block.
    if m and "\n### Breaking" in "\n" + m.group(1):
        return m.group(1)
    m = re.search(r"^## \[0\.9\.0\][^\n]*\n(.*?)(?=^## \[)", text, re.S | re.M)
    assert m, "no entries under [Unreleased] or [0.9.0]"
    return m.group(1)


def _section(name: str) -> str:
    m = re.search(
        rf"^### {re.escape(name)}\n(.*?)(?=^### |\Z)", _unreleased(), re.S | re.M
    )
    assert m, f"missing '### {name}' heading"
    return m.group(1)


def _v090() -> str:
    m = re.search(r"^## \[0\.9\.0\][^\n]*\n(.*?)(?=^## \[)", _text(), re.S | re.M)
    assert m, "no [0.9.0] block"
    return m.group(1)


def _v090_breaking() -> str:
    m = re.search(r"^### Breaking\n(.*?)(?=^### |\Z)", _v090(), re.S | re.M)
    assert m, "missing '### Breaking' under [0.9.0]"
    return m.group(1)


def _guide() -> str:
    return GUIDE.read_text(encoding="utf-8") if GUIDE.is_file() else ""


# The release block is the body of the public GitHub Releases and is synced to
# the public repository word for word: none of these may appear in it.
INTERNAL = {
    "private dashboard paths": r"dashboard-saas/",
    "private trust pack": r"docs/trust|trust\s+pack|CAIQ|SIG Lite|pentest",
    "review packet": r"lawyer",
    "hand-off ledger": r"HANDOFF",
    "epic ids": r"\bSU-\d",
    "operator release order": r"^### Release order",
    "private dashboard scripts": (
        r"schema_apply_logged|migration_rehearsal|backfill_artifact_columns"
        r"|ruleset_drift_check|dossier_bundle"
    ),
}

# One token per user-visible 0.9.0 break, in Breaking and in the upgrade guide.
BREAKING = {
    "sign without a key": "--sign-if-available",
    "multi-system manifest": "`systems`",
    "satisfy evidence note": "evidence_note",
    "HMAC dossiers": "UNSUPPORTED_SIGNATURE",
    "audit chain": "chain_head",
    "tenant roles": "admin-only",
    "portfolio status": "scan_passed",
    "ledger tips paging": "after_seq",
    "ingest body cap": "2 MiB",
    "signing key validation": "base64",
    "AI base install": "onnxruntime",
    "compose loopback": "OBSERVABILITY_BIND_ADDR",
    "push order": "SCHEMA_VIOLATION",
}

SUPERSEDED = [
    "for a later release to consume",
    "Nothing computes or stamps them yet",
    "No CLI command uses them yet",
    "Only the `artifact` kind exists so far",
    "nothing reads it yet",
    "Nothing emits `summaries` yet",
    "Deadline clocks are not shown yet",
    "They have no evidence yet",
    "accepted high-risk systems now pass",
    "no longer says accepted high-risk systems pass",
    "action-selftest.yml",
    "risk-register.md",
]

KNOWN_LIMITS = [
    "earlier events are kept but not chained",
    "cannot reach Sign out everywhere",
    "not yet published in the GitLab CI/CD Catalog",
    "whatever `OPENCOMPLAI_REQUIRE_RLS_POSTURE` is set to",
    "only the last system's report",
    "in the locale encoding",
    "GHCR packages are public",
]


def test_unreleased_heading_kept_once():
    assert len(re.findall(r"^## \[Unreleased\]", _text(), re.M)) == 1


def test_unreleased_uses_only_known_headings_in_order():
    heads = re.findall(r"^### (.+?)\s*$", _unreleased(), re.M)
    assert len(heads) == len(set(heads)), f"duplicate headings: {heads}"
    assert all(h in ORDER for h in heads), f"unknown heading in {heads}"
    assert heads == sorted(heads, key=ORDER.index), f"wrong order: {heads}"


def test_breaking_heading_names_sign_exit_code():
    body = _section("Breaking")
    for needle in ("--sign", "exit 2", "--sign-if-available"):
        assert needle in body, f"Breaking section does not mention {needle}"


@pytest.mark.parametrize("theme", sorted(THEMES))
def test_every_shipped_theme_has_a_line(theme):
    assert re.search(THEMES[theme], _unreleased(), re.I | re.S), (
        f"no line for theme: {theme}"
    )


@pytest.mark.parametrize("kind", sorted(INTERNAL))
def test_release_notes_have_no_internal_content(kind):
    pattern = re.compile(INTERNAL[kind], re.I | re.M)
    for name, text in (("release block", _unreleased()), ("upgrade guide", _guide())):
        lines = [ln for ln in text.splitlines() if pattern.search(ln)]
        assert not lines, f"{kind} in the {name}: {lines}"


def test_release_notes_have_no_duplicate_bullets():
    bullets = [ln for ln in _unreleased().splitlines() if ln.startswith("- ")]
    dupes = sorted({b for b in bullets if bullets.count(b) > 1})
    assert not dupes, f"duplicate bullets: {dupes}"


def test_upgrade_guide_is_in_nav_and_linked_from_breaking():
    assert GUIDE.is_file(), f"missing {GUIDE}"
    nav = (ROOT / "docs" / "mkdocs.yml").read_text(encoding="utf-8")
    assert "getting-started/upgrading-to-0.9.md" in nav
    assert GUIDE_URL in _v090_breaking()


@pytest.mark.parametrize("change", sorted(BREAKING))
def test_090_breaking_change_is_in_breaking_and_the_guide(change):
    token = BREAKING[change]
    assert token in _v090_breaking(), f"[0.9.0] Breaking lacks {token!r}"
    assert token in _guide(), f"upgrade guide lacks {token!r}"


@pytest.mark.parametrize("phrase", SUPERSEDED)
def test_090_has_no_superseded_statement(phrase):
    assert phrase not in _v090()


@pytest.mark.parametrize("phrase", KNOWN_LIMITS)
def test_090_states_known_limit(phrase):
    assert phrase in _v090()
