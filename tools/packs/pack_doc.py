"""Keep the row table of a pack's docs page current.

Usage (from the repo root):
  uv run python tools/packs/pack_doc.py <KEY>          # rewrite the table
  uv run python tools/packs/pack_doc.py <KEY> --check  # exit 1 when the page is stale

The table sits between the lines `<!-- rows:start -->` and `<!-- rows:end -->` of
`docs/src/<docs_page>`. `docs_page` is an optional `pack.json` field; the default is
`frameworks/<key in lower case, - for _>.md`. A page without both marker lines is an error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from opencomplai_core import pack_registry

REPO = Path(__file__).resolve().parents[2]
DOCS_SRC = REPO / "docs" / "src"
START = "<!-- rows:start -->"
END = "<!-- rows:end -->"
UNREVIEWED = "mapping not yet reviewed"
HEADER = (
    "| Requirement | Title | Evidence class | Sources | TTL days | Review |",
    "| --- | --- | --- | --- | --- | --- |",
)


def docs_page(key: str, meta: dict[str, Any] | None = None) -> str:
    """The page path below docs/src, from `pack.json` or the default."""
    if meta is None:
        try:
            meta = pack_registry.load_pack_meta(key)
        except ValueError:
            meta = {}
    page = meta.get("docs_page")
    if isinstance(page, str) and page.strip():
        return page.strip()
    return f"frameworks/{key.lower().replace('_', '-')}.md"


def page_path(key: str, meta: dict[str, Any] | None = None) -> Path:
    return DOCS_SRC / docs_page(key, meta)


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.split()).replace("|", "\\|")


def _sources(row: dict[str, Any]) -> str:
    parts = []
    for s in row.get("sources", []):
        if not isinstance(s, dict):
            continue
        role = s.get("role")
        parts.append(
            f"{s.get('kind', '')}: {s.get('ref', '')}" + (f" ({role})" if role else "")
        )
    return "; ".join(parts)


def render_rows(key: str) -> str:
    """The Markdown table for the pack's rows, without marker lines."""
    path = pack_registry.pack_dir(key) / "requirements.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path}: cannot read requirements: {exc}") from exc
    if not isinstance(rows, dict):
        raise ValueError(f"{path}: requirements must be a JSON object")
    lines: list[str] = list(HEADER)
    for rid, row in rows.items():
        if not isinstance(row, dict):
            continue
        review = UNREVIEWED if row.get("needs_founder_review") is True else ""
        cells = (
            rid,
            row.get("title"),
            row.get("evidence_class"),
            _sources(row),
            row.get("default_ttl_days"),
            review,
        )
        lines.append("| " + " | ".join(_cell(v) for v in cells) + " |")
    return "\n".join(lines)


def fill(text: str, table: str) -> str:
    """`text` with the block between the marker lines replaced by `table`."""
    lines = text.split("\n")
    stripped = [ln.strip() for ln in lines]
    if START not in stripped or END not in stripped:
        raise ValueError(f"page needs the lines {START} and {END}")
    first = stripped.index(START)
    last = stripped.index(END)
    if last < first:
        raise ValueError(f"{END} comes before {START}")
    return "\n".join([*lines[: first + 1], table, *lines[last:]])


def check(key: str) -> list[str]:
    """Problems that keep the page from being current; empty when it is."""
    path = page_path(key)
    if not path.is_file():
        return [f"no docs page {path.name}"]
    try:
        text = path.read_text(encoding="utf-8")
        want = fill(text, render_rows(key))
    except ValueError as exc:
        return [str(exc)]
    return [] if want == text else [f"{path.name} is stale; run pack_doc.py {key}"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("key", help="pack key, e.g. CRA")
    ap.add_argument("--check", action="store_true", help="exit 1 when stale")
    args = ap.parse_args(argv)
    path = page_path(args.key)
    if not path.is_file():
        print(f"no docs page {path}", file=sys.stderr)
        return 2
    try:
        text = path.read_text(encoding="utf-8")
        want = fill(text, render_rows(args.key))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.check:
        if want != text:
            print(f"{path.name} is stale; run pack_doc.py {args.key}", file=sys.stderr)
            return 1
        return 0
    if want != text:
        path.write_text(want, encoding="utf-8", newline="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
