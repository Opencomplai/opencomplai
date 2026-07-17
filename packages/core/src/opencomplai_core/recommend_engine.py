"""Render copy-paste remediation templates from a GapReport (opencomplai recommend).

Supports Markdown stubs and compile-checked Python examples. No code execution at
render time. Every output cites the article/gap row that triggered it.
"""

from __future__ import annotations

import json
import shutil
from functools import lru_cache
from pathlib import Path

from opencomplai_core.models import ArticleGapStatus, GapReport, GapStatus

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates" / "recommend"

_ACTIONABLE_STATUSES = frozenset({GapStatus.MISSING, GapStatus.PARTIAL})


@lru_cache(maxsize=1)
def load_template_map() -> dict[str, dict[str, str]]:
    path = _TEMPLATES_DIR / "template_map.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _render(content: str, row: ArticleGapStatus, template_id: str) -> str:
    return (
        content.replace("{{article}}", row.article)
        .replace("{{status}}", row.status.value.upper())
        .replace("{{source}}", row.source.value)
        .replace("{{evidence_ref}}", row.evidence_ref)
        .replace("{{rationale}}", row.rationale or "(no rationale recorded)")
        .replace("{{template_id}}", template_id)
    )


def render_recommendations(gap_report: GapReport, output_dir: Path) -> list[Path]:
    """Write one remediation template per Missing/Partial article row.

    Returns the list of files written. Python templates are copied (optionally
    with a short header comment noting the triggering article). Markdown templates
    get placeholder substitution.
    """
    template_map = load_template_map()
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for row in gap_report.articles:
        if row.status not in _ACTIONABLE_STATUSES:
            continue
        mapping = template_map.get(row.article)
        if mapping is None:
            continue

        kind = mapping.get("kind", "markdown")
        template_path = _TEMPLATES_DIR / mapping["file"]
        article_slug = row.article.lower().replace(" ", "").replace(".", "")
        template_id = mapping["template_id"]

        if kind == "python":
            suffix = template_path.suffix or ".py"
            out_path = output_dir / f"{article_slug}-{template_id}{suffix}"
            body = template_path.read_text(encoding="utf-8")
            header = (
                f"# Triggered by {row.article} status={row.status.value} "
                f"source={row.source.value} evidence={row.evidence_ref}\n"
            )
            if not body.lstrip().startswith("# Triggered by"):
                body = header + body
            out_path.write_text(body, encoding="utf-8")
            written.append(out_path)
            for asset in mapping.get("assets", []) or []:
                asset_src = _TEMPLATES_DIR / asset
                if asset_src.is_file():
                    dest = output_dir / Path(asset).name
                    shutil.copy2(asset_src, dest)
                    written.append(dest)
        else:
            content = template_path.read_text(encoding="utf-8")
            rendered = _render(content, row, template_id)
            out_path = output_dir / f"{article_slug}-{template_id}.md"
            out_path.write_text(rendered, encoding="utf-8")
            written.append(out_path)

    return written
