"""Every markdown anchor in the docs resolves, and the build keeps checking it.

`mkdocs build --strict` only logs a missing anchor at INFO level unless
`validation.anchors` is `warn`, and `sync/check-links.py` skips fragments by
design. These tests are the anchor gate: they apply the python-markdown `toc`
slug rule to every heading and fail on a link whose fragment has no heading.
They also pin the hosted-dashboard architecture page to the render-api routes
and the ingest body limit in source, and keep it free of internal identifiers.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path, PurePosixPath

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_DOCS = _ROOT / "docs" / "src"
_MKDOCS = _ROOT / "docs" / "mkdocs.yml"
_ARCH_PAGE = _DOCS / "architecture" / "dashboard-saas.md"
_RENDER_SRC = (
    _ROOT / "dashboard-saas" / "services" / "render-api" / "src" / "dashboard_render"
)
_INGEST_ROUTES = (
    _ROOT
    / "dashboard-saas"
    / "services"
    / "ingest-api"
    / "src"
    / "dashboard_ingest"
    / "routes.py"
)

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_EXPLICIT_ID = re.compile(r"\{#([^}\s]+)[^}]*\}\s*$")
_HTML_ID = re.compile(r"""\bid=["']([^"']+)["']""")
_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_CODE_SPAN = re.compile(r"`[^`\n]*`")


def _slug(text: str) -> str:
    """python-markdown `toc` slugify: drop non-word chars, lowercase, collapse runs of - and space."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # a link keeps its text
    text = text.replace("`", "").replace("*", "")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


def _prose_lines(md_text: str):
    """Yield the lines outside fenced code blocks."""
    fence = None
    for line in md_text.splitlines():
        m = _FENCE.match(line)
        if m:
            if fence is None:
                fence = m.group(1)
            elif m.group(1) == fence:
                fence = None
            continue
        if fence is None:
            yield line


def _anchors(md_text: str) -> set[str]:
    """Heading slugs (with toc's `_1`, `_2` suffix for repeats), explicit {#id} and id="..." anchors."""
    found: set[str] = set()
    seen: dict[str, int] = {}
    for line in _prose_lines(md_text):
        m = _HEADING.match(line)
        if m:
            title = m.group(1)
            explicit = _EXPLICIT_ID.search(title)
            if explicit:
                found.add(explicit.group(1))
                continue
            slug = _slug(title) or "section"
            n = seen.get(slug, 0)
            seen[slug] = n + 1
            found.add(slug if n == 0 else f"{slug}_{n}")
        found.update(_HTML_ID.findall(line))
    return found


def _broken(files: dict[str, str]) -> list[tuple[str, str]]:
    """(page, link) pairs whose `#fragment` is absent from the target page. Keys are docs-relative posix paths."""
    anchors = {name: _anchors(text) for name, text in files.items()}
    out: list[tuple[str, str]] = []
    for page, text in files.items():
        for line in _prose_lines(text):
            for target in _LINK.findall(_CODE_SPAN.sub("", line)):
                path, _, fragment = target.partition("#")
                if not fragment or re.match(r"^[a-z][a-z0-9+.-]*:", path):
                    continue
                if path:
                    dest = PurePosixPath(page).parent / path
                    parts: list[str] = []
                    for part in dest.parts:
                        if part == "..":
                            if parts:
                                parts.pop()
                        elif part != ".":
                            parts.append(part)
                    dest_name = "/".join(parts)
                else:
                    dest_name = page
                if dest_name in anchors and fragment not in anchors[dest_name]:
                    out.append((page, target))
    return out


def _docs_files() -> dict[str, str]:
    return {
        p.relative_to(_DOCS).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(_DOCS.rglob("*.md"))
    }


def test_every_docs_anchor_resolves() -> None:
    files = _docs_files()
    assert len(files) > 20, "docs/src was not found"
    assert _broken(files) == []


def test_a_missing_anchor_is_reported() -> None:
    files = {
        "a.md": "# Alpha\n\nSee [b](sub/b.md#real-one) and [bad](sub/b.md#nope).\n",
        "sub/b.md": "# Real one\n\nBack to [a](../a.md#alpha).\n",
    }
    assert _broken(files) == [("a.md", "sub/b.md#nope")]


def test_slug_matches_the_toc_rule() -> None:
    assert _slug("AI intent analysis (`--ai-intent`)") == "ai-intent-analysis-ai-intent"
    assert (
        _slug("Freshness \u2014 read-time only, no cron")
        == "freshness-read-time-only-no-cron"
    )


def test_mkdocs_anchor_validation_is_warn() -> None:
    text = _MKDOCS.read_text(encoding="utf-8")
    assert re.search(
        r"(?m)^validation:\s*\n(?:[ \t]+.*\n|[ \t]*\n)*?[ \t]+anchors:\s*warn\b", text
    ), "docs/mkdocs.yml needs a top-level `validation:` block with `anchors: warn`"


_ID_PATTERNS = [r"SU-\d", r"CL-[A-Z]\d", r"DG-\d", r"EX-\d", r"PLAN/"]
_PRIVATE_PATTERNS = [
    r"CLOSEOUT",
    r"SUMMIT",
    r"checkref",
    r"\.summit",
    r"C:\\",
    r"/Users/",
    r"WorkSpace",
    r"\.\./\.\./",
]


def test_dashboard_architecture_page_is_public_safe() -> None:
    page = _ARCH_PAGE.read_text(encoding="utf-8")
    for pattern in _ID_PATTERNS:
        assert not re.search(pattern, page), (
            f"internal identifier on the page: {pattern}"
        )
    assert "SET ROLE dashboard" not in page, (
        "stale role wording: must read SET LOCAL ROLE"
    )
    for needle in ("x-request-id", "hash chain", "SET LOCAL ROLE"):
        assert needle in page, f"the page lost: {needle}"


def test_dashboard_architecture_page_lists_every_get_route_and_ingest_limit() -> None:
    if not _RENDER_SRC.is_dir() or not _INGEST_ROUTES.is_file():
        pytest.skip("dashboard-saas tree is absent from this checkout")
    page = _ARCH_PAGE.read_text(encoding="utf-8")
    route_re = re.compile(r'@router\.get\("([^"]+)"\)')
    paths: list[str] = []
    for module in ("routes.py", "report_signoff.py"):
        paths += route_re.findall((_RENDER_SRC / module).read_text(encoding="utf-8"))
    assert len(paths) >= 20, f"route regex matched only {len(paths)} paths"
    missing = sorted({p for p in paths if p not in page})
    assert missing == [], f"render-api GET routes missing from the page: {missing}"

    ingest = _INGEST_ROUTES.read_text(encoding="utf-8")
    limit = re.search(
        r"^MAX_INGEST_BODY_BYTES\s*=\s*(\d+)\s*\*\s*1024\s*\*\s*1024\b", ingest, re.M
    )
    assert limit, "MAX_INGEST_BODY_BYTES not found in ingest routes"
    assert int(limit.group(1)) == 2, (
        "ingest body limit is no longer 2 MiB: update the page"
    )
    assert "2 MiB" in page


def test_dashboard_architecture_page_has_no_internal_or_private_text() -> None:
    page = _ARCH_PAGE.read_text(encoding="utf-8")
    for pattern in _ID_PATTERNS + _PRIVATE_PATTERNS:
        assert not re.search(pattern, page), (
            f"internal or private text on the page: {pattern}"
        )
