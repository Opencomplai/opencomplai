"""Doc-truth pins (SU-7o): claims the 2026-10-02 review found overstated must not
return, and each corrected fact must stay stated. Pure file reads."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]

STANDING_LINE = "EU AI Act evaluated; NIST AI RMF derived (partial, unreviewed); ISO 42001 native pack, attestation-led (partial, unreviewed); DORA and EBA mapped only"
STANDING_LINE_FILES = ["README.md", "docs/src/index.md", "docs/src/frameworks/index.md"]

RETIRED: list[tuple[str, str]] = [
    ("README.md", "audit-ready logs"),
    ("docs/src/index.md", "audit-ready logs"),
    ("README.md", "without risking your production code"),
    ("README.md", "catch AI errors"),
    ("docs/src/index.md", "without risking your production code"),
    ("docs/src/index.md", "catch AI errors"),
    ("README.md", "single sign-on"),
    ("README.md", "additional rule engines"),
    ("docs/src/license.md", "single sign-on"),
    ("docs/src/license.md", "additional rule engines"),
    ("docs/src/api/index.md", "Real-time event webhooks"),
    ("docs/src/api/webhooks.md", "v0.1"),
    ("docs/src/index.md", "Closed Beta Pilot"),
    ("docs/src/index.md", "closed-beta"),
    ("docs/src/concepts/control-codes.md", "informational rather than blocking"),
    ("docs/src/deployment/airgap.md", "ghcr.io/opencomplai/opencomplai"),
    (
        "docs/src/deployment/airgap.md",
        "docker compose -f infra/compose/docker-compose.yml pull",
    ),
]

CORRECTED: list[tuple[str, str]] = [
    ("README.md", "writes `compliance-artifact.json`"),
    ("README.md", "only when you pass `--sign`"),
    ("README.md", "It does not scan code."),
    ("docs/src/api/webhooks.md", "not implemented in this release"),
    ("docs/src/index.md", "hosted dashboard is in private beta"),
    ("docs/src/concepts/control-codes.md", "cannot be\n   switched off by a flag"),
    ("docs/src/cli/check.md", "`airgap` does not block network access"),
    ("docs/src/deployment/airgap.md", "`--scan-mode airgap` is a label only"),
    (
        "docs/src/deployment/airgap.md",
        "docker compose -f infra/compose/docker-compose.yml build",
    ),
    ("docs/src/guides/ci-integration.md", "needs no key"),
]


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def test_standing_line_present() -> None:
    missing = [rel for rel in STANDING_LINE_FILES if STANDING_LINE not in _read(rel)]
    assert not missing, f"standing line missing from: {missing}"


def test_retired_claims_absent() -> None:
    found = [f"{rel}: {phrase!r}" for rel, phrase in RETIRED if phrase in _read(rel)]
    assert not found, "retired claims are back: " + "; ".join(found)


def test_corrected_claims_present() -> None:
    missing = [
        f"{rel}: {phrase!r}" for rel, phrase in CORRECTED if phrase not in _read(rel)
    ]
    assert not missing, "corrected claims missing: " + "; ".join(missing)


def test_ci_guide_says_key_is_for_publish_only() -> None:
    head = "\n".join(_read("docs/src/guides/ci-integration.md").splitlines()[:25])
    assert "needs no key" in head
    assert "only needed to publish" in head


# --- SU-7o-b: second batch of stale prose ---

_JS_SDK_PAGES = [
    "docs/src/api/javascript-sdk/index.md",
    "docs/src/api/javascript-sdk/installation.md",
    "docs/src/api/javascript-sdk/api-reference.md",
]
_DEBUGGING = "docs/src/troubleshooting/debugging.md"
_PRE_COMMIT = "docs/src/guides/pre-commit.md"
_CONTRIBUTING = "docs/src/contributing/index.md"

DEFERRED_RETIRED: list[tuple[str, str]] = [
    *((page, "not yet available in v0.1") for page in _JS_SDK_PAGES),
    (_PRE_COMMIT, "v0.1.2"),
    (_PRE_COMMIT, "once one exists"),
    (_DEBUGGING, "opencomplai          0.1.0-dev"),
    (_DEBUGGING, "opencomplai-cli      0.1.0-dev"),
    (_DEBUGGING, "opencomplai-core     0.1.0-dev"),
    (_CONTRIBUTING, "only extracts AI-capability signals from Python"),
]

DEFERRED_PRESENT: list[tuple[str, str]] = [
    *(
        (page, "No JavaScript/TypeScript SDK ships in this release")
        for page in _JS_SDK_PAGES
    ),
    (_CONTRIBUTING, "regex"),
    (_PRE_COMMIT, "latest release"),
]

STANDING_LINE_PACKAGE_DOCS = [
    "packages/cli/README.md",
    "packages/core/README.md",
    "packages/sdk-python/README.md",
    "docs/src/getting-started/index.md",
]


def test_deferred_stale_strings_absent() -> None:
    found = [f"{rel}: {p!r}" for rel, p in DEFERRED_RETIRED if p in _read(rel)]
    assert not found, "stale strings are back: " + "; ".join(found)
    assert "detect anything in a `.js`" not in _read(_CONTRIBUTING)


def test_deferred_corrected_facts_present() -> None:
    missing = [f"{rel}: {p!r}" for rel, p in DEFERRED_PRESENT if p not in _read(rel)]
    assert not missing, "corrected facts missing: " + "; ".join(missing)


def test_standing_line_in_package_docs() -> None:
    missing = [
        rel for rel in STANDING_LINE_PACKAGE_DOCS if STANDING_LINE not in _read(rel)
    ]
    assert not missing, f"standing line missing from: {missing}"
    assert _read("packages/core/README.md").count(STANDING_LINE) >= 1


# --- SU-36: final claims sweep ---

_CLAIM_FILES = [
    "README.md",
    "docs/src/index.md",
    "docs/src/frameworks/index.md",
    "docs/src/license.md",
]


def test_no_unbacked_product_claims() -> None:
    banned = [
        re.compile(r"\bSSO\b|single sign-on|\bSCIM\b", re.I),
        re.compile(r"server-side PDF", re.I),
        re.compile(r"continuous(ly)? monitor", re.I),
    ]
    found = []
    for rel in _CLAIM_FILES:
        text = _read(rel)
        found += [f"{rel}: {m.pattern}" for m in banned if m.search(text)]
        found += [
            f"{rel}: scheduler"
            for m in re.finditer(r"scheduler", text, re.I)
            if text[max(0, m.start() - 3) : m.end()].lower() != "no scheduler"
        ]
    assert not found, "unbacked product claims: " + "; ".join(found)


def test_iso_and_regime_wording_is_not_overclaimed() -> None:
    banned = [
        re.compile(r"ISO[^.\n]{0,40}\b(certified|evaluated)\b", re.I),
        re.compile(r"DORA[^.\n]{0,40}\b(evaluated|verdict|compliant)\b", re.I),
    ]
    found = [
        f"{rel}: {m.pattern}"
        for rel in _CLAIM_FILES
        for m in banned
        if m.search(_read(rel))
    ]
    assert not found, "over-claimed wording: " + "; ".join(found)
